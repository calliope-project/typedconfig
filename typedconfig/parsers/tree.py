"""Hierarchical parser

"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import MutableSequence, MutableMapping
from copy import deepcopy
from dataclasses import field
from functools import reduce
from itertools import chain, product
from operator import add
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Set,
    Tuple,
    Type,
    Union,
)
from warnings import warn

from boltons.iterutils import research
from glom import Path as gPath
from glom import A, S, SKIP, T
from glom import Assign, Coalesce, Delete, glom, Invoke, Iter, Match, Spec

from typedconfig.helpers import merge_rules, NS
from typedconfig.factory import make_typedconfig, make_validator
from typedconfig.helpers import read_yaml
from typedconfig.parsers import _ConfigIO, _fpaths

# type specification keys, order of keys important
_type_spec = (
    "type",
    "opts",
    "validator",
    "validator_opts",
    "validator_params",
    "root_validator",
    "default",
    "optional",
    # following keys are used for documentation
    "doc",
)

# types for keys and paths as understood by boltons.iterutils
_key_t = Union[str, int]  # mapping keys and sequence index
_path_t = Tuple[_key_t, ...]


def path_if(nested: Dict, test: Callable[[_path_t, _key_t, Any], bool]) -> Set[_path_t]:
    """Filter the list of paths with `test`

    Parameters
    ----------
    nested : Dict
        Config dictionary

    test : Callable[[Tuple[_key_t, ...], _key_t, Any], bool]
        Function to filter paths (``_key_t`` is ``Union[str, int]``)

    Returns
    -------
    Set[Tuple[_key_t, ...]]
        List of paths that pass `test`

    """
    return {path for path, _ in research(nested, query=test)}


def is_node(path: _path_t, key: _key_t, value: Any) -> bool:
    """Detect a node in the configuration hierarchy

    NOTE: For whatever reason `remap(..)` starts with `(), None, ()`; which is
    why we reject the "entry" when `key` is `None`.  `research(..)` returns the
    current path (includes the current item, path + (key,)).  The logic is, if
    either of the type spec keys are present, we are inside the item described
    by the node, hence reject.

    Parameters
    ----------
    path : Tuple[_key_t, ...]
        Path to node
    key : _key_t
        Configuration key (``_key_t`` is ``Union[str, int]``)
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


def is_leaf(path: _path_t, key: _key_t, value: Any) -> bool:
    """Detect a leaf node

    Test criteria:
    - it's a node,
    - value is a dictionary
    - the dictionary has the key 'type'

    Parameters
    ----------
    path : Tuple[_key_t, ...]
        Path to node
    key : _key_t
        Configuration key (``_key_t`` is ``Union[str, int]``)
    value
        The configuration value

    Returns
    -------
    bool
        A leaf node or not

    """
    type_key = _type_spec[0]
    return is_node(path, key, value) and isinstance(value, dict) and type_key in value


def get_from_leaf(data: Dict, keys: Iterable[str]) -> Dict:
    """Retrieve keys from the leaf nodes, preserving the hierarchy

    Parameters
    ----------
    data: Dict
        Nested hierarchy of dictionary
    keys: Iterable[str]
        Keys to retrieve from the leaf nodes (as per `is_leaf`)

    Returns
    -------
    Dict
        Keys in the original hierarchy

    """
    key_values = glom(
        data,
        {
            p: (p, {k: Coalesce(k, default=SKIP) for k in keys})
            for p in path_if(data, is_leaf)
        },
    )
    # remove empty keys
    list(map(key_values.pop, [k for k, v in key_values.items() if v == {}]))

    def redict():
        """Factory method for a recursive dictionary"""
        return defaultdict(redict)

    return glom(redict(), tuple(Assign(gPath(*k), v) for k, v in key_values.items()))


def del_from_leaf(data: Dict, keys: Iterable[str]) -> Dict:
    """Delete keys from leaf nodes

    Parameters
    ----------
    data: Dict
        Nested hierarchy of dictionary
    keys: Iterable[str]
        Keys to delete from the leaf nodes (per `is_leaf`)

    Returns
    -------
    Dict
        Dictionary with the keys removed

    """
    return glom(
        data,
        tuple(
            Delete(gPath(*path, key), ignore_missing=True)
            for path, key in product(path_if(data, is_leaf), keys)
        ),
    )


def leaf_subset(paths: Iterable[_path_t]) -> Set[_path_t]:
    """From a set of paths, find the paths that are leaves.

    Leaves are paths with no further downstream branches.

    NOTE: if a path overlaps with another (given they are not the same), the
    shorter path has branches ahead, and is not in the leaf subset.  The
    implmentation assumes a path constitutes of unique keys:

    - path: (k1, k2, k3)
    - not path: (k1, k2, k1)

    Parameters
    ----------
    paths : Collection[Tuple[_key_t, ...]]
        List of paths

    Returns
    -------
    Set[Tuple[_key_t, ...]]
        List of paths to leaf nodes

    """

    def __is_leaf(path: _path_t) -> bool:
        return not any(set(path).issubset(q) for q in paths if path != q)

    return {p for p in paths if __is_leaf(p)}


