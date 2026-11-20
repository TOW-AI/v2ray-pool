from pathlib import Path

import pytest
import yaml

from engine.core.config import ConfigurationError, load_settings


def test_default_settings_validate():
    settings = load_settings("config/settings.yml")
    assert settings["tester"]["enabled"] is False
    assert settings["tester"]["min_successful_observers"] == 2
    assert settings["intelligence"]["fixed_verified"]["min_runs"] == 6


def test_enabled_testing_requires_xray_binary_hash(tmp_path):
    source = yaml.safe_load(Path("config/settings.yml").read_text(encoding="utf-8"))
    source["tester"]["enabled"] = True
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    settings = config_dir / "settings.yml"
    settings.write_text(yaml.safe_dump(source), encoding="utf-8")
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()
    for path in Path("schemas").glob("*.json"):
        (schema_dir / path.name).write_bytes(path.read_bytes())
    with pytest.raises(ConfigurationError, match="xray_binary"):
        load_settings(settings)


def test_required_family_must_be_enabled(tmp_path):
    source = yaml.safe_load(Path("config/settings.yml").read_text(encoding="utf-8"))
    source["tester"]["enable_ipv4"] = False
    source["intelligence"]["required_ip_families"] = ["ipv4"]
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    settings = config_dir / "settings.yml"
    settings.write_text(yaml.safe_dump(source), encoding="utf-8")
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()
    for path in Path("schemas").glob("*.json"):
        (schema_dir / path.name).write_bytes(path.read_bytes())
    with pytest.raises(ConfigurationError, match="required IP family"):
        load_settings(settings)
