# Zensical docs standard — follow-ups after rollout

After the 2026-05-26 rollout to 18 repos, the following items need attention. None block the standard itself; they're content/security debt surfaced by the new canonical workflows.

---

## Docs `--strict` failures (6 repos)

Each repo's `Docs` workflow fails because `zensical build --strict` aborts on broken Markdown reference links or missing pages. Two paths to clear:

1. **Fix the content** (right thing).
2. **Bypass temporarily** by adding `strict: false` to the `with:` block in the repo's `.github/workflows/docs.yml`:

```yaml
jobs:
  docs:
    uses: LukeEvansTech/shared-workflows/.github/workflows/zensical.yml@<sha> # v1
    with:
      publish: ${{ github.event_name != 'pull_request' }}
      strict: false  # <-- add this
```

### PSReddit

**File:** `docs/docs/changelog.md` (2 issues)
Missing keep-a-changelog reference URL definitions. Add at end of file:
```markdown
[Unreleased]: https://github.com/LukeEvansTech/PSReddit/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/LukeEvansTech/PSReddit/releases/tag/v0.0.1
```

### purview-content-explorer-export

**File:** `docs/docs/CHANGELOG.md` (1 issue)
Same keep-a-changelog pattern. Add the missing `[Unreleased]:` reference URL definition at the bottom of the file.

### defender-device-control-unmanaged

**Files** (8+ broken refs):
- `docs/docs/howto/onboard-to-mde.md`
- `docs/docs/howto/run-end-to-end-test.md`
- `docs/docs/reference/cmdlets/Get-DefenderDcPolicy.md`

Each has reference-style links like `[some text][some-ref]` without corresponding `[some-ref]: url` definitions at the bottom. Run `zensical build --strict` locally to enumerate; add the missing URL definitions.

### lgwebos

**File:** `docs/docs/ledger.md` lines 21–46 (36 issues)
Links a sub-tree of pages that don't exist (`debloat-runbooks/gaming/`, `debloat-runbooks/picture/`, etc.). Options:
- Create the missing pages, OR
- Remove the dead links from `ledger.md`, OR
- `strict: false` until you decide

### stwt-m365-consolidation

**Files** (39 issues across `information-architecture/` and `tenant-settings/`):
Substantial: 15 anchor mismatches on `tenant-settings/index.md` (likely renamed headings), plus broken refs in `information-architecture/` pages. Recommend `strict: false` while you iterate on the content, then flip back.

### network-ops

**File:** `docs/docs/opnsense-migration.md` line 576 (1 issue)
Links to `opnsense-rollback.md` which doesn't exist. Either create that page or fix the link.

---

## Lint failures (4 repos — workflow security/style debt)

These are in repo-owned workflows (NOT the docs standard files). Most common findings from ZIZMOR (super-linter's GitHub Actions security scanner).

### Auto-applied fixes (2026-05-26)

`persist-credentials: false` was added to the `actions/checkout` step in:
- `PSReddit/.github/workflows/psreddit-publish-module.yml`
- `col-entra-id/.github/workflows/generate-handover.yml` ⚠️ (see caveat below)
- `stwt-m365-consolidation/.github/workflows/docs-deploy.yml`
- `stwt-m365-consolidation/.github/workflows/infra-deploy.yml`

⚠️ **`col-entra-id/generate-handover.yml` caveat:** That workflow's `git push` step relies on the persisted GITHUB_TOKEN credential. With `persist-credentials: false`, the push will now fail with no auth instead of failing with the protected-branch hook. The workflow was already broken (couldn't push regenerated PDF to protected `main`); now it breaks earlier. Either revert this edit or replace the manual `git push` with `stefanzweifel/git-auto-commit-action@<sha>` (or `peter-evans/create-pull-request`) which handles its own auth properly.

### Remaining manual fixes

**PSReddit (`psreddit-publish-module.yml`):**
- Add `permissions:` block scoped to what the workflow actually needs (e.g., `contents: read` at workflow level, `packages: write` at job level if publishing to PSGallery).
- Move `secrets.PSGALLERY_API_KEY` into a GitHub environment (use `environment: psgallery` at job level).

**PSReddit (`psreddit-test-on-macos.yml`):**
- File has CRLF line endings. Normalize with `dos2unix` or add `* text=auto eol=lf` to `.gitattributes`.

**PSReddit (`psreddit-test-on-*.yml` all 3):**
- YAML indentation, line-length, missing `---` document marker.

**col-entra-id (`generate-handover.yml`):**
- Run Prettier and commit the formatting changes.
- Address the `git push` auth issue (see caveat above).

**github-infrastructure (`terraform-cloud.yml`):**
- **Template injection (High confidence security finding):** `github.actor` is interpolated into a `github-script` inline JS body. Replace with an env var:
  ```yaml
  - uses: actions/github-script@<sha>
    env:
      ACTOR: ${{ github.actor }}
    with:
      script: |
        const actor = process.env.ACTOR;
        // ...
  ```
- Move `TF_API_TOKEN` and `GH_TOKEN` secrets into a GitHub environment.

**github-infrastructure (`terraform-drift-detection.yml`, `terraform-lint.yml`):**
- Shellcheck: SC2086 (unquoted variable), SC2129 (use single redirect instead of multiple `>>`).

**stwt-m365-consolidation (`docs-deploy.yml`):**
- `ref-version-mismatch`: `Azure/static-web-apps-deploy@1a947af` comment says `# v1` but SHA points to a different tag. Update the comment or re-pin.
- Move `AZURE_STATIC_WEB_APPS_API_TOKEN` into an environment.

---

## Stale Renovate PRs — closed 2026-05-26

7 PRs proposing shared-workflows@2410829 were closed (they would regress the super-linter polarity fix). Renovate will reopen against the current `main` SHA on its next scheduled run.

Closed PRs: PSReddit #26, col-entra-id #4, github-infrastructure #62, stwt-m365-consolidation #6, network-ops #38, purview-content-explorer-export #5, lgwebos #29.

---

## Actions minutes

LukeEvansTech account is at 100% Actions minutes (notification 2026-05-26). New CI runs are queued but won't execute until billing resets or minutes are purchased.

This means: any fixes committed today won't be verified by CI until the quota resets. Plan accordingly.

---

## Other follow-ups (already known)

- gh-pages branches on PSReddit / purview-content-explorer-export / defender-device-control-unmanaged kept as rollback path. Delete after ~2026-06-02 if migrations stay green.
- `lgwebos-lint.yml` (bats/shellcheck/shfmt project tests, misleadingly named) — consider renaming to `test.yml`. Not a docs concern.
- Phase 5 phased linter rollout (Vale opt-in, link-check hard-fail) — defer until content is clean.
- Lychee link-check fundamentally incompatible with MkDocs root-relative URLs when `site_url` has a path prefix. `zensical.yml` defaults `link-check: false`. Real fix: pass `--base` matching `site_url`, or run lychee against the live deployed URL post-deploy.
