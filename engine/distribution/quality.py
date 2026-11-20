"""Validate the generated data tree before publish."""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from engine.collector.parser import parse_uri

SECRET_PATTERNS = [
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{20,}"),
]


class QualityGateError(RuntimeError):
    """Raised when generated data fails an acceptance check."""


def validate_data_tree(root: Path, settings: dict[str, Any], config_records: dict[str, dict]) -> dict:
    api_root = root / "api" / "v1"
    required_api = ["stats.json", "configs.json", "fixed.json", "rotating.json", "countries.json", "rankings.json"]
    api_payloads: dict[str, dict] = {}
    schema_root = Path(__file__).resolve().parents[2] / "schemas"
    api_schema = json.loads((schema_root / "api-v1.schema.json").read_text(encoding="utf-8"))
    api_schema_defs = api_schema.get("$defs", {})
    api_contracts = {
        "stats.json": "stats",
        "configs.json": "config_list",
        "fixed.json": "config_list",
        "rotating.json": "rotating",
        "countries.json": "countries",
        "rankings.json": "rankings",
    }
    for name in required_api:
        path = api_root / name
        if not path.is_file():
            raise QualityGateError(f"API_FILE_MISSING:{name}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise QualityGateError(f"API_JSON_INVALID:{name}") from exc
        if not isinstance(payload, dict) or payload.get("schema_version") != "1.0.0":
            raise QualityGateError(f"API_SCHEMA_VERSION_INVALID:{name}")
        for field in ("generated_at", "run_id", "source_commit", "data_commit", "data_age_seconds"):
            if field not in payload:
                raise QualityGateError(f"API_BASE_FIELD_MISSING:{name}:{field}")
        contract_name = api_contracts[name]
        contract = {
            "$schema": api_schema["$schema"],
            "$defs": api_schema_defs,
            "$ref": f"#/$defs/{contract_name}",
        }
        errors = sorted(
            Draft202012Validator(contract, format_checker=FormatChecker()).iter_errors(payload),
            key=lambda item: list(item.path),
        )
        if errors:
            location = ".".join(str(part) for part in errors[0].absolute_path) or "root"
            raise QualityGateError(f"API_SCHEMA_INVALID:{name}:{location}")
        api_payloads[name] = payload

    state_schema = json.loads((schema_root / "state.schema.json").read_text(encoding="utf-8"))
    for name in ("configs.json", "ip-history.json", "metrics.json"):
        state_path = root / "state" / name
        if not state_path.is_file():
            raise QualityGateError(f"STATE_FILE_MISSING:{name}")
        try:
            state_payload = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise QualityGateError(f"STATE_JSON_INVALID:{name}") from exc
        errors = sorted(
            Draft202012Validator(state_schema, format_checker=FormatChecker()).iter_errors(state_payload),
            key=lambda item: list(item.path),
        )
        if errors:
            raise QualityGateError(f"STATE_SCHEMA_INVALID:{name}")

    config_ids = [item.get("config_id") for item in api_payloads["configs.json"].get("configs", [])]
    if len(config_ids) != len(set(config_ids)):
        raise QualityGateError("API_DUPLICATE_CONFIG_ID")
    fixed_ids = {item.get("config_id") for item in api_payloads["fixed.json"].get("configs", [])}
    for config_id in fixed_ids:
        record = config_records.get(config_id, {})
        if record.get("status") not in {"FIXED_CANDIDATE", "FIXED_VERIFIED"}:
            raise QualityGateError("FIXED_API_STATUS_MISMATCH")

    encoding = settings["subscription"]["encoding"]
    sub_root = root / "sub"
    for path in sub_root.rglob("*.txt"):
        raw = path.read_bytes()
        if not raw:
            continue
        try:
            decoded = base64.b64decode(raw, validate=True).decode("utf-8") if encoding == "base64" else raw.decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise QualityGateError(f"SUBSCRIPTION_ENCODING_INVALID:{path.relative_to(root)}") from exc
        seen: set[str] = set()
        for line in decoded.splitlines():
            if not line.strip():
                continue
            try:
                parsed = parse_uri(line.strip())
            except ValueError as exc:
                raise QualityGateError(f"SUBSCRIPTION_URI_INVALID:{path.relative_to(root)}") from exc
            if parsed.config_id in seen:
                raise QualityGateError(f"SUBSCRIPTION_DUPLICATE:{path.relative_to(root)}")
            seen.add(parsed.config_id)
            if path.name == "fixed-verified.txt" and config_records.get(parsed.config_id, {}).get("status") != "FIXED_VERIFIED":
                raise QualityGateError("FIXED_VERIFIED_SUBSCRIPTION_CONTAINS_UNVERIFIED")

    scanned_files = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        scanned_files += 1
        if path.suffix.lower() in {".pem", ".key", ".p12", ".pfx", ".env"}:
            raise QualityGateError(f"SENSITIVE_FILE_IN_PUBLIC_DATA:{path.name}")
        if path.suffix.lower() in {".json", ".md", ".txt"}:
            content = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in SECRET_PATTERNS:
                if pattern.search(content):
                    raise QualityGateError(f"SECRET_PATTERN_FOUND:{path.name}")
    return {
        "api_files_validated": len(required_api),
        "subscription_files_validated": len(list(sub_root.rglob("*.txt"))),
        "scanned_files": scanned_files,
        "api_config_count": len(config_ids),
        "quality_gate": "passed",
    }
