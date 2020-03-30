"""Parsers for different kinds of configurations

Strictly speaking, the functions provided by this module are not parsers, they
don't parse the config file themselves.  Instead it relies on the dedicated
file parsing libraries like `pyyaml`, `json`, etc to parse the files into a
dictionary.  The functions in this module provide an API to traverse the nested
dictionary and parse the config rules and dynamically generate a configuration
type object which can be used to validate the actual config file from the user.

"""

from __future__ import annotations

from abc import ABC
from copy import deepcopy
from dataclasses import asdict
from functools import reduce
from itertools import chain
from pathlib import Path
from typing import (
    Any,
    cast,
    Callable,
    Dict,
    Iterable,
    Sequence,
    Set,
    Tuple,
    Type,
    Union,
)

from boltons.iterutils import research
from glom import Assign, Coalesce, glom, Invoke, Spec, SKIP, T

from pydc.helpers import NS
from pydc.factory import make_dataconfig
from pydc.helpers import read_yaml, read_json, to_yaml, to_json

# type specification keys, order of keys important
_type_spec = (
    "type",
    "opts",
    "validator",
    "validator_opts",
    "default",
    "id",
    "doc",
)

# types for keys and paths as understood by boltons.iterutils
_Key_t = Union[str, int]  # mapping keys and sequence index
_Path_t = Tuple[_Key_t, ...]


class _ConfigIO(ABC):
    """Base class to provide partial serialisation

    - reads rules directly from YAML or JSON files
    - saves config instances to YAML or JSON files (given all config values
      are serialisable)

    """

    @classmethod
    def from_yaml(cls, yaml_path: Union[str, Path]) -> _ConfigIO:
        # FIXME: type checking is ignored for the return statement because mypy
        # doesn't seem to know this is an abstract base class, and the argument
        # unpacking makes sense when instantiating any of the derived classes.
        return cls(**read_yaml(yaml_path))  # type: ignore

    @classmethod
    def from_json(cls, json_path: Union[str, Path]) -> _ConfigIO:
        return cls(**read_json(json_path))  # type: ignore

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_yaml(self, yaml_path: Union[str, Path]):
        to_yaml(self.to_dict(), yaml_path)

    def to_json(self, json_path: Union[str, Path]):
        to_json(self.to_dict(), json_path)


_ConfigIO_to_file_doc_ = """
Serialise to {0}

Please note, this cannot be readily reread to create the config type again.  It
requires a bit of hand editing to conform with the expected rules.

NOTE: serialising may fail depending on whether any of the items in the config
is {0} serialisable or not.

"""

_ConfigIO.to_yaml.__doc__ = _ConfigIO_to_file_doc_.format("YAML")
_ConfigIO.to_json.__doc__ = _ConfigIO_to_file_doc_.format("JSON")


def _is_node(path: _Path_t, key: _Key_t, value: Any) -> bool:
    """Detect a node in the configuration hierarchy

    NOTE: For whatever reason `remap(..)` starts with `(), None, ()`; which is
    why we reject the "entry" when `key` is `None`.  `research(..)` returns the
    current path (includes the current item, path + (key,)).  The logic is, if
    either of the type spec keys are present, we are inside the item described
    by the node, hence reject.

    Parameters
    ----------
    path : _Path_t
        Path to node
    key : _Key_t
        Configuration key
    value
        The configuration value

    Returns
    -------
    bool
        A node or not

    """
    if key is None:
        return False
    full_path = path + (key,)
    return all(type_key not in full_path for type_key in _type_spec)


def _nodes(conf: Dict) -> Set[_Path_t]:
    """Filter the list of paths for nodes

    Parameters
    ----------
    conf : Dict
        Config dictionary

    Returns
    -------
    Set[_Path_t]
        List of paths to nodes

    """
    return {path for path, _ in research(conf, query=_is_node)}


def _is_leaf(path: _Path_t, paths: Iterable[_Path_t]) -> bool:
    """Detect a leaf node

    NOTE: if a path overlaps with another path (given they are not the same),
    the shorter path is not a leaf node.  The implmentation assumes a path
    constitutes of unique keys:
    - (k1, k2, k3) Yes
    - (k1, k2, k1) No

    Parameters
    ----------
    path : _Path_t
        Path to the node
    paths : Iterable[_Path_t]
        Set of paths to compare against to determine if this is a leaf node

    Returns
    -------
    bool
        Leaf node or not

    """
    return not any(set(path).issubset(q) for q in paths if path != q)


def _leaves(paths: Iterable[_Path_t]) -> Set[_Path_t]:
    """Filter the list of paths for leaf nodes.

    Parameters
    ----------
    paths : Iterable[_Path_t]
        List of paths

    Returns
    -------
    Set[_Path_t]
        List of paths to leaf nodes

    """
    return {p for p in paths if _is_leaf(p, paths)}


def _T_parent(path: _Path_t) -> Tuple:
    """Accepts a path, and returns the full, and parent path as T object.

    This function converts a tuple based path used with `boltons` into a T
    object with keys as understood by `glom`.  While at it, it also separately
    returns the parent path, useful to access a parallel branch under the same
    branch.  This is needed when creating validators.

    Parameters
    ----------
    path : _Path_t
        Path to a node

    Returns
    -------
    Tuple (full_path, parent_path)
        A tuple of T objects refering to the full path, and parent path

    """
    res = reduce(cast(Callable, lambda t, key: t[key]), path[:-1], T)
    return (res[path[-1]], res) if res else (res[path[-1]], T)


