#!/usr/bin/env bash
# Shared helpers for the super-linter rollout script.
#
# All functions take absolute paths and return:
#   exit 0 = match / yes
#   exit 1 = no match / no

set -euo pipefail

# An existing meta-linter caller — match the `uses:` action line specifically
# so we don't accidentally match passing comments (e.g. a super-linter file
# with leftover MegaLinter comments). These files are DELETED and replaced.
# Matches MegaLinter, the standalone super-linter action (NOT our reusable
# workflow caller — that's detected separately by has_super_linter_caller),
# and a few common all-in-one linter actions.
readonly REPLACEABLE_USES_PATTERN='^[[:space:]]*-?[[:space:]]*uses:[[:space:]]*(oxsecurity/megalinter|nvuillam/mega-linter|super-linter/super-linter|github/super-linter)'

# Pure-lint single-tool workflows that may coexist with super-linter.
# Detected by single-tool action references in the workflow file.
readonly COEXIST_USES_PATTERN='^[[:space:]]*-?[[:space:]]*uses:[[:space:]]*(terraform-linters/setup-tflint|aquasecurity/tfsec-action|aquasecurity/trivy-action|bridgecrewio/checkov-action|tenable/terrascan-action|microsoft/ps-rule|hashicorp/setup-terraform|terraform-docs/gh-actions|reviewdog/action-actionlint|reviewdog/action-shellcheck|hadolint/hadolint-action|stylelint-actions|psscriptanalyzer|powershell-actions/check-psscriptanalyzer|ansible/ansible-lint|peter-evans/setup-bicep)'

