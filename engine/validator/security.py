"""Destination policy checks and TCP preflight."""

from __future__ import annotations

import ipaddress
import socket
from typing import Any

from engine.models import ParsedConfig, ValidationResult
from engine.validator.tcp import tcp_preflight


def is_public_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return bool(address.is_global and not address.is_multicast and not address.is_unspecified)


def resolve_target(host: str, port: int, policy: dict[str, Any]) -> list[str]:
    try:
        literal = ipaddress.ip_address(host)
        addresses = [literal]
    except ValueError:
        try:
            answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise ValueError("DNS_FAILURE") from exc
        addresses = []
        for answer in answers:
            try:
                addresses.append(ipaddress.ip_address(answer[4][0]))
            except ValueError:
                continue
    unique = list(dict.fromkeys(addresses))
    if not unique:
        raise ValueError("DNS_EMPTY")

    for address in unique:
        if policy.get("require_public_ip", True) and not address.is_global:
            raise ValueError("BLOCKED_SECURITY_POLICY")
        if policy.get("block_private_destinations", True) and address.is_private:
            raise ValueError("BLOCKED_PRIVATE_ADDRESS")
        if policy.get("block_loopback", True) and address.is_loopback:
            raise ValueError("BLOCKED_LOOPBACK")
        if policy.get("block_link_local", True) and address.is_link_local:
            raise ValueError("BLOCKED_LINK_LOCAL")
        if policy.get("block_multicast", True) and address.is_multicast:
            raise ValueError("BLOCKED_MULTICAST")
        if policy.get("block_reserved", True) and address.is_reserved:
            raise ValueError("BLOCKED_RESERVED")
    return [str(address) for address in unique]


def validate_config(config: ParsedConfig, policy: dict[str, Any], tcp_probe: bool = True) -> ValidationResult:
    """Validate protocol allow-list, destination policy, and TCP reachability."""
    if config.protocol not in policy.get("allowed_protocols", []):
        return ValidationResult("INVALID_SYNTAX", "PROTOCOL_NOT_ALLOWED")
    if not config.host or not 1 <= config.port <= 65535:
        return ValidationResult("INVALID_SYNTAX", "HOST_OR_PORT_INVALID")
    if config.port in set(policy.get("denied_ports", [])):
        return ValidationResult("BLOCKED_SECURITY_POLICY", "PORT_DENIED")
    try:
        addresses = resolve_target(config.host, config.port, policy)
    except ValueError as exc:
        code = str(exc)
        status = "DNS_FAILURE" if code.startswith("DNS_") else "BLOCKED_SECURITY_POLICY"
        return ValidationResult(status, code)
    if not tcp_probe:
        return ValidationResult("VALID", None, addresses, None)

    reachable, error_code = tcp_preflight(
        addresses, config.port, float(policy.get("tcp_timeout_seconds", 3))
    )
    if reachable:
        return ValidationResult("VALID", None, addresses, True)
    return ValidationResult(error_code or "TCP_UNREACHABLE", error_code, addresses, False)
