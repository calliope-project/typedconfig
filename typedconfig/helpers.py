from collections import Counter
from importlib import import_module
from itertools import chain
import json
from pathlib import Path
import re
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


def import_from(module: str, name: str) -> Any:
    """Import `name` from `module`

    Raises
    ------
    AttributeError
        If `name` doesn't exist

    """
    return getattr(import_module(module), name)


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

    _default_type_modules = [
        "typing",
        "typing_extensions",
        "pydantic.types",
        "typedconfig._types",
    ]
    _default_validator_modules = ["typedconfig.validators"]

    _type_modules = _default_type_modules.copy()
    _validator_modules = _default_validator_modules.copy()

    _types = False
    _validators = False

    class _Namespace(SimpleNamespace):
        def __getitem__(self, attr):
            try:
                res = getattr(self, attr)
            except AttributeError as err:
                identifier_re = r"'([a-zA-Z0-9_.]+)'"
                msg, *_ = err.args
                obj, attr = re.match(r".+".join([identifier_re] * 2), msg).groups()
                if type(self).__name__ == obj:
                    raise RuntimeError(f"{self._mods} has no {self._kind} {attr!r}")
                else:
                    raise
            else:
                return res

        def get(self, attr, default=None):
            try:
                res = self.__getitem__(attr)
            except RuntimeError:
                return default
            else:
                return res

    @classmethod
    def _import(cls, kind: str, modules: Iterable[str]):
        """Import names from a nested list of modules to namespace"""
        try:
            mods = [import_module(mod) for mod in modules]
        except ModuleNotFoundError as err:
            raise ValueError(err)

        try:
            ns = cls._Namespace(
                **{
                    name: getattr(mod, name)
                    for mod in mods
                    for name in mod.__all__  # type: ignore
                }
            )
        except AttributeError as err:
            raise TypeError(f"non-conformant module: {err}")
        else:
            ns._kind = kind
            ns._mods = modules
            return ns

    @property
    def types(self):
        if not self._types:
            self._types = self._import("type", self._type_modules)
        return self._types

    @property
    def validators(self):
        if not self._validators:
            self._validators = self._import("validator", self._validator_modules)
        return self._validators

    def reset(self):
        """Reset imported types and validators"""
        self._types = False
        self._validators = False

    def reset_modules(self):
        self._type_modules = self._default_type_modules.copy()
        self._validator_modules = self._default_validator_modules.copy()

    def add_modules(self, type_or_validator: str, modules: Sequence[str]) -> None:
        """Add custom modules to the list of modules"""
        if isinstance(modules, str):
            modules = [modules]
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

    Examples
    --------

    - e & b.d tests overwriting values
    - b, e & b.d tests key ordering
    - e & e.* tests adding new sub-keys

    >>> d1 = {"a": 1, "b": {"c": 3, "d": 4}, "e": True}
    >>> d2 = {"c": 3, "b": {"e": 5, "d": 40}, "e": {"g": True, "h": "foo"}}
    >>> expected = {
    ...     "a": 1,
    ...     "b": {"c": 3, "d": 40, "e": 5},
    ...     "e": {"g": True, "h": "foo"},
    ...     "c": 3,
    ... }
    >>> result = merge_dicts([d1, d2])
    >>> result == expected
    True
    >>> list(result) == list(expected)  # key ordering preserved
    True
    >>> list(result["b"]) == list(expected["b"])  # key ordering preserved
    True

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
