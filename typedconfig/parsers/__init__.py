"""Parsers

Strictly speaking, the modules in this sub-package are not parsers, they don't
parse the config file themselves.  It relies on dedicated parsers like
`pyyaml`, `json`, etc to parse the files into a python data structure like a
dictionary.  The functions provided by the moduels can then traverse the
dictionary and parse the rules and dynamically generate a configuration type
which can be used to validate the config file provided by the user.

"""

from __future__ import annotations

from abc import ABC
from dataclasses import asdict, fields, is_dataclass, MISSING
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Type, TypeVar, Union

from typedconfig.helpers import merge_rules, read_yaml, read_json, to_yaml, to_json
from typedconfig.helpers import import_from

log = logging.getLogger(__name__)

_file_t = TypeVar("_file_t", str, Path)
_fpaths = Union[_file_t, List[_file_t], Tuple[_file_t]]


def get_property(pname: str, namespace="dynamic"):
    return import_from(f"typedconfig._{namespace}", f"{pname}_t")


class _ConfigIO(ABC):
    """Base class to provide partial serialisation

    - reads rules directly from YAML or JSON files
    - saves config instances to YAML or JSON files (given all config values
      are serialisable)

    """

    def __post_init__(self):
        for f in fields(self):
            if is_dataclass(f.type):
                defaults = {}
                for _f in fields(f.type):
                    if _f.default != MISSING:
                        val = _f.default
                    elif _f.default_factory != MISSING:
                        val = _f.default_factory()
                    else:
                        continue
                    defaults[_f.name] = val
                kwargs = getattr(self, f.name)
                setattr(self, f.name, f.type(**{**defaults, **kwargs}))

    @classmethod
    def inherits_from(cls, type_names: List[str]) -> bool:
        """Check if type inherits from either of the types named in the list

        Parameters
        ----------
        type_names : List[str]
            List of type names to check in inheritance tree

        Returns
        -------
        bool
            True if one of the types named in the list is a parent

        Raises
        ------
        AttributeError
            If none of the named types are found in 'typedconfig.dynamic'

        """
        # TODO: parametrise module namespace
        def importer(type_name: str) -> Union[Type, None]:
            try:
                _type = get_property(type_name)
            except AttributeError:
                _type = Type
            return _type

        types = tuple(map(importer, type_names))
        try:
            res = issubclass(cls, types)
        except Exception as err:
            log.exception(f"unexpected exception: {cls} {type_names=} {types=} {err}")
            raise
        return res

    @classmethod
    def from_yaml(cls, yaml_path: _fpaths) -> _ConfigIO:
        # FIXME: type checking is ignored for the return statement because mypy
        # doesn't seem to know this is an abstract base class, and the argument
        # unpacking makes sense when instantiating any of the derived classes.
        return cls(**merge_rules(yaml_path, read_yaml))  # type: ignore

    @classmethod
    def from_json(cls, json_path: _fpaths) -> _ConfigIO:
        return cls(**merge_rules(json_path, read_json))  # type: ignore

    def to_dict(self) -> Dict:
        """NOTE: this probably doesn't work properly for nested dataclasses"""
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