# Detect existing MegaLinter (or other replaceable meta-linters) workflows.
# Echoes one filename per line. Exit 0 if any match; 1 otherwise.
detect_replaceable_lint_workflows() {
  local repo_dir="$1"
  if [[ ! -d "$repo_dir/.github/workflows" ]]; then
    return 1
  fi
  shopt -s nullglob
  local files=("$repo_dir"/.github/workflows/*.yml "$repo_dir"/.github/workflows/*.yaml)
  shopt -u nullglob
  if [[ ${#files[@]} -eq 0 ]]; then
    return 1
  fi
  local matches
  # Skip files that ARE our shared-workflow caller — those are not replaceable.
  matches=""
  for f in "${files[@]}"; do
    if grep -qE "$REPLACEABLE_USES_PATTERN" "$f" 2>/dev/null && \
       ! grep -qE 'LukeEvansTech/shared-workflows/\.github/workflows/super-linter\.yml' "$f" 2>/dev/null; then
      matches="${matches}${f}"$'\n'
    fi
  done
  matches="${matches%$'\n'}"
  if [[ -z "$matches" ]]; then
    return 1
  fi
  printf '%s\n' "$matches"
}

# Detect existing pure-lint workflows that should coexist (rename pattern).
# Echoes one filename per line. Exit 0 if any match; 1 otherwise.
detect_coexist_lint_workflows() {
  local repo_dir="$1"
  if [[ ! -d "$repo_dir/.github/workflows" ]]; then
    return 1
  fi
  shopt -s nullglob
  local files=("$repo_dir"/.github/workflows/*.yml "$repo_dir"/.github/workflows/*.yaml)
  shopt -u nullglob
  if [[ ${#files[@]} -eq 0 ]]; then
    return 1
  fi
  local matches
  matches=""
  for f in "${files[@]}"; do
    if grep -qE "$COEXIST_USES_PATTERN" "$f" 2>/dev/null; then
      matches="${matches}${f}"$'\n'
    fi
  done
  matches="${matches%$'\n'}"
  if [[ -z "$matches" ]]; then
    return 1
  fi
  printf '%s\n' "$matches"
}

# Detect whether the repo already has a super-linter caller workflow
# (calling LukeEvansTech/shared-workflows). Exit 0 if so.
has_super_linter_caller() {
  local repo_dir="$1"
  if [[ ! -d "$repo_dir/.github/workflows" ]]; then
    return 1
  fi
  shopt -s nullglob
  local files=("$repo_dir"/.github/workflows/*.yml "$repo_dir"/.github/workflows/*.yaml)
  shopt -u nullglob
  if [[ ${#files[@]} -eq 0 ]]; then
    return 1
  fi
  grep -qlE 'LukeEvansTech/shared-workflows/\.github/workflows/super-linter\.yml' "${files[@]}" 2>/dev/null
}

# Detect whether a workflow file contains anything that touches an external
# system (deploys, applies, releases). Exit 0 if it does — meaning the file
# must NOT be modified by the rollout script.
workflow_has_deploy_steps() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    return 1
  fi
  grep -qiE '\b(az[[:space:]]+(deployment|webapp|functionapp)[[:space:]]+(create|deploy)|terraform[[:space:]]+apply|kubectl[[:space:]]+apply|helm[[:space:]]+(install|upgrade)|peaceiris/actions-gh-pages|actions/deploy-pages|cloudflare/wrangler-action|azure/static-web-apps-deploy)\b' "$file"
}

# Render the per-repo caller workflow YAML.
#
# We pin to the commit SHA that v1 currently points to (rather than @v1
# directly). This satisfies zizmor's unpinned-uses audit and matches the
# GitHub-recommended security pattern. Renovate reads the trailing
# `# v1` comment and bumps both the SHA and the comment together when
# v1 moves on the central repo.
#
# Args:
#   $1 = default branch name (e.g. main, master)
render_caller_workflow() {
  local default_branch="$1"
  local sha
  sha=$(get_central_v1_sha)
  if [[ "$default_branch" == "main" ]]; then
    cat <<YAML
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
    uses: LukeEvansTech/shared-workflows/.github/workflows/super-linter.yml@${sha} # v1
YAML
  else
    cat <<YAML
name: Lint

on:
  pull_request:
  push:
    branches: [${default_branch}]
  workflow_dispatch:

permissions:
  contents: read
  statuses: write
  pull-requests: write

jobs:
  lint:
    uses: LukeEvansTech/shared-workflows/.github/workflows/super-linter.yml@${sha} # v1
    with:
      default-branch: ${default_branch}
YAML
  fi
}

# Render the stock .jscpd.json — copy-paste detection threshold 10%
# (industry-typical), with common vendored/build paths excluded.
render_jscpd_config() {
  cat <<'JSON'
{
  "threshold": 10,
  "reporters": ["consoleFull"],
  "ignore": [
    "**/node_modules/**",
    "**/vendor/**",
    "**/.terraform/**",
    "**/.venv/**",
    "**/dist/**",
    "**/build/**",
    "**/assets/scss/framework/**"
  ]
}
JSON
}

# Resolve the commit SHA that the central repo's v1 tag currently points to.
# Cached in $CENTRAL_V1_SHA after first call so we don't hit the API
# repeatedly during a single rollout.
CENTRAL_V1_SHA=""
get_central_v1_sha() {
  if [[ -z "$CENTRAL_V1_SHA" ]]; then
    CENTRAL_V1_SHA=$(gh api repos/LukeEvansTech/shared-workflows/git/refs/tags/v1 \
      --jq 'if .object.type == "tag" then .object.sha else .object.sha end' 2>/dev/null)
    # Annotated tags need one more dereference to get the commit SHA.
    if [[ -n "$CENTRAL_V1_SHA" ]]; then
      local resolved
      resolved=$(gh api "repos/LukeEvansTech/shared-workflows/git/tags/$CENTRAL_V1_SHA" \
        --jq '.object.sha' 2>/dev/null || true)
      if [[ -n "$resolved" ]]; then
        CENTRAL_V1_SHA="$resolved"
      fi
    fi
    if [[ -z "$CENTRAL_V1_SHA" ]]; then
      echo "ERROR: could not resolve LukeEvansTech/shared-workflows v1 SHA" >&2
      exit 1
    fi
  fi
  echo "$CENTRAL_V1_SHA"
}
