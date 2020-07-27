from inspect import getclosurevars
from dataclasses import field
from typing import Any, Dict

from pydantic import confloat, PositiveInt, validator, ValidationError
from pydantic.dataclasses import dataclass as pydantic_dataclass
import pytest
from typing_extensions import Literal  # in 3.8, 'from typing'

from dataconfig.factory import make_dataconfig, make_validator


# standard dataclass
@pydantic_dataclass
class RangeType0:
    min: PositiveInt
    max: PositiveInt

    @validator("max")
    def range_check(cls, _max, values):
        if "min" in values and values["min"] > _max:
            raise ValueError(f"bad range: {values['min']} not < {_max}")
        return _max


# dataclass factory, with a custom validator passed in the namespace
@validator("max")
def range_check(cls, _max, values):
    if "min" in values and values["min"] > _max:
        raise ValueError(f"bad range: {values['min']} not < {_max}")
    return _max


RangeType1 = make_dataconfig(
    "RangeType1",
    [("min", PositiveInt), ("max", PositiveInt)],
    namespace={"range_check": range_check},
)


# dataclass factory, with a custom validator passed as a baseclass
class RangeCheck:
    @validator("max")
    def range_check(cls, _max, values):
        if "min" in values and values["min"] > _max:
            raise ValueError(f"bad range: {values['min']} not < {max}")
        return _max


RangeType2 = make_dataconfig(
    "RangeType2",
    [("min", PositiveInt), ("max", PositiveInt)],
    bases=(RangeCheck,),
)


@pytest.mark.parametrize("range_t", [RangeType0, RangeType1, RangeType2])
def test_make_dataconfig(range_t, capsys):
    rng = range_t(1, 5)
    assert rng.min == 1
    assert rng.max == 5

    with pytest.raises(ValueError):
        # arg not +ve definite
        range_t(-1, 5)

    with pytest.raises(ValidationError):
        # validator: bad range, min > max
        range_t(10, 5)

    # FIXME: how to check exception text?
    # capture = capsys.readouterr()
    # assert "bad range" in capture.out

    with pytest.raises(TypeError):
        # missing arguments
        range_t(5)


RunConfig_t = make_dataconfig(
    "RunConfig_t",
    [
        ("mode", Literal[("quiet", "normal", "verbose")]),
        ("eff", confloat(gt=0, lt=1)),
    ],
)


def test_basic_checks():
    with pytest.raises(ValueError):
        # mode not in set
        RunConfig_t("foo", 0.3)

    with pytest.raises(ValueError):
        # eff not in range
        RunConfig_t("quiet", 1.3)


ObjOpts_t = make_dataconfig(
    "ObjOpts_t",
    [
        ("cost_class", Dict),
        ("sense", Literal[("maximize", "minimize")]),
        ("moreopts", Any, field(default=None)),
    ],
)


def test_set_defaults():
    obj_opts = ObjOpts_t(cost_class={"monetary": 1}, sense="minimize")
    assert obj_opts.moreopts is None


@validator("objective_options")
def mandatory_opts(cls, obj_opts, values):
    # alternate: isinstance(obj_opts, ObjOpts_t)
    mandatory = {"cost_class", "sense"}
    keys = set(vars(obj_opts))
    if (
        "objective" in values
        and "cost" in values["objective"]
        and keys.intersection(mandatory) == mandatory
    ):
        return obj_opts
    else:
        raise ValueError(
            f"missing mandatory options: {mandatory} not in {keys}"
        )


Objective_t = make_dataconfig(
    "Objective_t",
    [
        ("objective", Literal["minmax_cost_optimization"]),
        ("objective_options", ObjOpts_t),
    ],
    namespace={"mandatory_opts": mandatory_opts},
)


def test_conditional_keys():
    obj_opts = ObjOpts_t(
        cost_class={"monetary": 1}, sense="minimize", moreopts="foo"
    )
    optimiser_settings = Objective_t(
        objective="minmax_cost_optimization", objective_options=obj_opts,
    )
    assert optimiser_settings.objective_options.cost_class
    assert optimiser_settings.objective_options.sense

    assert Objective_t(
        objective="minmax_cost_optimization",
        objective_options={
            "cost_class": {"monetary": 1},
            "sense": "minimize",
            "moreopts": None,
        },
    )

    with pytest.raises(ValidationError):
        Objective_t(
            objective="minmax_cost_optimization",
            objective_options={"sense": "minimize", "moreopts": "foo"},
        )


Config_t = make_dataconfig(
    "Config_t",
    [("run", RunConfig_t), ("range", RangeType0), ("optimise", Objective_t)],
)


def test_nested_config():
    run = RunConfig_t(mode="normal", eff=0.42)
    rng = RangeType0(1, 5)
    obj_opts = ObjOpts_t(
        cost_class={"monetary": 1}, sense="minimize", moreopts=None
    )
    optimiser_settings = Objective_t(
        objective="minmax_cost_optimization", objective_options=obj_opts,
    )
    config = Config_t(run=run, range=rng, optimise=optimiser_settings)

    assert config.run.mode == "normal"
    assert abs(config.run.eff - 0.42) < 1e-3
    assert config.range.min == 1
    assert config.range.max == 5
    assert config.optimise.objective == "minmax_cost_optimization"
    assert config.optimise.objective_options.cost_class == {"monetary": 1}
    assert config.optimise.objective_options.sense == "minimize"
    assert config.optimise.objective_options.moreopts is None


def quadrant(cls, values, *, axes, signs):
    if all(k in values for k in axes) and all(
        values[k] * s > 0 for k, s in zip(axes, signs) if s != 0
    ):
        return values

    raise ValueError(f"{values} not in quadrant: {signs}")


def test_make_validator():
    params = {"axes": "xy", "signs": (1, -1)}
    key = "foo"

    name, validator = make_validator(quadrant, key, **params).popitem()
    assert isinstance(validator, classmethod)
    assert name == quadrant.__name__
    assert getclosurevars(validator.__func__).nonlocals["params"] == params
    assert validator.__validator_config__[0] == (key,)  # validated key

    name, root_validator = make_validator(quadrant, "", **params).popitem()
    assert isinstance(root_validator, classmethod)

    # TODO: test options
