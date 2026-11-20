"""Syntax gate for parsed configuration records."""

from __future__ import annotations

from engine.models import ParsedConfig, ValidationResult
from engine.validator.security import validate_config


def validate_syntax(config: ParsedConfig) -> ValidationResult:
    if config.protocol == "vless" and not config.credentials.get("id"):
        return ValidationResult("INVALID_SYNTAX", "VLESS_ID_MISSING")
    if config.protocol == "vmess" and not config.credentials.get("id"):
        return ValidationResult("INVALID_SYNTAX", "VMESS_ID_MISSING")
    if config.protocol == "trojan" and not config.credentials.get("password"):
        return ValidationResult("INVALID_SYNTAX", "TROJAN_PASSWORD_MISSING")
    if config.protocol == "ss" and not all(
        config.credentials.get(key) for key in ("method", "password")
    ):
        return ValidationResult("INVALID_SYNTAX", "SS_CREDENTIALS_MISSING")
    return ValidationResult("VALID")


def validate_full(config: ParsedConfig, policy: dict, tcp_probe: bool = True) -> ValidationResult:
    syntax = validate_syntax(config)
    if syntax.status != "VALID":
        return syntax
    return validate_config(config, policy, tcp_probe=tcp_probe)
