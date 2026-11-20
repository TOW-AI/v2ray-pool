import json
from pathlib import Path

import pytest

from engine.core.pipeline import PipelineError, run_pipeline
from engine.core.state import StateStore


def test_offline_pipeline_builds_valid_empty_snapshot(tmp_path):
    output = tmp_path / "generated" / "data"
    report = run_pipeline(
        "config/settings.yml",
        "config/sources.yml",
        tmp_path / "empty-source-data",
        output,
        offline=True,
    )
    assert report["quality"]["quality_gate"] == "passed"
    assert report["config_count"] == 0
    assert report["production_ready"] is False
    assert (output / "api/v1/configs.json").is_file()
    assert (output / "state/ip-history.json").is_file()
    assert (output / "sub/main.txt").read_bytes() == b""
    stats = json.loads((output / "api/v1/stats.json").read_text())
    assert stats["totals"]["publishable"] == 0
    assert stats["freshness"]["last_successful_run_at"] is None


def test_private_record_in_public_state_stops_pipeline(tmp_path):
    source = tmp_path / "data"
    state = {
        "configs": {
            "sha256:private": {
                "config_id": "sha256:private",
                "uri": "vless://secret@example.invalid:443",
                "public_redistribution": False,
                "status": "DISCOVERED",
            }
        },
        "observations": [],
        "transitions": [],
        "metrics": {},
    }
    StateStore.save(state, source)
    with pytest.raises(PipelineError, match="NON_PUBLIC_CONFIG_IN_PUBLIC_STATE"):
        run_pipeline(
            "config/settings.yml",
            "config/sources.yml",
            source,
            tmp_path / "generated" / "data",
            offline=True,
        )


def test_xray_test_pool_respects_configured_parallelism(tmp_path, monkeypatch):
    import shutil
    import threading
    import time

    import yaml

    import engine.core.pipeline as pipeline_module
    from engine.collector.parser import parse_uri
    from engine.models import ValidationResult
    from engine.tester.runner import XrayTestError

    config_dir = tmp_path / "config"
    schema_dir = tmp_path / "schemas"
    config_dir.mkdir()
    schema_dir.mkdir()
    for schema_file in Path("schemas").glob("*.json"):
        shutil.copy2(schema_file, schema_dir / schema_file.name)

    settings = yaml.safe_load(Path("config/settings.yml").read_text(encoding="utf-8"))
    settings["tester"]["enabled"] = True
    settings["tester"]["xray_binary"] = "/controlled/test/xray"
    settings["tester"]["xray_sha256"] = "a" * 64
    settings["tester"]["max_parallel_configs"] = 2
    settings_path = config_dir / "settings.yml"
    settings_path.write_text(yaml.safe_dump(settings), encoding="utf-8")

    records = {}
    for number in range(3):
        uri = f"vless://123e4567-e89b-12d3-a456-42661417400{number}@node{number}.example:443?encryption=none"
        parsed = parse_uri(uri)
        records[parsed.config_id] = {
            "config_id": parsed.config_id,
            "protocol": parsed.protocol,
            "uri": uri,
            "public_redistribution": True,
            "status": "DISCOVERED",
            "validation": {"status": "DISCOVERED"},
            "metrics": {},
        }

    data_root = tmp_path / "data"
    StateStore.save(
        {"configs": records, "observations": [], "transitions": [], "metrics": {}},
        data_root,
    )
    monkeypatch.setattr(pipeline_module, "verify_xray_binary", lambda _settings: tmp_path / "xray")
    monkeypatch.setattr(
        pipeline_module,
        "validate_full",
        lambda *_args, **_kwargs: ValidationResult("VALID", resolved_ips=["93.184.216.34"], tcp_reachable=True),
    )

    lock = threading.Lock()
    active = 0
    maximum_active = 0

    def fail_test(*_args, **_kwargs):
        nonlocal active, maximum_active
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        raise XrayTestError("CONTROLLED_TEST_FAILURE")

    monkeypatch.setattr(pipeline_module, "run_xray_test", fail_test)
    report = run_pipeline(
        settings_path,
        "config/sources.yml",
        data_root,
        tmp_path / "output" / "data",
        offline=False,
    )
    assert report["tests"] == {"successful": 0, "failed": 3, "skipped": 0}
    assert maximum_active == 2
    assert report["production_ready"] is False
