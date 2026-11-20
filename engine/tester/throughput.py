"""Measure download throughput from a controlled HTTPS endpoint."""

from __future__ import annotations

import time
from urllib.parse import urlsplit

import requests


def measure_throughput(
    url: str,
    socks_port: int,
    max_bytes: int,
    timeout_seconds: int,
) -> dict:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("THROUGHPUT_ENDPOINT_INVALID")
    proxy = f"socks5h://127.0.0.1:{socks_port}"
    session = requests.Session()
    session.trust_env = False
    started = time.perf_counter()
    downloaded = 0
    with session.get(
        url,
        stream=True,
        timeout=timeout_seconds,
        proxies={"http": proxy, "https": proxy},
        verify=True,
        allow_redirects=False,
    ) as response:
        response.raise_for_status()
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            remaining = max_bytes - downloaded
            downloaded += min(len(chunk), remaining)
            if downloaded >= max_bytes:
                break
    elapsed = max(time.perf_counter() - started, 0.001)
    return {
        "throughput_bps": round(downloaded * 8 / elapsed, 2) if downloaded else None,
        "downloaded_bytes": downloaded,
        "duration_seconds": round(elapsed, 3),
        "measurement_method": "controlled_https_download_over_tunnel",
    }
