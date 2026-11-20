"""Fetch public source URLs with redirect and DNS controls."""

from __future__ import annotations

import ipaddress
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urljoin, urlsplit


class FetchError(RuntimeError):
    """Raised when a source cannot be fetched within policy."""


def _resolve_public(host: str, port: int) -> str:
    try:
        literal = ipaddress.ip_address(host)
        addresses = [literal]
    except ValueError:
        try:
            answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise FetchError("DNS_FAILURE") from exc
        addresses = []
        for answer in answers:
            try:
                addresses.append(ipaddress.ip_address(answer[4][0]))
            except ValueError:
                continue
    if not addresses:
        raise FetchError("DNS_EMPTY")
    unique = list(dict.fromkeys(addresses))
    if any(not address.is_global for address in unique):
        raise FetchError("BLOCKED_SECURITY_POLICY")
    return str(unique[0])


def _curl_resolve_value(host: str, port: int, ip: str) -> str:
    address = f"[{ip}]" if ":" in ip else ip
    return f"{host}:{port}:{address}"


def fetch_source(source: dict, settings: dict) -> tuple[bytes, dict]:
    """Fetch a public source. Curl pins each request to a validated address."""
    curl = shutil.which("curl")
    if not curl:
        raise FetchError("CURL_NOT_AVAILABLE")

    url = str(source.get("url", ""))
    max_redirects = min(int(source.get("max_redirects", settings["max_redirects"])), 5)
    timeout = min(int(source.get("timeout_seconds", settings["request_timeout_seconds"])), 120)
    max_bytes = min(int(source.get("max_bytes", settings["max_response_bytes"])), 10 * 1024 * 1024)
    user_agent = str(settings.get("user_agent", "V2Ray-Pool-Intelligence-Engine/2.0"))
    if len(user_agent) > 120 or any(ord(char) < 32 for char in user_agent):
        raise FetchError("USER_AGENT_INVALID")

    for redirect_count in range(max_redirects + 1):
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise FetchError("SOURCE_URL_INVALID")
        if parsed.username or parsed.password or parsed.query or parsed.fragment or any(ord(char) < 32 for char in url):
            raise FetchError("SOURCE_URL_CREDENTIALS_QUERY_OR_CONTROL_CHAR")
        try:
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
        except ValueError as exc:
            raise FetchError("SOURCE_PORT_INVALID") from exc
        if port not in {80, 443}:
            raise FetchError("SOURCE_PORT_DENIED")
        pinned_ip = _resolve_public(parsed.hostname, port)

        with tempfile.TemporaryDirectory(prefix="v2ray-source-") as temp_dir:
            body_path = Path(temp_dir) / "body.bin"
            headers_path = Path(temp_dir) / "headers.txt"
            command = [
                curl,
                "--silent",
                "--show-error",
                "--fail-with-body",
                "--proto",
                "=http,https",
                "--connect-timeout",
                str(min(timeout, 20)),
                "--max-time",
                str(timeout),
                "--max-filesize",
                str(max_bytes),
                "--max-redirs",
                "0",
                "--user-agent",
                user_agent,
                "--resolve",
                _curl_resolve_value(parsed.hostname, port, pinned_ip),
                "--dump-header",
                str(headers_path),
                "--output",
                str(body_path),
                "--write-out",
                "%{http_code}",
                url,
            ]
            try:
                completed = subprocess.run(  # nosec B603 - fixed argument vector; shell=False
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=timeout + 2,
                    shell=False,
                    env={"PATH": str(Path(curl).parent), "HOME": temp_dir},
                )
            except subprocess.TimeoutExpired as exc:
                raise FetchError("SOURCE_TIMEOUT") from exc
            if completed.returncode != 0:
                raise FetchError("SOURCE_HTTP_OR_CURL_ERROR")
            try:
                status_code = int(completed.stdout.strip()[-3:])
            except ValueError as exc:
                raise FetchError("SOURCE_STATUS_INVALID") from exc
            if status_code in {301, 302, 303, 307, 308}:
                location = _last_header(headers_path, "location")
                if not location or redirect_count >= max_redirects:
                    raise FetchError("SOURCE_REDIRECT_LIMIT")
                url = urljoin(url, location)
                continue
            if not 200 <= status_code < 300:
                raise FetchError("SOURCE_HTTP_STATUS")
            body = body_path.read_bytes()
            if len(body) > max_bytes:
                raise FetchError("SOURCE_SIZE_LIMIT")
            return body, {
                "status_code": status_code,
                "bytes": len(body),
                "redirects": redirect_count,
                "resolved_ip": pinned_ip,
            }
    raise FetchError("SOURCE_REDIRECT_LIMIT")


def _last_header(path: Path, header_name: str, max_bytes: int = 65536) -> str | None:
    if not path.exists():
        return None
    with path.open("rb") as stream:
        payload = stream.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise FetchError("SOURCE_HEADERS_TOO_LARGE")
    target = header_name.lower() + ":"
    values = [
        line.split(":", 1)[1].strip()
        for line in payload.decode("iso-8859-1").splitlines()
        if line.lower().startswith(target)
    ]
    return values[-1] if values else None
