# Zensical Docs Standard — Design

**Date:** 2026-05-26
**Owner:** Luke Evans
**Scope:** 18 `LukeEvansTech/*` repos that publish (or could publish) documentation built with [zensical](https://zensical.org/).
**Status:** Approved design, awaiting implementation plan

---

## Goal

Define one canonical shape for every zensical docs site across the 18 repos — config, theme, deploy workflow, lint workflow, Renovate config, Pages settings — and a drift-check mechanism that fails PRs when a repo falls out of standard.

The standard enforces *structure* (config keys, workflow filenames, action versioning, palette block, deploy mechanism). It stays agnostic on *visuals* (primary/accent colour, custom CSS, OOTB zensical theming is fine).

---

## Non-goals

- Building a shared CSS / brand kit. Use OOTB zensical theming; per-repo overrides allowed.
- Standardising nav structure, page set, or content shape.
- Touching project-specific test workflows (e.g., `lgwebos-lint.yml` which is shellcheck/bats, not docs lint).
- Migrating mkdocs-material — already complete before this work; only the version pin needed updating, done 2026-05-26.
- Adding `.editorconfig`, `CODEOWNERS`, PR templates — these affect more than just docs.
- Auto-fixing existing markdown lint / link-check / Vale findings as part of rollout (soft-launched first; flip to hard once each repo is clean).

---

## Repo categorization

After disabling Pages on 4 private repos on 2026-05-26, the 18 repos split into:

**12 Pages-publishing repos** (`publish: true`):
PSReddit · copilot-kql-library · acinfinity-exporter · entra-ca-templates · maester-copilot-tests · copilot-security-checker · purview-content-explorer-helpers · purview-content-explorer-export · purview-dlp-export · defender-device-control-unmanaged · M365LabelSync · dotfiles

**6 build-only repos** (`publish: false`):
lgwebos · stwt-m365-consolidation · col-entra-id · github-infrastructure · network-ops · terraform-dns

The build-only repos still build their docs in CI (validates the site compiles) but don't deploy. lgwebos and stwt-m365-consolidation never had Pages; the other 4 had Pages disabled on 2026-05-26 because they're private repos with publicly-accessible Pages, which was not the intended posture.

---

## Architecture

Three pieces; nothing else.

### 1. `shared-workflows` (source of truth)

```
shared-workflows/.github/workflows/
├── super-linter.yml          (EXISTS — markdown/yaml/general lint; called by 13 repos already)
├── security-scans.yml        (EXISTS — Checkov + Trivy)
├── meta-actionlint.yml       (EXISTS)
├── zensical.yml              (NEW — reusable: build + deploy + link-check + prose)
└── zensical-drift-check.yml  (NEW — reusable: PR-blocking standard enforcement)

shared-workflows/templates/
├── docs.yml                  (NEW — canonical per-repo caller)
├── docs-standard-check.yml   (NEW — canonical per-repo drift-check caller)
├── lint.yml                  (NEW — canonical per-repo super-linter caller)
├── renovate.json             (NEW — canonical Renovate config)
└── .markdownlint.yml         (NEW — canonical markdownlint config)

shared-workflows/scripts/
└── zensical_drift.py         (NEW — implementation of drift checks)
```

### 2. Per-repo files (all 18)

```
<repo>/
├── docs/
│   ├── zensical.toml         (per-repo, conforms to canonical palette/theme block)
│   ├── requirements.txt      (zensical==X.Y.Z, Renovate-managed)
│   └── docs/                 (content — universal layout)
├── .markdownlint.yml         (mirrors shared-workflows/templates/.markdownlint.yml)
├── .vale.ini                 (optional — only when Vale is enabled for the repo)
├── renovate.json             (extends config:recommended + helpers:pinGitHubActionDigests)
└── .github/workflows/
    ├── docs.yml              (calls shared-workflows/zensical.yml)
    ├── docs-standard-check.yml  (calls shared-workflows/zensical-drift-check.yml on PR)
    └── lint.yml              (calls shared-workflows/super-linter.yml; already exists in 13 repos)
```

### 3. Per-repo GitHub settings

- Pages `build_type: workflow` for the 12 Pages-publishing repos.
- Pages disabled for the 6 build-only repos.

---

## Section 1 — Canonical `docs/zensical.toml`

Three classes of fields.

### Required-and-fixed (drift check enforces)

```toml
[project.theme]
name = "material"
variant = "modern"
language = "en"

# Palette: two entries, media-query auto-detect, nested toggle table
[[project.theme.palette]]
media = "(prefers-color-scheme: light)"
scheme = "default"

[project.theme.palette.toggle]
icon = "material/brightness-7"
name = "Switch to dark mode"

[[project.theme.palette]]
media = "(prefers-color-scheme: dark)"
scheme = "slate"

[project.theme.palette.toggle]
icon = "material/brightness-4"
name = "Switch to light mode"

# Markdown extensions baseline
[markdown_extensions]
admonition = {}
toc = { permalink = true }

[markdown_extensions.pymdownx]
highlight = { anchor_linenums = true, line_spans = "__span", pygments_lang_class = true }
inlinehilite = {}
snippets = {}
superfences = {}
```

### Required-but-per-repo (drift check verifies presence only)

| Field | Notes |
|---|---|
| `project.site_name` | Free text |
| `project.site_description` | Free text |
| `project.site_author` | Free text |
| `project.site_url` | Drift check enforces lowercase host + no `lukevanstech` typo |
| `project.copyright` | Free text |
| `project.repo_url` | |
| `project.repo_name` | |
| `project.edit_uri` | Conventionally `"edit/main/docs/docs/"` reflecting universal layout |
| `[project.theme.icon].repo` | Typically `"fontawesome/brands/github"` |
| `[[nav]]` | Free per-repo; not inspected |

### Optional (allowed, not required)

| Field | When |
|---|---|
| `project.generator = false` | Hides "Made with zensical" footer; OOTB default is acceptable |
| `project.extra_css = [...]` | When the repo has its own brand CSS |
| `primary` / `accent` in palette entries | Per-repo colour choice; both present or both absent |

### Forbidden (drift check fails)

- `theme.name` anything other than `"material"`
- Flat `toggle_icon` / `toggle_name` keys (must be nested `[project.theme.palette.toggle]` table; only that form renders the visible button in zensical compat mode)
- A `[[project.theme.palette]]` entry without a `media` query (breaks auto-detect)
- `site_url` with mixed-case host or `lukevanstech` typo

### `docs/requirements.txt`

Exactly one line: `zensical==X.Y.Z`. Renovate's `pip_requirements` manager bumps the version. No `>=`, no missing version.

---

## Section 2 — `shared-workflows/.github/workflows/zensical.yml`

Reusable workflow. Multiple jobs; caller controls which run via inputs. All inner actions SHA-pinned.

### Inputs

| Input | Type | Default | Purpose |
|---|---|---|---|
| `publish` | bool | `true` | Run the deploy job. `false` for build-only repos. |
| `python-version` | string | `"3.14"` | |
| `working-directory` | string | `"docs"` | |
| `link-check` | bool | `true` | Run lychee against built site. |
| `link-check-soft-launch` | bool | `true` | Lychee warnings only initially. |
| `vale` | bool | `false` | Opt-in prose linting. |
| `vale-soft-launch` | bool | `true` | Vale warnings only initially. |
| `strict` | bool | `true` | Pass `--strict` to `zensical build`. |

### Jobs

1. **`build`** — always.
   - `actions/checkout@<sha>`
   - `actions/setup-python@<sha>` (with pip cache keyed on `${{ working-directory }}/requirements.txt`)
   - `pip install -r ${{ working-directory }}/requirements.txt`
   - `cd ${{ working-directory }} && zensical build${{ inputs.strict && ' --strict' || '' }}`
   - `actions/configure-pages@<sha>`
   - `actions/upload-pages-artifact@<sha>` with path `${{ working-directory }}/site`

2. **`link-check`** — if `link-check: true`, depends on `build`.
   - `lycheeverse/lychee-action@<sha>` against `${{ working-directory }}/site`
   - `continue-on-error: ${{ inputs.link-check-soft-launch }}`
   - Caches lychee state to skip unchanged links
   - Default behaviour: skip private IPs, retry once on 429/5xx, accept 200/206/301/302

3. **`prose`** — if `vale: true`, depends on `build`.
   - `errata-ai/vale-action@<sha>`
   - Reads `.vale.ini` from repo root
   - `continue-on-error: ${{ inputs.vale-soft-launch }}`

4. **`deploy`** — if `publish: true` AND triggered by `push` to `main`, depends on `build` (and on `link-check` if hard-failed).
   - `actions/deploy-pages@<sha>`
   - `environment: github-pages` with `url` output

### Caller (per-repo `docs.yml`)

```yaml
name: Docs

on:
  push:
    branches: [main]
    paths: ["docs/**", ".github/workflows/docs.yml"]
  pull_request:
    paths: ["docs/**", ".github/workflows/docs.yml"]
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
    uses: LukeEvansTech/shared-workflows/.github/workflows/zensical.yml@<sha> # v1
    with:
      publish: ${{ github.event_name != 'pull_request' }}
```

Build-only repos override `publish: false`.

---

## Section 3 — `shared-workflows/.github/workflows/zensical-drift-check.yml`

PR-blocking reusable workflow. Runs the `scripts/zensical_drift.py` checker against the calling repo. Never deploys.

### Checks (each emits a separate annotated step)

1. `docs/zensical.toml` exists and parses as valid TOML.
2. **Pin format** — `docs/requirements.txt` has exactly one `zensical==X.Y.Z` line. Rejects `>=`, missing version, or extra deps.
3. **Palette block** — two `[[project.theme.palette]]` entries with required `media`/`scheme`/nested `toggle` shape.
4. **Theme baseline** — `[project.theme]` has `name = "material"`, `variant = "modern"`, `language = "en"`.
5. **Layout** — `docs/docs/` exists; `docs_dir` is `"docs"` or absent.
6. **Workflow filenames** — `.github/workflows/docs.yml`, `lint.yml`, `docs-standard-check.yml` exist with the canonical thin-caller shape.
7. **SHA-pinning** — every `uses:` line in those three workflows references a 40-hex SHA. Tag-pinned fails.
8. **Pages settings** (only when Pages enabled) — `build_type == "workflow"`. Queries `gh api repos/.../pages`.
9. **Renovate config** — `renovate.json` extends both `config:recommended` and `helpers:pinGitHubActionDigests`.
10. **`site_url` hygiene** — lowercase host, no `lukevanstech` typo. Warns on `localhost` (acceptable for build-only).
11. **`.markdownlint.yml` hash** — must match the canonical `shared-workflows/templates/.markdownlint.yml`. Drifted repos fail.

### Inputs

- `allow-build-type-legacy` (bool, default `false`) — escape hatch for repos mid-migration.
- `allow-no-pages` (bool, default `false`) — for build-only repos, marks check 8 as N/A.
- `vale-required` (bool, default `false`) — enforce `.vale.ini` presence when Vale is enabled.

### Caller (per-repo `docs-standard-check.yml`)

```yaml
name: Docs Standard Check

on:
  pull_request:
    paths: ["docs/**", ".github/workflows/**", "renovate.json", ".markdownlint.yml"]

permissions:
  contents: read
  pull-requests: write

jobs:
  drift:
    uses: LukeEvansTech/shared-workflows/.github/workflows/zensical-drift-check.yml@<sha> # v1
```

Build-only repos add `with: { allow-no-pages: true }`.

---

## Section 4 — `lint.yml` (per-repo super-linter caller)

The canonical content is 16 lines. Filename always `lint.yml`; no repo-name prefix.

```yaml
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
    uses: LukeEvansTech/shared-workflows/.github/workflows/super-linter.yml@<sha> # v1
    with:
      soft-launch: false
```

**Current state** (rollout targets):
- 13 repos already have this exact pattern. Drift check verifies SHA-pinning and `soft-launch: false`.
- 2 repos missing entirely (col-entra-id, acinfinity-exporter) — add during Phase 2.
- 1 repo has non-canonical filename (defender-device-control-unmanaged's `ddcu-lint.yml`) — rename during Phase 2.
- 4 repos use tag-pinned actions instead of SHA — Renovate will fix automatically after first run; pre-bump if convenient.
- `lgwebos`'s separate `lgwebos-lint.yml` (shellcheck/bats project tests) is **not** a docs lint workflow — explicitly out of scope, left alone.

---

## Section 5 — Auxiliary configs

### `renovate.json` (every repo)

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": [
    "config:recommended",
    "helpers:pinGitHubActionDigests"
  ]
}
```

`helpers:pinGitHubActionDigests` is what converts tag-pinned actions to SHA-pinned and keeps them updated. Drift check verifies both extensions present. Repos may add further presets per local need.

### `.markdownlint.yml` (every repo, at repo root)

Canonical content lives at `shared-workflows/templates/.markdownlint.yml`:

```yaml
default: true
MD013: false        # line length — disabled for prose
MD033: false        # inline HTML — allowed (zensical/material uses some inline HTML)
MD041: false        # first-line h1 — disabled (zensical uses page title from nav)
MD024:
  siblings_only: true
