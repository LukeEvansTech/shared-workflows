#!/usr/bin/env bash
# Shared helpers for the super-linter rollout script.
#
# All functions take absolute paths and return:
#   exit 0 = match / yes
#   exit 1 = no match / no

set -euo pipefail

# Path patterns that indicate an existing third-party meta-linter workflow.
# These are intended to be REPLACED by super-linter (per user directive).
# Match by content rather than filename — file names vary.
readonly REPLACEABLE_LINT_PATTERN='\b(mega-linter|megalinter)\b'

# Path patterns that indicate a pure-lint single-tool workflow that may
# coexist with super-linter (rename to descriptive name; never delete).
readonly COEXIST_LINT_PATTERN='\b(super-linter|tflint|terraform[[:space:]]+(fmt|validate)|terragrunt|terrascan|checkov|psscriptanalyzer|pylint|ruff|eslint|hadolint|ansible-lint|stylelint|markdownlint|reviewdog|tfsec|bicep[[:space:]]+build|az[[:space:]]+bicep|psrule|terraform-docs)\b'

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
  matches=$(grep -ilE "$REPLACEABLE_LINT_PATTERN" "${files[@]}" 2>/dev/null || true)
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
  matches=$(grep -ilE "$COEXIST_LINT_PATTERN" "${files[@]}" 2>/dev/null || true)
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
# Args:
#   $1 = default branch name (e.g. main, master)
render_caller_workflow() {
  local default_branch="$1"
  if [[ "$default_branch" == "main" ]]; then
    cat <<'YAML'
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
    uses: LukeEvansTech/shared-workflows/.github/workflows/super-linter.yml@v1
    with:
      default-branch: ${default_branch}
YAML
  fi
}
