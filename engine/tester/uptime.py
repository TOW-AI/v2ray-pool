"""Calculate uptime from eligible scheduled checks only."""


def uptime_ratio(record: dict) -> float | None:
    eligible = int(record.get("eligible_scheduled_checks", 0))
    successful = int(record.get("successful_scheduled_checks", 0))
    if eligible <= 0:
        return None
    return min(1.0, max(0.0, successful / eligible))
