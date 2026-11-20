import base64
import json

import pytest

from engine.collector.parser import ParseError, decode_subscription, parse_payload, parse_uri

UUID = "123e4567-e89b-12d3-a456-426614174000"


def vmess_uri(name: str = "Node", host: str = "example.com") -> str:
    payload = {
        "v": "2", "ps": name, "add": host, "port": "443", "id": UUID,
        "aid": "0", "scy": "auto", "net": "ws", "type": "none",
        "host": "edge.example.com", "path": "/ws", "tls": "tls",
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"vmess://{encoded}"


def test_parse_vless_and_remove_display_name_from_identity():
    first = parse_uri(f"vless://{UUID}@EXAMPLE.com:443?security=tls&type=ws&path=%2Fws#first")
    second = parse_uri(f"vless://{UUID}@example.com:443?path=%2Fws&type=ws&security=tls#second")
    assert first.protocol == "vless"
    assert first.host == "example.com"
    assert first.port == 443
    assert first.config_id == second.config_id


def test_parse_trojan():
    result = parse_uri("trojan://secret@example.com:443?sni=example.com#test")
    assert result.protocol == "trojan"
    assert result.credentials["password"] == "secret"
    assert result.params["sni"] == "example.com"


def test_parse_shadowsocks_legacy_uri_and_ignore_name_in_identity():
    auth = base64.urlsafe_b64encode(b"aes-128-gcm:password@example.com:8388").decode().rstrip("=")
    first = parse_uri(f"ss://{auth}#one")
    second = parse_uri(f"ss://{auth}#two")
    assert first.protocol == "ss"
    assert first.credentials["method"] == "aes-128-gcm"
    assert first.config_id == second.config_id


def test_parse_vmess_and_ignore_display_name():
    first = parse_uri(vmess_uri("first"))
    second = parse_uri(vmess_uri("second", "EXAMPLE.COM"))
    assert first.protocol == "vmess"
    assert first.params["network"] == "ws"
    assert first.config_id == second.config_id


def test_invalid_scheme_and_port_fail_closed():
    with pytest.raises(ParseError, match="SCHEME_UNSUPPORTED"):
        parse_uri("https://example.com")
    with pytest.raises(ParseError, match="PORT_INVALID"):
        parse_uri(f"vless://{UUID}@example.com:70000")


def test_base64_subscription_and_deduplication():
    uri = f"vless://{UUID}@example.com:443#node"
    encoded = base64.b64encode((uri + "\n" + uri.replace("#node", "#renamed")).encode())
    records, counts = parse_payload(encoded, "base64")
    assert len(records) == 1
    assert counts["parsed"] == 1
    assert counts["duplicates"] == 1


def test_json_source():
    uri = f"vless://{UUID}@example.com:443"
    records, counts = parse_payload(json.dumps({"configs": [uri]}), "json")
    assert len(records) == 1
    assert counts["parsed"] == 1


def test_invalid_base64_is_reported():
    with pytest.raises(ParseError, match="BASE64_INVALID"):
        decode_subscription("not valid base64 $$$", "base64")


def test_bad_shadowsocks_row_does_not_abort_other_rows():
    from engine.collector.parser import parse_payload

    bad = "ss://not-valid[broken"
    good = f"vless://{UUID}@node.example:443#valid"
    parsed, counts = parse_payload(f"{bad}\n{good}\n", "plain")
    assert len(parsed) == 1
    assert parsed[0].protocol == "vless"
    assert counts["rejected"] == 1


def test_control_characters_in_decoded_query_are_rejected():
    from engine.collector.parser import ParseError, parse_uri

    uri = f"vless://{UUID}@node.example:443?type=ws&host=good%0d%0aInjected%3Ayes"
    try:
        parse_uri(uri)
    except ParseError as exc:
        assert str(exc) == "URI_CONTROL_CHARACTER"
    else:
        raise AssertionError("Control characters must be rejected")
