<!--
Repo context for the Renovate reviewer (shared-workflows renovate-review reusable).

This file is spliced into the review prompt in place of the generic
"## Repo Context" section. Everything else in the prompt is generic and lives in
the reusable — put ONLY repo-specific facts here.

It is read from the PR's BASE commit, not the PR head, so a pull request cannot
rewrite the rules it is about to be judged by. That means changes here only take
effect once merged to the default branch.

Keep it to what changes a review verdict:
  - what this repo deploys and what deploys it (the blast radius of a bad bump)
  - which files reference or consume a dependency, so step 3 knows where to look
  - which components are high-blast-radius and why
Skip anything the reviewer can read from the diff.

Starts at H2 deliberately: this is a fragment spliced into a larger prompt,
not a standalone document, so MD041's top-level-heading rule does not apply.
-->
<!-- markdownlint-disable-file MD041 -->

## Repository Context

This is a <GitOps engine> repository managing <what>. Dependencies are:

- <e.g. Container images referenced in `apps/<name>/compose.yaml`, pinned with
  SHA256 digests (`tag@sha256:...`)>
- <e.g. Helm chart versions in HelmRelease CRDs (sourced from OCIRepository)>
- <e.g. GitHub Actions in `.github/workflows/`>

Architecture details relevant to impact assessment:

- **GitOps engine**: <what reconciles this repository onto the running system, how
  often, and what a bad bump does when it lands>
- **Secrets**: <how they are injected; confirm there are none in-repo>
- **Apps / components**: <the inventory, with a note on any whose downtime has a
  cost that is not obvious from the name>

When assessing impact (step 3), the files that consume a dependency are:
<e.g. the app's `apps/<name>/compose.yaml` (env vars, command flags, volume
layout, ports), any config file it mounts, and the secret mappings in
`.doco-cd.yaml`>

High-blast-radius components that warrant deeper scrutiny:

- **<Category>**: <component> (<why a bad bump here is worse than elsewhere>)
