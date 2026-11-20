"""Run a bounded TCP preflight against validated destination addresses."""

from __future__ import annotations

import socket


def tcp_preflight(addresses: list[str], port: int, timeout_seconds: float) -> tuple[bool, str | None]:
    last_error = "TCP_UNREACHABLE"
    for address in addresses:
        try:
            with socket.create_connection((address, port), timeout=timeout_seconds):
                return True, None
        except TimeoutError:
            last_error = "TCP_TIMEOUT"
        except OSError as exc:
            last_error = "TCP_TIMEOUT" if isinstance(exc, TimeoutError) else "TCP_UNREACHABLE"
    return False, last_error
