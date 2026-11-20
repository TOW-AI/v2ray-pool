"""Deterministic score calculation with explicit metric coverage."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from engine.tester.uptime import uptime_ratio
from engine.models import parse_time


def _freshness_score(measured_at: str | None, maximum_age_hours: float, now: datetime) -> float | None:
    measured = parse_time(measured_at)
    if measured is None:
        return None
    age = max(0.0, (now - measured).total_seconds() / 3600)
    if age > maximum_age_hours:
        return None
    return max(0.0, 1.0 - age / maximum_age_hours)


def _latency_score(value: Any) -> float | None:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value < 0:
        return None
    return max(0.0, min(1.0, 1.0 - float(value) / 1000.0))


def _throughput_score(value: Any) -> float | None:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value <= 0:
        return None
    return min(1.0, math.log10(float(value) + 1) / 8.0)


def _fixed_stability(record: dict[str, Any]) -> float | None:
    status = record.get("ip_status", {}).get("overall")
    if status == "FIXED_VERIFIED":
        return 1.0
    if status == "FIXED_CANDIDATE":
        return 0.75
    return None


def score_record(
    record: dict[str, Any], weights: dict[str, float], policy: dict[str, Any], now: datetime
) -> dict[str, Any] | None:
    metrics = record.get("metrics", {})
    age_limit = float(policy["max_metric_age_hours"])
    components: dict[str, float | None] = {
        "ip_stability": _fixed_stability(record),
        "connection_success": (
            float(record["connection_success_ratio"])
            if isinstance(record.get("connection_success_ratio"), (int, float))
            and math.isfinite(float(record["connection_success_ratio"]))
            and 0 <= float(record["connection_success_ratio"]) <= 1
            else None
        ),
        "latency": _latency_score(metrics.get("latency_ms")),
        "throughput": _throughput_score(metrics.get("throughput_bps")),
        "uptime": uptime_ratio(record),
        "freshness": _freshness_score(metrics.get("measured_at"), age_limit, now),
    }
    available_weight = sum(weight for key, weight in weights.items() if components.get(key) is not None)
    if available_weight <= 0:
        return None
    raw_score = sum(
        weights[key] * float(components[key])
        for key in weights
        if components.get(key) is not None
    ) / available_weight
    coverage = available_weight / sum(weights.values())
    if coverage < float(policy["minimum_score_coverage"]):
        return None
    return {
        "config_id": record["config_id"],
        "score": round(raw_score * 100, 4),
        "score_components": {
            key: round(float(components[key]), 5)
            for key in weights
            if components.get(key) is not None
        },
        "score_coverage": round(coverage, 5),
        "measured_at": metrics.get("measured_at"),
    }


def build_rankings(configs: dict[str, dict], ranking_settings: dict) -> dict[str, list[dict]]:
    now = datetime.now(UTC)
    ranked: dict[str, list[dict]] = {"fixed": [], "rotating": [], "fastest": [], "balanced": []}
    publishable_statuses = {"FIXED_CANDIDATE", "FIXED_VERIFIED", "ROTATING"}
    for config_id, record in configs.items():
        if record.get("public_redistribution") is not True:
            continue
        if record.get("status") == "FIXED_VERIFIED":
            scored = score_record(record, ranking_settings["fixed_weights"], ranking_settings, now)
            if scored:
                ranked["fixed"].append(scored)
        if record.get("status") == "ROTATING":
            scored = score_record(record, ranking_settings["rotating_weights"], ranking_settings, now)
            if scored:
                ranked["rotating"].append(scored)
        metrics = record.get("metrics", {})
        latency = metrics.get("latency_ms")
        measured_at = parse_time(metrics.get("measured_at"))
        if (
            record.get("status") in publishable_statuses
            and isinstance(latency, (int, float))
            and math.isfinite(float(latency))
            and latency >= 0
            and measured_at is not None
            and (now - measured_at).total_seconds() <= float(ranking_settings["max_metric_age_hours"]) * 3600
        ):
            ranked["fastest"].append(
                {
                    "config_id": config_id,
                    "latency_ms": float(latency),
                    "unit": "ms",
                    "measured_at": metrics.get("measured_at"),
                }
            )
        balanced = None
        if record.get("status") in publishable_statuses:
            balanced = score_record(record, ranking_settings["balanced_weights"], ranking_settings, now)
        if balanced:
            ranked["balanced"].append(balanced)

    for name in ("fixed", "rotating", "balanced"):
        ranked[name].sort(key=lambda item: (-item["score"], item["config_id"]))
    ranked["fastest"].sort(key=lambda item: (item["latency_ms"], item["config_id"]))
    for items in ranked.values():
        for index, item in enumerate(items, start=1):
            item["rank"] = index
    return ranked