```

Drift check compares SHA-256 of the per-repo file to the canonical (`shared-workflows/templates/.markdownlint.yml`). Initial rollout copies it in. Future updates: PR against the canonical in shared-workflows, then a `scripts/sync_markdownlint.py` helper (added in Phase 0) propagates the new content to all 18 repos in one batch run.

### `.vale.ini` (only when Vale enabled)

```ini
StylesPath = .vale/styles
MinAlertLevel = warning
Vocab = docs

Packages = proselint, Microsoft

[*.md]
BasedOnStyles = Vale, proselint, Microsoft

Microsoft.Contractions = NO
Microsoft.We = NO

[docs/changelog.md]
Microsoft.HeadingPunctuation = NO
```

`.vale/styles/` populated by the vale-action during CI. `.vale/styles/docs/` holds per-repo product/tech vocab.

Phased: every repo starts with Vale disabled. Once a repo's prose is clean, opt in with `vale: true, vale-soft-launch: true`. Flip to hard-fail once clean.

---

## Section 6 — Rollout plan

Six phases. Each phase has a verification step and an explicit rollback.

### Phase 0 — Prep in `shared-workflows`

Add to `LukeEvansTech/shared-workflows`:
1. `templates/.markdownlint.yml`
2. `templates/docs.yml`, `templates/lint.yml`, `templates/docs-standard-check.yml`, `templates/renovate.json`
3. `.github/workflows/zensical.yml` (Section 2)
4. `.github/workflows/zensical-drift-check.yml` (Section 3)
5. `scripts/zensical_drift.py` (implementation of drift checks)
6. Tag `v1`; capture SHA for downstream pinning.

**Verify:** shared-workflows own CI green; drift script produces expected output against a known-bad fixture and a known-good fixture.

**Rollback:** revert commits, untag.

### Phase 1 — Canary on `M365LabelSync`

Chosen because it's been touched most recently (2026-05-26 commits), public Pages, no gh-pages legacy. Apply all standard files.

**Verify:**
- New `Docs` workflow succeeds end-to-end via the reusable.
- Live site at `https://lukeevanstech.github.io/M365LabelSync/` still renders; dark-mode toggle still present.
- Drift check passes on a synthetic PR that conforms.
- Drift check fails on a synthetic PR that violates (e.g., flat `toggle_icon` key).
- Existing `Lint` workflow still passes.

