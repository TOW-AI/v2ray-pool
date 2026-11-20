"""Parse subscription payloads and V2Ray share URIs."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import urllib.parse
import uuid
from typing import Any

from engine.collector.normalizer import normalize_line
from engine.models import PROTOCOLS, ParsedConfig


class ParseError(ValueError):
    """Raised when a source record is not a supported share URI."""


URI_PATTERN = re.compile(r"^(vless|vmess|trojan|ss)://", re.IGNORECASE)


def _b64decode(value: str) -> bytes:
    cleaned = value.strip().replace("-", "+").replace("_", "/")
    cleaned += "=" * ((4 - len(cleaned) % 4) % 4)
    try:
        return base64.b64decode(cleaned, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ParseError("BASE64_INVALID") from exc


def decode_subscription(payload: bytes | str, mode: str = "auto") -> str:
    """Decode a plain or Base64 subscription. Return UTF-8 text."""
    if isinstance(payload, bytes):
        try:
            text = payload.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ParseError("TEXT_ENCODING_INVALID") from exc
    else:
        text = payload.lstrip("\ufeff")
    stripped = text.strip()
    if not stripped:
        return ""
    if mode == "plain" or (mode == "auto" and URI_PATTERN.search(stripped)):
        return stripped
    if mode not in {"auto", "base64"}:
        raise ParseError("SOURCE_FORMAT_UNSUPPORTED")
    decoded = _b64decode("".join(stripped.split()))
    try:
        return decoded.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ParseError("BASE64_TEXT_INVALID") from exc


def _reject_control_characters(values: list[str]) -> None:
    if any(any(ord(char) < 32 or ord(char) == 127 for char in value) for value in values):
        raise ParseError("URI_CONTROL_CHARACTER")


def _canonical_web_uri(uri: str, parsed: urllib.parse.SplitResult) -> str:
    raw_netloc = parsed.netloc
    userinfo, separator, host_part = raw_netloc.rpartition("@")
    hostname = parsed.hostname or ""
    if not hostname:
        raise ParseError("HOST_MISSING")
    try:
        ascii_host = hostname.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ParseError("HOST_INVALID") from exc
    if ":" in ascii_host and not ascii_host.startswith("["):
        ascii_host = f"[{ascii_host}]"
    port = parsed.port
    normalized_host = ascii_host + (f":{port}" if port is not None else "")
    normalized_netloc = f"{userinfo}@{normalized_host}" if separator else normalized_host
    query_items = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    canonical_query = urllib.parse.urlencode(sorted(query_items), doseq=True)
    return urllib.parse.urlunsplit(
        (parsed.scheme.lower(), normalized_netloc, parsed.path, canonical_query, "")
    )


def _decode_vmess(uri: str) -> tuple[str, dict[str, Any], dict[str, str], str, str]:
    raw = uri[uri.find("://") + 3 :].split("#", 1)[0]
    try:
        data = json.loads(_b64decode(raw).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ParseError("VMESS_PAYLOAD_INVALID") from exc
    if not isinstance(data, dict):
        raise ParseError("VMESS_PAYLOAD_INVALID")
    host = str(data.get("add", "")).strip()
    try:
        port = int(data.get("port", 0))
    except (TypeError, ValueError) as exc:
        raise ParseError("PORT_INVALID") from exc
    user_id = str(data.get("id", "")).strip()
    if not host or not user_id:
        raise ParseError("VMESS_REQUIRED_FIELD_MISSING")
    try:
        uuid.UUID(user_id)
    except ValueError as exc:
        raise ParseError("VMESS_ID_INVALID") from exc
    if not 1 <= port <= 65535:
        raise ParseError("PORT_INVALID")
    canonical_data = {key: value for key, value in data.items() if key != "ps"}
    canonical_data["id"] = user_id.lower()
    canonical_data["port"] = port
    canonical_data["aid"] = int(data.get("aid", 0) or 0)
    credentials = {
        "id": user_id,
        "alter_id": int(data.get("aid", 0) or 0),
        "security": str(data.get("scy", "auto") or "auto"),
    }
    params = {
        "network": str(data.get("net", "tcp") or "tcp").lower(),
        "type": str(data.get("type", "none") or "none"),
        "host": str(data.get("host", "") or ""),
        "path": str(data.get("path", "") or ""),
        "tls": str(data.get("tls", "") or "").lower(),
        "sni": str(data.get("sni", "") or ""),
        "alpn": str(data.get("alpn", "") or ""),
    }
    name = str(data.get("ps", "") or "")
    _reject_control_characters([host, user_id, name, *params.values(), str(credentials["security"])])
    try:
        canonical_host = host.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ParseError("HOST_INVALID") from exc
    canonical_data["add"] = canonical_host
    canonical = json.dumps(canonical_data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    canonical_uri = "vmess://" + base64.urlsafe_b64encode(canonical.encode()).decode().rstrip("=")
    return host, {"port": port, **credentials}, params, canonical_uri, name


def _decode_ss(uri: str) -> tuple[str, int, dict[str, Any], str]:
    body = uri[uri.find("://") + 3 :]
    body = body.split("#", 1)[0].split("?", 1)[0]
    if "@" in body:
        encoded_auth, server = body.rsplit("@", 1)
        try:
            auth = _b64decode(encoded_auth).decode("utf-8") if ":" not in encoded_auth else encoded_auth
            server_parts = urllib.parse.urlsplit("//" + server)
            host, port = server_parts.hostname or "", server_parts.port or 0
        except (UnicodeError, ValueError) as exc:
            raise ParseError("SS_URI_INVALID") from exc
        method, separator, password = auth.partition(":")
        if not separator:
            raise ParseError("SS_CREDENTIALS_INVALID")
    else:
        try:
            decoded = _b64decode(body).decode("utf-8")
            auth_server = decoded.rsplit("@", 1)
            if len(auth_server) != 2:
                raise ParseError("SS_URI_INVALID")
            server_parts = urllib.parse.urlsplit("//" + auth_server[1])
            host, port = server_parts.hostname or "", server_parts.port or 0
        except (UnicodeError, ValueError) as exc:
            if isinstance(exc, ParseError):
                raise
            raise ParseError("SS_URI_INVALID") from exc
        method, separator, password = auth_server[0].partition(":")
        if not separator:
            raise ParseError("SS_CREDENTIALS_INVALID")
    if not host or not 1 <= port <= 65535 or not method or not password:
        raise ParseError("SS_REQUIRED_FIELD_MISSING")
    _reject_control_characters([host, method, password])
    return host, port, {"method": method, "password": password}, method


def parse_uri(uri: str) -> ParsedConfig:
    """Parse one share URI. Do not include the URI in exception text."""
    value = uri.strip()
    if len(value) > 8192:
        raise ParseError("URI_TOO_LARGE")
    match = URI_PATTERN.match(value)
    if not match:
        raise ParseError("SCHEME_UNSUPPORTED")
    scheme = match.group(1).lower()
    if scheme not in PROTOCOLS:
        raise ParseError("SCHEME_UNSUPPORTED")
    value = scheme + value[value.find("://") :]

    if scheme == "vmess":
        host, vmess_data, params, canonical, name = _decode_vmess(value)
        port = int(vmess_data.pop("port"))
        credentials = vmess_data
    elif scheme == "ss":
        if "?" in value.split("#", 1)[0]:
            raise ParseError("SS_PLUGIN_UNSUPPORTED")
        host, port, credentials, _ = _decode_ss(value)
        params = {}
        name = urllib.parse.unquote(value.split("#", 1)[1]) if "#" in value else ""
        try:
            canonical_host = host.encode("idna").decode("ascii").lower()
        except UnicodeError as exc:
            raise ParseError("HOST_INVALID") from exc
        auth = f"{credentials['method']}:{credentials['password']}@{canonical_host}:{port}"
        canonical = "ss://" + base64.urlsafe_b64encode(auth.encode()).decode().rstrip("=")
    else:
        try:
            parsed = urllib.parse.urlsplit(value)
            host = parsed.hostname or ""
        except ValueError as exc:
            raise ParseError("URI_INVALID") from exc
        try:
            port = parsed.port or 0
        except ValueError as exc:
            raise ParseError("PORT_INVALID") from exc
        try:
            canonical = _canonical_web_uri(value, parsed)
        except ValueError as exc:
            raise ParseError("URI_INVALID") from exc
        if scheme == "vless":
            user_id = urllib.parse.unquote(parsed.username or "")
            if not user_id:
                raise ParseError("VLESS_ID_MISSING")
            try:
                uuid.UUID(user_id)
            except ValueError as exc:
                raise ParseError("VLESS_ID_INVALID") from exc
            credentials = {"id": user_id, "encryption": "none"}
        else:
            password = urllib.parse.unquote(parsed.username or "")
            if not password:
                raise ParseError("TROJAN_PASSWORD_MISSING")
            credentials = {"password": password}
        params = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
        name = urllib.parse.unquote(parsed.fragment or "")
        _reject_control_characters([host, *(params.keys()), *params.values(), name, credentials.get("id", credentials.get("password", ""))])
        if scheme == "vless" and params.get("flow"):
            credentials["flow"] = params["flow"]

    if not host:
        raise ParseError("HOST_MISSING")
    if not 1 <= int(port) <= 65535:
        raise ParseError("PORT_INVALID")
    config_id = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return ParsedConfig(
        config_id=config_id,
        protocol=scheme,
        uri=value,
        host=host,
        port=int(port),
        credentials=credentials,
        params=params,
        name=name[:128],
    )


def parse_payload(payload: bytes | str, mode: str = "auto") -> tuple[list[ParsedConfig], dict[str, int]]:
    """Parse a subscription or JSON source and return records plus counts."""
    if mode == "json":
        try:
            decoded = payload.decode("utf-8-sig") if isinstance(payload, bytes) else payload
            document = json.loads(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ParseError("JSON_SOURCE_INVALID") from exc
        if isinstance(document, list):
            lines = document
        elif isinstance(document, dict):
            lines = document.get("configs", document.get("items", []))
        else:
            raise ParseError("JSON_SOURCE_SHAPE_INVALID")
        if not isinstance(lines, list) or any(not isinstance(item, str) for item in lines):
            raise ParseError("JSON_SOURCE_SHAPE_INVALID")
        text = "\n".join(lines)
    else:
        text = decode_subscription(payload, mode)
    configs: dict[str, ParsedConfig] = {}
    counts = {"input_lines": 0, "parsed": 0, "duplicates": 0, "rejected": 0}
    reasons: dict[str, int] = {}
    for raw_line in text.splitlines():
        line = normalize_line(raw_line)
        if not line or line.startswith("#"):
            continue
        counts["input_lines"] += 1
        try:
            parsed = parse_uri(line)
        except ParseError as exc:
            counts["rejected"] += 1
            reasons[str(exc)] = reasons.get(str(exc), 0) + 1
            continue
        except (ValueError, UnicodeError, TypeError, KeyError):
            counts["rejected"] += 1
            reasons["URI_INVALID"] = reasons.get("URI_INVALID", 0) + 1
            continue
        if parsed.config_id in configs:
            counts["duplicates"] += 1
        else:
            configs[parsed.config_id] = parsed
            counts["parsed"] += 1
    counts.update({f"reason:{key}": value for key, value in sorted(reasons.items())})
    return list(configs.values()), counts
