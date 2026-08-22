# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

Central **reusable GitHub Actions workflows + a "zensical docs standard"** shared across ~18 repos in the `LukeEvansTech` and `codelooks-com` orgs. Nothing here runs on a server — repos consume it two ways:

1. **Reusable workflows** (`.github/workflows/*.yml` with `on: workflow_call`) that caller repos invoke via a thin `uses:` stub.
2. **A conformance standard** (canonical `templates/`, enforced by a drift check, propagated by rollout scripts).

The golden rule: **fix things in the reusable/template here, never by duplicating logic into caller repos.** Callers are deliberately thin.

## Architecture — the two-layer model

```text
shared-workflows (this repo, source of truth)
  .github/workflows/super-linter.yml      ← reusable: style/format lint
  .github/workflows/zensical.yml          ← reusable: build/deploy docs site (GitHub Pages)
  .github/workflows/zensical-drift-check.yml ← reusable: enforce the standard on a caller repo
  .github/workflows/security-scans.yml    ← reusable: Checkov + Trivy → SARIF
  .github/workflows/renovate-review.yml   ← reusable: Claude reviews Renovate PRs
  .github/workflows/release-v1.yml        ← self: force-moves the `v1` tag to main
        ▲ SHA-pinned `uses:` (with `# v1` comment)
        │
caller repo: .github/workflows/{lint,docs,docs-standard-check,renovate-review}.yml  ← thin stubs
```

- Callers **SHA-pin** the reusable with a trailing `# v1` comment (Renovate bumps both SHA and comment when the `v1` tag moves). Tag-pins fail the drift check.
- **Self-CI:** `lint-self.yml` runs `super-linter.yml` against this repository; `meta-actionlint.yml` actionlints the workflows. Both must stay green.
- **Versioning:** callers pin `@v1` (major). Non-breaking changes propagate automatically; breaking changes ship as `@v2` and require explicit caller bumps. `release-v1.yml` moves the tag — never do it by hand (invariant 7).

### super-linter.yml (the most-used reusable)

- Pins the super-linter image by SHA (`super-linter/super-linter@<sha> # v8`). The image tag effectively floats unless SHA-pinned — that determinism is the whole point of this reusable.
- **v8 polarity rule:** every `VALIDATE_X` env var must be the same polarity (all true _or_ all false). That is why `VALIDATE_KUBERNETES_KUBECONFORM` defaults `false` — to keep all the explicit `VALIDATE_*: false` lines consistent. Don't mix.
- Disables `BIOME`, `JSCPD`, and the security scanners (`CHECKOV`/`TRIVY`/`GITLEAKS` — owned by `security-scans.yml` to avoid double-runs). Kubeconform is opt-in.
- Reads **per-repo linter configs** from the caller's `.github/linters/` (e.g. `.tflint.hcl`, `.ansible-lint.yml`, `.codespellrc`).
- **Ansible repos:** if the caller has `ansible/requirements.yml`, a step installs collections with `ansible-galaxy ... -p ansible/collections --force` so ansible-lint's `--syntax-check` can resolve them. `--force` is required because some collections ship preinstalled on the runner and would otherwise be skipped (not copied into the workspace the super-linter container mounts).
- `filter-regex-exclude` default excludes `collections/` so vendored collection files aren't linted.

### renovate-review.yml (Claude reviews Renovate PRs)

Gates Renovate auto-merge on a `claude/renovate-review` commit status. Extracted 2026-08-21 from four hand-maintained ~700-line copies (talos-cluster, nut-apps, seedbox-apps, truenas-apps) that drifted apart twice in three weeks — 403 org-policy handling, then 429 usage-limit handling — each time leaving repos silently passing Renovate PRs through **unreviewed**.

