#!/usr/bin/env python3
"""Run deterministic, local security checks on Python and dashboard source."""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

DANGEROUS_CALLS = {"eval", "exec", "os.system", "os.popen", "subprocess.getoutput", "subprocess.getstatusoutput"}
SUBPROCESS_CALLS = {"subprocess.run", "subprocess.Popen", "subprocess.call", "subprocess.check_call", "subprocess.check_output"}
UNSAFE_JS_SINKS = re.compile(r"\.\s*(?:innerHTML|outerHTML)\s*=|document\s*\.\s*write\s*\(|\beval\s*\(")


def _call_name(node: ast.Call) -> str:
    try:
        return ast.unparse(node.func)
    except Exception:
        return ""


def audit_python(path: Path) -> list[str]:
    findings: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        return [f"PYTHON_PARSE_ERROR:{path}:{type(exc).__name__}"]
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if name in DANGEROUS_CALLS:
            findings.append(f"DANGEROUS_CALL:{path}:{node.lineno}:{name}")
        if name in SUBPROCESS_CALLS:
            shell_values = [item.value for item in node.keywords if item.arg == "shell"]
            if not shell_values or not isinstance(shell_values[0], ast.Constant) or shell_values[0].value is not False:
                findings.append(f"SUBPROCESS_SHELL_NOT_DISABLED:{path}:{node.lineno}")
            if not node.args or not isinstance(node.args[0], (ast.List, ast.Tuple, ast.Name)):
                findings.append(f"SUBPROCESS_ARGUMENTS_NOT_LITERAL_SEQUENCE:{path}:{node.lineno}")
    return findings


def audit_dashboard(path: Path) -> list[str]:
    content = path.read_text(encoding="utf-8")
    if UNSAFE_JS_SINKS.search(content):
        return [f"UNSAFE_DASHBOARD_SINK:{path}"]
    return []


def run_audit(root: Path) -> dict:
    findings: list[str] = []
    python_files = sorted((root / "engine").rglob("*.py")) + sorted((root / "scripts").glob("*.py"))
    for path in python_files:
        findings.extend(audit_python(path))
    for path in sorted((root / "dashboard").rglob("*.js")):
        findings.extend(audit_dashboard(path))
    return {
        "status": "passed" if not findings else "failed",
        "python_files_checked": len(python_files),
        "javascript_files_checked": len(list((root / "dashboard").rglob("*.js"))),
        "findings": findings,
        "scope_note": "Static checks only. This is not a penetration test.",
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    report = run_audit(root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    sys.exit(main())
