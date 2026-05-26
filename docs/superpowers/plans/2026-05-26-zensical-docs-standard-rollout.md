# Zensical Docs Standard Rollout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Roll out the zensical docs standard (see `docs/superpowers/specs/2026-05-26-zensical-docs-standard-design.md`) to all 18 `LukeEvansTech/*` zensical docs repos: build the shared infrastructure, migrate every repo to canonical workflow + config files, enforce via PR-blocking drift check.

**Architecture:** Three pieces. (1) `LukeEvansTech/shared-workflows` hosts two new reusable workflows (`zensical.yml`, `zensical-drift-check.yml`) plus a Python drift-check script and a set of canonical template files. (2) Each of the 18 repos gets four files refreshed (`docs.yml`, `lint.yml`, `docs-standard-check.yml`, `.markdownlint.yml`) and one updated (`renovate.json`). (3) GitHub Pages settings normalised: `build_type: workflow` for the 12 publishing repos, Pages disabled for the 6 build-only repos (Pages disable already executed 2026-05-26 for the 4 private repos that had public docs).

**Tech Stack:** GitHub Actions (reusable workflows), Python 3.11+ with `tomllib` / `pyyaml` / `requests` for the drift script and rollout helpers, `gh` CLI for repo-level API operations, `pytest` for drift-script tests, `lycheeverse/lychee-action` for link checking, `errata-ai/vale-action` (opt-in, later phase).

---

## File Structure

### New files in `LukeEvansTech/shared-workflows`

| Path | Responsibility |
|---|---|
| `.github/workflows/zensical.yml` | Reusable workflow: build → optional link-check → optional vale → optional deploy |
| `.github/workflows/zensical-drift-check.yml` | Reusable workflow: PR-blocking standard enforcement (calls `scripts/zensical_drift.py`) |
| `scripts/zensical_drift.py` | The drift checker. Reads target repo's files (current working directory) + Pages API, emits GitHub annotations, exits non-zero on violations |
| `scripts/test_zensical_drift.py` | pytest suite using fixture repos under `tests/fixtures/zensical/` |
| `scripts/rollout_zensical_standard.py` | One-shot rollout helper that applies templates to a target repo via the Contents API |
| `scripts/sync_markdownlint.py` | Helper to propagate `templates/.markdownlint.yml` updates to all 18 repos in one batch |
| `templates/.markdownlint.yml` | Canonical markdownlint config |
| `templates/docs.yml` | Canonical per-repo docs workflow |
| `templates/docs-standard-check.yml` | Canonical per-repo drift-check caller |
| `templates/lint.yml` | Canonical per-repo super-linter caller |
| `templates/renovate.json` | Canonical Renovate config |
| `tests/fixtures/zensical/good/` | Fixture: fully-conformant repo layout (used by drift tests) |
| `tests/fixtures/zensical/bad-flat-toggle/` | Fixture: violates nested-toggle requirement |
| `tests/fixtures/zensical/bad-loose-pin/` | Fixture: `requirements.txt` uses `>=` instead of `==` |
| `tests/fixtures/zensical/bad-missing-media/` | Fixture: palette entry missing `media` query |

### Files modified in each downstream repo

Each of the 18 target repos receives:
- `.github/workflows/docs.yml` — replaces existing `deploy-docs.yml`/`docs.yml`/etc.
- `.github/workflows/lint.yml` — adds where missing, rewrites where non-canonical
- `.github/workflows/docs-standard-check.yml` — new file
- `.markdownlint.yml` — new file at repo root
- `renovate.json` — extends list updated to include `helpers:pinGitHubActionDigests`

Old deploy workflow files (`deploy-docs.yml`, `psreddit-deploy-docs.yml`, `ddcu-deploy-docs.yml`) are deleted during the same commit that adds `docs.yml`.

---

## Phase 0 — Shared-workflows infrastructure

### Task 0.1: Add canonical `.markdownlint.yml` template

**Files:**
- Create: `templates/.markdownlint.yml`

- [ ] **Step 1: Create the template**

Content:
```yaml
# Canonical markdownlint config for zensical docs repos.
# Source of truth: shared-workflows/templates/.markdownlint.yml
# Drift check verifies SHA-256 of this file matches what each repo has.
default: true

# MD013: line length — disabled for prose
MD013: false

# MD033: inline HTML — allowed (zensical/material uses some inline HTML in admonitions, tabs)
MD033: false

# MD041: first-line h1 — disabled (zensical uses page title from nav/site_name)
MD041: false

# MD024: duplicate headings — only block siblings, not nested
MD024:
  siblings_only: true
```

- [ ] **Step 2: Commit**

```bash
git add templates/.markdownlint.yml
git commit -m "feat(templates): add canonical markdownlint config"
```

### Task 0.2: Add canonical `templates/lint.yml`

**Files:**
- Create: `templates/lint.yml`

- [ ] **Step 1: Create the template**

Content:
```yaml
# Canonical lint workflow for zensical docs repos.
# Thin caller of LukeEvansTech/shared-workflows super-linter reusable.
# Replace <SHA> with the digest of the latest super-linter.yml tagged commit.
name: Lint

on:
  pull_request:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  statuses: write
  pull-requests: write

jobs:
  lint:
    uses: LukeEvansTech/shared-workflows/.github/workflows/super-linter.yml@<SHA> # v1
    with:
      soft-launch: false
```

- [ ] **Step 2: Commit**

```bash
git add templates/lint.yml
git commit -m "feat(templates): add canonical lint workflow template"
```

### Task 0.3: Add canonical `templates/renovate.json`

**Files:**
- Create: `templates/renovate.json`

- [ ] **Step 1: Create the template**

Content:
```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": [
    "config:recommended",
    "helpers:pinGitHubActionDigests"
  ]
}
```

- [ ] **Step 2: Commit**

```bash
git add templates/renovate.json
git commit -m "feat(templates): add canonical renovate.json"
```

### Task 0.4: Add canonical `templates/docs.yml`

**Files:**
- Create: `templates/docs.yml`

- [ ] **Step 1: Create the template**

Content:
```yaml
# Canonical docs workflow for zensical docs repos.
# Thin caller of LukeEvansTech/shared-workflows zensical reusable.
# Build-only repos override `publish: false`.
name: Docs

on:
  push:
    branches: [main]
    paths:
      - "docs/**"
      - ".github/workflows/docs.yml"
  pull_request:
    paths:
      - "docs/**"
      - ".github/workflows/docs.yml"
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

jobs:
  docs:
    uses: LukeEvansTech/shared-workflows/.github/workflows/zensical.yml@<SHA> # v1
    with:
      publish: ${{ github.event_name != 'pull_request' }}
```

- [ ] **Step 2: Commit**

```bash
git add templates/docs.yml
git commit -m "feat(templates): add canonical docs deploy workflow template"
```

### Task 0.5: Add canonical `templates/docs-standard-check.yml`

**Files:**
- Create: `templates/docs-standard-check.yml`

- [ ] **Step 1: Create the template**

Content:
```yaml
# Canonical docs-standard-check workflow.
# Calls the zensical-drift-check reusable on every PR touching docs/ or workflows.
# Build-only repos override `allow-no-pages: true`.
name: Docs Standard Check

on:
  pull_request:
    paths:
      - "docs/**"
      - ".github/workflows/**"
      - "renovate.json"
      - ".markdownlint.yml"

permissions:
  contents: read
  pull-requests: write

jobs:
  drift:
    uses: LukeEvansTech/shared-workflows/.github/workflows/zensical-drift-check.yml@<SHA> # v1
```

- [ ] **Step 2: Commit**

```bash
git add templates/docs-standard-check.yml
git commit -m "feat(templates): add canonical docs-standard-check workflow template"
```

### Task 0.6: Create good and bad fixture repos for drift tests

