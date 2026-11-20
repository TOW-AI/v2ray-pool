from pathlib import Path

from scripts.security_audit import run_audit


def test_static_security_audit_passes_project_source():
    root = Path(__file__).resolve().parents[1]
    report = run_audit(root)
    assert report["status"] == "passed", report["findings"]
