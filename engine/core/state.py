"""Load and save State and append-only IP evidence."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temp_path.replace(path)
        if os.name == "posix":
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return default or {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"State file is not valid JSON: {path.name}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"State file root must be an object: {path.name}")
    version = payload.get("schema_version")
    if version and str(version).split(".")[0] != SCHEMA_VERSION.split(".")[0]:
        raise ValueError(f"Unsupported state schema version in {path.name}: {version}")
    return payload


class StateStore:
    def __init__(self, data_root: str | Path):
        self.data_root = Path(data_root)
        self.state_root = self.data_root / "state"

    def load(self) -> dict[str, Any]:
        configs = read_json(self.state_root / "configs.json", {"schema_version": SCHEMA_VERSION, "records": {}})
        ip_history = read_json(
            self.state_root / "ip-history.json",
            {"schema_version": SCHEMA_VERSION, "observations": [], "transitions": []},
        )
        metrics = read_json(self.state_root / "metrics.json", {"schema_version": SCHEMA_VERSION, "records": {}})
        records = configs.get("records", {})
        observations = ip_history.get("observations", [])
        transitions = ip_history.get("transitions", [])
        metric_records = metrics.get("records", {})
        if not isinstance(records, dict) or not isinstance(observations, list) or not isinstance(transitions, list):
            raise ValueError("State structure is invalid.")
        return {
            "configs": records,
            "observations": observations,
            "transitions": transitions,
            "metrics": metric_records,
        }

    @staticmethod
    def save(state: dict[str, Any], output_data_root: str | Path) -> None:
        root = Path(output_data_root) / "state"
        atomic_write_json(
            root / "configs.json",
            {"schema_version": SCHEMA_VERSION, "generated_at": _now(), "records": state["configs"]},
        )
        atomic_write_json(
            root / "ip-history.json",
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": _now(),
                "observations": state["observations"],
                "transitions": state["transitions"],
            },
        )
        atomic_write_json(
            root / "metrics.json",
            {"schema_version": SCHEMA_VERSION, "generated_at": _now(), "records": state["metrics"]},
        )


def _now() -> str:
    from engine.models import iso_utc

    return iso_utc()
