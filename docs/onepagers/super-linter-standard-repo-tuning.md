# One-pager: super-linter config tuning for the standard `terraform-*` repos (fleet-wide)

**Status:** Open question — needs a fleet decision.
**Raised from:** `LukeEvansTech/github-infrastructure` platform-standard migration (2026-06-14).
**Owner workflow:** `LukeEvansTech/shared-workflows/.github/workflows/super-linter.yml`.

## Problem

The shared super-linter (`lint.yml`, `soft-launch: false` = **blocking**) fails on the standard
`terraform-*` repo shape — **and it fails fleet-wide**, not just on one repo:

- `codelooks-com/terraform-tailscale` — latest `lint.yml` run: **failure** (same root causes).
- `LukeEvansTech/github-infrastructure` PR #66 — `ENV`, `MARKDOWN_PRETTIER`, `NATURAL_LANGUAGE`,
  `SHELL_SHFMT` all fail.

Because lint is blocking, this means the canonical repo shape **cannot go green** without
per-repo workarounds that diverge from the standard. The failures cluster into three systemic
causes:

### 1. `ENV` (dotenv-linter) vs the `TF_VAR_*` + `op://` convention

The standard `.env.example` (1Password-resolved) trips dotenv-linter:

- **`LowercaseKey`** on `TF_VAR_github_token` / `TF_VAR_tailscale_*` — but `TF_VAR_<name>` **must**
  carry the variable's real (lowercase) name; uppercasing it breaks Terraform. Unfixable in-file.
- **`ValueWithoutQuotes`** on `op://Home Operations/…` values (spaces in vault/item names).
- **`UnorderedKey`** — dotenv-linter wants global alphabetical key order, which fights logical
  grouping (`TF_VAR_*`, then `AWS_*`).

Note the reference repo `codelooks-com/terraform-cloudflare` simply **doesn't track a
`.env.example`** (it documents secrets in the README) — i.e. it dodges the linter rather than
satisfying it. `terraform-tailscale` tracks one and is red.

### 2. `NATURAL_LANGUAGE` + `MARKDOWN_PRETTIER` on `docs/superpowers/`

The `docs/superpowers/{specs,plans}` files are **internal agent planning artifacts** (from the
brainstorming/writing-plans workflow), not published product docs. Prose linting (textlint/
proselint) and prettier flag them heavily. The published docs live under `docs/` (zensical) and
are already governed by `docs.yml` / `docs-standard-check.yml`.

### 3. `SHELL_SHFMT` indent

super-linter's shfmt defaults to **tabs**; ad-hoc local `shfmt -i 2` (spaces) diverges. No repo
`.editorconfig` pins the intent, so it's easy to regress.

## Options

1. **Tune the shared `super-linter.yml` for the standard repo shape (recommended):**
   - `FILTER_REGEX_EXCLUDE` (or `IGNORE_GITIGNORED_FILES` + a path) to **exclude
     `docs/superpowers/.*`** from all linters — they're agent scaffolding, not product docs.
   - Either **`VALIDATE_ENV: false`** fleet-wide, or ship a dotenv-linter skip config
     (`DOTENV_LINTER_CONFIG_FILE`) that disables `LowercaseKey`/`UnorderedKey` for `TF_VAR_*`.
   - Commit a canonical **`.editorconfig`** (sh = tab) to the repo template so shfmt is stable.
2. **Drop `.env.example` fleet-wide** (match `terraform-cloudflare`) and document required env in
   each README. Removes the dotenv problem; loses the copy-paste template.
3. **Graduate lint back to `soft-launch: true`** for the `terraform-*` repos until the config is
   tuned — unblocks merges without ignoring findings permanently.
4. **Accept red lint** on these repos (it's not a required check). Worst option — defeats the
   point of a blocking gate.

## Recommendation

**Option 1** — tune `super-linter.yml` once in shared-workflows: exclude `docs/superpowers/`,
disable/relax `ENV` for the `TF_VAR_*` pattern, and ship a template `.editorconfig`. That greens
the whole fleet (github-infrastructure, tailscale, nextdns, dns, …) in one change instead of N
per-repo hacks. Combine with **Option 3** as the interim (soft-launch) so PRs aren't blocked
while the config lands.

## Decision needed
- Approve the `super-linter.yml` changes (exclude `docs/superpowers/`, `ENV` handling, editorconfig).
- Decide `.env.example`: keep (with `ENV` relaxed) or drop fleet-wide.
- Re-run lint across `terraform-*` to confirm green.

## Context
- Trigger PR: `LukeEvansTech/github-infrastructure#66`.
- Same-shape repo also red: `codelooks-com/terraform-tailscale`.
- Related: `private-repo-iac-security-scanning.md` (the security-scans private-repo issue).
