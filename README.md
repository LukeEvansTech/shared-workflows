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
  statuses: write
  pull-requests: write

jobs:
  lint:
    uses: LukeEvansTech/shared-workflows/.github/workflows/super-linter.yml@v1
```

> **Why the `permissions:` block?** GitHub's default `GITHUB_TOKEN` grants only `read` in modern repos. The reusable workflow declares `statuses: write` (per-linter check statuses) and uses `pull-requests: write` for super-linter's PR summary comment. Callers must grant equal-or-greater permissions, otherwise the runner refuses to start (`startup_failure`). The block above is the minimum.

### Inputs

| Input | Type | Default | Purpose |
| --- | --- | --- | --- |
| `default-branch` | string | `main` | Branch super-linter diffs against |
| `validate-all-codebase` | boolean | `false` | Lint everything, not just changed files |
| `soft-launch` | boolean | `true` | When `true`, lint failures don't fail the workflow |
| `filter-regex-exclude` | string | (vendor/node_modules/.terraform/.venv/dist/build) | Paths to exclude |

### Examples

**Repo whose default branch is `master`:**

```yaml
jobs:
  lint:
    uses: LukeEvansTech/shared-workflows/.github/workflows/super-linter.yml@v1
    with:
      default-branch: master
```

**Repo cleaned up — flip to blocking:**

```yaml
jobs:
  lint:
    uses: LukeEvansTech/shared-workflows/.github/workflows/super-linter.yml@v1
    with:
      soft-launch: false
```

### Per-repo rule overrides

Super-linter natively reads linter configs from the repo being linted. Drop files like `.markdownlint.json`, `.yamllint`, `.shellcheckrc` into `<repo>/.github/linters/`.

### Versioning

- Callers pin to `@v1` (major). Non-breaking changes propagate automatically.
- Breaking changes ship as `@v2` and require explicit caller bumps.
- The internal `super-linter/super-linter@v8` pin is bumped via Renovate (one PR per release here, no churn in caller repos).

## Design

See [docs/spec.md](docs/spec.md).
