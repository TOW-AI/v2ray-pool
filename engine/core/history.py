"""Append Run records, build UTC rollups, and archive old history safely."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from engine.core.state import atomic_write_json
from engine.models import iso_utc


def load_history(data_root: Path) -> dict[str, dict[str, list[dict]]]:
    result: dict[str, dict[str, list[dict]]] = {"daily": {}, "weekly": {}, "monthly": {}}
    for period in result:
        folder = data_root / "history" / period
        if not folder.exists():
            continue
        for path in folder.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                entries = payload.get("runs", [])
                if isinstance(entries, list):
                    result[period][path.stem] = entries
            except (OSError, json.JSONDecodeError, AttributeError) as exc:
                raise ValueError(f"History file is invalid: {path.name}") from exc
    return result


def append_run_history(
    root: Path,
    existing: dict,
    run_summary: dict[str, Any],
    run_time: datetime,
    retention: dict[str, int] | None = None,
) -> None:
    stamp = run_time.astimezone(UTC)
    day_key = stamp.strftime("%Y-%m-%d")
    daily = {key: list(value) for key, value in existing.get("daily", {}).items()}
    daily.setdefault(day_key, [])
    if not any(item.get("run_id") == run_summary["run_id"] for item in daily[day_key]):
        daily[day_key].append(run_summary)
    weekly_items: dict[str, list[dict]] = defaultdict(list)
    monthly_items: dict[str, list[dict]] = defaultdict(list)
    for key, runs in daily.items():
        try:
            parsed_day = datetime.strptime(key, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            continue
        year, week, _ = parsed_day.isocalendar()
        weekly_items[f"{year}-W{week:02d}"].extend(runs)
        monthly_items[parsed_day.strftime("%Y-%m")].extend(runs)

    # Keep prior rollup evidence when older daily files have moved to the archive.
    for key, previous_runs in existing.get("weekly", {}).items():
        weekly_items[key] = _merge_runs(previous_runs, weekly_items.get(key, []))
    for key, previous_runs in existing.get("monthly", {}).items():
        monthly_items[key] = _merge_runs(previous_runs, monthly_items.get(key, []))

    history_root = root / "history"
    daily_root = history_root / "daily"
    daily_root.mkdir(parents=True, exist_ok=True)
    for key, runs in sorted(daily.items()):
        atomic_write_json(
            daily_root / f"{key}.json",
            {
                "schema_version": "1.0.0",
                "period": key,
                "generated_at": iso_utc(),
                "run_count": len(runs),
                "runs": sorted(runs, key=lambda item: item.get("started_at", "")),
            },
        )
    _write_rollups(history_root / "weekly", weekly_items, "week")
    _write_rollups(history_root / "monthly", monthly_items, "month")
    if retention:
        archive_expired_history(history_root, stamp, retention)


def _merge_runs(*groups: list[dict]) -> list[dict]:
    """Merge Run records by stable ID and preserve append-only evidence."""
    merged: dict[str, dict] = {}
    for group in groups:
        for item in group:
            run_id = str(item.get("run_id", ""))
            if run_id:
                merged.setdefault(run_id, item)
    return list(merged.values())


def _write_rollups(folder: Path, grouped: dict[str, list[dict]], label: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for key, runs in sorted(grouped.items()):
        status_counts: Counter = Counter()
        for run in runs:
            for status, count in run.get("statuses", {}).items():
                status_counts[status] += int(count)
        atomic_write_json(
            folder / f"{key}.json",
            {
                "schema_version": "1.0.0",
                "period_type": label,
                "period": key,
                "generated_at": iso_utc(),
                "run_count": len(runs),
                "status_run_totals": dict(sorted(status_counts.items())),
                "runs": sorted(runs, key=lambda item: item.get("started_at", "")),
            },
        )


def _period_start(period: str, key: str) -> date:
    if period == "daily":
        return date.fromisoformat(key)
    if period == "monthly":
        year, month = (int(part) for part in key.split("-", 1))
        return date(year, month, 1)
    year_text, week_text = key.split("-W", 1)
    return date.fromisocalendar(int(year_text), int(week_text), 1)


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _hash_gzip(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with gzip.open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _archive_entry(history_root: Path, period: str, source: Path, manifest: Path) -> None:
    digest, raw_size = _hash_file(source)
    archive_dir = history_root / "archive" / period
    archive_dir.mkdir(parents=True, exist_ok=True)
    destination = archive_dir / f"{source.name}.gz"
    if destination.exists():
        archived_digest, archived_size = _hash_gzip(destination)
        if archived_digest != digest or archived_size != raw_size:
            raise ValueError(f"History archive conflict: {destination.name}")
    else:
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        with source.open("rb") as source_stream, temporary.open("wb") as raw_stream:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw_stream, compresslevel=9, mtime=0) as stream:
                shutil.copyfileobj(source_stream, stream, length=1024 * 1024)
        archived_digest, archived_size = _hash_gzip(temporary)
        if archived_digest != digest or archived_size != raw_size:
            temporary.unlink(missing_ok=True)
            raise ValueError(f"History archive verification failed: {destination.name}")
        os.replace(temporary, destination)

    entry = {
        "path": f"{period}/{source.name}",
        "archive": str(destination.relative_to(history_root / "archive")),
        "sha256": digest,
        "size_bytes": raw_size,
        "archived_at": iso_utc(),
    }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    existing = set()
    if manifest.exists():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    existing.add(json.loads(line).get("path"))
                except json.JSONDecodeError as exc:
                    raise ValueError("History archive manifest is invalid.") from exc
    if entry["path"] not in existing:
        with manifest.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    source.unlink()


def archive_expired_history(history_root: Path, now: datetime, retention: dict[str, int]) -> int:
    """Compress expired history, verify its hash, then remove the hot copy."""
    month_index = now.year * 12 + now.month - 1 - int(retention["monthly_retention_months"])
    monthly_cutoff = date(month_index // 12, month_index % 12 + 1, 1)
    rules = {
        "daily": now.date() - timedelta(days=int(retention["daily_retention_days"])),
        "weekly": now.date() - timedelta(weeks=int(retention["weekly_retention_weeks"])),
        "monthly": monthly_cutoff,
    }
    manifest = history_root / "archive" / "manifest.jsonl"
    archived_count = 0
    for period, cutoff in rules.items():
        folder = history_root / period
        if not folder.exists():
            continue
        for source in sorted(folder.glob("*.json")):
            try:
                start = _period_start(period, source.stem)
            except (ValueError, TypeError):
                continue
            if start < cutoff:
                _archive_entry(history_root, period, source, manifest)
                archived_count += 1
    return archived_count


def verify_history_archives(history_root: Path) -> dict[str, int | str]:
    manifest = history_root / "archive" / "manifest.jsonl"
    if not manifest.exists():
        return {"status": "valid", "entries": 0}
    try:
        entries = [
            json.loads(line)
            for line in manifest.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("History archive manifest is invalid.") from exc
    archive_root = (history_root / "archive").resolve()
    checked = 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("History archive manifest entry is invalid.")
        archive_name = entry.get("archive")
        digest_expected = entry.get("sha256")
        size_expected = entry.get("size_bytes")
        if (
            not isinstance(archive_name, str)
            or not archive_name
            or "\\" in archive_name
            or not isinstance(digest_expected, str)
            or len(digest_expected) != 64
            or any(char not in "0123456789abcdef" for char in digest_expected.lower())
            or not isinstance(size_expected, int)
            or size_expected < 0
        ):
            raise ValueError("History archive manifest entry is invalid.")
        relative = Path(archive_name)
        if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
            raise ValueError("History archive path is not safe.")
        archive = (archive_root / relative).resolve()
        if archive != archive_root and archive_root not in archive.parents:
            raise ValueError("History archive path is not safe.")
        digest, size = _hash_gzip(archive)
        if digest != digest_expected.lower() or size != size_expected:
            raise ValueError(f"History archive integrity failure: {archive_name}")
        checked += 1
    return {"status": "valid", "entries": checked}
