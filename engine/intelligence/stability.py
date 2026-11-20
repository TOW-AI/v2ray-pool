"""Track status transitions and calculate run-level uptime estimates."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from engine.models import iso_utc


def apply_classification(record: dict[str, Any], classification: dict[str, Any]) -> dict[str, Any] | None:
    old_status = record.get("status", "DISCOVERED")
    new_status = classification["overall"]
    record["ip_status"] = classification
    record["status"] = new_status
    record["classification_reason_codes"] = classification["classification_reason_codes"]
    if old_status == new_status:
        return None
    return {
        "config_id": record["config_id"],
        "from_status": old_status,
        "to_status": new_status,
        "changed_at": iso_utc(datetime.now(UTC)),
        "reason_codes": classification["classification_reason_codes"],
    }


def uptime_ratio(record: dict[str, Any]) -> float | None:
    eligible = int(record.get("eligible_scheduled_checks", 0))
    successful = int(record.get("successful_scheduled_checks", 0))
    if eligible <= 0:
        return None
    return min(1.0, max(0.0, successful / eligible))
