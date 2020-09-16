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
    _filter,
    _is_node,
    _is_leaf,
    _is_optional,
    _is_mandatory,
    _leaf_subset,
    _type,
    _validator,
    _str_to_spec,
    _spec_to_type,
    get_config_t,
    _resolve_optional,
    get_config,
)


def test_filter():
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
        "kaa": {"boom": {"type": str, "optional": True}},
    }
    nodes = [
        ("foo",),
        ("foo", "bar"),
        ("foo", "baz"),
        ("foo", "baz", "bah"),
        ("foo", "baz", "alt"),
        ("bla",),
        ("bla", "eg"),
        ("kaa",),
        ("kaa", "boom"),
    ]
    not_nodes = [
        ("foo", "bar", "type"),
        ("foo", "baz", "alt", "type"),
        ("foo", "baz", "alt", "opts"),
    ]

    def isnode(path):
        return _is_node(path, path[-1], glom(conf, path))

    assert all(list(map(isnode, nodes)))
    assert not any(list(map(isnode, not_nodes)))
    assert _filter(conf, _is_node) == set(nodes)

    leaves = [("foo", "bar"), ("foo", "baz", "alt"), ("kaa", "boom")]
    not_leaves = [
        ("foo", "baz"),
        ("foo", "baz", "bah"),
        ("bla", "eg"),
        ("foo", "bar", "type"),
    ]

    def isleaf(path):
        return _is_leaf(path, path[-1], glom(conf, path))

    assert all(list(map(isleaf, leaves)))
    assert not any(list(map(isleaf, not_leaves)))
    assert _filter(conf, _is_leaf) == set(leaves)

    optional = [("kaa", "boom")]
    not_optional = set(leaves) - set(optional)

    def isoptional(path):
        return _is_optional(path, path[-1], glom(conf, path))

    assert all(list(map(isoptional, optional)))
    assert not any(list(map(isoptional, not_optional)))
    assert not any(list(map(isoptional, not_leaves)))
    assert _filter(conf, _is_optional) == set(optional)

    def ismandatory(path):
        return _is_mandatory(path, path[-1], glom(conf, path))

    assert all(list(map(ismandatory, not_optional)))
    assert not any(list(map(ismandatory, optional)))
    assert not any(list(map(ismandatory, not_leaves)))
    assert _filter(conf, _is_mandatory) == set(not_optional)


def test_leaf_subset():
    # FIXME: generate examples
    paths = [
        ("foo",),
        ("foo", "bar"),
        ("foo", "bar", 0),
        ("foo", "bar", 1),
        ("foo", "bar", 1, "baz"),
        ("foo", "bar", 1, "bah"),
    ]
    result = _leaf_subset(paths)
    expected = {
        ("foo", "bar", 0),
        ("foo", "bar", 1, "baz"),
        ("foo", "bar", 1, "bah"),
    }
    assert result == expected


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

    spec = {
        "validator": ["range_check", "threshold"],
        "validator_params": [{"min_key": "min"}, {"threshold": 10}]
        # "validator_opts":  FIXME:
    }
    validators = _validator(key, spec)
    assert all(name in str(_val.__func__) for name, _val in validators.items())
    assert all(
        v.__validator_config__[0] == (key,) for v in validators.values()
    )


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

    spec = {
        "foo": {
            "type": "PositiveFloat",
            "validator": ["threshold", "mult_of"],
            "validator_params": [{"threshold": 15}, {"factor": 3}],
        }
    }
    spec["foo"] = _str_to_spec("foo", spec["foo"])
    config_t = _spec_to_type("foo", spec)

    conf = config_t(foo=9)
    assert isinstance(config_t, type)
    assert conf.foo == 9

    with pytest.raises(ValueError, match="not a multiple"):
        config_t(foo=10)
    with pytest.raises(ValueError, match="above threshold"):
        config_t(foo=16)
    with pytest.raises(ValueError, match="above threshold"):
        config_t(foo=18)


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


def test_optional():
    rules = {
        "foo": {"type": "int", "default": 0},
        "bar": {"type": "int", "optional": True},
        "baz": {"type": "float"},
        "parent": {
            "child": {"type": "bool", "default": False},
            "cousin": {"type": "bool", "optional": True},
        },
        "array1": {"type": "List", "opts": ["int"]},
        "array2": {"type": "List", "opts": ["int"], "optional": True},
    }

    expected = {("bar",), ("parent", "cousin"), ("array2",)}
    result = _filter(rules, _is_optional)
    assert result == expected

    conf = {
        "foo": 42,
        # "bar" is optional, and absent
        "baz": 3.14,
        "parent": {
            # "child", mandatory, but has a default, so can be missing
            "cousin": True  # optional, and present
        },
        "array1": [7, 49],
        "array2": [-3, 3],  # optional, and present
    }

    result = _resolve_optional(rules, conf)
    assert "bar" not in result
    assert "cousin" in result["parent"]
    assert "array2" in result

    config = get_config_t(result)(**conf)

    assert not hasattr(config, "bar")
    assert config.parent.child == False
    assert config.parent.cousin == True
    assert config.array2 == [-3, 3]
