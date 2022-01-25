from pathlib import Path

import pytest

from typedconfig.helpers import read_yaml, NS


@pytest.mark.skip(reason="validators not defined")
def test_properties():
    from typedconfig.parsers.graph import properties

    rules = {
        "name": {"type": "str"},
        "label": {"type": "str"},
        "carrier": {"type": "Dict", "opts": ["str", "bool"]},
        "energy_eff_per_distance": {
            "type": "confloat",
            "opts": {"gt": 0, "lt": 1},
        },
        "energy_prod": {"type": "bool"},
        "energy_cap_max": {"type": "PositiveFloat"},
        "lifetime": {"type": "PositiveInt"},
        "resource": {"type": "PositiveFloat"},
        "resource_array": {"type": "ConfFilePath"},
        "resource_unit": {
            "type": "Literal",
            "opts": ["energy", "energy_per_cap"],
        },
        "costs": {"type": "Dict"},
        "resource_area_per_energy_cap": {"type": "PositiveFloat"},
        "resource_area_max": {"type": "PositiveFloat"},
        "lat": {"type": "confloat", "opts": {"gt": -90, "lt": 90}},
        "lon": {"type": "confloat", "opts": {"gt": -180, "lt": 180}},
        "available_area": {"type": "PositiveFloat"},
    }

    conf_dir = Path("tests/conf")
    rules = read_yaml(conf_dir / "rules.yaml")
    conf = read_yaml(conf_dir / "techs.yaml")

    NS.set_confdir(f"{conf_dir}")

    props = properties(rules, {}, conf)
    assert props
