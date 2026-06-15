#!/usr/bin/env python3
"""Drift check for zensical docs standard.

Run with --repo-root <path> to check a target repo's conformance.
Emits GitHub annotations and exits non-zero on any violation.

Spec: docs/superpowers/specs/2026-05-26-zensical-docs-standard-design.md
"""

from __future__ import annotations

import argparse
import hashlib
import json as _json
import re
import subprocess
import sys
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

FAILURES: list[str] = []


def fail(check: str, file: str, message: str) -> None:
    FAILURES.append(f"::error file={file}::[{check}] {message}")
    print(f"FAIL [{check}] {file}: {message}", file=sys.stderr)


def check_pin(repo_root: Path) -> None:
    req = repo_root / "docs" / "requirements.txt"
    if not req.exists():
        fail("pin", str(req), "docs/requirements.txt is missing")
        return
    lines = [
        ln.strip()
        for ln in req.read_text().splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
    if not lines:
        fail("pin", str(req), "docs/requirements.txt has no non-comment lines")
        return
    if len(lines) > 1:
        fail(
            "pin",
            str(req),
            f"docs/requirements.txt should contain only `zensical==X.Y.Z`; found {len(lines)} non-comment lines",
        )
        return
    pin = lines[0]
    if not re.fullmatch(r"zensical==\d+\.\d+\.\d+", pin):
        fail(
            "pin",
            str(req),
            f"pin must use exact version (`zensical==X.Y.Z`); found `{pin}`",
        )


def check_palette(repo_root: Path) -> None:
    cfg = repo_root / "docs" / "zensical.toml"
    if not cfg.exists():
        fail("palette", str(cfg), "docs/zensical.toml is missing")
        return
    text = cfg.read_text()

    # Required: at least one [[project.theme.palette]] with prefers-color-scheme: light, one with dark
    # Use simple substring matching: find [[project.theme.palette]] headers and check content between them
    palette_blocks = re.findall(
        r"\[\[project\.theme\.palette\]\](.*?)(?=\[\[project\.theme\.palette\]\]|\Z)",
        text,
        re.DOTALL,
    )
    if len(palette_blocks) < 2:
        fail(
            "palette",
            str(cfg),
            f"need at least 2 [[project.theme.palette]] entries, found {len(palette_blocks)}",
        )
        return

    has_light = any(
        'media = "(prefers-color-scheme: light)"' in b for b in palette_blocks
    )
    has_dark = any(
        'media = "(prefers-color-scheme: dark)"' in b for b in palette_blocks
    )
    if not has_light:
        fail(
            "palette",
            str(cfg),
            'no palette entry with `media = "(prefers-color-scheme: light)"`',
        )
    if not has_dark:
        fail(
            "palette",
            str(cfg),
            'no palette entry with `media = "(prefers-color-scheme: dark)"`',
        )

    # Forbidden: flat toggle_icon / toggle_name keys at palette entry level
    if re.search(r"^\s*toggle_icon\s*=", text, re.M) or re.search(
        r"^\s*toggle_name\s*=", text, re.M
    ):
        fail(
            "palette",
            str(cfg),
            "use nested [project.theme.palette.toggle] table; flat toggle_icon/toggle_name does not render the toggle button",
        )

    # Required: each [[project.theme.palette]] must be followed by a [project.theme.palette.toggle] table
    toggle_tables = re.findall(r"\[project\.theme\.palette\.toggle\]", text)
    if len(toggle_tables) < 2:
        fail(
            "palette",
            str(cfg),
            f"need a [project.theme.palette.toggle] table for each palette entry; found {len(toggle_tables)}",
        )


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
            fail(
                "workflows",
                str(wf),
                f"`{wf_name}` must call `{display}@<SHA>` (40-hex SHA-pinned)",
            )
        # SHA-pinning check: every `uses:` line must reference a 40-hex SHA (not a tag)
        for line_num, line in enumerate(text.splitlines(), 1):
            m = re.match(r"\s*uses:\s*([^\s#]+)", line)
            if not m:
                continue
            ref = m.group(1)
            if "@" not in ref:
                fail("workflows", f"{wf}:{line_num}", f"uses without ref: {ref}")
                continue
            tag_part = ref.split("@", 1)[1]
            if not re.fullmatch(r"[a-f0-9]{40}", tag_part):
                fail(
                    "workflows",
                    f"{wf}:{line_num}",
                    f"action must be SHA-pinned (40-hex); found `@{tag_part}`",
                )


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
            fail(
                "site_url", str(cfg), f"site_url host must be lowercase; found `{host}`"
            )
        if "lukevanstech" in host.lower() and "lukeevanstech" not in host.lower():
            fail(
                "site_url",
                str(cfg),
                f"site_url has typo `lukevanstech` (should be `lukeevanstech`); found `{host}`",
            )


def check_theme_baseline(repo_root: Path) -> None:
    cfg = repo_root / "docs" / "zensical.toml"
    if not cfg.exists():
        return
    text = cfg.read_text()
    if not re.search(r'^\s*name\s*=\s*"material"', text, re.M):
        fail("theme", str(cfg), 'theme.name must be "material"')
    if not re.search(r'^\s*variant\s*=\s*"modern"', text, re.M):
        fail("theme", str(cfg), 'theme.variant must be "modern"')
    if not re.search(r'^\s*language\s*=\s*"en"', text, re.M):
        fail("theme", str(cfg), 'theme.language must be "en"')


def check_layout(repo_root: Path) -> None:
    if not (repo_root / "docs" / "docs").is_dir():
        fail(
            "layout",
            str(repo_root / "docs" / "docs"),
            "docs/docs/ directory is missing (canonical content path)",
        )


# Accepted Renovate config filenames, in preference order. `.renovaterc.json5`
# is the house standard (permits comments); `renovate.json` is the legacy name
# kept for back-compat during the fleet migration.
RENOVATE_CONFIG_NAMES = (".renovaterc.json5", "renovate.json")
CENTRAL_PRESET = "github>LukeEvansTech/renovate-config"


def _strip_jsonc(text: str) -> str:
    """Best-effort JSON5/JSONC → JSON so stdlib json can parse it.

    Handles the house `.renovaterc.json5` idiom (prettier-formatted): `//` line
    comments, `/* */` block comments, trailing commas, and unquoted identifier
    keys. Keys with non-identifier characters are already quoted in valid JSON5;
    check_renovate falls back to a substring check if a parse still fails.
    """
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)  # block comments
    # line comments — `(?<!:)` so we don't eat the `//` in `https://` URLs
    text = re.sub(r"(?m)(?<!:)//[^\n]*$", "", text)
    text = re.sub(r",(\s*[}\]])", r"\1", text)  # trailing commas
    # quote unquoted identifier keys: `  extends:` -> `  "extends":`
    text = re.sub(r"(?m)^(\s*)([A-Za-z_$][A-Za-z0-9_$]*)(\s*:)", r'\1"\2"\3', text)
    return text


