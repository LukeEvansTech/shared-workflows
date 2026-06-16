# One-pager: IaC security scanning on **private** repos (fleet-wide)

**Status:** Open question — needs a fleet decision.
**Raised from:** `LukeEvansTech/github-infrastructure` platform-standard migration (2026-06-14).
**Owner workflow:** `LukeEvansTech/shared-workflows/.github/workflows/security-scans.yml`.

## Problem

The shared `security-scans.yml` reusable runs Checkov + Trivy and **uploads SARIF to GitHub
Code Scanning** (`github/codeql-action/upload-sarif`). Code Scanning is **free only on public
repositories**. On a **private** repo without **GitHub Advanced Security (GHAS)** — which
requires GitHub Enterprise + per-committer GHAS licensing — the `upload-sarif` step fails with
`Advanced Security must be enabled for this repository to use code scanning`, so the whole check
fails **even when the scan itself passes**.

### Evidence
- On `github-infrastructure` (private) PR #66, `scan / Checkov` logged
  **`Passed checks: 32, Failed checks: 0`** but the **job still failed** — on the SARIF upload.
- `scan / Trivy` failed similarly, plus a secondary `cannot find ignorefile '.trivyignore.yaml'`.
- The private reference repo `codelooks-com/terraform-cloudflare` deliberately runs **only**
  `lint.yml` + `docs.yml` — it never adopted `security-scans.yml`. So today, **private repos get
  no IaC security scanning**, and the standard silently assumes public.

### Blast radius
This affects **every private repo** that would otherwise adopt the standard — most of the
`terraform-*` infra repos (e.g. `terraform-github`, `terraform-cloudflare`, `terraform-tailscale`,
`terraform-nextdns`, `terraform-dns`, `terraform-vsphere`) are private. Quick inventory for the
session to run:

```bash
for owner in LukeEvansTech codelooks-com; do
  gh repo list "$owner" --limit 300 --json name,visibility,isArchived \
    --jq '.[] | select(.isArchived|not) | "\(.visibility)\t\(.name)"'
done | sort
```

## Options

1. **Enable GHAS on private repos** — turns on Code Scanning so the current reusable works
   unchanged. **Cost:** GitHub Enterprise + per-active-committer GHAS seats. Cleanest UX
   (findings in the Security tab) but the most expensive; likely overkill for a personal fleet.
2. **Make the reusable visibility-aware (recommended).** Detect repo visibility
   (`github.event.repository.visibility` / `private`) and branch:
   - **public** → keep SARIF → Code Scanning (today's behavior).
   - **private** → skip `upload-sarif`; instead run Checkov/Trivy with a **non-zero exit on
     findings** (or `soft_fail` + a job-summary / PR comment). One reusable, works everywhere.
3. **Split into two reusables** — `security-scans-public.yml` (SARIF) and
   `security-scans-private.yml` (exit-code / PR-comment). More files; callers pick by visibility.
   Functionally same as (2) but less ergonomic.
4. **Accept no IaC security scanning on private repos** — match the current
   `terraform-cloudflare` reality (lint + docs only). Cheapest; loses Checkov/Trivy coverage on
   the infra repos that arguably need it most. The inline `# trivy:ignore:` comments in those
   repos become vestigial.
5. **Make selected infra repos public** — where there's nothing sensitive (most `terraform-*`
   repos hold no secrets; state lives in R2). Unblocks the existing reusable for those repos.
   Per-repo judgement; not a blanket answer.

## Recommendation

**Option 2** — make `security-scans.yml` visibility-aware. It keeps a single reusable, preserves
the SARIF/Code-Scanning experience on public repos, and gives private repos real Checkov/Trivy
gating (exit-code or PR-comment) without GHAS. Combine with **Option 5** opportunistically for
repos that have no reason to stay private.

### Sketch (visibility-aware reusable)

```yaml
# inside each job, after the scan produces SARIF:
- name: Upload SARIF (public repos only)
  if: ${{ !github.event.repository.private }}
  uses: github/codeql-action/upload-sarif@... 
  with: { sarif_file: results.sarif }

- name: Fail on findings (private repos — no Code Scanning)
  if: ${{ github.event.repository.private }}
  run: |
    # convert SARIF -> count, or re-run scanner with exit-code/soft_fail off,
    # and emit to $GITHUB_STEP_SUMMARY instead of the Security tab.
```

Also fix the secondary papercut: the reusable expects `.trivyignore.yaml`
(`trivyignore-file` default) and errors if absent — make a missing file a no-op.

## Decision needed
- Pick an option (recommend **2**, optionally **5** per-repo).
- If 2: implement visibility branching in `security-scans.yml`, then re-add the
  `security-scans.yml` caller to the private infra repos (it was removed from
  `github-infrastructure` on 2026-06-14 because of this issue).

## Context links
- Trigger PR: `LukeEvansTech/github-infrastructure#66` (platform-standard migration).
- Reference private repo (no security-scans today): `codelooks-com/terraform-cloudflare`.
- Working reusable on **public** repos: `codelooks-com/packer-vsphere`, `LukeEvansTech/talos-cluster`.