**Files:**
- Create: `tests/fixtures/zensical/good/docs/zensical.toml`
- Create: `tests/fixtures/zensical/good/docs/requirements.txt`
- Create: `tests/fixtures/zensical/good/.markdownlint.yml`
- Create: `tests/fixtures/zensical/good/renovate.json`
- Create: `tests/fixtures/zensical/good/.github/workflows/docs.yml`
- Create: `tests/fixtures/zensical/good/.github/workflows/lint.yml`
- Create: `tests/fixtures/zensical/good/.github/workflows/docs-standard-check.yml`
- Create: `tests/fixtures/zensical/bad-flat-toggle/docs/zensical.toml`
- Create: `tests/fixtures/zensical/bad-loose-pin/docs/requirements.txt`
- Create: `tests/fixtures/zensical/bad-missing-media/docs/zensical.toml`
- Create: `tests/fixtures/zensical/bad-no-palette/docs/zensical.toml`
- Create: `tests/fixtures/zensical/bad-tag-pinned/.github/workflows/docs.yml`
- Create: `tests/fixtures/zensical/bad-uppercase-host/docs/zensical.toml`

- [ ] **Step 1: Build `good/docs/zensical.toml`**

```toml
[project]
site_name = "Fixture Good"
site_description = "Conformant fixture"
site_author = "Tests"
site_url = "https://example.github.io/good/"
copyright = "Copyright 2026"
repo_url = "https://github.com/example/good"
repo_name = "example/good"
edit_uri = "edit/main/docs/docs/"

[project.theme]
name = "material"
variant = "modern"
language = "en"

[project.theme.icon]
repo = "fontawesome/brands/github"

[[project.theme.palette]]
media = "(prefers-color-scheme: light)"
scheme = "default"
primary = "indigo"
accent = "indigo"

[project.theme.palette.toggle]
icon = "material/brightness-7"
name = "Switch to dark mode"

[[project.theme.palette]]
media = "(prefers-color-scheme: dark)"
scheme = "slate"
primary = "indigo"
accent = "indigo"

[project.theme.palette.toggle]
icon = "material/brightness-4"
name = "Switch to light mode"

[markdown_extensions]
admonition = {}
toc = { permalink = true }

[markdown_extensions.pymdownx]
highlight = { anchor_linenums = true, line_spans = "__span", pygments_lang_class = true }
inlinehilite = {}
snippets = {}
superfences = {}
```

- [ ] **Step 2: Build `good/docs/requirements.txt`**

```
zensical==0.0.43
```

- [ ] **Step 3: Build `good/.markdownlint.yml`** — identical to `templates/.markdownlint.yml` from Task 0.1 (the fixture must match the canonical SHA).

- [ ] **Step 4: Build `good/renovate.json`** — identical to `templates/renovate.json` from Task 0.3.

- [ ] **Step 5: Build `good/.github/workflows/docs.yml`** — copy `templates/docs.yml` with `<SHA>` replaced by `0000000000000000000000000000000000000000` (placeholder valid 40-hex; drift script only checks shape).

- [ ] **Step 6: Build `good/.github/workflows/lint.yml`** — copy `templates/lint.yml` with the same placeholder SHA.

- [ ] **Step 7: Build `good/.github/workflows/docs-standard-check.yml`** — copy `templates/docs-standard-check.yml` with the same placeholder SHA.

- [ ] **Step 8: Build `bad-flat-toggle/docs/zensical.toml`** — copy good's zensical.toml, replace each `[project.theme.palette.toggle]` block (table + 2 keys) with flat keys on the palette entry:

```toml
[[project.theme.palette]]
media = "(prefers-color-scheme: light)"
scheme = "default"
toggle_icon = "material/brightness-7"
toggle_name = "Switch to dark mode"
```

(and similar for the dark entry)

- [ ] **Step 9: Build `bad-loose-pin/docs/requirements.txt`**

```
zensical>=0.0.4
```

- [ ] **Step 10: Build `bad-missing-media/docs/zensical.toml`** — copy good's, delete the two `media =` lines.

- [ ] **Step 11: Build `bad-no-palette/docs/zensical.toml`** — copy good's, delete both `[[project.theme.palette]]` blocks entirely.

- [ ] **Step 12: Build `bad-tag-pinned/.github/workflows/docs.yml`** — copy good's docs.yml but use `@v1` instead of the 40-hex SHA placeholder.

- [ ] **Step 13: Build `bad-uppercase-host/docs/zensical.toml`** — copy good's, change site_url to `https://LukeEvansTech.github.io/good/`.

- [ ] **Step 14: Commit**

```bash
git add tests/fixtures/zensical/
git commit -m "test(zensical-drift): add good + bad fixtures for drift checks"
```

### Task 0.7: Write drift script — pin format check (TDD)

**Files:**
- Create: `scripts/zensical_drift.py`
- Create: `scripts/test_zensical_drift.py`

- [ ] **Step 1: Write the failing test**

`scripts/test_zensical_drift.py`:
```python
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
    assert "requirements.txt" in result.stdout + result.stderr
    assert "zensical>=" in result.stdout + result.stderr or "must use ==" in result.stdout + result.stderr
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest scripts/test_zensical_drift.py::test_loose_pin_fails -v
```

Expected: FAIL with "file not found" or similar (script doesn't exist yet).

- [ ] **Step 3: Write minimal `zensical_drift.py` with pin check**

```python
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    args = parser.parse_args()
    check_pin(args.repo_root)
    for line in FAILURES:
        print(line)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest scripts/test_zensical_drift.py::test_loose_pin_fails -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
chmod +x scripts/zensical_drift.py
git add scripts/zensical_drift.py scripts/test_zensical_drift.py
git commit -m "feat(zensical-drift): pin format check"
```

### Task 0.8: Drift script — palette block check (TDD)

**Files:**
- Modify: `scripts/zensical_drift.py`
- Modify: `scripts/test_zensical_drift.py`

- [ ] **Step 1: Write failing tests for three palette violations**

Append to `scripts/test_zensical_drift.py`:
```python
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
    """When only palette check is implemented, good fixture should pass for that aspect."""
    result = run_drift("good")
    # We won't assert returncode==0 here because other checks aren't implemented yet;
    # just that the good fixture doesn't trip the palette-specific failures.
    out = result.stdout + result.stderr
    assert "[palette]" not in out
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest scripts/test_zensical_drift.py -v -k palette
```

Expected: 3 fail with `assert result.returncode != 0` on bad fixtures (script currently only checks pin, so those bad fixtures may pass pin check). The good-fixture test should pass trivially since `[palette]` isn't yet emitted by anything.

Actually wait — `bad-flat-toggle` has correct pin but bad toggle. Current script only checks pin → returns 0 → test fails on `result.returncode != 0`. Confirmed.

- [ ] **Step 3: Add `check_palette` function**

Add to `scripts/zensical_drift.py` (above `main`):
```python
def check_palette(repo_root: Path) -> None:
    cfg = repo_root / "docs" / "zensical.toml"
    if not cfg.exists():
        fail("palette", str(cfg), "docs/zensical.toml is missing")
        return
    text = cfg.read_text()

    # Required: at least one [[project.theme.palette]] with prefers-color-scheme: light, one with dark
    palette_blocks = re.findall(
        r'\[\[project\.theme\.palette\]\][^\[]*?(?=\[(?!project\.theme\.palette\.toggle))',
        text + "\n[",  # sentinel
        re.DOTALL,
    )
    if len(palette_blocks) < 2:
        fail("palette", str(cfg), f"need at least 2 [[project.theme.palette]] entries, found {len(palette_blocks)}")
        return

    has_light = any('media = "(prefers-color-scheme: light)"' in b for b in palette_blocks)
    has_dark = any('media = "(prefers-color-scheme: dark)"' in b for b in palette_blocks)
    if not has_light:
        fail("palette", str(cfg), "no palette entry with `media = \"(prefers-color-scheme: light)\"`")
    if not has_dark:
        fail("palette", str(cfg), "no palette entry with `media = \"(prefers-color-scheme: dark)\"`")

    # Forbidden: flat toggle_icon / toggle_name keys at palette entry level
    if re.search(r'^\s*toggle_icon\s*=', text, re.M) or re.search(r'^\s*toggle_name\s*=', text, re.M):
        fail("palette", str(cfg), "use nested [project.theme.palette.toggle] table; flat toggle_icon/toggle_name does not render the toggle button")

    # Required: each [[project.theme.palette]] must be followed by a [project.theme.palette.toggle] table
    toggle_tables = re.findall(r'\[project\.theme\.palette\.toggle\]', text)
    if len(toggle_tables) < 2:
        fail("palette", str(cfg), f"need a [project.theme.palette.toggle] table for each palette entry; found {len(toggle_tables)}")


