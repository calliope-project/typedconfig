from collections import Counter
from importlib import import_module
from itertools import chain
import json
from pathlib import Path
from types import SimpleNamespace
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Sequence,
    TextIO,
    Tuple,
    TypeVar,
    Union,
)

import yaml


class _Names:
    """This is a namespace class used to create and hold several namespaces

    The sub-namespaces are properties of this class, and are instantiated on
    first access.  The class attributes `_type_modules` and
    `_validator_modules` are a list of modules.  On first access the
    corresponding properties (`types` and `validators`) are populated with all
    the names included in `__all__` in these modules.  This "convention" is
    used to limit the names that are imported for the sake of namespace
    pollution.  The different sets of modules are also seperated under
    different sub-namespaces to reduce the chance of name collissions.

    This class is not supposed to be accessed directly; instead the singleton
    object instantiated below should be imported.

    If you want to add your custom modules, they can be included by adding to
    the list of modules _before_ accessing the sub-namespaces.

    >>> isinstance(NS.types, SimpleNamespace)
    True
    >>> isinstance(NS.validators, SimpleNamespace)
    True

    >>> hasattr(NS.types, 'List')  # from typing import List
    True
    >>> hasattr(NS.types, 'Literal')  # from typing_extensions import Literal
    True
    >>> hasattr(NS.types, 'conint')  # from pydantic.types import conint
    True
    >>> hasattr(NS.types, 'bool')  # from typedconfig.types import bool
    True

    # from typedconfig.validators import range_check
    >>> hasattr(NS.validators, 'range_check')
    True

    """

    _type_modules = [
        "typing",
        "typing_extensions",
        "pydantic.types",
        "typedconfig._types",
    ]
    _validator_modules = ["typedconfig.validators"]

    _types = False
    _validators = False

    @classmethod
    def _import(cls, modules: Iterable[str]):
        """Import names from a nested list of modules to namespace"""
        try:
            mods = [import_module(mod) for mod in modules]
        except ModuleNotFoundError as err:
            raise ValueError(err)

        try:
            ns = SimpleNamespace(
                **{
                    name: getattr(mod, name)
                    for mod in mods
                    for name in mod.__all__  # type: ignore
                }
            )
        except AttributeError as err:
            raise TypeError(f"non-conformant module: {err}")
        else:
            return ns

    @property
    def types(self):
        if not self._types:
            self._types = self._import(self._type_modules)
        return self._types

    @property
    def validators(self):
        if not self._validators:
            self._validators = self._import(self._validator_modules)
        return self._validators

    def reset(self):
        """Reset imported types and validators"""
        self._types = False
        self._validators = False

    def add_modules(
        self, type_or_validator: str, modules: Sequence[str]
    ) -> None:
        """Add custom modules to the list of modules"""
        if type_or_validator == "type":
            self._type_modules += list(modules)
        elif type_or_validator == "validator":
            self._validator_modules += list(modules)
        else:
            raise ValueError(f"{type_or_validator}: unknown module type")
        self.reset()  # invalidate imports after adding new modules

    def set_confdir(self, confdir: Union[str, Path]) -> None:
        """Set the config directory for the `ConfFilePath` type"""
        # FIXME: dirty hack
        self.types.ConfFilePath.confdir = confdir


NS = _Names()


def read_yaml(fpath: Union[str, Path]) -> Dict:  # pragma: no cover, trivial
    """Read a yaml file into a dictionary"""
    with open(fpath) as fp:
        return yaml.safe_load(fp)


def to_yaml(obj, fpath: Union[str, Path]):  # pragma: no cover, trivial
    """Serialise Python object to yaml"""
    with open(fpath, mode="w") as fp:
        yaml.dump(obj, fp)


def read_json(fpath: Union[str, Path]) -> Dict:  # pragma: no cover, trivial
    """Read a json file into a dictionary"""
    with open(fpath) as fp:
        return json.load(fp)


def to_json(obj, fpath: Union[str, Path]):  # pragma: no cover, trivial
    """Serialise Python object to json"""
    with open(fpath, mode="w") as fp:
        json.dump(obj, fp)


def merge_dicts(confs: Sequence[Dict]) -> Dict:
    """Merge a sequence of dictionaries

    Common keys at the same depth are recursively reconciled.  The newer value
    overwrites earlier values.  The order of the keys are preserved.  When
    merging repeated keys, the position of the first occurence is considered as
    correct.

    Parameters
    ----------
    confs: Sequence[Dict]
        A list of dictionaries

    Returns
    -------
    Dict
        Merged dictionary

    """
    if not all(map(lambda obj: isinstance(obj, dict), confs)):
        return confs[-1]

    res: Dict[str, Any] = {}
    for key, count in Counter(chain.from_iterable(confs)).items():
        matches = [conf[key] for conf in confs if key in conf]
        if count > 1:
            res[key] = merge_dicts(matches)  # duplicate keys, recurse
        else:
            res[key] = matches[0]  # only one element
    return res


_file_t = TypeVar("_file_t", str, Path, TextIO)


def merge_rules(
    fpaths: Union[_file_t, List[_file_t], Tuple[_file_t]],
    reader: Callable[[_file_t], Dict],
) -> Dict:
    """Merge a sequence of dictionaries

    Common keys at the same depth are recursively reconciled.  The newer value
    overwrites earlier values.  The order of the keys are preserved.  When
    merging repeated keys, the position of the first occurence is considered as
    correct.

    Note, the type `T` refers to any object that can refer to a file; e.g. a
    file path or stream object, as long as the matching function knows how to
    read it.

    Parameters
    ----------
    fpaths: Union[T, List[T], Tuple[T]]
        Path to a rules file, or a sequence of paths
    reader: Callable[[T], Dict]
        Function used to read the files; should return a dictionary

    Returns
    -------
    Dict
        Dictionary after merging rules

    """
    if isinstance(fpaths, (list, tuple)):
        conf = merge_dicts([reader(f) for f in fpaths])
    else:
        conf = reader(fpaths)
    return conf
