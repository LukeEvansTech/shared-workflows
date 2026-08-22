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

<!-- -->

> **Why permissions at the job level?** Top-level `contents: read` is read-only
> by default (least-privilege; satisfies CHECKOV `CKV2_GHA_1`). Per-job
> permissions add the specific writes super-linter needs (`statuses: write` for
> per-linter check statuses, `pull-requests: write` for the PR summary comment).
> Job-level scoping satisfies zizmor's `excessive-permissions` audit — only the
> lint job gets the writes, no other (hypothetical) job in the same workflow
> would. Callers must grant equal-or-greater permissions on the lint job,
> otherwise the runner refuses to start (`startup_failure`).

### Inputs

| Input                   | Type    | Default                                           | Purpose                                                                                                            |
| ----------------------- | ------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `default-branch`        | string  | `main`                                            | Branch super-linter diffs against                                                                                  |
| `validate-all-codebase` | boolean | `false`                                           | Lint everything, not just changed files                                                                            |
| `soft-launch`           | boolean | `true`                                            | When `true`, lint failures don't fail the workflow                                                                 |
| `filter-regex-exclude`  | string  | (vendor/node_modules/.terraform/.venv/dist/build) | Paths to exclude                                                                                                   |
| `runner`                | string  | `ubuntu-latest`                                   | Runner label to execute on. Set to an ARC runner scale set name to run self-hosted (free minutes on private repos) |

### Examples

**Repository whose default branch is `master`:**

```yaml
jobs:
  lint:
    uses: LukeEvansTech/shared-workflows/.github/workflows/super-linter.yml@<sha> # v1
    with:
      default-branch: master
```

**Repository cleaned up — flip to blocking:**

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

Super-linter natively reads linter configs from the repository being linted. Drop files like `.markdownlint.json`, `.yamllint`, `.shellcheckrc` into `<repo>/.github/linters/`.

### Versioning

- Callers pin to `@v1` (major). Non-breaking changes propagate automatically.
- Breaking changes ship as `@v2` and require explicit caller bumps.
- The internal `super-linter/super-linter@v8` pin is bumped via Renovate (one PR per release here, no churn in caller repos).

## renovate-review

Claude reviews Renovate PRs for breaking changes and gates auto-merge through the `claude/renovate-review` commit status. The reusable owns the whole mechanism (classify → model tier → diff fingerprint → OAuth pre-flight → review → status → failure annotations) and the generic two-thirds of the review prompt. Callers supply only what is genuinely repo-specific.

It replaced four hand-maintained ~700-line copies that had drifted apart twice in three weeks — once on 403 org-policy handling, once on 429 usage-limit handling. Fix things here, never in a caller.

### Minimal caller

```yaml
name: "Renovate PR Review"

on:
  pull_request:
    types: [opened, synchronize, reopened]

concurrency:
  group: renovate-review-${{ github.event.pull_request.number }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  review:
    permissions:
      contents: read
      pull-requests: write
      statuses: write
      id-token: write
    uses: LukeEvansTech/shared-workflows/.github/workflows/renovate-review.yml@<SHA> # v1
    with:
      blast-regex: "doco-cd|traefik|garage"
      forbidden-commands: "docker, docker compose, doco-cd, ssh, or deploy commands"
    secrets:
      CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
```

The caller also needs `.github/renovate-review-context.md` describing the repository — see
[templates/renovate-review-context.md](templates/renovate-review-context.md). It is spliced
into the prompt in place of the generic `## Repository Context` section, and is read from the PR's
**base** commit so a pull request cannot rewrite the rules it is about to be judged by. A
missing or empty context file fails the review closed.

### Caller inputs

