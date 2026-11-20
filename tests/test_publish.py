import subprocess
from pathlib import Path


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        shell=False,
    )
    return result.stdout.strip()


def test_publisher_rejects_stale_data_branch(tmp_path):
    repo = tmp_path / "data-repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "data", str(repo)], check=True, capture_output=True)
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.invalid")
    (repo / "README.md").write_text("existing data\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "Initial data")
    original_commit = git(repo, "rev-parse", "HEAD")
    source = tmp_path / "snapshot"
    source.mkdir()
    (source / "README.md").write_text("new data\n", encoding="utf-8")

    script = Path(__file__).resolve().parents[1] / "scripts" / "publish_data.py"
    result = subprocess.run(
        [
            "python",
            str(script),
            "--source",
            str(source),
            "--repo",
            str(repo),
            "--branch",
            "data",
            "--expected-parent",
            "0" * 40,
        ],
        check=False,
        capture_output=True,
        text=True,
        shell=False,
    )
    assert result.returncode == 2
    assert "DATA_BRANCH_CHANGED_DURING_BUILD" in result.stderr
    assert git(repo, "rev-parse", "HEAD") == original_commit
    assert (repo / "README.md").read_text(encoding="utf-8") == "existing data\n"
