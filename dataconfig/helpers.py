from importlib import import_module
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, Iterable, Union

import yaml


class _Names(SimpleNamespace):
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

    >>> isinstance(NS, SimpleNamespace)
    True
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
    >>> hasattr(NS.types, 'bool')  # from dataconfig.types import bool
    True

    # from dataconfig.validators import range_check
    >>> hasattr(NS.validators, 'range_check')
    True

    """

    _type_modules = [
        "typing",
        "typing_extensions",
        "pydantic.types",
        "dataconfig.types",
    ]
    _validator_modules = ["dataconfig.validators"]

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
