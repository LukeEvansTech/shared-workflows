#!/usr/bin/env python3
"""Drift check for zensical docs standard.

Run with --repo-root <path> to check a target repo's conformance.
Emits GitHub annotations and exits non-zero on any violation.

Spec: docs/superpowers/specs/2026-05-26-zensical-docs-standard-design.md
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FAILURES: list[str] = []


def fail(check: str, file: str, message: str) -> None:
    FAILURES.append(f"::error file={file}::[{check}] {message}")
    print(f"FAIL [{check}] {file}: {message}", file=sys.stderr)


def check_pin(repo_root: Path) -> None:
    req = repo_root / "docs" / "requirements.txt"
    if not req.exists():
        fail("pin", str(req), "docs/requirements.txt is missing")
        return
    lines = [l.strip() for l in req.read_text().splitlines() if l.strip() and not l.startswith("#")]
    if not lines:
        fail("pin", str(req), "docs/requirements.txt has no non-comment lines")
        return
    if len(lines) > 1:
        fail("pin", str(req), f"docs/requirements.txt should contain only `zensical==X.Y.Z`; found {len(lines)} non-comment lines")
        return
    pin = lines[0]
    if not re.fullmatch(r"zensical==\d+\.\d+\.\d+", pin):
        fail("pin", str(req), f"pin must use exact version (`zensical==X.Y.Z`); found `{pin}`")


def check_palette(repo_root: Path) -> None:
    cfg = repo_root / "docs" / "zensical.toml"
    if not cfg.exists():
        fail("palette", str(cfg), "docs/zensical.toml is missing")
        return
    text = cfg.read_text()

    # Required: at least one [[project.theme.palette]] with prefers-color-scheme: light, one with dark
    # Use simple substring matching: find [[project.theme.palette]] headers and check content between them
    palette_blocks = re.findall(
        r'\[\[project\.theme\.palette\]\](.*?)(?=\[\[project\.theme\.palette\]\]|\Z)',
        text,
        re.DOTALL,
    )
    if len(palette_blocks) < 2:
        fail("palette", str(cfg), f"need at least 2 [[project.theme.palette]] entries, found {len(palette_blocks)}")
        return

    has_light = any('media = "(prefers-color-scheme: light)"' in b for b in palette_blocks)
    has_dark = any('media = "(prefers-color-scheme: dark)"' in b for b in palette_blocks)
    if not has_light:
        fail("palette", str(cfg), 'no palette entry with `media = "(prefers-color-scheme: light)"`')
    if not has_dark:
        fail("palette", str(cfg), 'no palette entry with `media = "(prefers-color-scheme: dark)"`')

    # Forbidden: flat toggle_icon / toggle_name keys at palette entry level
    if re.search(r'^\s*toggle_icon\s*=', text, re.M) or re.search(r'^\s*toggle_name\s*=', text, re.M):
        fail("palette", str(cfg), "use nested [project.theme.palette.toggle] table; flat toggle_icon/toggle_name does not render the toggle button")

    # Required: each [[project.theme.palette]] must be followed by a [project.theme.palette.toggle] table
    toggle_tables = re.findall(r'\[project\.theme\.palette\.toggle\]', text)
    if len(toggle_tables) < 2:
        fail("palette", str(cfg), f"need a [project.theme.palette.toggle] table for each palette entry; found {len(toggle_tables)}")


REQUIRED_WORKFLOWS = {
    "docs.yml": r"LukeEvansTech/shared-workflows/\.github/workflows/zensical\.yml",
    "lint.yml": r"LukeEvansTech/shared-workflows/\.github/workflows/super-linter\.yml",
    "docs-standard-check.yml": r"LukeEvansTech/shared-workflows/\.github/workflows/zensical-drift-check\.yml",
}


def check_workflows(repo_root: Path) -> None:
    wf_dir = repo_root / ".github" / "workflows"
    if not wf_dir.exists():
        fail("workflows", str(wf_dir), ".github/workflows/ missing")
        return
    for wf_name, expected_reusable in REQUIRED_WORKFLOWS.items():
        wf = wf_dir / wf_name
        if not wf.exists():
            fail("workflows", str(wf), f"required workflow `{wf_name}` is missing")
            continue
        text = wf.read_text()
        # Shape check: must call the expected reusable workflow
        if not re.search(rf"uses:\s*{expected_reusable}@[a-f0-9]{{40}}", text):
            display = expected_reusable.replace("\\", "")
            fail("workflows", str(wf), f"`{wf_name}` must call `{display}@<SHA>` (40-hex SHA-pinned)")
        # SHA-pinning check: every `uses:` line must reference a 40-hex SHA (not a tag)
        for line_num, line in enumerate(text.splitlines(), 1):
            m = re.match(r'\s*uses:\s*([^\s#]+)', line)
            if not m:
                continue
            ref = m.group(1)
            if "@" not in ref:
                fail("workflows", f"{wf}:{line_num}", f"uses without ref: {ref}")
                continue
            tag_part = ref.split("@", 1)[1]
            if not re.fullmatch(r"[a-f0-9]{40}", tag_part):
                fail("workflows", f"{wf}:{line_num}", f"action must be SHA-pinned (40-hex); found `@{tag_part}`")


def check_site_url(repo_root: Path) -> None:
    cfg = repo_root / "docs" / "zensical.toml"
    if not cfg.exists():
        return
    text = cfg.read_text()
    m = re.search(r'^\s*site_url\s*=\s*"([^"]+)"', text, re.M)
    if not m:
        return
    url = m.group(1)
    if url.startswith("http"):
        host = url.split("//", 1)[1].split("/", 1)[0]
        if host.lower() != host:
            fail("site_url", str(cfg), f"site_url host must be lowercase; found `{host}`")
        if "lukevanstech" in host.lower() and "lukeevanstech" not in host.lower():
            fail("site_url", str(cfg), f"site_url has typo `lukevanstech` (should be `lukeevanstech`); found `{host}`")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    args = parser.parse_args()
    check_pin(args.repo_root)
    check_palette(args.repo_root)
    check_workflows(args.repo_root)
    check_site_url(args.repo_root)
    for line in FAILURES:
        print(line)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
