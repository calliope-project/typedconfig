from inspect import getclosurevars
from pathlib import Path
import platform
import shutil

from boltons.iterutils import remap
import pydantic.types
import pytest
import typing_extensions

from pydc.helpers import read_yaml
from pydc.parsers import get_config_t, _type, _validator


def test_type_getters():
    spec = {
        "type": "Literal",
        "opts": ["foo", "bar"],
    }

    # type with [..]
    assert (
        _type(spec)
        == getattr(typing_extensions, spec["type"])[tuple(spec["opts"])]
    )

    # type from facttory
    spec.update(type="conint", opts={"gt": 0, "le": 10})
    c_int = _type(spec)
    c_int2 = getattr(pydantic.types, spec["type"])(**spec["opts"])
    assert type(c_int) == type(c_int2)
    assert c_int.gt == c_int2.gt and c_int.lt == c_int2.lt

    # just type, FIXME: not sure why this fails
    spec.update(type="PositiveInt")
    del spec["opts"]
    with pytest.raises(AssertionError):
        assert type(_type(spec)) == getattr(pydantic.types, spec["type"])


def test_validator_getter():
    spec = {
        "validator": "range_check",
        # "validator_opts":  FIXME:
    }
    keys = ("bar", "foo")
    validator = _validator(keys[-1], keys, spec)[spec["validator"]]

    assert isinstance(validator, classmethod)  # type
    assert validator.__validator_config__[0] == keys[-1:]  # validated key
    # list of all keys of parent
    assert getclosurevars(validator.__func__).nonlocals["keys"] == keys


# not a unit test, more of an integration test
@pytest.mark.skipif(
    platform.system() != "Linux", reason="FIXME: Test setup is Linux specific"
)
def test_config_t():
    conf_dir = Path("tests/conf")
    rules = read_yaml(conf_dir / "rules.yaml")
    # remove validator because none are implemented
    conf_rules = remap(rules, visit=lambda p, k, v: k not in ("validator",))
    config_t = get_config_t(conf_rules)

    # ensure dirs/files exist
    log_dir = Path("/tmp/pydc-dir")
    log_dir.mkdir(exist_ok=True)
    (log_dir / "file.log").touch()

    config = config_t.from_yaml(conf_dir / "config.yaml")
    assert config.run and config.model

    shutil.rmtree(log_dir)
