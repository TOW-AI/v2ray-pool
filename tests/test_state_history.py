from datetime import UTC, datetime
import json

import pytest

from engine.core.history import append_run_history, load_history
from engine.core.state import StateStore


def test_state_store_round_trip(tmp_path):
    state = {
        "configs": {"sha256:test": {"config_id": "sha256:test", "status": "DISCOVERED"}},
        "observations": [{"observation_id": "obs-1", "run_id": "run-1"}],
        "transitions": [],
        "metrics": {"sha256:test": {"latency_ms": None}},
    }
    StateStore.save(state, tmp_path)
    restored = StateStore(tmp_path).load()
    assert restored == state


def test_history_is_idempotent_and_builds_utc_rollups(tmp_path):
    summary = {
        "run_id": "run-1",
        "started_at": "2026-02-01T00:00:00Z",
        "finished_at": "2026-02-01T00:01:00Z",
        "statuses": {"FIXED_VERIFIED": 2},
    }
    stamp = datetime(2026, 2, 1, 0, 1, tzinfo=UTC)
    append_run_history(tmp_path, load_history(tmp_path), summary, stamp)
    append_run_history(tmp_path, load_history(tmp_path), summary, stamp)
    history = load_history(tmp_path)
    assert len(history["daily"]["2026-02-01"]) == 1
    weekly = json.loads((tmp_path / "history/weekly/2026-W05.json").read_text())
    monthly = json.loads((tmp_path / "history/monthly/2026-02.json").read_text())
    assert weekly["run_count"] == monthly["run_count"] == 1
    assert weekly["status_run_totals"]["FIXED_VERIFIED"] == 2


def test_expired_history_is_archived_and_verified(tmp_path):
    from engine.core.history import archive_expired_history, verify_history_archives

    history = tmp_path / "history"
    daily = history / "daily"
    daily.mkdir(parents=True)
    source = daily / "2020-01-01.json"
    payload = {"schema_version": "1.0.0", "period": "2020-01-01", "runs": []}
    source.write_text(json.dumps(payload), encoding="utf-8")
    archived = archive_expired_history(
        history,
        datetime(2026, 1, 1, tzinfo=UTC),
        {"daily_retention_days": 30, "weekly_retention_weeks": 10, "monthly_retention_months": 12},
    )
    assert archived == 1
    assert not source.exists()
    report = verify_history_archives(history)
    assert report == {"status": "valid", "entries": 1}


def test_history_archive_detects_missing_archive(tmp_path):
    from engine.core.history import verify_history_archives

    history = tmp_path / "history"
    archive = history / "archive" / "daily"
    archive.mkdir(parents=True)
    manifest = history / "archive" / "manifest.jsonl"
    manifest.write_text(
        json.dumps({"archive": "daily/missing.json.gz", "sha256": "0" * 64, "size_bytes": 5}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(OSError):
        verify_history_archives(history)


def test_history_archive_rejects_path_traversal(tmp_path):
    from engine.core.history import verify_history_archives

    history = tmp_path / "history"
    archive = history / "archive"
    archive.mkdir(parents=True)
    (tmp_path / "outside.gz").write_bytes(b"not an archive")
    (archive / "manifest.jsonl").write_text(
        json.dumps({"archive": "../outside.gz", "sha256": "0" * 64, "size_bytes": 1}) + "\n",
        encoding="utf-8",
    )
    try:
        verify_history_archives(history)
    except ValueError as exc:
        assert "not safe" in str(exc)
    else:
        raise AssertionError("Archive path traversal must fail verification")


def test_rollups_keep_archived_daily_run_evidence(tmp_path):
    from engine.core.history import archive_expired_history

    first = {
        "run_id": "run-first",
        "started_at": "2026-01-05T00:00:00Z",
        "finished_at": "2026-01-05T00:01:00Z",
        "statuses": {"TESTED": 1},
    }
    second = {
        "run_id": "run-second",
        "started_at": "2026-01-06T00:00:00Z",
        "finished_at": "2026-01-06T00:01:00Z",
        "statuses": {"TESTED": 1},
    }
    root = tmp_path / "data"
    append_run_history(root, load_history(root), first, datetime(2026, 1, 5, 0, 1, tzinfo=UTC))

    daily = root / "history" / "daily" / "2026-01-05.json"
    assert daily.is_file()
    archive_expired_history(
        root / "history",
        datetime(2026, 2, 1, tzinfo=UTC),
        {"daily_retention_days": 1, "weekly_retention_weeks": 52, "monthly_retention_months": 12},
    )
    assert not daily.exists()

    append_run_history(root, load_history(root), second, datetime(2026, 1, 6, 0, 1, tzinfo=UTC))
    weekly = json.loads((root / "history" / "weekly" / "2026-W02.json").read_text())
    monthly = json.loads((root / "history" / "monthly" / "2026-01.json").read_text())
    assert {item["run_id"] for item in weekly["runs"]} == {"run-first", "run-second"}
    assert {item["run_id"] for item in monthly["runs"]} == {"run-first", "run-second"}