# In main(), call after check_pin:
#   check_palette(args.repo_root)
```

Update `main()`:
```python
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    args = parser.parse_args()
    check_pin(args.repo_root)
    check_palette(args.repo_root)
    for line in FAILURES:
        print(line)
    return 1 if FAILURES else 0
```

- [ ] **Step 4: Run tests to verify all palette tests pass**

```bash
pytest scripts/test_zensical_drift.py -v -k palette
```

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/zensical_drift.py scripts/test_zensical_drift.py
git commit -m "feat(zensical-drift): palette + toggle block check"
```

### Task 0.9: Drift script — workflow filename + SHA-pinning checks (TDD)

**Files:**
- Modify: `scripts/zensical_drift.py`
- Modify: `scripts/test_zensical_drift.py`

- [ ] **Step 1: Write failing tests**

Append to `scripts/test_zensical_drift.py`:
```python
def test_tag_pinned_workflow_fails():
    result = run_drift("bad-tag-pinned")
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert "SHA" in out or "sha-pinn" in out.lower() or "tag-pinned" in out.lower()


def test_uppercase_host_fails():
    result = run_drift("bad-uppercase-host")
    assert result.returncode != 0
    out = result.stdout + result.stderr
    assert "site_url" in out.lower() or "host" in out.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest scripts/test_zensical_drift.py -v -k "tag_pinned or uppercase_host"
```

Expected: 2 FAIL.

- [ ] **Step 3: Add `check_workflows` and `check_site_url`**

Add to `scripts/zensical_drift.py`:
```python
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
            fail("workflows", str(wf), f"`{wf_name}` must call `{expected_reusable.replace(chr(92), '')}@<SHA>`")
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
        return  # palette check already reported
    text = cfg.read_text()
    m = re.search(r'^\s*site_url\s*=\s*"([^"]+)"', text, re.M)
    if not m:
        return  # presence is required-but-per-repo; absence flagged elsewhere if we add that check
    url = m.group(1)
    if url.startswith("http"):
        host = url.split("//", 1)[1].split("/", 1)[0]
        if host.lower() != host:
            fail("site_url", str(cfg), f"site_url host must be lowercase; found `{host}`")
        if "lukevanstech" in host.lower() and "lukeevanstech" not in host.lower():
            fail("site_url", str(cfg), f"site_url has typo `lukevanstech` (should be `lukeevanstech`); found `{host}`")
```

Update `main()` to call them:
```python
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
```

- [ ] **Step 4: Run tests**

```bash
pytest scripts/test_zensical_drift.py -v
```

Expected: All tests pass (pin, palette × 3, tag_pinned, uppercase_host, good-palette-only).

- [ ] **Step 5: Commit**

```bash
git add scripts/zensical_drift.py scripts/test_zensical_drift.py
git commit -m "feat(zensical-drift): workflow SHA-pinning + site_url hygiene checks"
```

### Task 0.10: Drift script — remaining checks (theme baseline, layout, renovate, markdownlint hash, Pages settings) (TDD)

**Files:**
- Modify: `scripts/zensical_drift.py`
- Modify: `scripts/test_zensical_drift.py`
- Create: `tests/fixtures/zensical/bad-renovate/renovate.json`
- Create: `tests/fixtures/zensical/bad-markdownlint/.markdownlint.yml`

- [ ] **Step 1: Add the two new bad-fixture files**

`tests/fixtures/zensical/bad-renovate/renovate.json`:
```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:recommended"]
}
```
(missing `helpers:pinGitHubActionDigests`)

`tests/fixtures/zensical/bad-markdownlint/.markdownlint.yml`:
```yaml
default: true
# missing the canonical overrides
```

For each bad fixture, also copy the other "good" files so only the targeted check fails. Use a helper script or manually:

```bash
cd tests/fixtures/zensical/
for f in bad-renovate bad-markdownlint; do
  mkdir -p $f/docs $f/.github/workflows
  cp good/docs/zensical.toml $f/docs/
  cp good/docs/requirements.txt $f/docs/
  cp good/.github/workflows/*.yml $f/.github/workflows/
  cp good/renovate.json $f/ 2>/dev/null || true
  cp good/.markdownlint.yml $f/ 2>/dev/null || true
done
# Then overwrite the targeted file with bad content
# (done above)
```

Run that, then put bad-renovate/renovate.json and bad-markdownlint/.markdownlint.yml back with the bad content.

- [ ] **Step 2: Write failing tests**

Append to `scripts/test_zensical_drift.py`:
```python
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
    assert result.returncode == 0, f"good fixture should pass; got: {result.stdout}\n{result.stderr}"
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest scripts/test_zensical_drift.py -v -k "renovate or markdownlint or good_fixture_passes_overall"
```

Expected: 3 FAIL (good fixture probably fails because some checks still missing).

- [ ] **Step 4: Add the remaining checks**

Add to `scripts/zensical_drift.py`:
```python
import hashlib
import json

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def check_theme_baseline(repo_root: Path) -> None:
    cfg = repo_root / "docs" / "zensical.toml"
    if not cfg.exists():
        return
    text = cfg.read_text()
    if 'name = "material"' not in text:
        fail("theme", str(cfg), 'theme.name must be "material"')
    if 'variant = "modern"' not in text:
        fail("theme", str(cfg), 'theme.variant must be "modern"')
    if 'language = "en"' not in text:
        fail("theme", str(cfg), 'theme.language must be "en"')


def check_layout(repo_root: Path) -> None:
    if not (repo_root / "docs" / "docs").is_dir():
        fail("layout", str(repo_root / "docs" / "docs"), "docs/docs/ directory is missing (canonical content path)")


def check_renovate(repo_root: Path) -> None:
    r = repo_root / "renovate.json"
    if not r.exists():
        fail("renovate", str(r), "renovate.json is missing")
        return
    try:
        data = json.loads(r.read_text())
    except json.JSONDecodeError as e:
        fail("renovate", str(r), f"renovate.json is not valid JSON: {e}")
        return
    extends = data.get("extends", [])
    if "config:recommended" not in extends:
        fail("renovate", str(r), "extends must include `config:recommended`")
    if "helpers:pinGitHubActionDigests" not in extends:
        fail("renovate", str(r), "extends must include `helpers:pinGitHubActionDigests`")


def check_markdownlint(repo_root: Path) -> None:
    ml = repo_root / ".markdownlint.yml"
    canonical = TEMPLATES_DIR / ".markdownlint.yml"
    if not ml.exists():
        fail("markdownlint", str(ml), ".markdownlint.yml is missing at repo root")
        return
    if not canonical.exists():
        # When script is run standalone outside shared-workflows (e.g. inside a target repo's checkout),
        # the canonical may not be available. In that case, skip the hash check with a warning.
        print(f"::warning::canonical .markdownlint.yml not found at {canonical}; hash check skipped", file=sys.stderr)
        return
    if hashlib.sha256(ml.read_bytes()).hexdigest() != hashlib.sha256(canonical.read_bytes()).hexdigest():
        fail("markdownlint", str(ml), "content differs from canonical templates/.markdownlint.yml; run scripts/sync_markdownlint.py")
```

Update `main()`:
```python
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    args = parser.parse_args()
    check_pin(args.repo_root)
    check_palette(args.repo_root)
    check_theme_baseline(args.repo_root)
    check_layout(args.repo_root)
    check_workflows(args.repo_root)
    check_site_url(args.repo_root)
    check_renovate(args.repo_root)
    check_markdownlint(args.repo_root)
    for line in FAILURES:
        print(line)
    return 1 if FAILURES else 0
```

- [ ] **Step 5: Run all tests**