def get_type(value: Dict) -> Type:
    """Parse config and create the respective type"""
    leaf_type = NS.types[value[_type_spec[0]]]
    opts = value.get(_type_spec[1], None)
    if opts and isinstance(opts, (tuple, list, set)):
        config_t = leaf_type[tuple(NS.types.get(i, i) for i in opts)]
    elif opts and isinstance(opts, dict):
        config_t = leaf_type(**opts)
    else:
        config_t = leaf_type
        if opts:
            warn(f"ambiguous option ignored: {opts}", category=UserWarning)
    return config_t


def get_validator(key: str, value: Dict) -> Dict[str, classmethod]:
    """Parse config and create the respective validator method

    The validator is bound to a specific key, and a list of all other keys at
    the same level are also made available in the closure; NOTE: the order of
    the keys in the rules file is significant.

    Parameters
    ----------
    key : str
        The config key to associate the validator with
    value : Dict
        The config dictionary

    Returns
    -------
    Dict[str, classmethod]
        A dictionary, with the validator method name as key, and the validator
        classmethod as value

    """
    _1, _2, val_key, opts_key, params_key, is_root, *__ = _type_spec
    validators = value[val_key]
    params = value.get(params_key, {})
    if isinstance(validators, str):
        funcs = [(NS.validators[validators], params)]
    else:  # list of validators
        if not isinstance(validators, list):
            raise ValueError(f"{validators}: must be a 'str' or 'list'")
        params = params if isinstance(params, list) else [{}] * len(validators)
        if len(validators) != len(params):
            raise ValueError(
                f"{validators}, {params}: no. of validators and param sets don't match"
            )
        glom(params, Match([dict]))
        funcs = [(NS.validators[fn], pars) for fn, pars in zip(validators, params)]
    key = "" if is_root in value else key  # don't actually use the value
    opts = value.get(opts_key, {})
    return dict(
        chain.from_iterable(
            make_validator(fn, key, opts=opts, **pars).items() for fn, pars in funcs
        )
    )


def str_to_spec(key: str, value: Dict) -> Dict:
    """Parse the config dictionary and create the types and validators

    Parameters
    ----------
    key : str
        The key name corresponding to the specification.
    value : Dict
        The config dictionary.

    Returns
    -------
    Dict
        A new dictionary is returned, with the strings interpreted as types and
        validators.  Note that typically type and validators are not parsed at
        the same pass:

          { "type": <type>, "validator": <validator> }

    """
    type_key, _, validator_key, *__ = _type_spec  # get key names

    if type_key in value:  # only for basic types (leaf nodes)
        value[type_key] = get_type(value)

    if validator_key in value:  # for validators at all levels
        value[validator_key] = get_validator(key, value)

    return value


def spec_to_type(
    key: str, value: Dict[str, Dict], bases: Tuple[Type, ...] = ()
) -> Type:
    """Using the type specification, create the custom type objects

    Parameters
    ----------
    key : str
        The key name corresponding to the specification. It is used as a
        template for the custom type name.
    value : Dict
        The dictionary with the type specification.  It looks like::

          {
              "validator": <validator>,
              "root_validator": True,
              # ...
              "key1": {"type": <type1>, "validator": <validator1>},
              "key2": {"type": <type2>, "validator": <validator2>},
              # ...
          }

        All <validator> instances are dictionaries themselves, w/ validator
        name as the key, and the fuction as value.:

          {"name": <classmethod>}

    bases : Tuple[Type, ...]
        Base classes

    Returns
    -------
    Type
        Custom type object with validators

    """
    type_k = _type_spec[0]
    default_k = _type_spec[6]

    def _type_w_defaults(key: str, value: Dict) -> Tuple:
        _type = value[type_k]
        _default = value.get(default_k)
        if _default:
            if isinstance(_default, (MutableMapping, MutableSequence)):
                _field = field(default_factory=lambda: _default)
            else:
                _field = field(default=_default)
            return (key, _type, _field)
        else:
            return (key, _type)

    # convert to list of (key, value [, defaults]). apart from moving the data
    # members w/ a default argument later, original ordering is preserved
    _fields = glom(
        value.items(),
        (
            Iter()
            # only keep type specfication dicts
            .filter(lambda i: isinstance(i[1], dict) and type_k in i[1])
            .map(Invoke(_type_w_defaults).specs("0", "1"))
            .all(),  # NOTE: expand to list, otherwise checkpoint will fail
            A.globals._all,  # checkpoint: all
            Iter().filter(lambda i: len(i) == 2).all(),
            A.globals.nodef,  # checkpoint: no default
            S.globals._all,
            Iter().filter(lambda i: len(i) == 3).all(),  # w/ default
            # concat no default + w/ default
            Invoke(add).specs(S.globals.nodef, T),
        ),
    )
    spec = (  # get validators
        Coalesce("validator", default_factory=dict),
        T.items(),  # item: (fn.__name__, classmethod)
    )
    rv_spec = (  # root validators
        *spec,
        Iter().filter(lambda i: hasattr(i[1], "__root_validator_config__")),
    )
    v_spec = (  # regular validators
        *spec,
        Iter().filter(lambda i: hasattr(i[1], "__validator_config__")),
    )
    ns = dict(chain(glom(value, rv_spec), *glom(value.values(), [v_spec])))
    return make_typedconfig(f"{key}_t", _fields, namespace=ns, bases=bases)


