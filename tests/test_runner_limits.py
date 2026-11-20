from pathlib import Path

import pytest

from engine.tester import runner


def test_linux_xray_command_uses_prlimit_without_preexec(monkeypatch, tmp_path):
    monkeypatch.setattr(runner.sys, "platform", "linux")
    monkeypatch.setattr(runner.shutil, "which", lambda name: "/usr/bin/prlimit" if name == "prlimit" else None)
    command = runner._xray_command(Path("/opt/xray"), tmp_path / "xray.json", 25)
    assert command[:4] == [
        "/usr/bin/prlimit",
        "--cpu=27:27",
        "--nofile=128:128",
        "--as=536870912:536870912",
    ]
    assert command[4:] == ["--", "/opt/xray", "run", "-c", str(tmp_path / "xray.json")]


def test_linux_xray_command_fails_closed_without_prlimit(monkeypatch, tmp_path):
    monkeypatch.setattr(runner.sys, "platform", "linux")
    monkeypatch.setattr(runner.shutil, "which", lambda _name: None)
    with pytest.raises(runner.XrayTestError, match="XRAY_RESOURCE_LIMIT_TOOL_NOT_FOUND"):
        runner._xray_command(Path("/opt/xray"), tmp_path / "xray.json", 25)


def test_non_linux_xray_command_uses_direct_argument_vector(monkeypatch, tmp_path):
    monkeypatch.setattr(runner.sys, "platform", "darwin")
    monkeypatch.setattr(runner.shutil, "which", lambda _name: None)
    assert runner._xray_command(Path("/opt/xray"), tmp_path / "xray.json", 25) == [
        "/opt/xray", "run", "-c", str(tmp_path / "xray.json")
    ]
