"""Classify egress IP stability from independent, consensus-backed runs."""

from __future__ import annotations

import ipaddress
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from engine.models import parse_time


def _has_valid_quorum(item: dict, family: str, minimum: int) -> bool:
    if item.get("ip_family") != family or item.get("consensus") is not True:
        return False
    if not item.get("ip") or not item.get("run_id"):
        return False
    try:
        address = ipaddress.ip_address(str(item["ip"]))
    except ValueError:
        return False
    if (family == "ipv4" and address.version != 4) or (family == "ipv6" and address.version != 6):
        return False
    observers = item.get("observers", [])
    if not isinstance(observers, list):
        return False
    successful_ids = set()
    observed_ips = set()
    for observer in observers:
        if not isinstance(observer, dict) or observer.get("success") is not True:
            continue
        if observer.get("ip_family") != family:
            continue
        if observer.get("ip"):
            observed_ips.add(str(observer["ip"]))
        observer_id = observer.get("observer_id")
        if observer_id:
            successful_ids.add(str(observer_id))
    return len(successful_ids) >= minimum and observed_ips == {str(address)}


def _valid_evidence(items: list[dict], family: str, minimum: int) -> list[dict]:
    """Return consensus-backed observations with a valid timestamp and observer quorum."""
    valid: list[dict] = []
    for item in items:
        if not _has_valid_quorum(item, family, minimum):
            continue
        observed_at = parse_time(item.get("observed_at"))
        if observed_at is None:
            continue
        valid.append(item)
    return valid


def _unverified(reason: str, evidence: list[dict] | None = None) -> dict[str, Any]:
    evidence = evidence or []
    latest = max(
        evidence,
        key=lambda item: parse_time(item.get("observed_at")) or datetime.min.replace(tzinfo=UTC),
        default=None,
    )
    return {
        "status": "IP_UNVERIFIED",
        "ip": None,
        "run_count": len({str(item.get("run_id")) for item in evidence}),
        "observer_count": len(
            {
                observer.get("observer_id")
                for item in evidence
                for observer in item.get("observers", [])
                if observer.get("success") and observer.get("observer_id")
            }
        ),
        "first_observed_at": min(
            (item["observed_at"] for item in evidence), default=None
        ),
        "last_observed_at": latest.get("observed_at") if latest else None,
        "distinct_ips": sorted({str(item["ip"]) for item in evidence if item.get("ip")}),
        "reason_codes": [reason],
    }


