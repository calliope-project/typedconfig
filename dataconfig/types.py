"""Types that maybe used in a config file"""

# import standard library types for singleton namespace to import
from builtins import bool, int, float, str
from pathlib import Path
from typing import Type

from pydantic.dataclasses import dataclass as pydantic_dataclass
from pydantic.types import confloat, conint, FilePath
from pandas import Timedelta


__all__ = [
    "bool",
    "int",
    "float",
    "str",
    "Path",
    "unitfloat",
    "unitint",
    "FileWithSubset",
    "Timedelta",
]


def unitfloat(unit: str, **kwargs) -> Type[float]:
    namespace = dict(unit=unit)
    confloat_t = confloat(**kwargs)
    return type("UnitFloat", (confloat_t,), namespace)


def unitint(unit: str, **kwargs,) -> Type[int]:
    namespace = dict(unit=unit)
    conint_t = conint(**kwargs)
    return type("UnitInt", (conint_t,), namespace)


@pydantic_dataclass
class FileWithSubset:
    filepath: FilePath
    column: str

    @classmethod
    def from_string(cls, string):
        filepath, column = string.rsplit(":", 1)
        return cls(filepath=filepath, column=column)
