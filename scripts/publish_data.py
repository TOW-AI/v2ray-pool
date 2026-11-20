#!/usr/bin/env python3
"""Copy a validated snapshot to the data branch and push a normal commit."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(  # nosec B603 - fixed argument vector; shell=False
        ["git", "-C", str(repo), *args],
        check=check,
        capture_output=True,
        text=True,
        shell=False,
        timeout=120,
    )


def sync_tree(source: Path, target: Path) -> None:
    source = source.resolve()
    target = target.resolve()
    if not source.is_dir() or not target.is_dir():
        raise ValueError("Source and target must be existing directories.")
    if source == target or target in source.parents or source in target.parents:
        raise ValueError("Source and target paths must be separate.")
    if any(path.is_symlink() for path in source.rglob("*")):
        raise ValueError("Snapshot must not contain symbolic links.")

    for item in target.iterdir():
        if item.name == ".git":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
    for item in source.iterdir():
        destination = target / item.name
        if item.is_dir():
            shutil.copytree(item, destination)
        else:
            shutil.copy2(item, destination)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--branch", default="data")
    parser.add_argument("--expected-parent", default="", help="Expected data branch commit from the build job.")
    args = parser.parse_args()
    source, repo = Path(args.source), Path(args.repo)
    try:
        branch = run_git(repo, "branch", "--show-current").stdout.strip()
        if branch != args.branch:
            raise ValueError(f"Expected branch {args.branch}; found {branch or '<detached>'}.")
        if args.expected_parent:
            current_commit = run_git(repo, "rev-parse", "HEAD").stdout.strip()
            if current_commit != args.expected_parent:
                raise ValueError("DATA_BRANCH_CHANGED_DURING_BUILD: refusing to overwrite newer data.")
        sync_tree(source, repo)
        run_git(repo, "add", "--all")
        staged = run_git(repo, "diff", "--cached", "--quiet", check=False)
        if staged.returncode == 0:
            print("No data changes. Publish skipped.")
            return 0
        if staged.returncode != 1:
            raise RuntimeError("Cannot inspect the staged Git diff.")
        readme = (source / "README.md").read_text(encoding="utf-8") if (source / "README.md").is_file() else ""
        match = re.search(r"Last generated run: `([a-f0-9-]{36})` at `([0-9TZ:-]+)`", readme)
        if match:
            commit_message = f"Update data snapshot {match.group(1)} at {match.group(2)}"
        else:
            commit_message = "Update data snapshot"
        run_git(repo, "-c", "user.name=github-actions[bot]", "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com", "commit", "-m", commit_message)
        run_git(repo, "push", "origin", f"HEAD:{args.branch}")
        print("Data commit pushed without force.")
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        detail = getattr(exc, "stderr", None) or str(exc)
        print(f"Publish failed: {detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
