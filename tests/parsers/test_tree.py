from inspect import getclosurevars
from pathlib import Path
import platform
import shutil

from boltons.iterutils import remap
from glom import glom
import pydantic.types
import pytest
import typing_extensions

from typedconfig.helpers import read_yaml
from typedconfig.parsers.tree import (
    _is_node,
    _nodes,
    _is_leaf,
    _leaves,
    _path_to_glom_spec,
    _type,
    _validator,
    _str_to_spec,
    _spec_to_type,
    get_config_t,
)


def test_nodes():
    # FIXME: generate examples
    conf = {
        "foo": {
            "bar": {"type": "int"},
            "baz": {
                "bah": 42,
                "alt": {"type": "Literal", "opts": ["abc", "xyz"]},
            },
        },
        "bla": {"eg": "str"},
    }
    nodes = [
        ("foo",),
        ("foo", "bar"),
        ("foo", "baz"),
        ("foo", "baz", "bah"),
        ("foo", "baz", "alt"),
        ("bla",),
        ("bla", "eg"),
    ]
    not_nodes = [
        ("foo", "bar", "type"),
        ("foo", "baz", "alt", "type"),
        ("foo", "baz", "alt", "opts"),
    ]

    def isnode(path):
        return _is_node(path, path[-1], glom(conf, ".".join(path)))

    assert all(list(map(isnode, nodes)))
    assert not any(list(map(isnode, not_nodes)))

    assert _nodes(conf) == set(nodes)


def test_leaves():
    # FIXME: generate examples
    paths = [
        ("foo",),
        ("foo", "bar"),
        ("foo", "bar", 0),
        ("foo", "bar", 1),
        ("foo", "bar", 1, "baz"),
        ("foo", "bar", 1, "bah"),
    ]

    assert _is_leaf(("foo", "bar", 1, "baz"), paths)
    assert not _is_leaf(("foo", "bar", 1), paths)
    assert not _is_leaf(("not", "there"), paths)

    result = _leaves(paths)
    expected = {
        ("foo", "bar", 0),
        ("foo", "bar", 1, "baz"),
        ("foo", "bar", 1, "bah"),
    }
    assert result == expected


def test_path_to_glom_spec():
    path = ("foo", "bar", 5, "baz")
    spec = _path_to_glom_spec(path)
    assert isinstance(spec, str)
    assert len(spec.split(".")) == len(path)


def test_type_getter():
    spec = {"type": "Literal", "opts": ["foo", "bar"]}

    # type with [..]
    result = _type(spec)
    expected = getattr(typing_extensions, spec["type"])[tuple(spec["opts"])]
    assert result == expected

    # type from factory
    spec = {"type": "conint", "opts": {"gt": 0, "le": 10}}
    c_int1 = _type(spec)
    c_int2 = getattr(pydantic.types, spec["type"])(**spec["opts"])
    assert type(c_int1) == type(c_int2)
    assert c_int1.gt == c_int2.gt and c_int1.lt == c_int2.lt

    # just type
    spec = {"type": "PositiveInt"}
    expected = getattr(pydantic.types, spec["type"])
    assert _type(spec) == expected

    # type with unsupported option
    spec.update(opts="foo")
    with pytest.warns(UserWarning, match="ambiguous option ignored.+"):
        assert _type(spec) == expected


def test_validator_getter():
    # TODO: test all variations
    spec = {
        "validator": "range_check",
        "validator_params": {"min_key": "min"}
        # "validator_opts":  FIXME:
    }
    key = "foo"

    name, validator = _validator(key, spec).popitem()
    assert name in str(validator.__func__)  # function import
    assert validator.__validator_config__[0] == (key,)  # validated key
    assert (
        getclosurevars(validator.__func__).nonlocals["params"]
        == spec["validator_params"]
    )  # function parameters
    # TODO: test validator opts

    spec.update(root_validator=True)
    name, validator = _validator(key, spec).popitem()  # 'key' is ignored
    assert hasattr(validator, "__root_validator_config__")


def test_spec_parsing():
    # see `typedconfig.validators` for the definition of `threshold`
    spec = {
        "foo": {
            "type": "PositiveFloat",
            "validator": "threshold",
            "validator_params": {"threshold": 5},
        }
    }

    # Test if the spec is modified in-place
    _str_to_spec("foo", spec["foo"])
    # the base type is imported
    assert isinstance(glom(spec, "foo.type"), type)
    # the custom validator is still a dictionary: {"methodname": <method>}
    assert isinstance(glom(spec, "foo.validator"), dict)
    assert isinstance(glom(spec, "foo.validator.threshold"), classmethod)

    config_t = _spec_to_type("foo", spec)
    assert isinstance(config_t, type)
    assert config_t(foo=2).foo == 2

    # 'foo' is a 'PositiveFloat'
    with pytest.raises(ValueError):
        config_t(foo=-1)
    # custom validator with the threshold set to 5
    with pytest.raises(ValueError, match="above threshold:.+"):
        config_t(foo=6)


def test_spec_parsing_nested():
    # root validator on a leaf node
    spec = {
        "zero_sum_total": {
            "foo": {"type": "PositiveInt"},
            "bar": {
                "type": "PositiveInt",
                "validator": "zero_sum",
                "validator_params": {"total": 15},
                "root_validator": True,
            },
        }
    }

    config_t = get_config_t(spec)
    conf = config_t(zero_sum_total=dict(foo=5, bar=10))
    assert conf.zero_sum_total.foo + conf.zero_sum_total.bar == 15

    with pytest.raises(ValueError, match=".+do not add up.+"):
        config_t(zero_sum_total={"foo": 15, "bar": 10})
    with pytest.raises(ValueError, match=".+do not add up.+"):
        config_t(zero_sum_total={"foo": 5, "bar": 1})

    # root validator on an intermediate node
    spec = {
        "top": {
            "first": {"type": "PositiveInt"},
            "second": {
                "type": "PositiveInt",
                "validator": "sum_by_name",
                "validator_params": {"total": 15},
                "root_validator": True,
            },
            "nest": {"leaf": {"type": "conint", "opts": {"multiple_of": 5}}},
        }
    }

    config_t = get_config_t(spec)
    conf = config_t(top=dict(first=5, second=10, nest={"leaf": 15}))
    assert conf.top.first + conf.top.second == 15
    assert conf.top.nest.leaf % 5 == 0

    with pytest.raises(ValueError, match=".+do not add up.+"):
        config_t(top=dict(first=5, second=1, nest={"leaf": 15}))
    with pytest.raises(ValueError, match=".+multiple of+"):
        config_t(top=dict(first=5, second=10, nest={"leaf": 13}))


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
    log_dir = Path("/tmp/typedconfig-dir")
    log_dir.mkdir(exist_ok=True)
    (log_dir / "file.log").touch()

    config = config_t.from_yaml(conf_dir / "config.yaml")
    assert config.run and config.model

    shutil.rmtree(log_dir)