def nested_type(key: str, value: Dict[str, Dict]) -> Dict:
    """Create the type dictionary for nested types (not leaf nodes)

    Parameters
    ----------
    key : str
        The key name corresponding to the specification. It is used as a
        template for the custom type name.
    value : Dict[str, Dict]
        The config dictionary

    Returns
    -------
    Dict
        The dictionary with the specifications:
          { "type": <type>, "validator": <validator> }

    """
    # parse validator before type creation
    return {
        "validator": str_to_spec(key, value),
        "type": spec_to_type(key, value),
    }


def bind_updater(func: Callable[[str, Dict], Dict]) -> Callable[[Dict, _path_t], Dict]:
    """Bind the given function to `update_inplace` defined below"""

    def update_inplace(_conf: Dict, path: _path_t) -> Dict:
        """Invoke the bound function to reassign matching items

        FIXME: possibly this can be simplified using functools.partial

        """
        glom_spec = gPath(*path)
        _config_t = Spec(Invoke(func).constants(path[-1]).specs(glom_spec))
        return glom(_conf, Assign(glom_spec, _config_t))

    return update_inplace


def get_spec(rules: Dict) -> Tuple[Dict[str, Dict], Set, Set]:
    """Return the config specification from the rules dict

    It also returns all paths, leaf nodes in the config.

    Parameters
    ----------
    rules : Dict
        Rules dictionary

    Returns
    -------
    Tuple[Dict[str, Dict], Set, Set]
        Config specification, set of paths, set of leaf nodes

    """
    paths = path_if(rules, is_node)
    leaves = path_if(rules, is_leaf)

    # create a copy of the dictionary, and recursively update the leaf nodes
    spec = reduce(bind_updater(str_to_spec), leaves, deepcopy(rules))
    return spec, paths, leaves


def get_config_t(rules: Dict) -> Type:
    """Read the config dictionary and create the config type"""
    _conf, paths, leaves = get_spec(rules)

    # walk up the tree, and process the "new" leaf nodes.  using a set takes
    # care of duplicates.
    branches: Set[_path_t] = leaf_subset(paths - leaves)
    while branches:
        _conf = reduce(bind_updater(nested_type), branches, _conf)
        branches = leaf_subset(path[:-1] for path in branches if path[:-1])

    return spec_to_type("config", _conf, bases=(_ConfigIO,))


def is_optional(path: _path_t, key: _key_t, value: Any) -> bool:
    """Detect if a node is optional

    This checks if a key is a node, and if it's an optional attribute.

    Parameters
    ----------
    path : _path_t
        Path to node
    key : _key_t
        Configuration key
    value
        The configuration value

    Returns
    -------
    bool
        If a node corresponds to an optional attribute.

    """
    opt_key = _type_spec[7]
    return is_leaf(path, key, value) and value.get(opt_key, False)


def is_mandatory(path: _path_t, key: _key_t, value: Any) -> bool:
    """Detect if a node is mandatory

    NOTE: This is not trivially the opposite of _is_optional because not all
    paths represent leaf nodes, and simply negating _is_optional would include
    paths that are not leaf nodes.

    Parameters
    ----------
    path : _path_t
        Path to node
    key : _key_t
        Configuration key
    value
        The configuration value

    Returns
    -------
    bool
        If a node is a mandatory attribute.

    """
    opt_key = _type_spec[7]
    return is_leaf(path, key, value) and (not value.get(opt_key, False))


def resolve_optional(rules: Dict, conf: Dict) -> Dict:
    """Go through the rules and drop optional keys that are absent in conf"""
    # leaves defined in rules
    leaves = path_if(rules, is_leaf)
    # keys present in config; also contains keys from dictionary that are part
    # of the config, e.g. validator_params, or keyword options to type
    keys = path_if(conf, is_node)
    # valid_leaves ∩ keys = valid_leaves present in config
    present = leaves.intersection(keys)
    for node in path_if(rules, is_optional):
        if node not in present:
            # delete unused optional rules
            glom(rules, Delete(gPath(*node)))
    return rules


def get_config(rule_files: _fpaths, conf_files: _fpaths):
    """Return the config object

    Both rules files and config files are first merged, then a config type is
    created based on the rules.  Which is then used to instantiate a config
    object.  The instantiation also validates the config values.

    When rules/config files are merged, any attribute repeated in a later file
    overrides any earlier value.

    Parameters
    ----------
    rule_files : Path | List[Path]

    conf_files : Path | List[Path]

    Returns
    -------
    Config
        Config object after validation

    """
    rules = merge_rules(rule_files, read_yaml)
    confs = merge_rules(conf_files, read_yaml)
    config_t = get_config_t(resolve_optional(rules, confs))
    return config_t(**confs)