```bash
pytest scripts/test_zensical_drift.py -v
```

Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/zensical_drift.py scripts/test_zensical_drift.py tests/fixtures/zensical/bad-renovate tests/fixtures/zensical/bad-markdownlint
git commit -m "feat(zensical-drift): theme/layout/renovate/markdownlint checks"
```

### Task 0.11: Drift script — Pages settings check (TDD)

**Files:**
- Modify: `scripts/zensical_drift.py`
- Modify: `scripts/test_zensical_drift.py`

The Pages check queries the GitHub API, not the local filesystem. It's run only when the workflow knows the target repo's `owner/name` (passed as `--repo` arg).

- [ ] **Step 1: Write failing test (skips on no `gh` CLI / no auth)**

Append to `scripts/test_zensical_drift.py`:
```python
import shutil


def has_gh():
    return shutil.which("gh") is not None


@pytest.mark.skipif(not has_gh(), reason="gh CLI not available in this env")
def test_pages_check_skipped_when_no_repo_arg():
    result = run_drift("good")
    # Without --repo arg, Pages check is N/A. Should not fail.
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest scripts/test_zensical_drift.py -v -k pages
```

Expected: tests fail because new args aren't yet parsed.

- [ ] **Step 3: Add `check_pages` to drift script**

Add to `scripts/zensical_drift.py`:
```python
import subprocess
import json as _json


def check_pages(repo: str | None, allow_no_pages: bool, allow_build_type_legacy: bool) -> None:
    if not repo:
        return  # Pages check is opt-in via --repo argument
    r = subprocess.run(["gh", "api", f"repos/{repo}/pages"], capture_output=True, text=True)
    if r.returncode != 0:
        if allow_no_pages:
            return
        fail("pages", f"repos/{repo}/pages", "Pages is not enabled (pass --allow-no-pages for build-only repos)")
        return
    try:
        data = _json.loads(r.stdout)
    except _json.JSONDecodeError:
        fail("pages", f"repos/{repo}/pages", "could not parse Pages API response")
        return
    build_type = data.get("build_type")
    if build_type == "legacy" and not allow_build_type_legacy:
        fail("pages", f"repos/{repo}/pages", f"Pages build_type is `legacy`; standard requires `workflow`")
```

Update `main()` and argument parser:
```python
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--repo", help="owner/name for Pages API check (optional)")
    parser.add_argument("--allow-no-pages", action="store_true", help="for build-only repos: don't fail when Pages is disabled")
    parser.add_argument("--allow-build-type-legacy", action="store_true", help="escape hatch for repos mid-migration")
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
```

- [ ] **Step 4: Run all tests**

```bash
pytest scripts/test_zensical_drift.py -v
```

Expected: All PASS (Pages tests pass when `gh` is available; skip otherwise).

- [ ] **Step 5: Commit**

```bash
git add scripts/zensical_drift.py scripts/test_zensical_drift.py
git commit -m "feat(zensical-drift): Pages settings check"
```

### Task 0.12: Create `.github/workflows/zensical-drift-check.yml` reusable

**Files:**
- Create: `.github/workflows/zensical-drift-check.yml`

- [ ] **Step 1: Write the reusable workflow**

```yaml
name: Zensical Drift Check (reusable)

on:
  workflow_call:
    inputs:
      allow-no-pages:
        description: For build-only repos that don't have Pages enabled
        type: boolean
        default: false
      allow-build-type-legacy:
        description: Escape hatch for repos mid-migration
        type: boolean
        default: false

jobs:
  drift:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - name: Checkout target repo
        uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6
        with:
          persist-credentials: false
          path: target

      - name: Checkout shared-workflows (for drift script + canonical templates)
        uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6
        with:
          repository: LukeEvansTech/shared-workflows
          ref: main
          path: shared-workflows
          persist-credentials: false

      - name: Set up Python
        uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v6
        with:
          python-version: '3.14'

      - name: Run drift check
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          python3 shared-workflows/scripts/zensical_drift.py \
            --repo-root target \
            --repo "${{ github.repository }}" \
            ${{ inputs.allow-no-pages && '--allow-no-pages' || '' }} \
            ${{ inputs.allow-build-type-legacy && '--allow-build-type-legacy' || '' }}
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/zensical-drift-check.yml
git commit -m "feat(workflows): add zensical-drift-check reusable workflow"
```

### Task 0.13: Create `.github/workflows/zensical.yml` reusable — build job

**Files:**
- Create: `.github/workflows/zensical.yml`

- [ ] **Step 1: Write the reusable workflow with build job only (first pass)**

```yaml
name: Zensical (reusable)

on:
  workflow_call:
    inputs:
      publish:
        description: Deploy to GitHub Pages. Set false for build-only repos.
        type: boolean
        default: true
      python-version:
        description: Python version for the build
        type: string
        default: "3.14"
      working-directory:
        description: Path to the zensical project (where zensical.toml lives)
        type: string
        default: docs
      link-check:
        description: Run lychee link check against the built site
        type: boolean
        default: true
      link-check-soft-launch:
        description: When true, lychee failures do not fail the workflow
        type: boolean
        default: true
      vale:
        description: Run Vale prose linter (requires .vale.ini in repo root)
        type: boolean
        default: false
      vale-soft-launch:
        description: When true, Vale failures do not fail the workflow
        type: boolean
        default: true
      strict:
        description: Pass --strict to zensical build
        type: boolean
        default: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6
        with:
          fetch-depth: 0
          persist-credentials: false

      - name: Set up Python
        uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v6
        with:
          python-version: ${{ inputs.python-version }}
          cache: pip
          cache-dependency-path: ${{ inputs.working-directory }}/requirements.txt

      - name: Install zensical
        working-directory: ${{ inputs.working-directory }}
        run: pip install -r requirements.txt

      - name: Build site
        working-directory: ${{ inputs.working-directory }}
        run: zensical build${{ inputs.strict && ' --strict' || '' }}

      - name: Configure Pages
        if: inputs.publish
        uses: actions/configure-pages@e1c1afe2b3d094c66fbe49fcec3252b6a2af6695 # v6

      - name: Upload artifact
        if: inputs.publish
        uses: actions/upload-pages-artifact@7b1f4a764d45c48632c6b24a0339c27f5614fb0b # v5
        with:
          path: ${{ inputs.working-directory }}/site
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/zensical.yml
git commit -m "feat(workflows): add zensical reusable workflow (build + upload)"
```

### Task 0.14: Add link-check job to `zensical.yml`

**Files:**
- Modify: `.github/workflows/zensical.yml`

- [ ] **Step 1: Append link-check job**

Insert after the `build` job:
```yaml
  link-check:
    needs: build
    if: inputs.link-check
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6
        with:
          persist-credentials: false

      - name: Set up Python
        uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v6
        with:
          python-version: ${{ inputs.python-version }}
          cache: pip
          cache-dependency-path: ${{ inputs.working-directory }}/requirements.txt

      - name: Install zensical
        working-directory: ${{ inputs.working-directory }}
        run: pip install -r requirements.txt

      - name: Build site
        working-directory: ${{ inputs.working-directory }}
        run: zensical build${{ inputs.strict && ' --strict' || '' }}

      - name: Restore lychee cache
        uses: actions/cache@2f8e54208210a422b2efd51efaa6bd6d7ca8920f # v5
        with:
          path: .lycheecache
          key: lychee-${{ github.sha }}
          restore-keys: lychee-

      - name: Run lychee
        id: lychee
        uses: lycheeverse/lychee-action@82202e5e9c2f4ef1a55a3d02563e1cb6da7fdd03 # v2
        with:
          args: --cache --max-cache-age 1d --retry-wait-time 60 --max-retries 1 --no-progress ${{ inputs.working-directory }}/site
        continue-on-error: ${{ inputs.link-check-soft-launch }}
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/zensical.yml
git commit -m "feat(zensical-workflow): add lychee link-check job"
```

### Task 0.15: Add prose (Vale) job to `zensical.yml`

**Files:**
- Modify: `.github/workflows/zensical.yml`

- [ ] **Step 1: Append prose job**

Insert after `link-check`:
```yaml
  prose:
    needs: build
    if: inputs.vale
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6
        with:
          persist-credentials: false

      - name: Vale
        uses: errata-ai/vale-action@d89dee975228ae261d22c15adcd03578634d429c # v2
        with:
          files: ${{ inputs.working-directory }}/docs
        continue-on-error: ${{ inputs.vale-soft-launch }}
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/zensical.yml
git commit -m "feat(zensical-workflow): add Vale prose job (opt-in)"
```

### Task 0.16: Add deploy job to `zensical.yml`

**Files:**
- Modify: `.github/workflows/zensical.yml`

- [ ] **Step 1: Append deploy job**

```yaml
  deploy:
    needs: build
    if: inputs.publish && github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@cd2ce8fcbc39b97be8ca5fce6e763baed58fa128 # v5
