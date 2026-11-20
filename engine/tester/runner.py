"""Run Xray in a bounded process and collect tunnel evidence."""

from __future__ import annotations

import hashlib
import json
import os
import signal
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import requests

from engine.models import ParsedConfig, iso_utc
from engine.tester.connectivity import has_tunnel_connectivity
from engine.tester.latency import summarize_latency
from engine.tester.observers import consensus_for_family, query_observers
from engine.tester.throughput import measure_throughput
from engine.tester.xray import XrayConfigError, build_xray_config


class XrayTestError(RuntimeError):
    """Raised when Xray cannot start or complete a test."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_xray_binary(settings: dict[str, Any]) -> Path:
    binary_text = settings.get("xray_binary") or os.environ.get("XRAY_BINARY", "")
    expected_hash = str(settings.get("xray_sha256", "")).lower()
    expected_version = str(settings.get("xray_version", "")).lstrip("v")
    if not binary_text:
        raise XrayTestError("XRAY_BINARY_NOT_CONFIGURED")
    binary = Path(binary_text).expanduser().resolve()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise XrayTestError("XRAY_BINARY_NOT_EXECUTABLE")
    if len(expected_hash) != 64 or any(char not in "0123456789abcdef" for char in expected_hash):
        raise XrayTestError("XRAY_SHA256_NOT_CONFIGURED")
    if sha256_file(binary) != expected_hash:
        raise XrayTestError("XRAY_SHA256_MISMATCH")
    try:
        result = subprocess.run(  # nosec B603 - fixed argument vector; shell=False
            [str(binary), "version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise XrayTestError("XRAY_VERSION_CHECK_FAILED") from exc
    version_output = (result.stdout + result.stderr).lower()
    if result.returncode != 0 or (expected_version and expected_version not in version_output):
        raise XrayTestError("XRAY_VERSION_MISMATCH")
    return binary


def _xray_command(binary: Path, config_path: Path, timeout_seconds: int) -> list[str]:
    """Build an Xray command with OS resource limits and no pre-exec Python hook."""
    command = [str(binary), "run", "-c", str(config_path)]
    if not sys.platform.startswith("linux"):
        return command
    prlimit = shutil.which("prlimit")
    if not prlimit:
        raise XrayTestError("XRAY_RESOURCE_LIMIT_TOOL_NOT_FOUND")
    cpu_limit = max(3, int(timeout_seconds) + 2)
    memory_limit = 512 * 1024 * 1024
    return [
        prlimit,
        f"--cpu={cpu_limit}:{cpu_limit}",
        "--nofile=128:128",
        f"--as={memory_limit}:{memory_limit}",
        "--",
        *command,
    ]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_listener(process: subprocess.Popen, port: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def run_xray_test(
    config: ParsedConfig,
    validation: dict,
    tester_settings: dict,
    run_id: str,
) -> dict:
    """Run a single bounded test. Always terminate the child process."""
    binary = verify_xray_binary(tester_settings)
    resolved = validation.get("resolved_ips", [])
    if not resolved:
        raise XrayTestError("VALIDATED_DESTINATION_MISSING")
    port = _free_port()
    started_at = iso_utc()
    test_id = hashlib.sha256(f"{run_id}:{config.config_id}".encode()).hexdigest()[:24]
    process: subprocess.Popen | None = None
    with tempfile.TemporaryDirectory(prefix="v2ray-test-") as temp_dir:
        config_path = Path(temp_dir) / "xray.json"
        try:
            xray_config = build_xray_config(config, port, resolved[0])
            config_path.write_text(
                json.dumps(xray_config, separators=(",", ":")),
                encoding="utf-8",
            )
            config_path.chmod(0o600)
            process_timeout = int(tester_settings.get("process_timeout_seconds", 25))
            deadline = time.monotonic() + process_timeout
            command = _xray_command(binary, config_path, process_timeout)
            process = subprocess.Popen(  # nosec B603 - fixed argument vector; shell=False
                command,
                cwd=temp_dir,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
                close_fds=True,
                start_new_session=True,
                env={"PATH": str(binary.parent), "HOME": temp_dir, "TMPDIR": temp_dir},
            )
            startup_budget = min(
                float(tester_settings.get("startup_timeout_seconds", 5)),
                max(0.1, deadline - time.monotonic()),
            )
            if not _wait_for_listener(process, port, startup_budget):
                raise XrayTestError("XRAY_STARTUP_FAILED")
            observer_results = []
            families: dict[str, dict] = {}
            minimum = int(tester_settings.get("min_successful_observers", 2))
            for family, enabled in (
                ("ipv4", tester_settings.get("enable_ipv4", True)),
                ("ipv6", tester_settings.get("enable_ipv6", True)),
            ):
                if not enabled:
                    continue
                family_results = query_observers(
                    tester_settings["ip_observers"],
                    port,
                    int(tester_settings.get("observer_timeout_seconds", 8)),
                    total_timeout_seconds=max(0.1, deadline - time.monotonic()),
                    family=family,
                )
                observer_results.extend(family_results)
                families[family] = consensus_for_family(family_results, family, minimum)
            successful = has_tunnel_connectivity(observer_results)
            latency_samples = [
                result.latency_ms
                for result in observer_results
                if result.success and result.latency_ms is not None
            ]
            latency = summarize_latency(latency_samples)
            throughput = {"throughput_bps": None, "measurement_method": None}
            if tester_settings.get("throughput_enabled"):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    throughput = {"throughput_bps": None, "measurement_method": None}
                else:
                    try:
                        throughput = measure_throughput(
                            tester_settings["throughput_url"],
                            port,
                            int(tester_settings.get("throughput_max_bytes", 1048576)),
                            max(1, min(int(tester_settings.get("throughput_timeout_seconds", 10)), int(remaining))),
                        )
                    except (requests.RequestException, ValueError):
                        throughput = {"throughput_bps": None, "measurement_method": "failed"}
            result = {
                "test_id": test_id,
                "run_id": run_id,
                "config_id": config.config_id,
                "started_at": started_at,
                "finished_at": iso_utc(),
                "xray_version": tester_settings["xray_version"],
                "connectivity": "connected" if successful else "failed",
                "ip_observation": families,
                "metrics": {
                    **latency,
                    "throughput_bps": throughput.get("throughput_bps"),
                    "throughput_downloaded_bytes": throughput.get("downloaded_bytes"),
                    "measurement_method": {
                        "latency": "observer_http_round_trip",
                        "throughput": throughput.get("measurement_method"),
                    },
                    "measured_at": iso_utc(),
                },
                "error_code": None if successful else "IP_OBSERVER_QUORUM_FAILED",
            }
            return result
        except XrayConfigError as exc:
            raise XrayTestError(str(exc)) from exc
        except (requests.RequestException, ValueError) as exc:
            raise XrayTestError("XRAY_TEST_STAGE_FAILED") from exc
        finally:
            if process is not None and process.poll() is None:
                if os.name == "posix":
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass  # noqa: B110 - the process group has already exited.
                else:
                    process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    if os.name == "posix":
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    else:
                        process.kill()
                    process.wait(timeout=3)
