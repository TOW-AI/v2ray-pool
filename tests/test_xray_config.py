import pytest

from engine.collector.parser import parse_uri
from engine.tester.xray import XrayConfigError, build_xray_config

UUID = "123e4567-e89b-12d3-a456-426614174000"


def test_vless_build_uses_validated_ip_and_disables_insecure_tls():
    config = parse_uri(
        f"vless://{UUID}@origin.example:443?security=tls&type=ws&host=edge.example&path=%2Fws&sni=front.example#name"
    )
    output = build_xray_config(config, 10999, "93.184.216.34")
    outbound = output["outbounds"][0]
    assert outbound["settings"]["vnext"][0]["address"] == "93.184.216.34"
    assert outbound["streamSettings"]["tlsSettings"]["allowInsecure"] is False
    assert outbound["streamSettings"]["tlsSettings"]["serverName"] == "front.example"
    assert output["inbounds"][0]["listen"] == "127.0.0.1"


def test_reality_requires_public_key():
    config = parse_uri(f"vless://{UUID}@origin.example:443?security=reality&sni=front.example")
    with pytest.raises(XrayConfigError, match="REALITY_PUBLIC_KEY_MISSING"):
        build_xray_config(config, 10999, "93.184.216.34")


def test_unsupported_transport_fails_closed():
    config = parse_uri(f"vless://{UUID}@origin.example:443?type=kcp")
    with pytest.raises(XrayConfigError, match="TRANSPORT_NOT_SUPPORTED"):
        build_xray_config(config, 10999, "93.184.216.34")


def test_shadowsocks_maps_to_xray_shadowsocks_protocol():
    config = parse_uri("ss://YWVzLTEyOC1nY206cGFzcw==@origin.example:8388")
    output = build_xray_config(config, 10999, "93.184.216.34")
    outbound = output["outbounds"][0]
    assert outbound["protocol"] == "shadowsocks"
    assert outbound["settings"]["servers"][0]["address"] == "93.184.216.34"
