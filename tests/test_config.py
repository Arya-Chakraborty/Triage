from pathlib import Path

import pytest

from triage.config.loader import load_config
from triage.config.models import config_from_dict


def test_bad_port():
    with pytest.raises(ValueError, match="dashboard.port"):
        config_from_dict({"dashboard": {"port": 99999}}, Path("."))


def test_health_requires_url():
    with pytest.raises(ValueError, match="watch.health"):
        config_from_dict({"watch": {"health": [{"name": "x"}]}}, Path("."))


def test_invalid_yaml(tmp_path: Path):
    (tmp_path / ".triage.yaml").write_text("dashboard: [\n")
    with pytest.raises(ValueError, match="YAML"):
        load_config(tmp_path)
