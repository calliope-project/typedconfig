"""Types that maybe used in a config file"""

# import standard library types for singleton namespace to import
from builtins import bool, int, float, str
from pathlib import Path
from typing import Any, Callable, Dict, Generator
from warnings import warn

from pydantic import errors
from pydantic.color import Color
from pydantic.validators import path_validator


__all__ = [
    "bool",
    "int",
    "float",
    "str",
    "Path",
    "Color",
    "ConfFilePath",
]


AnyCallable = Callable[..., Any]
CallableGenerator = Generator[AnyCallable, None, None]


class ConfFilePath(Path):
    """Custom type to validate file paths relative to the config directory

    Sometimes a different config file might need to be referenced.  In this
    case, the user expects the path to be relative to the current file.  But to
    validate this data, the type needs to know where the config files are
    located.  This is runtime information, not to mention it is not possible to
    infer this info dynamically.  So this custom type provides a configuration
    hook to specify a config directory, and allows files path to be validated
    relatively to it.

    Use the namespace instance (`helpers.NS`) to set the config direcory.

    """

    confdir = ""

    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Any]) -> None:
        field_schema.update(format="conf-file-path")

    @classmethod
    def __get_validators__(cls) -> CallableGenerator:
        yield path_validator
        yield cls.validate

    @classmethod
    def validate(cls, value: Path) -> Path:
        # FIXME: dirty hack, doesn't validate correctly unless cls.confdir is
        # set correctly, which has to be done externally.  Unfortunately, can't
        # find a way to "deduce" this information.
        if not cls.confdir:
            warn(
                f"{cls}: confdir not set, validation might fail",
                category=RuntimeWarning,
            )
        conf = Path(cls.confdir) / value
        if not conf.exists():
            raise errors.PathNotExistsError(path=conf)
        if not conf.is_file():
            raise errors.PathNotAFileError(path=conf)
        return value