**Rollback:** revert each file via the contents API; Pages settings unchanged.

### Phase 2 — Bulk rollout: 8 "easy" repos

The 12 Pages-publishing repos minus the canary minus the 3 gh-pages-branch repos:

```
copilot-kql-library, acinfinity-exporter, entra-ca-templates, maester-copilot-tests,
copilot-security-checker, purview-content-explorer-helpers, purview-dlp-export, dotfiles
```

(`PSReddit`, `purview-content-explorer-export`, and `defender-device-control-unmanaged` are in Phase 3.)

Same file changes as the canary, applied in parallel.

**Special cases:**
- `acinfinity-exporter` — add `lint.yml` (currently missing). Re-pin its tag-pinned actions to SHA.

**Verify per repo:** push triggers new Docs workflow, succeeds, site renders, drift check passes on synthetic PR.

**Rollback per repo:** revert the four file commits.

### Phase 3 — Migrate the 3 gh-pages-branch repos

```
PSReddit, purview-content-explorer-export, defender-device-control-unmanaged
```

Per repo:
1. Switch Pages `build_type: legacy` → `workflow` via API.
2. Replace existing deploy workflow with canonical `docs.yml`.
3. Trigger `Docs` workflow via `workflow_dispatch`.
4. Verify live URL serves new artifact-based content.
5. Wait one week before deleting `gh-pages` branch (rollback path).

