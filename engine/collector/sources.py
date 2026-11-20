"""Source registry and bounded collection orchestration."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from engine.collector.deduplicator import deduplicate
from engine.collector.fetcher import FetchError, fetch_source
from engine.collector.parser import ParseError, parse_payload
from engine.models import ParsedConfig, iso_utc


def load_sources(path: str | Path) -> list[dict[str, Any]]:
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ValueError("Source registry YAML is invalid.") from exc
    if not isinstance(raw, dict):
        raise ValueError("Source registry root must be an object.")
    sources = raw.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("Source registry must contain a list.")
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "source.schema.json"
    schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    for index, source in enumerate(sources):
        errors = sorted(validator.iter_errors(source), key=lambda item: list(item.path))
        if errors:
            raise ValueError(f"Source registry item {index} is invalid: {errors[0].message}")
    source_ids = [source["source_id"] for source in sources]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Source IDs must be unique.")
    return sources


def _collect_one(source: dict, collector_settings: dict) -> tuple[dict, list[ParsedConfig], dict]:
    report = {
        "source_id": source["source_id"],
        "status": "failed",
        "started_at": iso_utc(),
        "error_code": None,
        "http": None,
    }
    try:
        if not source.get("public_redistribution", False):
            raise FetchError("SOURCE_NOT_APPROVED_FOR_PUBLIC_REDISTRIBUTION")
        payload, metadata = fetch_source(source, collector_settings)
        configs, counts = parse_payload(payload, str(source.get("format", "auto")))
        report.update({"status": "success", "http": metadata, "counts": counts})
        return report, configs, counts
    except (FetchError, ParseError, OSError, ValueError) as exc:
        report["error_code"] = str(exc)[:80]
        return report, [], {"input_lines": 0, "parsed": 0, "duplicates": 0, "rejected": 1}
    except Exception:
        # Do not expose exception text. It can contain a URL or source-controlled data.
        report["error_code"] = "SOURCE_PROCESS_ERROR"
        return report, [], {"input_lines": 0, "parsed": 0, "duplicates": 0, "rejected": 1}
    finally:
        report["finished_at"] = iso_utc()


def collect_sources(sources: list[dict], collector_settings: dict) -> tuple[list[ParsedConfig], dict]:
    """Collect sources in parallel. Keep reports and output order deterministic."""
    discovered: dict[str, ParsedConfig] = {}
    report: dict[str, Any] = {
        "started_at": iso_utc(datetime.now(UTC)),
        "sources_total": len([source for source in sources if source.get("enabled")]),
        "sources_succeeded": 0,
        "sources_failed": 0,
        "sources": [],
        "counts": {"input_lines": 0, "parsed": 0, "duplicates": 0, "rejected": 0},
        "config_source_ids": {},
    }
    ordered = sorted(sources, key=lambda source: (int(source.get("priority", 100)), source["source_id"]))
    enabled = [source for source in ordered if source.get("enabled")]
    workers = max(1, min(int(collector_settings.get("max_concurrency", 1)), 16, len(enabled) or 1))

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="source-fetch") as pool:
        futures = [pool.submit(_collect_one, source, collector_settings) for source in enabled]
        results = [future.result() for future in futures]

    for item_report, configs, counts in results:
        report["sources"].append(item_report)
        if item_report["status"] == "success":
            report["sources_succeeded"] += 1
        else:
            report["sources_failed"] += 1
        for key in report["counts"]:
            report["counts"][key] += int(counts.get(key, 0))
        for config in configs:
            if config.config_id in discovered:
                report["counts"]["duplicates"] += 1
            else:
                discovered[config.config_id] = config
            report["config_source_ids"].setdefault(config.config_id, []).append(item_report["source_id"])

    deduplicated, duplicate_count = deduplicate(list(discovered.values()))
    report["counts"]["duplicates"] += duplicate_count
    report["unique_configs"] = len(deduplicated)
    report["finished_at"] = iso_utc()
    return deduplicated, report
