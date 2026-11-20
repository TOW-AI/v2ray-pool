import json

from engine.cli import main


def test_cli_validate_settings(capsys):
    assert main(["validate-settings", "--settings", "config/settings.yml"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "valid"
    assert report["source_count"] == 0


def test_cli_run_validate_and_audit_offline_tree(tmp_path, capsys):
    data_root = tmp_path / "source-data"
    output_root = tmp_path / "build" / "data"
    common = ["--settings", "config/settings.yml", "--sources", "config/sources.yml"]

    assert main(["run", *common, "--data-root", str(data_root), "--output", str(output_root), "--offline"]) == 0
    run_report = json.loads(capsys.readouterr().out)
    assert run_report["quality"]["quality_gate"] == "passed"
    assert run_report["production_ready"] is False

    assert main(["validate-output", "--data-root", str(output_root)]) == 0
    output_report = json.loads(capsys.readouterr().out)
    assert output_report["quality_gate"] == "passed"

    assert main(["audit-state", "--data-root", str(output_root)]) == 0
    state_report = json.loads(capsys.readouterr().out)
    assert state_report["status"] == "valid"
    assert state_report["configs"] == 0


def test_cli_returns_controlled_error_for_invalid_limit(tmp_path, capsys):
    result = main(
        [
            "run",
            "--settings",
            "config/settings.yml",
            "--sources",
            "config/sources.yml",
            "--data-root",
            str(tmp_path / "source"),
            "--output",
            str(tmp_path / "output"),
            "--offline",
            "--limit",
            "0",
        ]
    )
    report = json.loads(capsys.readouterr().err)
    assert result == 2
    assert report["status"] == "failed"
    assert "greater than zero" in report["error"]