**Risk:** brief window (seconds) where Pages may serve stale gh-pages snapshot. Acceptable.

**Rollback:** flip build_type back to `legacy`; the gh-pages branch is still intact.

### Phase 4 — Build-only repos

```
lgwebos, stwt-m365-consolidation, col-entra-id, github-infrastructure,
network-ops, terraform-dns
```

Apply standard files with caller override:

```yaml
jobs:
  docs:
    uses: LukeEvansTech/shared-workflows/.github/workflows/zensical.yml@<sha> # v1
    with:
      publish: false
```

The `docs-standard-check.yml` for these repos passes `allow-no-pages: true`.

The 4 newly-disabled-Pages repos have their old deploy workflows already neutered (push/PR triggers stripped 2026-05-26); Phase 4 replaces them entirely with the canonical `docs.yml`.

**Add lint.yml to col-entra-id** during this phase.

**Verify per repo:** push triggers Docs workflow, build job succeeds, deploy job skipped (`publish: false`), drift check passes.

### Phase 5 — Phased linter rollout

After all 18 are on the standard:

1. **Week 1:** every repo has `link-check: true, link-check-soft-launch: true`. Triage warnings.
2. **Week 2:** flip `link-check-soft-launch: false` per repo as warnings clear. Some repos may need `.lycheeignore` for flaky externals.
3. **Week 3+ (optional):** opt repos into Vale by adding `.vale.ini` and `vale: true, vale-soft-launch: true`. Once clean, flip to hard-fail.

