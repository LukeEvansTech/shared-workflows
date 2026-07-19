"""Tests for zensical_drift.py."""

import subprocess
from pathlib import Path

import pytest  # pylint: disable=import-error  # present at runtime, not in the lint env

SCRIPT = Path(__file__).parent / "zensical_drift.py"
FIXTURES = Path(__file__).parent.parent / "tests" / "fixtures" / "zensical"


def run_drift(fixture_name: str, *extra_args: str) -> subprocess.CompletedProcess:
    """Run zensical_drift.py in the given fixture directory."""
    return subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--repo-root",
            str(FIXTURES / fixture_name),
            *extra_args,
        ],
        capture_output=True,
        text=True,
    )


def test_loose_pin_fails():
    result = run_drift("bad-loose-pin")
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert "[pin]" in out
    assert "exact version" in out or "zensical==" in out


def test_flat_toggle_fails():
    result = run_drift("bad-flat-toggle")
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert "[palette]" in out
    assert "nested" in out.lower() and "toggle" in out.lower()


def test_missing_media_fails():
    result = run_drift("bad-missing-media")
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert "[palette]" in out
    assert "prefers-color-scheme" in out


def test_no_palette_fails():
    result = run_drift("bad-no-palette")
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert "[palette]" in out
    assert "2 [[project.theme.palette]] entries" in out or "need at least" in out


def test_good_fixture_passes_palette_only():
    result = run_drift("good")
    out = result.stdout + result.stderr
    assert "[palette]" not in out


def test_tag_pinned_workflow_fails():
    result = run_drift("bad-tag-pinned")
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert "[workflows]" in out
    assert "SHA-pinned" in out or "must be SHA-pinned" in out or "@v1" in out


def test_uppercase_host_fails():
    result = run_drift("bad-uppercase-host")
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert "[site_url]" in out
    assert "lowercase" in out or "host" in out.lower()


def test_renovate_missing_shared_config_fails():
    result = run_drift("bad-renovate")
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert "renovate" in out.lower()
    assert "github>LukeEvansTech/renovate-config" in out or "renovate-config" in out


def test_markdownlint_hash_mismatch_fails():
    result = run_drift("bad-markdownlint")
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert "markdownlint" in out.lower()


def test_good_fixture_passes_overall():
    result = run_drift("good")
    msg = f"good fixture should pass:\n{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, msg


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
        [
            "python3",
            str(SCRIPT),
            "--repo-root",
            str(FIXTURES / "good"),
            "--repo",
            "LukeEvansTech/M365LabelSync",
        ],
        capture_output=True,
        text=True,
    )
    assert "[pages]" not in (result.stdout + result.stderr)


@pytest.mark.skipif(not has_gh(), reason="gh CLI not available in this env")
def test_pages_check_allow_no_pages():
    """With --allow-no-pages, an empty Pages response should not fail."""
    result = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--repo-root",
            str(FIXTURES / "good"),
            "--repo",
            "LukeEvansTech/lgwebos",
            "--allow-no-pages",
        ],
        capture_output=True,
        text=True,
    )
    assert "[pages]" not in (result.stdout + result.stderr)


def test_theme_baseline_fails():
    result = run_drift("bad-theme")
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert "[theme]" in out
    assert "theme.name" in out


def test_layout_fails():
    result = run_drift("bad-layout")
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert "[layout]" in out
    assert "docs/docs" in out


# --- check_renovate unit tests: filename acceptance + JSON5 tolerance ---
import zensical_drift

CENTRAL = '{"extends": ["github>LukeEvansTech/renovate-config"]}'


def _run_check_renovate(tmp_path, files):
    """Write {filename: content} into tmp_path, run check_renovate in isolation,
    and return the resulting failure annotations."""
    for name, content in files.items():
        (tmp_path / name).write_text(content)
    zensical_drift.FAILURES = []
    zensical_drift.check_renovate(tmp_path)
    return zensical_drift.FAILURES


def test_renovate_accepts_renovaterc_json5(tmp_path):
    assert _run_check_renovate(tmp_path, {".renovaterc.json5": CENTRAL}) == []


def test_renovate_accepts_json5_with_comments_and_trailing_comma(tmp_path):
    content = '{\n  // house standard\n  "extends": ["github>LukeEvansTech/renovate-config"],\n}\n'
    assert _run_check_renovate(tmp_path, {".renovaterc.json5": content}) == []


def test_renovate_accepts_legacy_renovate_json(tmp_path):
    assert _run_check_renovate(tmp_path, {"renovate.json": CENTRAL}) == []


def test_renovate_missing_any_config_fails(tmp_path):
    failures = _run_check_renovate(tmp_path, {})
    assert failures and "no Renovate config" in failures[0]


def test_renovate_not_extending_central_fails(tmp_path):
    failures = _run_check_renovate(
        tmp_path, {".renovaterc.json5": '{"extends": ["config:recommended"]}'}
    )
    assert failures and "renovate-config" in failures[0]


def test_renovate_dual_config_fails(tmp_path):
    failures = _run_check_renovate(
        tmp_path, {".renovaterc.json5": CENTRAL, "renovate.json": CENTRAL}
    )
    assert failures and "multiple Renovate config" in failures[0]


def test_renovate_url_with_comment_parses_not_fallback(tmp_path):
    # Comment + https:// URL + non-central extends. Must FAIL via the parse path
    # ("extends must include"), proving the `//` in the URL is not stripped as a
    # comment (which would force the weaker substring fallback).
    content = (
        "{\n"
        "  // the :// in the schema URL must survive comment-stripping\n"
        '  "$schema": "https://docs.renovatebot.com/renovate-schema.json",\n'
        '  "extends": ["config:recommended"],\n'
        "}\n"
    )
    failures = _run_check_renovate(tmp_path, {".renovaterc.json5": content})
    assert failures and "extends must include" in failures[0]


def test_renovate_accepts_house_idiom_unquoted_keys(tmp_path):
    # Prettier's JSON5 idiom for the fleet: unquoted keys + trailing comma.
    content = (
        "{\n"
        '  $schema: "https://docs.renovatebot.com/renovate-schema.json",\n'
        '  extends: ["github>LukeEvansTech/renovate-config"],\n'
        "}\n"
    )
    assert _run_check_renovate(tmp_path, {".renovaterc.json5": content}) == []


def test_strip_jsonc_is_string_aware():
    """`/*` inside a string + `*/` inside a later comment must not pair up.

    Regression: talos-cluster's `ignorePaths: [".archive/**"]` (line 3) plus a
    `kubernetes/**/...` glob mentioned in a much later `//` comment made the old
    regex-based stripper swallow everything between them — including the
    `extends` line — failing check_renovate on an otherwise-valid config.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("zensical_drift", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    sample = """{
  ignorePaths: [".archive/**"],
  extends: ["github>LukeEvansTech/renovate-config"],
  // per-app twins in kubernetes/**/ocirepository.yaml are exempt
  rebaseWhen: "conflicted", /* real block comment */
}"""
    stripped = mod._strip_jsonc(sample)  # pylint: disable=protected-access
    assert "github>LukeEvansTech/renovate-config" in stripped
    import json

    data = json.loads(stripped)
    assert data["ignorePaths"] == [".archive/**"]
    assert data["extends"] == ["github>LukeEvansTech/renovate-config"]
    assert "real block comment" not in stripped

    # URLs inside strings keep their `//`
    url = mod._strip_jsonc(
        '{ $schema: "https://example.com/x.json" }'
    )  # pylint: disable=protected-access
    assert "https://example.com/x.json" in url
