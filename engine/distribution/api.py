"""Build the static JSON API from one state snapshot."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from engine.core.state import SCHEMA_VERSION, atomic_write_json
from engine.models import iso_utc


def _base(run_id: str, source_commit: str | None, data_commit: str | None, generated_at: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "run_id": run_id,
        "source_commit": source_commit,
        "data_commit": data_commit,
        "data_age_seconds": 0,
    }


def _public_config(record: dict, publish_uri: bool) -> dict:
    ip_status = record.get("ip_status", {})
    ipv4 = ip_status.get("ipv4", {})
    ipv6 = ip_status.get("ipv6", {})
    egress_ip = None
    ip_family = None
    if ipv4.get("status") in {"FIXED_CANDIDATE", "FIXED_VERIFIED"}:
        egress_ip, ip_family = ipv4.get("ip"), "ipv4"
    elif ipv6.get("status") in {"FIXED_CANDIDATE", "FIXED_VERIFIED"}:
        egress_ip, ip_family = ipv6.get("ip"), "ipv6"
    item = {
        "config_id": record["config_id"],
        "protocol": record.get("protocol"),
        "status": record.get("status"),
        "verification_level": record.get("status"),
        "ip_status": {
            "ipv4": ipv4.get("status", "IP_UNVERIFIED"),
            "ipv6": ipv6.get("status", "IP_UNVERIFIED"),
            "overall": ip_status.get("overall", "IP_UNVERIFIED"),
        },
        "ip_evidence": {
            "ipv4": {key: ipv4.get(key) for key in ("run_count", "observer_count", "first_observed_at", "last_observed_at", "span_hours", "distinct_ips", "change_count", "last_ip_change_at")},
            "ipv6": {key: ipv6.get(key) for key in ("run_count", "observer_count", "first_observed_at", "last_observed_at", "span_hours", "distinct_ips", "change_count", "last_ip_change_at")},
        },
        "egress_ip": egress_ip,
        "ip_family": ip_family,
        "country_code": record.get("country_code"),
        "country_name": record.get("country_name"),
        "last_test_at": record.get("last_test_at"),
        "metrics": {
            "latency_ms": record.get("metrics", {}).get("latency_ms"),
            "throughput_bps": record.get("metrics", {}).get("throughput_bps"),
            "unit_latency": "ms",
            "unit_throughput": "bit/s",
            "measured_at": record.get("metrics", {}).get("measured_at"),
            "measurement_method": record.get("metrics", {}).get("measurement_method"),
        },
        "scores": record.get("scores", {}),
        "score_coverage": record.get("score_coverage"),
        "classification_reason_codes": record.get("classification_reason_codes", []),
    }
    if publish_uri and record.get("public_redistribution") is True:
        item["uri"] = record.get("uri")
    return item


def build_api(
    root: Path,
    configs: dict[str, dict],
    observations: list[dict],
    rankings: dict[str, list[dict]],
    run_id: str,
    publish_raw_uri: bool,
    source_commit: str | None = None,
    data_commit: str | None = None,
    generated_at: str | None = None,
    test_summary: dict | None = None,
) -> dict[str, int]:
    api_root = root / "api" / "v1"
    api_root.mkdir(parents=True, exist_ok=True)
    stamp = generated_at or iso_utc()
    base = _base(run_id, source_commit, data_commit, stamp)
    publishable_statuses = {"FIXED_CANDIDATE", "FIXED_VERIFIED", "ROTATING"}
    public_records = [
        _public_config(record, publish_raw_uri)
        for record in configs.values()
        if record.get("public_redistribution") is True and record.get("status") in publishable_statuses
    ]
    public_records.sort(key=lambda item: item["config_id"])
    statuses = Counter(record.get("status", "DISCOVERED") for record in configs.values())
    protocols = Counter(record.get("protocol", "unknown") for record in configs.values())
    countries = Counter(record.get("country_code") or "XX" for record in public_records)
    statuses_out = {status: int(statuses.get(status, 0)) for status in sorted({
        "DISCOVERED", "VALIDATED", "TESTED", "FIXED_CANDIDATE", "FIXED_VERIFIED", "ROTATING",
        "UNSTABLE", "IP_UNVERIFIED", "QUARANTINED", "EXPIRED", "INVALID"
    })}
    stats = {
        **base,
        "totals": {
            "discovered": len(configs),
            "validated": sum(record.get("validation", {}).get("status") == "VALID" for record in configs.values()),
            "tested": sum(bool(record.get("last_test_at")) for record in configs.values()),
            "publishable": len(public_records),
        },
        "statuses": statuses_out,
        "protocols": dict(sorted(protocols.items())),
        "countries": dict(sorted(countries.items())),
        "tests": test_summary or {"successful": 0, "failed": 0, "skipped": 0},
        "freshness": {
            "last_successful_run_at": (
                stamp if public_records and (test_summary or {}).get("successful", 0) > 0 else None
            ),
            "oldest_published_measurement_at": min(
                (record.get("last_test_at") for record in public_records if record.get("last_test_at")),
                default=None,
            ),
        },
    }
    fixed = [record for record in public_records if record.get("status") in {"FIXED_CANDIDATE", "FIXED_VERIFIED"}]
    rotating = [record for record in public_records if record.get("status") == "ROTATING"]
    ip_sets: dict[str, set[str]] = {}
    for record in configs.values():
        if record.get("status") == "ROTATING":
            for family in ("ipv4", "ipv6"):
                ip_sets.setdefault(record["config_id"] + ":" + family, set()).update(
                    record.get("ip_status", {}).get(family, {}).get("distinct_ips", [])
                )
    countries_payload: dict[str, Any] = {
        **base,
        "countries": [
            {
                "country_code": code,
                "config_count": int(count),
                "fixed_verified": sum(
                    item.get("country_code") == code and item.get("status") == "FIXED_VERIFIED"
                    for item in public_records
                ),
                "rotating": sum(
                    item.get("country_code") == code and item.get("status") == "ROTATING"
                    for item in public_records
                ),
                "last_geoip_update": max(
                    (item.get("geoip_checked_at") for item in configs.values() if item.get("country_code") == code and item.get("geoip_checked_at")),
                    default=None,
                ),
            }
            for code, count in sorted(countries.items()) if code != "XX"
        ],
        "unknown_count": int(countries.get("XX", 0)),
    }
    ranking_payload = {
        **base,
        "ranking_policy_version": "1.0.0",
        "fixed": rankings.get("fixed", []),
        "rotating": rankings.get("rotating", []),
        "fastest": rankings.get("fastest", []),
        "balanced": rankings.get("balanced", []),
    }
    outputs = {
        "stats.json": stats,
        "configs.json": {**base, "configs": public_records},
        "fixed.json": {**base, "configs": fixed},
        "rotating.json": {
            **base,
            "configs": rotating,
            "distinct_ip_count": sum(len(values) for values in ip_sets.values()),
            "ip_changes": [
                {
                    "config_id": item["config_id"],
                    "ipv4": item.get("ip_evidence", {}).get("ipv4"),
                    "ipv6": item.get("ip_evidence", {}).get("ipv6"),
                }
                for item in rotating
            ],
        },
        "countries.json": countries_payload,
        "rankings.json": ranking_payload,
    }
    for name, payload in outputs.items():
        atomic_write_json(api_root / name, payload)
    return {"configs": len(public_records), "fixed": len(fixed), "rotating": len(rotating)}