### Phase 6 — Validation & sign-off

- Run an audit script that calls drift check against all 18 repos and reports a green table.
- Spot-check 3-4 live sites visually.
- Update memory notes; archive obsolete migration scripts.

---

## Out of scope (flagged but not addressed)

- **`col-entra-id` `Generate Handover Document` workflow failure** — protected-branch + GH Actions bot can't push regenerated PDF to main. Independent of docs standard; needs PAT or PR-based commit pattern. Fix separately.
- **`lgwebos-lint.yml`** — bats/shellcheck/shfmt project tests. Not a docs workflow despite the misleading filename; leave alone (or rename to `test.yml` independently).

---

## Why these choices

| Choice | Reason |
|---|---|
| Reusable workflow in shared-workflows | Anchors a single source of truth; works with existing super-linter pattern; Renovate digest helper covers update flow |
| Exact-version pin `zensical==X.Y.Z` | zensical is alpha (0.0.x), releasing every 3-7 days × 8 transitive deps. Hash-pinning would churn Renovate. Docs-build tooling, not runtime — modest supply-chain blast radius. |
| Actions-based deploy for everyone | Modern pattern; `actions/deploy-pages` requires `build_type: workflow`; cleaner artifact handling than gh-pages branch |
| SHA-pinned action versions | Matches user's stated preference; security-correct; Renovate `helpers:pinGitHubActionDigests` automates |
| Nested `[project.theme.palette.toggle]` syntax | The flat `toggle_icon`/`toggle_name` keys parse as valid TOML but don't render the visible toggle button in zensical compat mode. Verified empirically across all 18 sites on 2026-05-26. |
| Drift check as PR-blocking, not weekly audit | Catches violations at introduction time, when context is freshest; lower-friction than scheduled issue-opening |
| Soft-launch lint additions | Avoids a flood of red PRs on existing content; gives each repo time to clear warnings before hard-fail |
