"""M0 checks: version string, budgets (spec 01 section 5) and spec sync."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from sayform import __version__
from sayform.cli import main, version_text

ROOT = Path(__file__).resolve().parents[1]


def test_version(capsys: object) -> None:
    assert main(["--version"]) == 0
    assert version_text().startswith(f"say {__version__} (spec 0.1-lite, edition 0")


def run_tool(name: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(ROOT / "tools" / name)], capture_output=True, text=True, check=False)


def test_budgets_hold() -> None:
    r = run_tool("check_budgets.py")
    assert r.returncode == 0, r.stdout


def test_spec_in_sync() -> None:
    r = run_tool("check_spec_sync.py")
    assert r.returncode == 0, r.stdout