def _type(value: Dict) -> Type:
    """Parse config and create the respective type"""
    type_key = _type_spec[0]
    opts = value.get(_type_spec[1], None)
    if opts and isinstance(opts, Sequence):
        config_t = getattr(NS.types, value[type_key])[tuple(opts)]
    elif opts and isinstance(opts, dict):
        config_t = getattr(NS.types, value[type_key])(**opts)
    elif not opts:
        config_t = getattr(NS.types, value[type_key])
    else:
        pass  # ambiguous option FIXME: log this!
    return config_t


def _validator(
    key: str, keys: Sequence[_Key_t], value: Dict
) -> Dict[str, classmethod]:
    """Parse config and create the respective validator method

    The validator is bound to a specific key, and a list of all other keys at
    the same level are also made available in the closure; NOTE: the order of
    the keys in the rules file is significant.

    Parameters
    ----------
    key : str
        The config key to associate the validator with
    keys : Sequence[_Key_t]
        List of all keys at the same level
    value : Dict
        The config dictionary

    Returns
    -------
    classmethod
        The validator classmethod

    """
    factory = getattr(NS.validators, value[_type_spec[2]])
    opts = value.get(_type_spec[3], {})
    return factory(key, keys, **opts)


def _str_to_spec(key: str, value: Dict, parent: Iterable[_Key_t]) -> Dict:
    """Parse the config dictionary and create the types and validators

    Parameters
    ----------
    key : str
        The key name corresponding to the specification.
    value : Dict
        The config dictionary
    parent : Dict
        The config dictionary for the parent key

    Returns
    -------
    Dict
        The dictionary with the specifications:
          { "type": <type>, "validator": <validator> }

    """
    type_key, _, validator_key, *__ = _type_spec  # get key names

    res: Dict = {}
    if type_key in value:  # only for basic types (leaf nodes)
        res[type_key] = _type(value)

    if validator_key in value:  # for validators at all levels
        res[validator_key] = _validator(key, list(parent), value)

    return res


def _spec_to_type(
    key: str, value: Dict[str, Dict], bases: Tuple[Type, ...] = ()
) -> Type:
    """Using the type specification, create the custom type objects

    Parameters
    ----------
    key : str
        The key name corresponding to the specification. It is used as a
        template for the custom type name.
    value : Dict
        The dictionary with the type specification.  It looks like:
          {
              "key1": {"type": <type1>, "validator": <validator1>},
              "key2": {"type": <type2>, "validator": <validator2>},
              # ...
          }

    bases : Tuple[Type]
        Base classes

    Returns
    -------
    Type
        Custom type object with validators

    """
    fields = glom(
        value.items(),
        [
            (
                {
                    "k": "0",
                    "v": "1.type",
                    # TODO: non-trivial defaults like mutable types
                    "d": Coalesce("1.default", default=SKIP),
                },
                T.values(),
                tuple,
            )
        ],
    )  # extract key, value and convert to list of tuples
    ns = dict(
        chain(
            *glom(
                value.values(),
                [(Coalesce("validator", default_factory=dict), T.items())],
            )
        )
    )  # chain dict.items() and create namespace
    return make_dataconfig(f"{key}_t", fields, namespace=ns, bases=bases)


def _nested_type(key: str, value: Dict[str, Dict], parent: Dict) -> Dict:
    """Create the type dictionary for nested types (not leaf nodes)

    Parameters
    ----------
    key : str
        The key name corresponding to the specification. It is used as a
        template for the custom type name.
    value : Dict[str, Dict]
        The config dictionary
    parent : Dict
        The config dictionary for the parent key

    Returns
    -------
    Dict
        The dictionary with the specifications:
          { "type": <type>, "validator": <validator> }

    """
    return {
        "type": _spec_to_type(key, value),
        "validator": _str_to_spec(key, value, parent),
    }


def _update_inplace(
    func: Callable[[str, Dict, Dict], Dict]
) -> Callable[[Dict, _Path_t], Dict]:
    """Bind the given function to `update_inplace` defined below

    """

    def update_inplace(_conf: Dict, path: _Path_t) -> Dict:
        """Invoke the bound function to reassign matching items

        FIXME: possibly this can be simplified using functools.partial

        """
        _config_t = Spec(
            Invoke(func).constants(path[-1]).specs(*_T_parent(path))
        )
        return glom(_conf, Assign(".".join(map(str, path)), _config_t))

    return update_inplace


def get_config_t(conf: Dict) -> Type:
    """Read the config dictionary and create the config type"""
    paths = _nodes(conf)
    leaves = _leaves(paths)

    # create a copy of the dictionary, and recursively update the leaf nodes
    _conf = reduce(_update_inplace(_str_to_spec), leaves, deepcopy(conf))

    # walk up the tree, and process the "new" leaf nodes.  using a set takes
    # care of duplicates.
    branches: Set[_Path_t] = _leaves(paths - leaves)
    while branches:
        _conf = reduce(_update_inplace(_nested_type), branches, _conf)
        branches = {path[:-1] for path in branches if path[:-1]}

    return _spec_to_type("config", _conf, bases=(_ConfigIO,))
