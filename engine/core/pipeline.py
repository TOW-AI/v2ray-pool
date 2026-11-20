"""Run the full collection-to-publication data pipeline."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from engine.collector.parser import ParseError, parse_uri
from engine.collector.sources import collect_sources, load_sources
from engine.core.config import load_settings
from engine.core.history import append_run_history, load_history
from engine.core.state import StateStore
from engine.distribution.api import build_api
from engine.distribution.quality import validate_data_tree
from engine.distribution.subscriptions import write_subscriptions
from engine.core.scheduler import select_configs
from engine.intelligence.classification import classify_config
from engine.intelligence.geoip import lookup_country
from engine.intelligence.ip_tracker import append_observations
from engine.intelligence.ranking import build_rankings
from engine.intelligence.stability import apply_classification
from engine.models import iso_utc
from engine.tester.runner import XrayTestError, run_xray_test, verify_xray_binary
from engine.validator.syntax import validate_full, validate_syntax


class PipelineError(RuntimeError):
    """Raised when a pipeline stage cannot complete safely."""


def _load_or_create_record(config, source_ids: list[str], public: bool) -> dict[str, Any]:
    stamp = iso_utc()
    return {
        "config_id": config.config_id,
        "protocol": config.protocol,
        "uri": config.uri,
        "name": config.name,
        "canonicalizer_version": config.canonicalizer_version,
        "source_ids": source_ids,
        "public_redistribution": public,
        "status": "DISCOVERED",
        "validation": {"status": "DISCOVERED", "reason_code": None},
        "first_seen_at": stamp,
        "last_seen_at": stamp,
        "last_test_at": None,
        "last_connectivity": None,
        "eligible_scheduled_checks": 0,
        "successful_scheduled_checks": 0,
        "connection_success_ratio": None,
        "metrics": {
            "latency_ms": None,
            "throughput_bps": None,
            "measured_at": None,
            "measurement_method": None,
        },
        "ip_status": {},
        "classification_reason_codes": [],
    }


def _update_run_metrics(record: dict, result: dict, scheduled: bool) -> None:
    record["last_test_at"] = result["finished_at"]
    record["last_connectivity"] = result["connectivity"]
    record["last_test_id"] = result["test_id"]
    record["connection_success_ratio"] = None
    if scheduled:
        record["eligible_scheduled_checks"] = int(record.get("eligible_scheduled_checks", 0)) + 1
        if result["connectivity"] == "connected":
            record["successful_scheduled_checks"] = int(record.get("successful_scheduled_checks", 0)) + 1
    eligible = int(record.get("eligible_scheduled_checks", 0))
    if eligible:
        record["connection_success_ratio"] = int(record.get("successful_scheduled_checks", 0)) / eligible
    record["metrics"] = result.get("metrics", record.get("metrics", {}))
    record.pop("last_test_error", None)


def run_pipeline(
    settings_path: str | Path,
    sources_path: str | Path,
    data_root: str | Path,
    output_root: str | Path,
    *,
    offline: bool = False,
    scheduled: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    """Build one complete, validated data snapshot."""
    settings = load_settings(settings_path)
    if limit is not None and limit < 1:
        raise PipelineError("The config limit must be greater than zero.")
    sources = load_sources(sources_path)
    if any(item.get("enabled") and not item.get("public_redistribution", False) for item in sources):
        raise PipelineError("A source is enabled without public redistribution approval.")

    run_id = str(uuid.uuid4())
    started = datetime.now(UTC)
    source_root = Path(data_root).resolve()
    output = Path(output_root).resolve()
    if output == source_root:
        raise PipelineError("The output directory must not replace the source data directory.")

    state = StateStore(source_root).load()
    unsafe_state_records = [
        config_id for config_id, record in state["configs"].items()
        if record.get("public_redistribution") is not True and record.get("uri")
    ]
    if unsafe_state_records:
        raise PipelineError(
            "NON_PUBLIC_CONFIG_IN_PUBLIC_STATE: remove or migrate private records before this branch can be published."
        )
    existing_history = load_history(source_root)
    collector_report: dict[str, Any]
    if offline:
        discovered, collector_report = [], {
            "sources_total": 0, "sources_succeeded": 0, "sources_failed": 0,
            "sources": [], "counts": {"input_lines": 0, "parsed": 0, "duplicates": 0, "rejected": 0},
            "unique_configs": 0, "offline": True,
        }
    else:
        discovered, collector_report = collect_sources(sources, settings["collector"])

    source_map = collector_report.get("config_source_ids", {})
    source_map_public = {
        source["source_id"]: bool(source.get("public_redistribution", False))
        for source in sources if source.get("enabled")
    }
    for config in discovered:
        config_sources = list(source_map.get(config.config_id, []))
        public = any(source_map_public.get(source_id, False) for source_id in config_sources)
        record = state["configs"].get(config.config_id)
        if record is None:
            record = _load_or_create_record(config, config_sources, public)
            state["configs"][config.config_id] = record
        else:
            record["uri"] = config.uri
            record["last_seen_at"] = iso_utc()
            record["source_ids"] = sorted(set(record.get("source_ids", [])) | set(config_sources))
            record["public_redistribution"] = bool(record.get("public_redistribution")) or public

    parsed_records = []
    parse_errors = 0
    for record in state["configs"].values():
        try:
            parsed_records.append(parse_uri(record["uri"]))
        except (ParseError, ValueError, UnicodeError, KeyError, TypeError):
            record["status"] = "INVALID"
            record["validation"] = {"status": "INVALID_SYNTAX", "reason_code": "STORED_URI_INVALID"}
            parse_errors += 1

    validation_report = Counter()
    candidates = select_configs(
        parsed_records,
        int(settings["tester"].get("max_configs_per_run", 100)),
        limit,
    )

    if settings["tester"].get("enabled") and not offline:
        try:
            verify_xray_binary(settings["tester"])
        except XrayTestError as exc:
            raise PipelineError(str(exc)) from exc

    for parsed in candidates:
        if offline:
            result = validate_syntax(parsed)
        else:
            result = validate_full(parsed, settings["validator"], tcp_probe=True)
        record = state["configs"][parsed.config_id]
        record["validation"] = result.to_dict()
        validation_report[result.status] += 1
        if result.status == "VALID":
            record["status"] = "VALIDATED" if not record.get("last_test_at") else record.get("status", "VALIDATED")
        elif result.status.startswith("BLOCKED"):
            record["status"] = "QUARANTINED"
        elif result.status == "INVALID_SYNTAX":
            record["status"] = "INVALID"
        elif result.status in {"TCP_UNREACHABLE", "TCP_TIMEOUT", "DNS_FAILURE"}:
            record["status"] = "UNSTABLE"

    test_report = {"successful": 0, "failed": 0, "skipped": 0}
    if settings["tester"].get("enabled") and not offline:
        valid_candidates = []
        for parsed in candidates:
            record = state["configs"][parsed.config_id]
            if record.get("validation", {}).get("status") == "VALID":
                valid_candidates.append(parsed)
            else:
                test_report["skipped"] += 1

        if valid_candidates:
            workers = max(
                1,
                min(
                    int(settings["tester"].get("max_parallel_configs", 1)),
                    len(valid_candidates),
                ),
            )
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="xray-test") as executor:
                futures = {
                    executor.submit(
                        run_xray_test,
                        parsed,
                        state["configs"][parsed.config_id]["validation"],
                        settings["tester"],
                        run_id,
                    ): parsed
                    for parsed in valid_candidates
                }
                for future in as_completed(futures):
                    parsed = futures[future]
                    record = state["configs"][parsed.config_id]
                    try:
                        result = future.result()
                        append_observations(state["observations"], result)
                        _update_run_metrics(record, result, scheduled)
                        if result["connectivity"] == "connected":
                            record["status"] = "TESTED"
                            test_report["successful"] += 1
                        else:
                            test_report["failed"] += 1
                    except XrayTestError as exc:
                        record["last_test_at"] = iso_utc()
                        record["last_connectivity"] = "failed"
                        record["last_test_error"] = str(exc)
                        if scheduled:
                            record["eligible_scheduled_checks"] = int(
                                record.get("eligible_scheduled_checks", 0)
                            ) + 1
                        eligible = int(record.get("eligible_scheduled_checks", 0))
                        successful = int(record.get("successful_scheduled_checks", 0))
                        record["connection_success_ratio"] = successful / eligible if eligible else None
                        test_report["failed"] += 1
    else:
        test_report["skipped"] = len(candidates)

    # Update country information only when a verified egress address exists.
    observations_by_config: dict[str, list[dict]] = defaultdict(list)
    for observation in state["observations"]:
        observations_by_config[observation.get("config_id", "")].append(observation)

    transitions = []
    for config_id, record in state["configs"].items():
        classification_policy = {
            **settings["intelligence"],
            "min_successful_observers": settings["tester"]["min_successful_observers"],
        }
        classification = classify_config(
            record,
            observations_by_config.get(config_id, []),
            classification_policy,
        )
        event = apply_classification(record, classification)
        if event:
            transitions.append(event)
        ip_status = record.get("ip_status", {})
        egress_ip = None
        if ip_status.get("ipv4", {}).get("status") in {"FIXED_CANDIDATE", "FIXED_VERIFIED"}:
            egress_ip = ip_status["ipv4"].get("ip")
        elif ip_status.get("ipv6", {}).get("status") in {"FIXED_CANDIDATE", "FIXED_VERIFIED"}:
            egress_ip = ip_status["ipv6"].get("ip")
        if egress_ip:
            record.update(lookup_country(egress_ip))
        else:
            record.update({"country_code": None, "country_name": None, "geoip_checked_at": None})

    state["transitions"].extend(transitions)
    for config_id, record in state["configs"].items():
        state["metrics"][config_id] = record.get("metrics", {})

    rankings = build_rankings(state["configs"], settings["ranking"])
    for group in ("fixed", "rotating", "balanced"):
        for item in rankings[group]:
            record = state["configs"].get(item["config_id"])
            if record is not None:
                record.setdefault("scores", {})[group] = item["score"]
                record["score_coverage"] = item["score_coverage"]
    for item in rankings["fastest"]:
        record = state["configs"].get(item["config_id"])
        if record is not None:
            record.setdefault("scores", {})["fastest_latency_ms"] = item["latency_ms"]

    statuses = Counter(record.get("status", "DISCOVERED") for record in state["configs"].values())
    finished = datetime.now(UTC)
    run_summary = {
        "run_id": run_id,
        "started_at": iso_utc(started),
        "finished_at": iso_utc(finished),
        "duration_seconds": round((finished - started).total_seconds(), 3),
        "collector": collector_report.get("counts", {}),
        "validation": dict(validation_report),
        "tests": test_report,
        "statuses": dict(statuses),
        "config_count": len(state["configs"]),
        "observation_count": len(state["observations"]),
        "scheduled": scheduled,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    temp_output = Path(tempfile.mkdtemp(prefix="v2ray-data-build-", dir=output.parent))
    try:
        StateStore.save(state, temp_output)
        history_existing = existing_history
        append_run_history(
            temp_output, history_existing, run_summary, finished, settings.get("history", {})
        )
        api_counts = build_api(
            temp_output,
            state["configs"],
            state["observations"],
            rankings,
            run_id,
            bool(settings["api"]["publish_raw_uri"]),
            source_commit=os.environ.get("GITHUB_SHA"),
            data_commit=os.environ.get("DATA_COMMIT"),
            generated_at=iso_utc(finished),
            test_summary=test_report,
        )
        sub_counts = write_subscriptions(temp_output, state["configs"], rankings, settings["subscription"])
        (temp_output / "README.md").write_text(
            "# Public data branch\n\n"
            "This branch contains generated public subscriptions, static API files, state, and history.\n\n"
            "All files in this branch are public. Do not place private configurations or secrets here.\n\n"
            f"Last generated run: `{run_id}` at `{iso_utc(finished)}`.\n",
            encoding="utf-8",
        )
        quality_report = validate_data_tree(temp_output, settings, state["configs"])
        if output.exists():
            shutil.rmtree(output)
        temp_output.replace(output)
    except Exception:
        shutil.rmtree(temp_output, ignore_errors=True)
        raise

    report = {
        "run_id": run_id,
        "started_at": iso_utc(started),
        "finished_at": iso_utc(finished),
        "collector": collector_report,
        "validation": dict(validation_report),
        "tests": test_report,
        "stored_uri_parse_errors": parse_errors,
        "config_count": len(state["configs"]),
        "observation_count": len(state["observations"]),
        "api_counts": api_counts,
        "subscription_counts": sub_counts,
        "quality": quality_report,
        "output_dir": str(output),
        "production_ready": bool(
            not offline
            and settings["tester"].get("enabled")
            and test_report.get("successful", 0) > 0
            and quality_report.get("quality_gate") == "passed"
        ),
    }
    report_dir = output.parent / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "last-run.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report
