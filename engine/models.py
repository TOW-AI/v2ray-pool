"""Shared data types and time helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

STATUSES = {
    "DISCOVERED",
    "VALIDATED",
    "TESTED",
    "FIXED_CANDIDATE",
    "FIXED_VERIFIED",
    "ROTATING",
    "UNSTABLE",
    "IP_UNVERIFIED",
    "QUARANTINED",
    "EXPIRED",
    "INVALID",
}
PROTOCOLS = {"vless", "vmess", "trojan", "ss"}


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso_utc(value: datetime | None = None) -> str:
    current = value or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return current.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


@dataclass(slots=True)
class ParsedConfig:
    config_id: str
    protocol: str
    uri: str = field(repr=False)
    host: str = ""
    port: int = 0
    credentials: dict[str, Any] = field(default_factory=dict, repr=False)
    params: dict[str, str] = field(default_factory=dict)
    name: str = ""
    canonicalizer_version: str = "1"

    def public_dict(self, publish_uri: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "config_id": self.config_id,
            "protocol": self.protocol,
            "name": self.name,
        }
        if publish_uri:
            result["uri"] = self.uri
        return result


@dataclass(slots=True)
class ValidationResult:
    status: str
    reason_code: str | None = None
    resolved_ips: list[str] = field(default_factory=list)
    tcp_reachable: bool | None = None
    checked_at: str = field(default_factory=iso_utc)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ObserverResult:
    observer_id: str
    ip: str | None
    ip_family: str | None
    latency_ms: float | None
    observed_at: str
    success: bool
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
