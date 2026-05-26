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


def test_tag_pinned_workflow_fails():
    result = run_drift("bad-tag-pinned")
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert "SHA" in out or "sha-pinn" in out.lower() or "tag-pinned" in out.lower() or "@v" in out


def test_uppercase_host_fails():
    result = run_drift("bad-uppercase-host")
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert "site_url" in out.lower() or "host" in out.lower() or "lowercase" in out.lower()


def test_renovate_missing_pin_digest_fails():
    result = run_drift("bad-renovate")
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert "renovate" in out.lower()
    assert "pinGitHubActionDigests" in out or "digest" in out.lower()


def test_markdownlint_hash_mismatch_fails():
    result = run_drift("bad-markdownlint")
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert "markdownlint" in out.lower()


def test_good_fixture_passes_overall():
    result = run_drift("good")
    assert result.returncode == 0, f"good fixture should pass; got:\n{result.stdout}\n{result.stderr}"


import shutil


def has_gh():
    return shutil.which("gh") is not None


@pytest.mark.skipif(not has_gh(), reason="gh CLI not available in this env")
def test_pages_check_skipped_when_no_repo_arg():
    result = run_drift("good")
    assert "[pages]" not in result.stdout + result.stderr


@pytest.mark.skipif(not has_gh(), reason="gh CLI not available in this env")
def test_pages_check_passes_on_known_workflow_repo():
    """Live test against M365LabelSync which has build_type=workflow as of 2026-05-26."""
    result = subprocess.run(
        ["python3", str(SCRIPT), "--repo-root", str(FIXTURES / "good"), "--repo", "LukeEvansTech/M365LabelSync"],
        capture_output=True, text=True,
    )
    assert "[pages]" not in (result.stdout + result.stderr)


@pytest.mark.skipif(not has_gh(), reason="gh CLI not available in this env")
def test_pages_check_allow_no_pages():
    """With --allow-no-pages, an empty Pages response should not fail."""
    result = subprocess.run(
        ["python3", str(SCRIPT), "--repo-root", str(FIXTURES / "good"), "--repo", "LukeEvansTech/lgwebos", "--allow-no-pages"],
        capture_output=True, text=True,
    )
    assert "[pages]" not in (result.stdout + result.stderr)
