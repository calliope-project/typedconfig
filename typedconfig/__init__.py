import sys
from types import ModuleType


def register(obj, submodule: str):
    """Register a type with the module

    Parameters
    ----------
    _type : Type
        Type to register
    submodule : str
        Name of the submodule the type is added to is created by prepending an
        underscore: foo -> typedconfig._foo

    Returns
    -------
    Type
        Returns the type after registering it with the module

    """
    modname = f"{__name__}._{submodule}"
    module = sys.modules.setdefault(modname, ModuleType(modname))
    setattr(obj, "__module__", modname)
    stringify = obj.__name__ if isinstance(obj, type) else str(obj)
    setattr(module, stringify, obj)
    return obj
