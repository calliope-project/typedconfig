import pytest

from pydc.helpers import _Names


def test_nonexistent_module():
    # Importing the singleton namespace and misconfiguring it meant all
    # following tests would be affected, and those depending on it would fail.
    # So create an isolated singleton object.
    NS = _Names()
    NS._type_modules = ("nonexistent",)
    with pytest.raises(ValueError):
        NS.types


def test_edit_module_list():
    NS = _Names()
    NS._type_modules = ("typing",)
    assert hasattr(NS.types, "List")
    assert not hasattr(NS.types, "PositiveInt")


def test_nonconformant_module():
    # modules in the module list are required to have __all__ defined; simulate
    # a non-conformant module by importing one of the internal modules
    NS = _Names()
    NS._type_modules = ("pydc.helpers",)
    with pytest.raises(TypeError):
        NS.types
