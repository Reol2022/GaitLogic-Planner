import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "security" / "check_public_boundary.py"


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def test_public_boundary_check_reports_staged_secret(tmp_path):
    git(tmp_path, "init")
    token = "abcdefgh" + "ijklmnop"
    (tmp_path / "notes.txt").write_text(f'access_token="{token}"', encoding="utf-8")
    git(tmp_path, "add", "notes.txt")
    result = subprocess.run([sys.executable, str(SCRIPT), "--repo-root", str(tmp_path)], text=True, capture_output=True, check=False)
    assert result.returncode == 2
    assert "credential or token literal" in result.stdout