def check_renovate(repo_root: Path) -> None:
    found = [
        repo_root / name
        for name in RENOVATE_CONFIG_NAMES
        if (repo_root / name).exists()
    ]
    if not found:
        fail(
            "renovate",
            str(repo_root / RENOVATE_CONFIG_NAMES[0]),
            "no Renovate config found (expected `.renovaterc.json5` or legacy `renovate.json`)",
        )
        return
    if len(found) > 1:
        names = ", ".join(p.name for p in found)
        fail(
            "renovate",
            str(found[0]),
            f"multiple Renovate config files found ({names}); keep exactly one "
            "(`.renovaterc.json5` preferred) — Renovate errors on duplicate configs",
        )
        return
    r = found[0]
    raw = r.read_text()
    data = None
    for candidate in (raw, _strip_jsonc(raw)):
        try:
            data = _json.loads(candidate)
            break
        except _json.JSONDecodeError:
            continue
    if data is not None:
        if CENTRAL_PRESET not in data.get("extends", []):
            fail(
                "renovate",
                str(r),
                f"extends must include `{CENTRAL_PRESET}` "
                "(the shared config; it bundles config:recommended and "
                "pinGitHubActionDigests via home-operations/renovate-presets)",
            )
        return
    # Could not parse even after stripping comments (e.g. unquoted JSON5 keys):
    # fall back to a textual check for the preset reference in the de-commented body.
    if CENTRAL_PRESET not in _strip_jsonc(raw):
        fail(
            "renovate",
            str(r),
            f"`{r.name}` is not parseable and does not reference `{CENTRAL_PRESET}`",
        )


def check_markdownlint(repo_root: Path) -> None:
    ml = repo_root / ".markdownlint.yml"
    canonical = TEMPLATES_DIR / ".markdownlint.yml"
    if not ml.exists():
        fail("markdownlint", str(ml), ".markdownlint.yml is missing at repo root")
        return
    if not canonical.exists():
        print(
            f"::warning::canonical .markdownlint.yml not found at {canonical}; hash check skipped",
            file=sys.stderr,
        )
        return
    if (
        hashlib.sha256(ml.read_bytes()).hexdigest()
        != hashlib.sha256(canonical.read_bytes()).hexdigest()
    ):
        fail(
            "markdownlint",
            str(ml),
            "content differs from canonical templates/.markdownlint.yml; run scripts/sync_markdownlint.py",
        )


def check_pages(
    repo: str | None, allow_no_pages: bool, allow_build_type_legacy: bool
) -> None:
    if not repo:
        return
    try:
        r = subprocess.run(
            ["gh", "api", f"repos/{repo}/pages"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        print("::warning::gh CLI not found; pages check skipped", file=sys.stderr)
        return
    except subprocess.TimeoutExpired:
        fail("pages", f"repos/{repo}/pages", "gh CLI timed out after 30s")
        return
    if r.returncode != 0:
        if allow_no_pages:
            return
        fail(
            "pages",
            f"repos/{repo}/pages",
            "Pages is not enabled (pass --allow-no-pages for build-only repos)",
        )
        return
    try:
        data = _json.loads(r.stdout)
    except _json.JSONDecodeError:
        fail("pages", f"repos/{repo}/pages", "could not parse Pages API response")
        return
    build_type = data.get("build_type")
    if build_type == "legacy" and not allow_build_type_legacy:
        fail(
            "pages",
            f"repos/{repo}/pages",
            "Pages build_type is `legacy`; standard requires `workflow`",
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--repo", help="owner/name for Pages API check (optional)")
    parser.add_argument("--allow-no-pages", action="store_true")
    parser.add_argument("--allow-build-type-legacy", action="store_true")
    args = parser.parse_args()
    check_pin(args.repo_root)
    check_palette(args.repo_root)
    check_theme_baseline(args.repo_root)
    check_layout(args.repo_root)
    check_workflows(args.repo_root)
    check_site_url(args.repo_root)
    check_renovate(args.repo_root)
    check_markdownlint(args.repo_root)
    check_pages(args.repo, args.allow_no_pages, args.allow_build_type_legacy)
    for line in FAILURES:
        print(line)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
