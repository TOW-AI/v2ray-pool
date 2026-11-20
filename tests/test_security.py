import socket

import pytest

from engine.collector.fetcher import FetchError, _resolve_public
from engine.collector.parser import parse_uri
from engine.validator.security import is_public_address, resolve_target, validate_config

UUID = "123e4567-e89b-12d3-a456-426614174000"
POLICY = {
    "allowed_protocols": ["vless", "vmess", "trojan", "ss"],
    "block_private_destinations": True,
    "block_link_local": True,
    "block_loopback": True,
    "block_multicast": True,
    "block_reserved": True,
    "require_public_ip": True,
    "denied_ports": [22, 23],
    "tcp_timeout_seconds": 0.1,
}


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "fc00::1"])
def test_private_or_special_destinations_are_rejected(address):
    with pytest.raises(ValueError):
        resolve_target(address, 443, POLICY)


def test_public_address_classifier():
    assert is_public_address("93.184.216.34")
    assert not is_public_address("192.168.1.1")
    assert not is_public_address("::1")


def test_fetcher_blocks_private_literal_ip():
    with pytest.raises(FetchError, match="BLOCKED_SECURITY_POLICY"):
        _resolve_public("127.0.0.1", 443)


def test_validator_rejects_denied_port_without_connecting():
    config = parse_uri(f"vless://{UUID}@93.184.216.34:22")
    result = validate_config(config, POLICY, tcp_probe=False)
    assert result.status == "BLOCKED_SECURITY_POLICY"
    assert result.reason_code == "PORT_DENIED"


def test_dns_resolution_rejects_private_answers(monkeypatch):
    def fake_getaddrinfo(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.9", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(ValueError, match="BLOCKED_SECURITY_POLICY"):
        resolve_target("rebind.example", 443, POLICY)


def test_fetcher_rejects_oversized_header_file(tmp_path):
    from engine.collector.fetcher import _last_header

    header_file = tmp_path / "headers.txt"
    header_file.write_bytes(b"X-Test: value\r\n" + b"A" * 128)
    try:
        _last_header(header_file, "location", max_bytes=32)
    except FetchError as exc:
        assert str(exc) == "SOURCE_HEADERS_TOO_LARGE"
    else:
        raise AssertionError("Oversized response headers must be rejected")