- Owns the mechanism AND the generic two-thirds of the review prompt. Callers pass `blast-regex` + `forbidden-commands` and keep a `.github/renovate-review-context.md`; everything else is here.
- **The context file is read from the PR's BASE commit**, not the checked-out head. It is part of the reviewer's instructions, so reading it from the head would let a PR rewrite the rules it is about to be judged by. Consequence: edits to a context file only take effect once merged.
- **Fail-closed vs fail-open is the whole design.** Dead token (401), org-policy denial (403 `permission_error`), and usage-limit (429, at pre-flight _or_ mid-review via the action's `api_error_status`) all BLOCK. Only genuinely transient errors pass through, so a blip can't wedge auto-merge. Every regression in this workflow's history has been a case that was wrongly on the fail-open path.
- **`scripts/report-claude-usage.sh`** writes the sticky usage comment and the hidden diff
  fingerprint that lets the next run skip a redundant (paid) review. It must NOT store a
  fingerprint for a run that errored — an API-error result still has a result record, and
  storing its fingerprint makes the next run skip Claude on the strength of a review that never
  happened. Guarded by the `api_error_status` check at the top.
- The reusable checks itself out at `job.workflow_sha` to run that script, for the same version-locking reason as the drift check — and does so AFTER the review step so the reviewer never globs `.shared-workflows/`.
- `anthropics/claude-code-action` is pinned here, so Renovate bumps it once instead of four times.

### The "zensical docs standard" + drift check

`scripts/zensical_drift.py` is the enforcement engine (run by `zensical-drift-check.yml`). It checks a target repository for:

- **pin** — `docs/requirements.txt` is exactly `zensical==X.Y.Z`
- **palette** — `docs/zensical.toml` has light+dark palette with nested `[project.theme.palette.toggle]`
- **workflows** — the three required caller workflows exist and are 40-hex SHA-pinned to this repo's reusables
- **markdownlint** — the repo's root `.markdownlint.yml` is **byte-identical (SHA-256)** to `templates/.markdownlint.yml`
- **site_url** — lowercase host

Per-repo linter rule overrides go in the caller's `.github/linters/`; markdownlint is the exception — it's a single canonical file, drift-checked.

## Commands

No task runner, no `requirements.txt`. Scripts are Python 3 stdlib + the authenticated `gh` CLI.

```bash
# Run the drift-check unit tests (15 tests over tests/fixtures/zensical/{good,bad-*})
python3 -m pytest scripts/test_zensical_drift.py -q
python3 -m pytest scripts/test_zensical_drift.py -q -k markdownlint   # single test

# Drift-check one repo locally (clone it first, point --repo-root at it)
python3 scripts/zensical_drift.py --repo-root /path/to/clone --repo owner/name [--allow-no-pages]

# Read-only drift audit across ALL 18 repos (clones each shallow, runs the check)
python3 scripts/audit_zensical_standard.py

# Apply the full standard to ONE repo — commits DIRECTLY to its default branch via gh API
python3 scripts/rollout_zensical_standard.py --repo owner/name [--dry-run] [--no-publish] [--allow-no-pages]

# Propagate ONLY the markdownlint template to all 18 repos (see invariant below before using)
python3 scripts/sync_markdownlint.py
```

- `actionlint` validates the workflows locally; CI does this via `meta-actionlint.yml`.
- Always run `gh` with a token that has `workflow` scope — the rollout writes `.github/workflows/*` via the contents API.

## Critical invariants & gotchas

1. **Never run `sync_markdownlint.py` alone.** Each caller's drift check compares against the
   template **at the SHA that repository is pinned to** — not `main`. Changing
   `templates/.markdownlint.yml` only drifts a repository once it's re-pinned to a newer SHA.
   `rollout_zensical_standard.py` is what binds the two together (re-pins the caller SHAs
   **and** syncs the config in the same pass). Syncing the config without bumping the pins
   makes the config disagree with the pinned template → drift fails. Editing the template
   therefore also means updating the matching `tests/fixtures/zensical/*/.markdownlint.yml`
   fixtures (all but `bad-markdownlint`).

2. **Repository classification lives in `scripts/audit_zensical_standard.py`** — `REPOS_PUBLISHING` (publish docs) vs `REPOS_BUILD_ONLY` (build-only, rolled out with `--allow-no-pages`). This is the source of truth for which flags each repo's rollout needs. `sync_markdownlint.py` has its own flat repository list.

3. **`rollout_zensical_standard.py` commits straight to each repo's default branch** (no PRs) via `gh api PUT /contents`. It is idempotent (re-running produces NO-CHANGE) and renders `templates/*` by substituting the `<SHA>` placeholder with the latest `shared-workflows` `main` SHA.

4. **Permissions:** every workflow uses top-level `permissions: contents: read` with job-level write scopes (zizmor `excessive-permissions`, CHECKOV `CKV2_GHA_1`). A caller must grant the lint job ≥ the perms the reusable needs, or the run fails with `startup_failure`.

5. **codespell scans the whole workspace tree** and ignores `FILTER_REGEX_EXCLUDE`. To stop it spell checking vendored/generated files (e.g. installed Ansible collections), add a per-repo `.github/linters/.codespellrc` with `skip = ...` (and `ignore-words-list` for domain false positives).

6. **All `uses:` must be 40-hex SHA-pinned** with a `# vN` comment — the drift check enforces this on callers, and zizmor/`unpinned-uses` enforces it here.

7. **`v1` is moved by CI, and only for the consumed surface.** `release-v1.yml`
   force-moves the annotated tag on any push to `main` touching
   `.github/workflows/**`, `scripts/**` or `templates/**` — exactly what a pinned
   caller executes or is compared against (`scripts/` runs from `job.workflow_sha`;
   `templates/.markdownlint.yml` is compared at the pinned SHA). A documentation
   commit therefore leaves the tag behind on purpose, and it is still byte-identical
   to `main` for every caller. **Add a path there if a new reusable starts reading one
   at `job.workflow_sha`**, or `v1` can go stale in a way that matters again. Stale is
   not merely unnoticed: Renovate resolves each caller's `# v1` comment and rewrites
   pins BACKWARDS onto the tag — on 2026-08-20 that re-pinned a caller onto a tree
   without `renovate-review.yml`, which failed at startup, posted no commit status,
   and silently blocked every pull request in that repository behind its required
   check.

8. **Caller pins are stamped from the `v1` tag, not `main` HEAD.**
   `scripts/lib.sh` always resolved the tag; `rollout_zensical_standard.py` used to
   stamp `main` while writing a `# v1` comment beside it, which is how a caller came
   to be pinned ahead of the tag in the first place. Both now resolve `v1`.

## Where to look

- `docs/spec.md` — original design (goal, non-goals, soft-launch-then-graduate rollout philosophy).
- `README.md` — caller copy/paste snippets and input reference (note: its `filter-regex-exclude` default text predates the `collections` addition).
- `tests/fixtures/zensical/` — `good` (fully conformant) + one `bad-*` per drift dimension; the harness asserts each `bad-*` fails on its own axis only.