```

> **Note on action SHAs in this plan:** all SHAs referenced (`actions/checkout@de0fac…`, `actions/setup-python@a26af6…`, `actions/cache@0057852…`, `lycheeverse/lychee-action@8646ba…`, `errata-ai/vale-action@d89dee9…`, `actions/deploy-pages@cd2ce8f…`, `actions/upload-pages-artifact@7b1f4a…`, `actions/configure-pages@e1c1af…`) were resolved on 2026-05-26 against the published tags. Renovate's `helpers:pinGitHubActionDigests` will keep them updated post-rollout.

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/zensical.yml
git commit -m "feat(zensical-workflow): add Pages deploy job"
```

### Task 0.17: Write `scripts/rollout_zensical_standard.py` — single-repo apply

**Files:**
- Create: `scripts/rollout_zensical_standard.py`

This script applies the standard files to one target repo via the GitHub Contents API. It's idempotent and supports `--dry-run`.

- [ ] **Step 1: Create the script skeleton**

```python
#!/usr/bin/env python3
"""Apply the zensical docs standard to one repo.

Usage:
    python3 scripts/rollout_zensical_standard.py --repo owner/name [--publish/--no-publish] [--dry-run]

Idempotent: re-running produces no commits if everything is already conformant.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
from pathlib import Path

TEMPLATES = Path(__file__).parent.parent / "templates"
SHARED_WORKFLOWS_REPO = "LukeEvansTech/shared-workflows"


def gh(args: list[str], input: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["gh"] + args, capture_output=True, text=True, input=input, timeout=30)


def get_latest_sha() -> str:
    """Get the latest SHA on shared-workflows main."""
    r = gh(["api", f"repos/{SHARED_WORKFLOWS_REPO}/commits/main"])
    if r.returncode != 0:
        raise SystemExit(f"could not fetch shared-workflows SHA: {r.stderr}")
    return json.loads(r.stdout)["sha"]


def render_template(name: str, sha: str, publish: bool, allow_no_pages: bool) -> str:
    text = (TEMPLATES / name).read_text()
    text = text.replace("<SHA>", sha)
    if name == "docs.yml" and not publish:
        # Build-only override: replace the `with:` block
        text = text.replace(
            "with:\n      publish: ${{ github.event_name != 'pull_request' }}",
            "with:\n      publish: false",
        )
    if name == "docs-standard-check.yml" and allow_no_pages:
        text = text.replace(
            "jobs:\n  drift:\n    uses: LukeEvansTech/shared-workflows/.github/workflows/zensical-drift-check.yml@" + sha + " # v1",
            "jobs:\n  drift:\n    uses: LukeEvansTech/shared-workflows/.github/workflows/zensical-drift-check.yml@" + sha + " # v1\n    with:\n      allow-no-pages: true",
        )
    return text


def upsert_file(repo: str, path: str, content: str, message: str, dry_run: bool) -> None:
    r = gh(["api", f"repos/{repo}/contents/{path}"])
    if r.returncode == 0:
        existing = json.loads(r.stdout)
        sha = existing["sha"]
        current_text = base64.b64decode(existing["content"]).decode()
        if current_text == content:
            print(f"  {path}: NO-CHANGE")
            return
    else:
        sha = None
    if dry_run:
        print(f"  {path}: WOULD WRITE ({'create' if sha is None else 'update'})")
        return
    new_b64 = base64.b64encode(content.encode()).decode()
    api_args = ["api", "-X", "PUT", f"repos/{repo}/contents/{path}",
                "-f", f"message={message}",
                "-f", f"content={new_b64}"]
    if sha:
        api_args.extend(["-f", f"sha={sha}"])
    r = gh(api_args)
    if r.returncode == 0:
        commit_sha = json.loads(r.stdout)["commit"]["sha"][:7]
        print(f"  {path}: OK {commit_sha}")
    else:
        print(f"  {path}: FAIL — {r.stderr.strip()[:200]}", file=sys.stderr)
        raise SystemExit(1)


def delete_file(repo: str, path: str, message: str, dry_run: bool) -> None:
    r = gh(["api", f"repos/{repo}/contents/{path}"])
    if r.returncode != 0:
        return  # already absent
    sha = json.loads(r.stdout)["sha"]
    if dry_run:
        print(f"  {path}: WOULD DELETE")
        return
    r = gh(["api", "-X", "DELETE", f"repos/{repo}/contents/{path}",
            "-f", f"message={message}",
            "-f", f"sha={sha}"])
    if r.returncode == 0:
        print(f"  {path}: DELETED")
    else:
        print(f"  {path}: DELETE FAIL — {r.stderr.strip()[:200]}", file=sys.stderr)


# Files in target repo that are replaced by canonical docs.yml; delete them.
SUPERSEDED_DEPLOY_WORKFLOWS = [
    ".github/workflows/deploy-docs.yml",
    ".github/workflows/psreddit-deploy-docs.yml",
    ".github/workflows/ddcu-deploy-docs.yml",
]
SUPERSEDED_LINT_WORKFLOWS = [
    ".github/workflows/ddcu-lint.yml",
]


def apply(repo: str, publish: bool, allow_no_pages: bool, dry_run: bool) -> None:
    sha = get_latest_sha()
    print(f"shared-workflows SHA: {sha}")
    print(f"Applying standard to {repo} (publish={publish}, allow_no_pages={allow_no_pages})")

    # Delete any superseded workflows first
    for path in SUPERSEDED_DEPLOY_WORKFLOWS + SUPERSEDED_LINT_WORKFLOWS:
        delete_file(repo, path, "ci: remove superseded workflow (replaced by canonical docs.yml/lint.yml)", dry_run)

    # Write canonical workflow callers
    upsert_file(repo, ".github/workflows/docs.yml",
                render_template("docs.yml", sha, publish, allow_no_pages),
                "ci(docs): adopt canonical docs workflow", dry_run)
    upsert_file(repo, ".github/workflows/lint.yml",
                render_template("lint.yml", sha, publish, allow_no_pages),
                "ci(lint): adopt canonical lint workflow", dry_run)
    upsert_file(repo, ".github/workflows/docs-standard-check.yml",
                render_template("docs-standard-check.yml", sha, publish, allow_no_pages),
                "ci(docs): adopt drift-check workflow", dry_run)

    # Root config files
    upsert_file(repo, ".markdownlint.yml",
                (TEMPLATES / ".markdownlint.yml").read_text(),
                "chore: adopt canonical markdownlint config", dry_run)

    # Renovate — merge rather than overwrite, since some repos may have local additions
    update_renovate(repo, dry_run)


def update_renovate(repo: str, dry_run: bool) -> None:
    r = gh(["api", f"repos/{repo}/contents/renovate.json"])
    canonical = json.loads((TEMPLATES / "renovate.json").read_text())
    if r.returncode != 0:
        # Doesn't exist — write canonical
        upsert_file(repo, "renovate.json", json.dumps(canonical, indent=2) + "\n",
                    "chore: add canonical renovate.json", dry_run)
        return
    existing_raw = base64.b64decode(json.loads(r.stdout)["content"]).decode()
    try:
        existing = json.loads(existing_raw)
    except json.JSONDecodeError:
        print(f"  renovate.json: BAILING — existing file is not valid JSON", file=sys.stderr)
        return
    extends = existing.get("extends", [])
    changed = False
    for required in canonical["extends"]:
        if required not in extends:
            extends.append(required)
            changed = True
    if not changed:
        print(f"  renovate.json: NO-CHANGE")
        return
    existing["extends"] = extends
    new_content = json.dumps(existing, indent=2) + "\n"
    upsert_file(repo, "renovate.json", new_content,
                "chore(renovate): add helpers:pinGitHubActionDigests", dry_run)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True, help="owner/name")
    publish_group = p.add_mutually_exclusive_group()
    publish_group.add_argument("--publish", dest="publish", action="store_true", default=True)
    publish_group.add_argument("--no-publish", dest="publish", action="store_false")
    p.add_argument("--allow-no-pages", action="store_true",
                   help="add `allow-no-pages: true` to drift-check caller (for build-only repos)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    apply(args.repo, args.publish, args.allow_no_pages, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Commit**

```bash
chmod +x scripts/rollout_zensical_standard.py
git add scripts/rollout_zensical_standard.py
git commit -m "feat(rollout): add per-repo zensical standard rollout script"
```

### Task 0.18: Write `scripts/sync_markdownlint.py`

**Files:**
- Create: `scripts/sync_markdownlint.py`

- [ ] **Step 1: Create the script**

```python
#!/usr/bin/env python3
"""Propagate templates/.markdownlint.yml to all 18 zensical docs repos.

Run after editing the canonical template. Idempotent.
"""
import base64
import json
import subprocess
import sys
from pathlib import Path

