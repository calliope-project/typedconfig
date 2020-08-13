from io import StringIO

import pytest
import yaml

from typedconfig.helpers import _Names, merge_dicts, merge_rules


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
    NS._type_modules = ("typedconfig.helpers",)
    with pytest.raises(TypeError):
        NS.types


def test_reload():
    NS = _Names()
    # all default modules loaded
    assert hasattr(NS.types, "List")
    assert hasattr(NS.types, "PositiveInt")
    NS._type_modules = ["typing"]
    NS.reset()
    # pydantic.types is not loaded, so PositiveInt isn't available
    assert hasattr(NS.types, "List")
    assert not hasattr(NS.types, "PositiveInt")


def test_merge():
    d1 = {"a": 1, "b": {"c": 3, "d": 4}, "e": True}
    d2 = {"c": 3, "b": {"e": 5, "d": 40}, "e": {"g": True, "h": "foo"}}
    # - b.d tests overwriting values
    # - e & b.d tests order
    # - e & e.* tests adding new sub-keys
    expected = {
        "a": 1,
        "b": {"c": 3, "d": 40, "e": 5},
        "e": {"g": True, "h": "foo"},
        "c": 3,
    }
    result = merge_dicts([d1, d2])
    assert result == expected
    # check order
    assert result.keys() == expected.keys()
    assert result["b"].keys() == expected["b"].keys()

    streams = [StringIO(), StringIO()]
    for i, d in enumerate((d1, d2)):
        yaml.dump(d, streams[i])
        streams[i].seek(0)

    result = merge_rules(streams, yaml.safe_load)
    assert result == expected
    # check order
    assert result.keys() == expected.keys()
    assert result["b"].keys() == expected["b"].keys()
