from pathlib import Path
import shutil

from boltons.iterutils import remap

from pydc.helpers import read_yaml
from pydc.parsers import get_config_t


# not a unit test, more of an integration test
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