CANONICAL = Path(__file__).parent.parent / "templates" / ".markdownlint.yml"

REPOS = [
    "LukeEvansTech/PSReddit",
    "LukeEvansTech/copilot-kql-library",
    "LukeEvansTech/col-entra-id",
    "LukeEvansTech/acinfinity-exporter",
    "LukeEvansTech/github-infrastructure",
    "LukeEvansTech/entra-ca-templates",
    "LukeEvansTech/maester-copilot-tests",
    "LukeEvansTech/copilot-security-checker",
    "LukeEvansTech/purview-content-explorer-helpers",
    "LukeEvansTech/purview-content-explorer-export",
    "LukeEvansTech/purview-dlp-export",
    "LukeEvansTech/defender-device-control-unmanaged",
    "LukeEvansTech/lgwebos",
    "LukeEvansTech/stwt-m365-consolidation",
    "LukeEvansTech/M365LabelSync",
    "LukeEvansTech/dotfiles",
    "LukeEvansTech/network-ops",
    "LukeEvansTech/terraform-dns",
]


def gh(args):
    return subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=30)


def main() -> int:
    canonical_text = CANONICAL.read_text()
    canonical_b64 = base64.b64encode(canonical_text.encode()).decode()
    for repo in REPOS:
        r = gh(["api", f"repos/{repo}/contents/.markdownlint.yml"])
        if r.returncode == 0:
            data = json.loads(r.stdout)
            current = base64.b64decode(data["content"]).decode()
            if current == canonical_text:
                print(f"{repo}: NO-CHANGE")
                continue
            sha = data["sha"]
            r = gh(["api", "-X", "PUT", f"repos/{repo}/contents/.markdownlint.yml",
                    "-f", "message=chore: sync canonical markdownlint config",
                    "-f", f"content={canonical_b64}",
                    "-f", f"sha={sha}"])
        else:
            r = gh(["api", "-X", "PUT", f"repos/{repo}/contents/.markdownlint.yml",
                    "-f", "message=chore: add canonical markdownlint config",
                    "-f", f"content={canonical_b64}"])
        if r.returncode == 0:
            sha = json.loads(r.stdout)["commit"]["sha"][:7]
            print(f"{repo}: OK {sha}")
        else:
            print(f"{repo}: FAIL — {r.stderr.strip()[:200]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Commit**

```bash
chmod +x scripts/sync_markdownlint.py
git add scripts/sync_markdownlint.py
git commit -m "feat(rollout): add markdownlint sync helper"
```

### Task 0.19: Push shared-workflows changes and tag `v1`

- [ ] **Step 1: Push to main**

```bash
git push origin main
```

- [ ] **Step 2: Capture the SHA of the latest commit**

```bash
HEAD_SHA=$(git rev-parse HEAD)
echo "shared-workflows main SHA after rollout prep: $HEAD_SHA"
```

Save this SHA — every downstream repo's docs.yml / lint.yml / docs-standard-check.yml will reference it (until Renovate bumps it).

- [ ] **Step 3: Verify shared-workflows CI is green**

```bash
gh run list --repo LukeEvansTech/shared-workflows --branch main --limit 5
```

Expected: most recent runs `success` for Lint, Meta-actionlint, Security Scans.

- [ ] **Step 4: Tag v1 (optional — pinning is by SHA, but tag is human-readable)**

```bash
git tag -a v1 -m "Zensical docs standard infrastructure"
git push origin v1
```

---

## Phase 1 — Canary: M365LabelSync

### Task 1.1: Apply standard to M365LabelSync (dry-run first)

**Files (in target repo `LukeEvansTech/M365LabelSync`):**
- Create: `.github/workflows/docs.yml`
- Create: `.github/workflows/lint.yml` (replaces existing if not already canonical)
- Create: `.github/workflows/docs-standard-check.yml`
- Create: `.markdownlint.yml`
- Modify: `renovate.json`
- Delete: `.github/workflows/deploy-docs.yml`

- [ ] **Step 1: Dry-run**

```bash
cd /Users/luke.evans/Scratch/zenscialupdates/shared-workflows
python3 scripts/rollout_zensical_standard.py --repo LukeEvansTech/M365LabelSync --publish --dry-run
```

Expected output: lists what would be created/updated/deleted; no actual API writes.

- [ ] **Step 2: Apply for real**

```bash
python3 scripts/rollout_zensical_standard.py --repo LukeEvansTech/M365LabelSync --publish
```

Expected: ~6 commits to M365LabelSync — delete old deploy-docs.yml, create new docs.yml/lint.yml/docs-standard-check.yml/.markdownlint.yml, update renovate.json.

- [ ] **Step 3: Verify CI runs trigger and pass**

```bash
sleep 10
HEAD=$(gh api repos/LukeEvansTech/M365LabelSync/commits?per_page=1 --jq '.[0].sha')
gh api "repos/LukeEvansTech/M365LabelSync/actions/runs?head_sha=$HEAD" --jq '.workflow_runs[] | {name, status, conclusion}'
```

Wait for completion (poll until all complete). Expected: Docs, Lint, Docs Standard Check, pages build and deployment — all `success`.

- [ ] **Step 4: Verify live site still works**

```bash
URL=$(gh api repos/LukeEvansTech/M365LabelSync/pages --jq '.html_url')
curl -sL "$URL" | grep -oE '<meta name="generator" content="[^"]+"' | head -1
```

Expected: `<meta name="generator" content="zensical-0.0.43"`.

Toggle button check:
```bash
curl -sL "$URL" | grep -oiE 'switch to (dark|light) mode' | head -2
```

Expected: both `Switch to dark mode` and `Switch to light mode`.

- [ ] **Step 5: Verify drift check passes on a synthetic conformant PR**

Open a PR that bumps a comment in docs/zensical.toml; the `Docs Standard Check` workflow should run and pass. Close PR after.

```bash
gh pr create --repo LukeEvansTech/M365LabelSync --base main --head <branch> --title "test: trigger drift check" --body "Synthetic PR for drift-check verification"
```

After the workflow completes:
```bash
gh pr checks <PR#> --repo LukeEvansTech/M365LabelSync
```

Expected: `Docs Standard Check` passes.

- [ ] **Step 6: Verify drift check fails on a synthetic non-conformant PR**

Create a branch that reverts a palette entry to flat `toggle_icon` keys. Open PR. Verify `Docs Standard Check` fails with annotation pointing to the palette section.

Close PR; don't merge.

- [ ] **Step 7: If anything broke, revert each file via API and tune**

Per-file revert pattern:
```bash
# Get the commit BEFORE the rollout commit
PREV=$(gh api repos/LukeEvansTech/M365LabelSync/commits?path=.github/workflows/docs.yml --jq '.[1].sha')
# Re-fetch its content, write back via Contents API
```

This step is "no-op if everything's green".

---

## Phase 2 — Bulk rollout: 8 main-branch publishing repos

### Task 2.1: Apply standard to the 8 "easy" repos

**Repos:**
```
copilot-kql-library
acinfinity-exporter
entra-ca-templates
maester-copilot-tests
copilot-security-checker
purview-content-explorer-helpers
purview-dlp-export
dotfiles
```

- [ ] **Step 1: Dry-run all 8**

```bash
for repo in copilot-kql-library acinfinity-exporter entra-ca-templates maester-copilot-tests copilot-security-checker purview-content-explorer-helpers purview-dlp-export dotfiles; do
  echo "=== $repo ==="
  python3 scripts/rollout_zensical_standard.py --repo "LukeEvansTech/$repo" --publish --dry-run
done
```

Review the output; any unexpected diffs in `renovate.json` (existing local overrides) get flagged here.

- [ ] **Step 2: Apply for real, one repo at a time**

```bash
for repo in copilot-kql-library acinfinity-exporter entra-ca-templates maester-copilot-tests copilot-security-checker purview-content-explorer-helpers purview-dlp-export dotfiles; do
  echo "=== $repo ==="
  python3 scripts/rollout_zensical_standard.py --repo "LukeEvansTech/$repo" --publish
  echo ""
done
```

- [ ] **Step 3: Wait for all docs deploys to complete**

```python
# Save as /tmp/wait_deploys_phase2.py
import subprocess, json, time
repos = ["copilot-kql-library", "acinfinity-exporter", "entra-ca-templates", "maester-copilot-tests",
         "copilot-security-checker", "purview-content-explorer-helpers", "purview-dlp-export", "dotfiles"]
start = time.time()
while True:
    pending = []
    failed = []
    for r in repos:
        head = json.loads(subprocess.run(["gh","api",f"repos/LukeEvansTech/{r}/commits?per_page=1"], capture_output=True, text=True).stdout)[0]["sha"]
        runs = json.loads(subprocess.run(["gh","api",f"repos/LukeEvansTech/{r}/actions/runs?head_sha={head}"], capture_output=True, text=True).stdout).get("workflow_runs", [])
        docs = [run for run in runs if run["name"] == "Docs"]
        if not docs: continue
        d = docs[0]
        if d["status"] != "completed":
            pending.append(r)
        elif d["conclusion"] != "success":
            failed.append((r, d["conclusion"]))
    print(f"[{int(time.time()-start)}s] pending={len(pending)} failed={len(failed)}")
    if not pending: break
    if time.time()-start > 600: break
    time.sleep(20)
print(f"\nFailed: {failed}")
```

```bash
python3 /tmp/wait_deploys_phase2.py
```

Expected: all 8 `Docs` workflows complete `success`.

- [ ] **Step 4: Verify each live site has zensical generator + toggle**

```bash
for repo in copilot-kql-library acinfinity-exporter entra-ca-templates maester-copilot-tests copilot-security-checker purview-content-explorer-helpers purview-dlp-export dotfiles; do
  url=$(gh api "repos/LukeEvansTech/$repo/pages" --jq '.html_url')
  gen=$(curl -sL "$url" | grep -oE '<meta name="generator" content="zensical-[^"]*"' | head -1)
  toggle=$(curl -sL "$url" | grep -c 'Switch to dark mode')
  echo "$repo: $gen | toggle_lines=$toggle"
done
```

Expected: each shows `generator="zensical-0.0.43"` and `toggle_lines=1`.

- [ ] **Step 5: Per-repo verification of drift check**

For each repo, open a synthetic PR (whitespace change in docs/) and confirm Docs Standard Check passes. Close PR. Can be batched by writing a tiny helper that opens 8 PRs and reports their check status, then closes them.

- [ ] **Step 6: Rollback per repo if needed**

If a specific repo fails, run the script's reverse: per-file revert via API to the pre-rollout commit. The Pages settings haven't changed; the gh-pages branch (if any) is untouched.

---

## Phase 3 — Migrate the 3 gh-pages-branch repos

### Task 3.1: PSReddit — switch Pages build_type and apply standard

**Files (target repo `LukeEvansTech/PSReddit`):**
- Modify: Pages settings (API)
- Create: `.github/workflows/docs.yml`, `lint.yml` (already exists; canonical), `docs-standard-check.yml`, `.markdownlint.yml`
- Modify: `renovate.json`
- Delete: `.github/workflows/psreddit-deploy-docs.yml`

- [ ] **Step 1: Switch Pages build_type to workflow**

```bash
gh api -X PUT repos/LukeEvansTech/PSReddit/pages -f build_type=workflow
gh api repos/LukeEvansTech/PSReddit/pages --jq '.build_type'
```

Expected: `workflow`.

- [ ] **Step 2: Apply standard rollout**

```bash
python3 scripts/rollout_zensical_standard.py --repo LukeEvansTech/PSReddit --publish
```

- [ ] **Step 3: Trigger Docs workflow manually (so the artifact deploys via the new path)**

```bash
gh workflow run docs.yml --repo LukeEvansTech/PSReddit --ref main
```

- [ ] **Step 4: Wait + verify**

```bash
sleep 5
RUN=$(gh api 'repos/LukeEvansTech/PSReddit/actions/runs?event=workflow_dispatch&per_page=1' --jq '.workflow_runs[0].id')
until [ "$(gh api repos/LukeEvansTech/PSReddit/actions/runs/$RUN --jq '.status')" = "completed" ]; do sleep 15; done
gh api "repos/LukeEvansTech/PSReddit/actions/runs/$RUN" --jq '{conclusion, html_url}'
```

Expected: `conclusion: success`.

Live check:
```bash
curl -sL https://lukeevanstech.github.io/PSReddit/ | grep -oE '<meta name="generator" content="[^"]+"' | head -1
```

Expected: `zensical-0.0.43`.

- [ ] **Step 5: Hold for one week; document gh-pages branch for later deletion**

Add a follow-up note in the implementation log: "Delete `gh-pages` branch on `PSReddit` after 2026-06-02 if all live checks remain green."

Do NOT delete the branch in this step. The branch is the rollback path.

### Task 3.2: purview-content-explorer-export — same as Task 3.1

- [ ] **Step 1: Switch Pages build_type**

```bash
gh api -X PUT repos/LukeEvansTech/purview-content-explorer-export/pages -f build_type=workflow
```

- [ ] **Step 2: Apply standard**

```bash
python3 scripts/rollout_zensical_standard.py --repo LukeEvansTech/purview-content-explorer-export --publish
```

- [ ] **Step 3: Trigger Docs workflow**

```bash
gh workflow run docs.yml --repo LukeEvansTech/purview-content-explorer-export --ref main
```

- [ ] **Step 4: Wait + verify** (same as 3.1 Step 4 with appropriate repo substitution)

- [ ] **Step 5: Document gh-pages branch for week-out deletion**

### Task 3.3: defender-device-control-unmanaged — same as Task 3.1

- [ ] **Step 1: Switch Pages build_type**

```bash
gh api -X PUT repos/LukeEvansTech/defender-device-control-unmanaged/pages -f build_type=workflow
```

- [ ] **Step 2: Apply standard**

```bash
python3 scripts/rollout_zensical_standard.py --repo LukeEvansTech/defender-device-control-unmanaged --publish
```

The rollout script also deletes the superseded `ddcu-deploy-docs.yml` and `ddcu-lint.yml`.

- [ ] **Step 3: Trigger Docs workflow**

```bash
gh workflow run docs.yml --repo LukeEvansTech/defender-device-control-unmanaged --ref main
```

- [ ] **Step 4: Wait + verify**

- [ ] **Step 5: Document gh-pages branch for week-out deletion**

---

## Phase 4 — Build-only repos

### Task 4.1: Apply standard with `publish: false` to the 6 build-only repos

**Repos:**
```
lgwebos
stwt-m365-consolidation
col-entra-id
github-infrastructure
network-ops
terraform-dns
```

- [ ] **Step 1: Dry-run**

```bash
for repo in lgwebos stwt-m365-consolidation col-entra-id github-infrastructure network-ops terraform-dns; do
  echo "=== $repo ==="
  python3 scripts/rollout_zensical_standard.py --repo "LukeEvansTech/$repo" --no-publish --allow-no-pages --dry-run
done
```

- [ ] **Step 2: Apply for real**

```bash
for repo in lgwebos stwt-m365-consolidation col-entra-id github-infrastructure network-ops terraform-dns; do
  echo "=== $repo ==="
  python3 scripts/rollout_zensical_standard.py --repo "LukeEvansTech/$repo" --no-publish --allow-no-pages
done
```

The rollout script's `delete_file` step removes the four now-orphaned `deploy-docs.yml` files in `col-entra-id`, `github-infrastructure`, `network-ops`, `terraform-dns`. `lgwebos` and `stwt-m365-consolidation` never had a docs deploy workflow.

- [ ] **Step 3: Verify each Docs workflow builds (but does not deploy)**

```bash
for repo in lgwebos stwt-m365-consolidation col-entra-id github-infrastructure network-ops terraform-dns; do
  head=$(gh api "repos/LukeEvansTech/$repo/commits?per_page=1" --jq '.[0].sha')
  runs=$(gh api "repos/LukeEvansTech/$repo/actions/runs?head_sha=$head" --jq '.workflow_runs[] | select(.name=="Docs") | {status, conclusion}')
  echo "$repo: $runs"
done
```

Expected: each `status: completed`, `conclusion: success`. Deploy job will be skipped (visible in the run summary).

- [ ] **Step 4: Verify drift check passes (with allow-no-pages flag effective)**

Open a synthetic PR on one of these (e.g., `col-entra-id`). The `Docs Standard Check` job should pass because `allow-no-pages: true` skips the Pages-API check.

- [ ] **Step 5: Sanity-check `col-entra-id`'s separate Handover-Document workflow**

```bash
gh api repos/LukeEvansTech/col-entra-id/actions/workflows --jq '.workflows[] | .name'
```

Confirm `Generate Handover Document` is still listed but its push-trigger failure remains (out-of-scope per spec).

---

## Phase 5 — Phased linter rollout (documented checklist only)

This phase happens over calendar weeks, not implementation tasks. Status is tracked manually.

### Week 1 — link-check soft-launched

State after Phase 4: every repo has `link-check: true, link-check-soft-launch: true` (defaults). Triage any 4xx/5xx that appear in workflow runs:

- For genuinely dead internal links → fix in content.
- For flaky external links → add to a `.lycheeignore` at repo root.

### Week 2 — flip link-check to hard

Per repo, edit the per-repo `.github/workflows/docs.yml` to set `link-check-soft-launch: false`:
```yaml
jobs:
  docs:
    uses: LukeEvansTech/shared-workflows/.github/workflows/zensical.yml@<sha>
    with:
      publish: ${{ github.event_name != 'pull_request' }}
      link-check-soft-launch: false
```

### Week 3+ — opt repos into Vale

Per repo:
1. Add `.vale.ini` at repo root (template content from spec Section 5).
2. Add `vale: true, vale-soft-launch: true` to the per-repo docs.yml `with:` block.
3. Triage warnings. Add per-repo product vocab to `.vale/styles/docs/`.
4. Once clean, flip `vale-soft-launch: false`.

(No code changes in this plan; these adjustments are made per-repo as each is ready.)

---

## Phase 6 — Validation & sign-off

### Task 6.1: Run drift check against all 18 repos via the audit script

**Files:**
- Create: `scripts/audit_zensical_standard.py`

- [ ] **Step 1: Create the audit script**

```python
#!/usr/bin/env python3
"""Run zensical drift check against all 18 repos and report a summary.

Clones each into a temp dir, runs zensical_drift.py against it, collects results.
"""
import subprocess, json, tempfile, sys
from pathlib import Path

REPOS_PUBLISHING = [
    "LukeEvansTech/PSReddit",
    "LukeEvansTech/copilot-kql-library",
    "LukeEvansTech/acinfinity-exporter",
    "LukeEvansTech/entra-ca-templates",
    "LukeEvansTech/maester-copilot-tests",
    "LukeEvansTech/copilot-security-checker",
    "LukeEvansTech/purview-content-explorer-helpers",
    "LukeEvansTech/purview-content-explorer-export",
    "LukeEvansTech/purview-dlp-export",
    "LukeEvansTech/defender-device-control-unmanaged",
    "LukeEvansTech/M365LabelSync",
    "LukeEvansTech/dotfiles",
]
REPOS_BUILD_ONLY = [
    "LukeEvansTech/lgwebos",
    "LukeEvansTech/stwt-m365-consolidation",
    "LukeEvansTech/col-entra-id",
    "LukeEvansTech/github-infrastructure",
    "LukeEvansTech/network-ops",
    "LukeEvansTech/terraform-dns",
]
DRIFT = Path(__file__).parent / "zensical_drift.py"


def audit(repo: str, allow_no_pages: bool) -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run(["gh", "repo", "clone", repo, tmp, "--", "--depth=1"], capture_output=True, text=True)
        if r.returncode != 0:
            return 1, f"clone failed: {r.stderr.strip()}"
        args = ["python3", str(DRIFT), "--repo-root", tmp, "--repo", repo]
        if allow_no_pages: args.append("--allow-no-pages")
        r = subprocess.run(args, capture_output=True, text=True)
        return r.returncode, (r.stdout + r.stderr).strip()


def main() -> int:
    overall = 0
    print(f"{'Repo':45}  {'Result'}")
    print("-" * 80)
    for repo in REPOS_PUBLISHING:
        rc, out = audit(repo, allow_no_pages=False)
        status = "PASS" if rc == 0 else "FAIL"
        print(f"{repo:45}  {status}")
        if rc != 0:
            for line in out.splitlines()[-5:]:
                print(f"    {line}")
            overall = 1
    for repo in REPOS_BUILD_ONLY:
        rc, out = audit(repo, allow_no_pages=True)
        status = "PASS" if rc == 0 else "FAIL"
        print(f"{repo:45}  {status} (build-only)")
        if rc != 0:
            for line in out.splitlines()[-5:]:
                print(f"    {line}")
            overall = 1
    print()
    print("OVERALL:", "GREEN" if overall == 0 else "RED")
    return overall


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Commit the audit script**

```bash
chmod +x scripts/audit_zensical_standard.py
git add scripts/audit_zensical_standard.py
git commit -m "feat(audit): add zensical standard audit script"
git push origin main
```

- [ ] **Step 3: Run the audit**

```bash
python3 scripts/audit_zensical_standard.py
```

Expected: every repo shows `PASS`. If any FAIL, fix the specific drift and re-run.

- [ ] **Step 4: Visual spot-check 3-4 random Pages sites**

```bash
for repo in PSReddit dotfiles M365LabelSync purview-dlp-export; do
  url=$(gh api "repos/LukeEvansTech/$repo/pages" --jq '.html_url')
  echo "=== $url ==="
  curl -sL "$url" | grep -oE 'generator" content="[^"]+|Switch to (dark|light) mode' | sort -u
done
```

Expected: each shows `generator="zensical-0.0.43"` plus both toggle texts.

### Task 6.2: Update memory; document follow-ups

- [ ] **Step 1: Update memory notes**

Add to `MEMORY.md` (in claude memory dir): a one-liner pointing to the new standard.

- [ ] **Step 2: List remaining follow-ups (separate, not in this plan)**

- `col-entra-id` Generate Handover Document workflow still failing on docs/** pushes — needs PAT or PR-based commit pattern. Track as separate issue.
- `lgwebos-lint.yml` is misleadingly named (it's bats/shellcheck tests, not docs lint) — rename to `test.yml` separately.
- Week 2 link-check hard-flip — track in followup checklist.
- Week 3 Vale opt-in — track in followup checklist.
- Delete the gh-pages branches on PSReddit, purview-content-explorer-export, defender-device-control-unmanaged after one week of green deploys.

### Task 6.3: Final commit message and push

- [ ] **Step 1: Push any final shared-workflows changes**

```bash
cd /Users/luke.evans/Scratch/zenscialupdates/shared-workflows
git status
git push origin main
```

- [ ] **Step 2: Tag a follow-up release if scripts changed**

```bash
# Only if substantive changes since v1
git tag -a v1.1 -m "audit + sync helpers"
git push origin v1.1
```

---

## Out of scope (flagged in spec; not implemented here)

- `col-entra-id`'s `Generate Handover Document` workflow failure (independent fix).
- Renaming `lgwebos-lint.yml` (it's bats/shellcheck, not docs).
- Per-repo phased linter hardening (Week 2-3+ activities — calendar-paced).
- Deleting the legacy `gh-pages` branches (deferred one week as rollback path).