def _classify_family(
    items: list[dict], family: str, policy: dict[str, Any], now: datetime
) -> dict[str, Any]:
    family_items = [
        item for item in items
        if item.get("ip_family") == family and parse_time(item.get("observed_at")) is not None
    ]
    if not family_items:
        return _unverified("INSUFFICIENT_RUNS")

    latest_event = max(family_items, key=lambda item: parse_time(item["observed_at"]) or now)
    minimum_observers = int(policy.get("min_successful_observers", 2))
    evidence = _valid_evidence(family_items, family, minimum_observers)

    # A newer failed or conflicting observation must not inherit an older fixed claim.
    if not _has_valid_quorum(latest_event, family, minimum_observers):
        reason = (
            "OBSERVER_DISAGREEMENT"
            if latest_event.get("result_code") == "OBSERVER_DISAGREEMENT"
            else "INSUFFICIENT_OBSERVERS"
        )
        return _unverified(reason, evidence)

    by_run: dict[str, list[dict]] = defaultdict(list)
    for item in evidence:
        by_run[str(item["run_id"])].append(item)

    run_evidence: list[dict] = []
    conflicting_runs: list[dict] = []
    for run_id, run_items in by_run.items():
        ips = {str(item["ip"]) for item in run_items}
        newest = max(run_items, key=lambda item: parse_time(item["observed_at"]) or now)
        if len(ips) != 1:
            conflicting_runs.append(newest)
        else:
            run_evidence.append(newest)

    if conflicting_runs:
        latest_conflict = max(
            conflicting_runs, key=lambda item: parse_time(item["observed_at"]) or now
        )
        conflict_time = parse_time(latest_conflict["observed_at"])
        if conflict_time is None:
            return _unverified("OBSERVER_DISAGREEMENT", evidence)
        # A conflicting Run breaks the evidence streak. Only later independent Runs
        # can establish a new Candidate or Verified result.
        run_evidence = [
            item
            for item in run_evidence
            if (parse_time(item["observed_at"]) or datetime.min.replace(tzinfo=UTC)) > conflict_time
        ]
        if not run_evidence:
            return _unverified("OBSERVER_DISAGREEMENT", evidence)

    run_evidence.sort(key=lambda item: parse_time(item["observed_at"]) or now)
    max_age = float(policy["fixed_evidence_max_age_hours"])
    fresh_runs = [
        item for item in run_evidence
        if (now - (parse_time(item["observed_at"]) or now)).total_seconds() / 3600 <= max_age
    ]
    if not fresh_runs:
        return _unverified("EVIDENCE_EXPIRED", run_evidence)

    last_time = parse_time(fresh_runs[-1]["observed_at"])
    first_time = parse_time(fresh_runs[0]["observed_at"])
    assert first_time is not None and last_time is not None
    age_hours = max(0.0, (now - last_time).total_seconds() / 3600)

    # Only the continuous run sequence after the last IP change can verify a return to Fixed.
    last_change_index = 0
    for index in range(1, len(fresh_runs)):
        if fresh_runs[index - 1]["ip"] != fresh_runs[index]["ip"]:
            last_change_index = index
    current_streak = fresh_runs[last_change_index:]
    streak_first = parse_time(current_streak[0]["observed_at"])
    streak_last = parse_time(current_streak[-1]["observed_at"])
    assert streak_first is not None and streak_last is not None
    streak_span_hours = (streak_last - streak_first).total_seconds() / 3600

    distinct_ips = sorted({str(item["ip"]) for item in fresh_runs})
    streak_run_count = len(current_streak)
    change_events = [
        fresh_runs[index]["observed_at"]
        for index in range(1, len(fresh_runs))
        if fresh_runs[index - 1]["ip"] != fresh_runs[index]["ip"]
    ]

    if streak_run_count >= int(policy["fixed_verified"]["min_runs"]) and streak_span_hours >= float(
        policy["fixed_verified"]["min_span_hours"]
    ):
        status, reasons = "FIXED_VERIFIED", ["IP_CONSISTENT_THRESHOLD_MET"]
    elif streak_run_count >= int(policy["fixed_candidate"]["min_runs"]) and streak_span_hours >= float(
        policy["fixed_candidate"]["min_span_hours"]
    ):
        status, reasons = "FIXED_CANDIDATE", ["IP_CONSISTENT_THRESHOLD_MET"]
    elif len(distinct_ips) >= int(policy["rotating"]["min_distinct_ips"]) and len(fresh_runs) >= int(
        policy["rotating"]["min_runs"]
    ):
        status, reasons = "ROTATING", ["IP_CHANGED_ACROSS_RUNS"]
    else:
        status, reasons = "IP_UNVERIFIED", []
        if streak_run_count < int(policy["fixed_candidate"]["min_runs"]):
            reasons.append("INSUFFICIENT_RUNS")
        if streak_span_hours < float(policy["fixed_candidate"]["min_span_hours"]):
            reasons.append("INSUFFICIENT_TIME_SPAN")

    reported_runs = fresh_runs if status == "ROTATING" else current_streak
    reported_distinct_ips = sorted({str(item["ip"]) for item in reported_runs})
    observer_ids = {
        observer.get("observer_id")
        for item in reported_runs
        for observer in item.get("observers", [])
        if observer.get("success") and observer.get("observer_id")
    }
    reported_first = parse_time(reported_runs[0]["observed_at"])
    reported_last = parse_time(reported_runs[-1]["observed_at"])
    assert reported_first is not None and reported_last is not None

    return {
        "status": status,
        "ip": current_streak[-1]["ip"] if status in {"FIXED_CANDIDATE", "FIXED_VERIFIED"} else None,
        "run_count": len(reported_runs),
        "observer_count": len(observer_ids),
        "first_observed_at": reported_runs[0]["observed_at"],
        "last_observed_at": reported_runs[-1]["observed_at"],
        "span_hours": round((reported_last - reported_first).total_seconds() / 3600, 3),
        "age_hours": round(age_hours, 3),
        "distinct_ips": reported_distinct_ips,
        "change_count": len(change_events),
        "last_ip_change_at": change_events[-1] if change_events else None,
        "reason_codes": reasons,
    }


def classify_config(
    config_record: dict[str, Any],
    observations: list[dict],
    policy: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = now or datetime.now(UTC)
    by_family = {
        family: _classify_family(observations, family, policy, current_time)
        for family in ("ipv4", "ipv6")
    }
    required = policy.get("required_ip_families", ["ipv4"])
    required_statuses = [by_family[family]["status"] for family in required]
    if required_statuses and all(status == "FIXED_VERIFIED" for status in required_statuses):
        overall = "FIXED_VERIFIED"
    elif "ROTATING" in required_statuses:
        overall = "ROTATING"
    elif "FIXED_CANDIDATE" in required_statuses:
        overall = "FIXED_CANDIDATE"
    elif "IP_UNVERIFIED" in required_statuses:
        overall = "IP_UNVERIFIED"
    else:
        overall = "UNSTABLE"

    validation_status = config_record.get("validation", {}).get("status")
    if validation_status not in {"VALID", "TCP_UNREACHABLE", "TCP_TIMEOUT"}:
        overall = "QUARANTINED" if validation_status == "BLOCKED_SECURITY_POLICY" else "INVALID"
    elif config_record.get("last_connectivity") == "failed":
        overall = "UNSTABLE"

    reasons = sorted(
        {
            reason
            for family in required
            for reason in by_family[family].get("reason_codes", [])
        }
    )
    if config_record.get("last_connectivity") == "failed":
        reasons = sorted(set(reasons) | {"CONNECTION_FAILED"})

    return {
        "overall": overall,
        "ipv4": by_family["ipv4"],
        "ipv6": by_family["ipv6"],
        "classification_reason_codes": reasons,
        "classified_at": current_time.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