| Input                        | Type    | Default                                                  | Purpose                                                                       |
| ---------------------------- | ------- | -------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `forbidden-commands`         | string  | (required)                                               | Commands the reviewer must never run, phrased to drop into a sentence         |
| `blast-regex`                | string  | `""`                                                     | High-blast-radius components, matched against the PR title; always full depth |
| `blast-from-renovaterc`      | boolean | `false`                                                  | Derive the blast list from the caller's `.renovaterc.json5` instead           |
| `protected-rule-description` | string  | `Protected infra — never auto-merge, manual review only` | The packageRules `description` to derive from                                 |
| `context-file`               | string  | `.github/renovate-review-context.md`                     | Repository context spliced into the prompt                                    |
| `light-model`                | string  | `claude-sonnet-5`                                        | Model for routine patch container bumps                                       |
| `full-model`                 | string  | `claude-opus-5`                                          | Model for minor/major/high-blast-radius bumps                                 |
| `max-turns`                  | number  | `60`                                                     | Turn ceiling for the reviewer                                                 |
| `ungated-labels`             | string  | `type/digest\|renovate/github-action`                    | Renovate labels that skip review entirely                                     |
| `runner`                     | string  | `ubuntu-latest`                                          | Runner label to execute on                                                    |
| `timeout-minutes`            | number  | `30`                                                     | Job timeout; a timeout mid-review hits the fail-open path                     |

Exactly one of `blast-regex` or `blast-from-renovaterc` must yield a non-empty regular expression — an empty one would match every PR title, so the job fails loudly rather than silently mis-tiering every bump.

### Failure modes

The review **fails closed** (PR blocks) when the token is dead (401), refused by org policy
(403 `permission_error`), or the usage window is spent (429, whether hit at pre-flight or
mid-review). It **fails open** (PR passes, flagged in the status) only on genuinely transient
errors, so a blip cannot wedge the auto-merge pipeline. Each closed failure also emits a red
annotation naming the fix — rotate the token, re-mint from an allowed account, or simply re-run
once the window resets.

### Pinning and versions

- Callers pin to `@v1` (major). Non-breaking changes propagate automatically.
- Breaking changes ship as `@v2` and require explicit caller bumps.
- The internal `anthropics/claude-code-action` pin is bumped via Renovate here — one PR per release, no churn in caller repos.

## The `v1` tag

Callers pin a reusable by commit SHA with a trailing `# v1` comment, and Renovate resolves
that comment against the real `v1` tag. The tag is not decoration — it is what Renovate
rewrites caller pins to.

[`.github/workflows/release-v1.yml`](.github/workflows/release-v1.yml) force-moves the
annotated `v1` tag to the new `main` HEAD on every push that touches
`.github/workflows/**`, `scripts/**` or `templates/**` — the paths a pinned caller
executes or is compared against. Documentation, tests and repository configuration
deliberately do not move it: a tag move offers a Renovate bump to every calling
repository, and a `README.md` edit changes nothing any of them run.

Before moving the tag the job refuses two things:

- moving `v1` onto a commit that is not a descendant of where it already points; and
- shipping a `main` that has deleted a reusable workflow, or one of its `workflow_call`
  inputs or secrets, that exists at the current `v1`.

Both break callers at startup, so they belong in `v2`. The check is structural — a
renamed input, a changed default, or a behaviour change inside a job is still a pull
request review question.

Run it by hand from the Actions tab (`workflow_dispatch`) after a documentation-only
merge, or to recover if the tag is ever left behind.

### Why it exists

`v1` used to be moved by hand. On 2026-08-20 `renovate-review.yml` landed on `main` two
commits past the tag, and the tag was not moved. A caller pinned ahead of it was
"corrected" backwards by Renovate onto a tree where that file did not exist; the workflow
failed at startup with zero jobs and posted no commit status. That status was a required
check, so every pull request in that repository silently stopped being mergeable.

### Why there is no `v1.x.y`

Nobody would pin one. Callers pin a commit SHA and Renovate tracks the major tag, so a
patch/minor series across five independently-evolving reusables would be a numbering
decision with no consumer to serve. The annotated tag message records the previous SHA and
the commits it moved over, so `git show v1` is the changelog.

## Design

See [docs/spec.md](docs/spec.md).
