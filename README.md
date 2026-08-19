# shared-workflows

Reusable GitHub Actions workflows shared across [@LukeEvansTech](https://github.com/LukeEvansTech) and [@codelooks-com](https://github.com/codelooks-com).

## super-linter

Soft-launched [super-linter](https://github.com/super-linter/super-linter) as a reusable workflow. Callers add a small `lint.yml`; lint failures do **not** block CI by default.

### Minimal caller (defaults: `main` branch, soft launch on, changed files only)

`.github/workflows/lint.yml`:

```yaml
name: Lint

on:
  pull_request:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

jobs:
  lint:
    permissions:
      contents: read
      statuses: write
      pull-requests: write
    uses: LukeEvansTech/shared-workflows/.github/workflows/super-linter.yml@<sha> # v1
```

> **Why the SHA pin with `# v1` comment?** GitHub's recommended security pattern (and zizmor's `unpinned-uses` audit) requires SHA pins. The `# v1` trailing comment is a Renovate convention — Renovate bumps **both** the SHA and the comment when the `v1` tag on `shared-workflows` moves. This gives you the security of pin-to-SHA with the readability of pin-to-version.
>
> The rollout script (`scripts/rollout-lint-workflow.sh`) auto-resolves and inserts the current `v1` SHA when generating per-repo callers. To get the current SHA manually:
>
> ```bash
> gh api repos/LukeEvansTech/shared-workflows/git/refs/tags/v1 \
>   --jq '.object.sha' \
>   | xargs -I{} gh api repos/LukeEvansTech/shared-workflows/git/tags/{} \
>   --jq '.object.sha'
> ```

> **Why permissions at the job level?** Top-level `contents: read` is read-only by default (least-privilege; satisfies CHECKOV `CKV2_GHA_1`). Per-job permissions add the specific writes super-linter needs (`statuses: write` for per-linter check statuses, `pull-requests: write` for the PR summary comment). Job-level scoping satisfies zizmor's `excessive-permissions` audit — only the lint job gets the writes, no other (hypothetical) job in the same workflow would. Callers must grant equal-or-greater permissions on the lint job, otherwise the runner refuses to start (`startup_failure`).

### Inputs

| Input                   | Type    | Default                                           | Purpose                                                                                                            |
| ----------------------- | ------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `default-branch`        | string  | `main`                                            | Branch super-linter diffs against                                                                                  |
| `validate-all-codebase` | boolean | `false`                                           | Lint everything, not just changed files                                                                            |
| `soft-launch`           | boolean | `true`                                            | When `true`, lint failures don't fail the workflow                                                                 |
| `filter-regex-exclude`  | string  | (vendor/node_modules/.terraform/.venv/dist/build) | Paths to exclude                                                                                                   |
| `runner`                | string  | `ubuntu-latest`                                   | Runner label to execute on. Set to an ARC runner scale set name to run self-hosted (free minutes on private repos) |

### Examples

**Repo whose default branch is `master`:**

```yaml
jobs:
  lint:
    uses: LukeEvansTech/shared-workflows/.github/workflows/super-linter.yml@<sha> # v1
    with:
      default-branch: master
```

**Repo cleaned up — flip to blocking:**

```yaml
jobs:
  lint:
    uses: LukeEvansTech/shared-workflows/.github/workflows/super-linter.yml@<sha> # v1
    with:
      soft-launch: false
```

**Run on a self-hosted ARC runner instead of billable GitHub-hosted minutes:**

```yaml
jobs:
  lint:
    uses: LukeEvansTech/shared-workflows/.github/workflows/super-linter.yml@<sha> # v1
    with:
      runner: seedbox-apps-runner
```

> **Create the runner scale set first.** A job requesting a label that no
> runner advertises queues indefinitely rather than failing, so a premature
> `runner:` looks like a hung PR, not a broken one. Confirm the listener is
> Running (`kubectl get autoscalingrunnerset -n actions-runner-system`) before
> pointing a caller at it.
>
> Personal-account repos can only register runners at repository scope, so each
> needs its own scale set. Org repos can share one org-level scale set via a
> runner group.

### Per-repo rule overrides

Super-linter natively reads linter configs from the repo being linted. Drop files like `.markdownlint.json`, `.yamllint`, `.shellcheckrc` into `<repo>/.github/linters/`.

### Versioning

- Callers pin to `@v1` (major). Non-breaking changes propagate automatically.
- Breaking changes ship as `@v2` and require explicit caller bumps.
- The internal `super-linter/super-linter@v8` pin is bumped via Renovate (one PR per release here, no churn in caller repos).

## Design

See [docs/spec.md](docs/spec.md).
