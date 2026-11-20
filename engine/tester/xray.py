"""Build a constrained Xray client configuration from a parsed URI."""

from __future__ import annotations

from typing import Any

from engine.models import ParsedConfig


class XrayConfigError(ValueError):
    """Raised when this build cannot safely represent a share URI."""


def _stream_settings(config: ParsedConfig) -> dict[str, Any]:
    params = config.params
    if config.protocol == "vmess":
        network = (params.get("network") or "tcp").lower()
    else:
        network = (params.get("type") or params.get("network") or "tcp").lower()
    if network not in {"tcp", "ws", "grpc", "httpupgrade"}:
        raise XrayConfigError("TRANSPORT_NOT_SUPPORTED")
    settings: dict[str, Any] = {"network": network}
    if network == "ws":
        ws: dict[str, Any] = {"path": params.get("path", "/") or "/"}
        host_header = params.get("host")
        if host_header:
            ws["headers"] = {"Host": host_header}
        settings["wsSettings"] = ws
    elif network == "grpc":
        settings["grpcSettings"] = {
            "serviceName": params.get("serviceName", params.get("path", "")),
            "authority": params.get("authority", params.get("host", "")),
        }
    elif network == "httpupgrade":
        settings["httpupgradeSettings"] = {
            "path": params.get("path", "/") or "/",
            "host": params.get("host", ""),
        }

    security = (params.get("security") or params.get("tls") or "none").lower()
    if config.protocol == "trojan" and security in {"", "none"}:
        security = "tls"
    if security == "tls":
        tls: dict[str, Any] = {
            "serverName": params.get("sni") or config.host,
            "allowInsecure": False,
        }
        if params.get("fp"):
            tls["fingerprint"] = params["fp"]
        if params.get("alpn"):
            tls["alpn"] = [part.strip() for part in params["alpn"].split(",") if part.strip()]
        settings["security"] = "tls"
        settings["tlsSettings"] = tls
    elif security == "reality":
        if not params.get("pbk") and not params.get("publicKey"):
            raise XrayConfigError("REALITY_PUBLIC_KEY_MISSING")
        reality: dict[str, Any] = {
            "serverName": params.get("sni") or config.host,
            "fingerprint": params.get("fp", "chrome"),
            "publicKey": params.get("pbk", params.get("publicKey", "")),
            "shortId": params.get("sid", params.get("shortId", "")),
        }
        if params.get("spx") or params.get("spiderX"):
            reality["spiderX"] = params.get("spx", params.get("spiderX"))
        settings["security"] = "reality"
        settings["realitySettings"] = reality
    elif security not in {"", "none", "false"}:
        raise XrayConfigError("SECURITY_MODE_NOT_SUPPORTED")
    return settings


def build_xray_config(
    config: ParsedConfig,
    local_socks_port: int,
    resolved_ip: str,
) -> dict[str, Any]:
    """Build one outbound. Use the validated IP to reduce DNS rebinding risk."""
    user = dict(config.credentials)
    user["address"] = resolved_ip
    user["port"] = config.port
    stream = _stream_settings(config)

    if config.protocol == "vless":
        user = {
            "id": user["id"],
            "encryption": user.get("encryption", "none"),
        }
        if config.credentials.get("flow"):
            user["flow"] = config.credentials["flow"]
        outbound = {
            "protocol": "vless",
            "settings": {"vnext": [{"address": resolved_ip, "port": config.port, "users": [user]}]},
            "streamSettings": stream,
        }
    elif config.protocol == "vmess":
        user = {
            "id": config.credentials["id"],
            "alterId": int(config.credentials.get("alter_id", 0)),
            "security": config.credentials.get("security", "auto"),
        }
        outbound = {
            "protocol": "vmess",
            "settings": {"vnext": [{"address": resolved_ip, "port": config.port, "users": [user]}]},
            "streamSettings": stream,
        }
    elif config.protocol == "trojan":
        outbound = {
            "protocol": "trojan",
            "settings": {
                "servers": [
                    {
                        "address": resolved_ip,
                        "port": config.port,
                        "password": config.credentials["password"],
                    }
                ]
            },
            "streamSettings": stream,
        }
    elif config.protocol == "ss":
        outbound = {
            "protocol": "shadowsocks",
            "settings": {
                "servers": [
                    {
                        "address": resolved_ip,
                        "port": config.port,
                        "password": config.credentials["password"],
                        "method": config.credentials["method"],
                    }
                ]
            },
        }
    else:
        raise XrayConfigError("PROTOCOL_NOT_SUPPORTED")

    return {
        "log": {"loglevel": "none"},
        "inbounds": [
            {
                "tag": "local-socks",
                "listen": "127.0.0.1",
                "port": local_socks_port,
                "protocol": "socks",
                "settings": {"auth": "noauth", "udp": False},
            }
        ],
        "outbounds": [outbound],
        "routing": {"domainStrategy": "AsIs", "rules": []},
    }
