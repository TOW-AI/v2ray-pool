"""Validate local publishing paths before a data-branch commit."""

from __future__ import annotations

from pathlib import Path


def validate_publish_paths(snapshot: str | Path, repository: str | Path, branch: str) -> tuple[Path, Path]:
    source = Path(snapshot).resolve()
    target = Path(repository).resolve()
    if not source.is_dir() or not target.is_dir():
        raise ValueError("Snapshot and repository paths must exist.")
    if source == target or source in target.parents or target in source.parents:
        raise ValueError("Snapshot and repository paths must be separate.")
    if branch != "data":
        raise ValueError("Only the data branch is a valid publication target.")
    if not (target / ".git").exists():
        raise ValueError("Publication target is not a Git work tree.")
    return source, target
