"""Load and validate application settings."""

from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml
from jsonschema import Draft202012Validator


class ConfigurationError(ValueError):
    """Raised when application settings are not valid."""


def _validate_https_endpoint(url: str, label: str, allow_query: bool = True) -> None:
    parsed = urlsplit(url)
    try:
        port = parsed.port or 443
    except ValueError as exc:
        raise ConfigurationError(f"{label} has an invalid port.") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
        or (parsed.query and not allow_query)
        or port != 443
        or any(ord(char) < 32 for char in url)
    ):
        raise ConfigurationError(f"{label} must be a credential-free HTTPS URL on port 443.")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        hostname = parsed.hostname.lower().rstrip(".")
        if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(
            (".localhost", ".local", ".internal", ".lan")
        ):
            raise ConfigurationError(f"{label} must not target a local host.")
    else:
        if not address.is_global:
            raise ConfigurationError(f"{label} must not target a non-public IP address.")


def load_settings(path: str | Path) -> dict[str, Any]:
    config_path = Path(path).resolve()
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"Cannot read settings file: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigurationError("Settings root must be a YAML object.")

    schema_path = config_path.parent.parent / "schemas" / "settings.schema.json"
    try:
        import json

        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        source_schema = json.loads((schema_path.parent / "source.schema.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConfigurationError(f"Cannot read settings schema: {exc}") from exc
    # Resolve the only external schema reference without network access.
    from referencing import Registry, Resource

    registry = Registry().with_resource(
        "source.schema.json", Resource.from_contents(source_schema)
    )
    validator = Draft202012Validator(schema, registry=registry)
    errors = sorted(validator.iter_errors(raw), key=lambda item: list(item.path))
    if errors:
        details = "; ".join(
            f"{'.'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
            for error in errors
        )
        raise ConfigurationError(details)

    _validate_weight_totals(raw)
    _validate_threshold_order(raw)
    _validate_observers(raw)
    if raw["tester"].get("throughput_enabled"):
        endpoint = raw["tester"].get("throughput_url", "")
        _validate_https_endpoint(endpoint, "tester.throughput_url", allow_query=False)
    if raw["tester"].get("enabled"):
        tester = raw["tester"]
        if not tester.get("xray_binary"):
            raise ConfigurationError("tester.xray_binary is required when Xray tests are enabled.")
        digest = tester.get("xray_sha256", "")
        if len(digest) != 64 or any(char not in "0123456789abcdefABCDEF" for char in digest):
            raise ConfigurationError("tester.xray_sha256 must contain a valid SHA-256 digest.")
    return raw


def _validate_weight_totals(settings: dict[str, Any]) -> None:
    for name in ("fixed_weights", "rotating_weights", "balanced_weights"):
        weights = settings["ranking"][name]
        total = sum(float(value) for value in weights.values())
        if abs(total - 1.0) > 1e-9:
            raise ConfigurationError(f"ranking.{name} must sum to 1.0; found {total:.6f}.")


def _validate_threshold_order(settings: dict[str, Any]) -> None:
    candidate = settings["intelligence"]["fixed_candidate"]
    verified = settings["intelligence"]["fixed_verified"]
    if verified["min_runs"] < candidate["min_runs"]:
        raise ConfigurationError("Fixed Verified must require at least as many runs as Candidate.")
    if verified["min_span_hours"] < candidate["min_span_hours"]:
        raise ConfigurationError("Fixed Verified must require at least as much time as Candidate.")
    if settings["tester"]["min_successful_observers"] > len(settings["tester"]["ip_observers"]):
        raise ConfigurationError("The observer quorum exceeds the configured observer count.")


def _validate_observers(settings: dict[str, Any]) -> None:
    tester = settings["tester"]
    observers = tester["ip_observers"]
    ids = [str(item["id"]) for item in observers]
    if len(ids) != len(set(ids)):
        raise ConfigurationError("Observer IDs must be unique.")

    for observer in observers:
        for key in ("url", "url_ipv4", "url_ipv6"):
            if observer.get(key):
                _validate_https_endpoint(str(observer[key]), f"observer {observer['id']} {key}")

    required = set(settings["intelligence"]["required_ip_families"])
    enabled = {
        family for family, flag in (
            ("ipv4", tester.get("enable_ipv4", True)),
            ("ipv6", tester.get("enable_ipv6", True)),
        ) if flag
    }
    if not required.issubset(enabled):
        raise ConfigurationError("Every required IP family must be enabled in the Tester.")

    quorum = int(tester["min_successful_observers"])
    for family, flag in (("ipv4", tester.get("enable_ipv4", True)), ("ipv6", tester.get("enable_ipv6", True))):
        if not flag:
            continue
        key = f"url_{family}"
        available = sum(bool(observer.get(key) or observer.get("url")) for observer in observers)
        if available < quorum:
            raise ConfigurationError(f"The {family} observer quorum cannot be met by the configured URLs.")
