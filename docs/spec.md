# Super-Linter Rollout — Design

**Date:** 2026-05-03
**Owner:** Luke Evans
**Scope:** Two GitHub accounts — `LukeEvansTech` (~36 active repos) and `codelooks-com` (~18 repos)
**Status:** Approved design, awaiting implementation plan

---

## Goal

Make [super-linter](https://github.com/super-linter/super-linter) the standard linting layer across every non-archived repo in both GitHub accounts. Replace bespoke single-language lint workflows where super-linter covers the language; keep custom workflows only for languages or tools super-linter doesn't support.

Soft-launch the rollout (linter runs but does not block CI), then clean up findings repo-by-repo at the user's pace.

---

## Non-goals

- Auto-fixing existing lint issues across all repos as part of rollout
- Enforcing blocking CI on day 1
- Building a shared rule-config layer up front (deferred until commonalities emerge naturally — bottom-up consolidation)
- Standardising forks (forks are flagged for review; user will decide per-fork during a separate cleanup pass)
- Modifying archived repos

---

## Architecture

Two pieces; nothing else.

### 1. Central reusable workflow

A new **public** repo `LukeEvansTech/shared-workflows` hosts one reusable workflow.

`.github/workflows/super-linter.yml`:

```yaml
name: Super-Linter (reusable)
on:
  workflow_call:
    inputs:
      default-branch:
        type: string
        default: main
      validate-all-codebase:
        type: boolean
        default: false
      soft-launch:
        type: boolean
        default: true
      filter-regex-exclude:
        type: string
        default: '(^|/)(vendor|node_modules|\.terraform|\.venv|dist|build)/'

jobs:
  lint:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      statuses: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Super-Linter
        uses: super-linter/super-linter@v8
        continue-on-error: ${{ inputs.soft-launch }}
        env:
          DEFAULT_BRANCH: ${{ inputs.default-branch }}
          VALIDATE_ALL_CODEBASE: ${{ inputs.validate-all-codebase }}
          FILTER_REGEX_EXCLUDE: ${{ inputs.filter-regex-exclude }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          LOG_LEVEL: WARN
          SAVE_SUPER_LINTER_SUMMARY: true
          SAVE_SUPER_LINTER_OUTPUT: true
```

Tagged `v1`. Callers pin to `@v1` and get non-breaking updates automatically.

A `renovate.json` (preset `config:recommended`) on this repo only — Renovate opens **one** PR per super-linter release, propagating to all callers via the floating `@v1` tag.

### 2. Per-repo caller workflow

Each target repo gets `.github/workflows/lint.yml`:

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
```

The `permissions:` block is required: GitHub's modern default is `default_workflow_permissions: read`, but the reusable workflow declares `statuses: write` for super-linter. If the caller doesn't grant equal-or-greater permissions, the runner refuses to start (`startup_failure`). This was discovered during Phase 1 and is documented in lessons-learned at the bottom of this spec.

For non-`main` default branches, override:

```yaml
    with:
      default-branch: master
```

When a repo is cleaned up and ready to gate merges, flip:

```yaml
    with:
      soft-launch: false
```

### 3. Per-repo `.github/linters/` (optional)

Super-linter natively reads linter config files (`.markdownlint.json`, `.yamllint`, `.shellcheckrc`, etc.) from the repo being linted. No extra wiring needed. Each repo owns its rules. We do not centralise rule configs at this stage — bottom-up consolidation only if patterns repeat ≥5 times across repos.

---

## Distribution & versioning

| Concern | Approach |
| --- | --- |
| Cross-account access | Central repo is **public** so `codelooks-com` repos can call it |
| Sensitive content | None — workflow is generic super-linter orchestration |
| Version pinning | Callers pin `@v1` (major). Central workflow internally pins `super-linter@v8` |
| Bumps | Renovate on central repo → 1 PR per super-linter release. Callers float on `@v1` |
| Breaking changes | Tag `v2` on central repo when behaviour changes. Callers stay on `@v1` until they explicitly opt in |

---

## Rollout phases

### Phase 0 — Build the central workflow (1 repo)

- Create `LukeEvansTech/shared-workflows` (public)
- Author the reusable workflow with soft-launch defaults
- Tag `v1`
- Enable Renovate (single `renovate.json`)
- Write README with usage snippet
- Author `scripts/rollout-lint-workflow.sh` (used in Phase 2)
- Move this design doc into the repo as the founding documentation

### Phase 1 — Pilot on 1 repo per language family (~5 repos)

Drop in the caller workflow, verify super-linter runs end-to-end, tune the central workflow if anything's broken or noisy:

| Language family | Pilot repo |
| --- | --- |
| Python | `domainpulse` |
| PowerShell | `PSReddit` |
| Terraform / HCL | `terraform-dns` |
| Bicep / Azure | `codelooks-alz` (also exercises bespoke-linter replacement) |
| Hugo / SCSS | `hugo-codelooks-com` |

Acceptance: each pilot's `Lint` workflow runs to completion (green or red — soft launch tolerates red), step summary contains super-linter findings, no `super-linter failed to run` errors.

### Phase 2 — Fan out to remaining ~45 repos

Script-driven (`rollout-lint-workflow.sh` in the central repo):

1. List repos for a given owner via `gh repo list --json name,isArchived,isFork,defaultBranchRef,primaryLanguage,description`
2. Auto-skip: archived
3. Flag (skip with surface-list at end): forks, empty repos, repos with existing lint workflows
4. For each remaining repo: clone if missing, create branch `chore/add-super-linter`, write `lint.yml` with detected default branch, open PR with templated body
5. At the end, print a summary:
   - Repos onboarded (PR URLs)
   - Repos skipped (reason: archived / fork / empty)
   - Repos requiring manual review (existing lint workflow detected — file matches included)

### Phase 3 — Clean up repo-by-repo (ongoing, user's pace)

For each repo:
1. Read super-linter findings from latest workflow summary
2. Fix issues (or add `.github/linters/` config to relax noisy rules)
3. Flip `soft-launch: false` in the repo's `lint.yml`
4. Mark `Lint` as a required check in branch protection if desired

No deadline — happens organically as repos are touched.

---

## Repo classification

### Skip (archived, not touched)

`talos-cluster-pw` (LET), `k3s-cluster` (CL), `k3s-cluster-solo` (CL)

### Flag for manual review (forks)

`packer-vsphere` (CL), `uYouPlus`, `dotfiles-archive`, `powershell-modules`, `terraform-github-repo`, `shelly_exporter` (all LET)

Rationale: adding a lint workflow to a fork creates merge friction with upstream. User will decide per-fork during a separate cleanup pass.

### Flag for manual review (empty / placeholder repos)

`network-configs` (auto-generated by Oxidized — explicitly skip), `endpointmanager`, `bcb-core-banking-test`, `opnsense-coppice-road`, `powershell-vsphere`, `maester-tests` (CL), `hugo-codelooks-staging`, `hugo-codelooks`

Rationale: `null` `primaryLanguage` suggests no real code yet. User chooses whether to onboard placeholders now or later.

### Flag for manual review (existing lint workflows)

Detected by greping `.github/workflows/*.yml` for: `super-linter`, `tflint`, `bicep build`, `psscriptanalyzer`, `pylint`, `ruff`, `eslint`, `hadolint`, `ansible-lint`, `terraform fmt`, `terraform validate`.

Expected matches (to verify in Phase 1/2):
- `codelooks-alz` — Bicep CI (replace with super-linter; super-linter v8 supports Bicep natively)
- `terraform-dns`, `terraform-vsphere`, `network-ops`, `terraform-cloudflare`, `terraform-azure-landingzone` — likely tflint
- `containers` — likely Hadolint

For each: user decides replace / coexist / skip.

### Onboard (default path)

All other non-archived repos in both accounts.

---

## Verification

### Per-repo (Phase 1 & 2)

After PR merge:
- Next push or PR triggers the `Lint` workflow
- Workflow runs to completion (status: success or `continue-on-error` allowed-failure)
- Step summary contains super-linter's findings markdown
- No `super-linter failed to run` errors in logs

### Cross-rollout (Phase 2 closing checklist)

- `gh workflow list -R <owner>/<repo>` shows `Lint` for every targeted repo
- Spot-check one repo per language family: Python, PowerShell, HCL, Bicep, Hugo, Shell
- Confirm super-linter actually detected the language (look for `INFO: Successfully ran <linter>` in logs)

---

## Risks & mitigations

| Risk | Mitigation |
| --- | --- |
| First-run slow (~3-5 min while super-linter docker image pulls) | Accepted — subsequent runs cache. Soft launch means slow runs don't block anyone. |
| Cross-account public-workflow dependency: deleting/renaming `LukeEvansTech/shared-workflows` breaks every `codelooks-com` caller | Document the dependency in the repo README. Don't rename casually. |
| Forks diverge from upstream when we add workflows | Flagged separately — user reviews per-fork |
| `@v1` major-version pin auto-updates | Acceptable for this use case (soft launch absorbs surprises). Repos can pin tighter (`@v1.0.3`) if desired |
| Renovate fatigue (1 PR per super-linter release) | Concentrated on the central repo only — not 50 repos |
| Bespoke lint workflows that already work | Script flags rather than overwrites; user reviews each |

---

## Open questions deferred to implementation plan

- Exact repo to host this spec long-term (proposal: move into `LukeEvansTech/shared-workflows` in Phase 0)
- Whether to direct-commit to `main` or open PRs on solo-owner repos during Phase 2 (proposal: PRs by default, user can override per-repo)
- Renovate configuration depth (proposal: start with `config:recommended` preset only)
- PR body template content (proposal: brief explainer + link to this spec)

---

## Lessons learned during Phase 1 (2026-05-03)

### Repo name `.github-workflows` was renamed to `shared-workflows`

Originally the central repo was named `LukeEvansTech/.github-workflows` (mirroring the `.github` special-repo convention). During Phase 1 pilot validation we hit `startup_failure` on every cross-repo `uses:` call. The leading-dot name was *not* the cause (the actual cause was permissions — see below) but renaming to `shared-workflows` was kept because it's clearer: it's a normal shared repo, not a `.github`-style special repo. Tag `v1` was preserved through the rename via `gh repo rename`.

### Caller `permissions:` block is required

The reusable workflow declares `permissions: { contents: read, statuses: write }` at the job level. GitHub's modern repo default is `default_workflow_permissions: read`. Because the called workflow's permissions exceed what the caller's default token can grant, the runner refuses to start before any job runs (`startup_failure`, 1s duration, no billable time, `referenced_workflows` resolves correctly but `check_runs` are never created).

The fix is to require every caller to declare the equivalent `permissions:` block. The plan's per-repo caller template, the `render_caller_workflow` bash function (Task 14), and the README example all include this block. A `lint-self.yml` was added to the central repo (`shared-workflows`) so the same pattern is exercised end-to-end on every PR — catching this kind of regression before it ships to caller repos.

### Net effect on caller line count

Caller grew from ~10 lines to ~14 lines. Acceptable trade-off for principle-of-least-privilege correctness.

### Phase 3 — JSCPD disabled (2026-05-04)

JSCPD (copy-paste detector) ships with a 0% duplicate threshold by default — flags any duplicate, including small coincidental matches across language families. Across the rollout sweep, 8+ repos had a single JSCPD-only finding, and the genuine signal was small (most flagged duplicates were either tiny stretches of boilerplate or vendored library code).

JSCPD's threshold is configured via `.jscpd.json` *in the linted repo* — there's no super-linter env var to set a global threshold from the central workflow. Adding 41 stock config files just to bump one number isn't a good trade.

**Decision: disable JSCPD globally (`VALIDATE_JSCPD=false`).** Repos that want duplication detection can re-enable per-repo via env override + their own `.jscpd.json`.

### Phase 3 — Biome decision (2026-05-04)

Super-linter v8 enables both Biome and Prettier/ESLint/Stylelint by default, generating "X and Y are both enabled, might conflict" warnings on every run across every repo. We picked one side rather than tolerate the noise:

**Decision: disable Biome (`VALIDATE_BIOME_FORMAT=false`, `VALIDATE_BIOME_LINT=false`).**

Rationale:
- The user's repos lean infra (PowerShell, Bicep, HCL, Python) — JS/TS is a tiny fraction; Biome's strength (Rust speed on JS/TS) is largely wasted.
- Where formatting/linting *does* run (Hugo SCSS, docs Markdown, package.json), Prettier has wider coverage. Biome's Markdown and YAML support is partial; Prettier's is mature.
- Plugin ecosystem and Stack Overflow surface area for Prettier/ESLint/Stylelint vastly exceeds Biome.

A repo can re-enable Biome per-repo via env override in its caller workflow if it ever becomes the better fit (e.g. a greenfield TS project).

### Phase 3 update — SHA-pin migration (2026-05-03)

Zizmor's `unpinned-uses` audit flagged every caller for using `@v1` (a tag, not a SHA). We migrated to pinning the commit SHA with a trailing `# v1` comment that Renovate updates atomically with the SHA when `v1` moves on the central repo.

Tradeoff: Renovate now opens one PR per caller repo when shared-workflows updates `v1`, instead of all callers tracking the floating tag silently. We accepted this — the user prefers explicit, reviewable bumps over invisible automatic ones.

The rollout script auto-resolves the current `v1` SHA via `gh api`. The README's "Minimal caller" example shows `<sha>` as a literal placeholder so readers know to substitute the current SHA when copy-pasting; the script handles it for you when fanning out.
