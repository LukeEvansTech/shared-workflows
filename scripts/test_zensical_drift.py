"""Tests for zensical_drift.py."""
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "zensical_drift.py"
FIXTURES = Path(__file__).parent.parent / "tests" / "fixtures" / "zensical"


def run_drift(fixture_name: str, *extra_args: str) -> subprocess.CompletedProcess:
    """Run zensical_drift.py in the given fixture directory."""
    return subprocess.run(
        ["python3", str(SCRIPT), "--repo-root", str(FIXTURES / fixture_name), *extra_args],
        capture_output=True,
        text=True,
    )


def test_loose_pin_fails():
    result = run_drift("bad-loose-pin")
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert "requirements.txt" in out
    assert "zensical>=" in out or "must use ==" in out or "exact version" in out


def test_flat_toggle_fails():
    result = run_drift("bad-flat-toggle")
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert "toggle" in out.lower()
    assert "nested" in out.lower() or "flat" in out.lower()


def test_missing_media_fails():
    result = run_drift("bad-missing-media")
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert "media" in out.lower() or "prefers-color-scheme" in out.lower()


def test_no_palette_fails():
    result = run_drift("bad-no-palette")
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert "palette" in out.lower()


def test_good_fixture_passes_palette_only():
    result = run_drift("good")
    out = result.stdout + result.stderr
    assert "[palette]" not in out
