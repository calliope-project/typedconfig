import pytest

from pydc.helpers import NS


@pytest.mark.xfail(
    reason="passes only when runs first, how to ensure order?", strict=False
)
def test_nonexistent_module():
    NS._type_modules = ("nonexistent",)
    with pytest.raises(ValueError):
        NS.types


@pytest.mark.skip(reason="not sure how to generate a module on the fly")
def test_nonconformant_module():
    # modules with custom types and validators are required to have __all__
    # defined.  The names defined there are imported into the namespace.
    pass
