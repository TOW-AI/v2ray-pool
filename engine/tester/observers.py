"""Query trusted, family-specific IP observers through the local Xray SOCKS tunnel."""

from __future__ import annotations

import ipaddress
import json
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

import requests

from engine.models import ObserverResult, iso_utc

MAX_OBSERVER_BODY_BYTES = 4096


def _observer_url(observer: dict[str, Any], family: str | None) -> tuple[str | None, bool]:
    """Return the selected URL and whether the URL is family-specific."""
    key = f"url_{family}" if family else "url"
    selected = observer.get(key)
    if selected:
        return str(selected), True
    fallback = observer.get("url")
    return (str(fallback), False) if fallback else (None, False)


def _validate_observer_url(url: str) -> None:
    parsed = urlsplit(url)
    try:
        port = parsed.port or 443
    except ValueError as exc:
        raise ValueError("OBSERVER_URL_INVALID") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
        or port != 443
    ):
        raise ValueError("OBSERVER_URL_INVALID")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError as exc:
        hostname = parsed.hostname.lower().rstrip(".")
        if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(
            (".localhost", ".local", ".internal", ".lan")
        ):
            raise ValueError("OBSERVER_URL_BLOCKED") from exc
    else:
        if not address.is_global:
            raise ValueError("OBSERVER_URL_BLOCKED")


def _read_bounded_body(response: requests.Response) -> bytes:
    content_length = response.headers.get("Content-Length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_OBSERVER_BODY_BYTES:
        raise ValueError("OBSERVER_RESPONSE_TOO_LARGE")
    chunks: list[bytes] = []
    size = 0
    for chunk in response.iter_content(chunk_size=1024):
        if not chunk:
            continue
        size += len(chunk)
        if size > MAX_OBSERVER_BODY_BYTES:
            raise ValueError("OBSERVER_RESPONSE_TOO_LARGE")
        chunks.append(chunk)
    return b"".join(chunks)


def _extract_ip(body: bytes, observer: dict) -> str:
    try:
        text = body.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ValueError("OBSERVER_RESPONSE_ENCODING_INVALID") from exc
    if observer["response_format"] == "json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("OBSERVER_RESPONSE_JSON_INVALID") from exc
        if not isinstance(payload, dict):
            raise ValueError("OBSERVER_RESPONSE_JSON_INVALID")
        value = payload.get(observer.get("response_field", "ip"))
    else:
        value = text
    try:
        return str(ipaddress.ip_address(str(value).strip()))
    except ValueError as exc:
        raise ValueError("OBSERVER_RESPONSE_NOT_IP") from exc


def query_observers(
    observers: list[dict[str, Any]],
    socks_port: int,
    timeout_seconds: int,
    total_timeout_seconds: float | None = None,
    family: str | None = None,
) -> list[ObserverResult]:
    """Query every configured observer. Bound response size and reject redirects."""
    results: list[ObserverResult] = []
    proxy = f"socks5h://127.0.0.1:{socks_port}"
    deadline = time.monotonic() + total_timeout_seconds if total_timeout_seconds is not None else None
    expected_version = 4 if family == "ipv4" else 6 if family == "ipv6" else None

    for observer in observers:
        started = time.perf_counter()
        observer_id = str(observer.get("id", "unknown"))
        url, family_specific = _observer_url(observer, family)
        if not url:
            results.append(
                ObserverResult(
                    observer_id, None, None, None, iso_utc(datetime.now(UTC)), False,
                    "OBSERVER_URL_NOT_CONFIGURED",
                )
            )
            continue

        remaining = max(0.1, deadline - time.monotonic()) if deadline is not None else timeout_seconds
        if deadline is not None and remaining <= 0.1:
            results.append(
                ObserverResult(
                    observer_id, None, None, None, iso_utc(datetime.now(UTC)), False,
                    "PROCESS_TIMEOUT",
                )
            )
            continue

        try:
            _validate_observer_url(url)
            with requests.Session() as session:
                session.trust_env = False
                with session.get(
                    url,
                    timeout=min(float(timeout_seconds), remaining),
                    proxies={"http": proxy, "https": proxy},
                    headers={"Accept": "application/json,text/plain"},
                    verify=True,
                    allow_redirects=False,
                    stream=True,
                ) as response:
                    if 300 <= response.status_code < 400:
                        raise ValueError("OBSERVER_REDIRECT_BLOCKED")
                    response.raise_for_status()
                    ip_value = _extract_ip(_read_bounded_body(response), observer)
            address = ipaddress.ip_address(ip_value)
            if expected_version is not None and family_specific and address.version != expected_version:
                raise ValueError("OBSERVER_FAMILY_MISMATCH")
            results.append(
                ObserverResult(
                    observer_id=observer_id,
                    ip=ip_value,
                    ip_family="ipv4" if address.version == 4 else "ipv6",
                    latency_ms=round((time.perf_counter() - started) * 1000, 3),
                    observed_at=iso_utc(datetime.now(UTC)),
                    success=True,
                )
            )
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            if isinstance(exc, requests.Timeout):
                reason = "OBSERVER_TIMEOUT"
            elif isinstance(exc, ValueError) and str(exc).startswith("OBSERVER_"):
                reason = str(exc)
            else:
                reason = "OBSERVER_FAILED"
            results.append(
                ObserverResult(
                    observer_id=observer_id,
                    ip=None,
                    ip_family=None,
                    latency_ms=None,
                    observed_at=iso_utc(datetime.now(UTC)),
                    success=False,
                    error_code=reason,
                )
            )
    return results


def consensus_for_family(results: list[ObserverResult], family: str, minimum: int) -> dict:
    """Require a quorum and unanimous agreement for the requested address family."""
    matched = [result for result in results if result.success and result.ip_family == family]
    ips = sorted({result.ip for result in matched if result.ip})
    enough = len(matched) >= minimum
    consensus = enough and len(ips) == 1
    return {
        "ip": ips[0] if consensus else None,
        "ip_family": family,
        "observers": [result.to_dict() for result in results],
        "successful_observers": len(matched),
        "distinct_ips": ips,
        "consensus": consensus,
        "result_code": "CONSENSUS" if consensus else (
            "OBSERVER_DISAGREEMENT" if len(ips) > 1 else "INSUFFICIENT_OBSERVERS"
        ),
    }
