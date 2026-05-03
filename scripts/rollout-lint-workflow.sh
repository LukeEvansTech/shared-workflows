#!/usr/bin/env bash
# Roll out the super-linter caller workflow to all eligible repos in a
# given GitHub owner.
#
# Usage:
#   scripts/rollout-lint-workflow.sh <owner> <local-base-dir> [flags]
#
# Flags:
#   --dry-run            Don't clone, branch, push, or open PRs. Just classify.
#   --include-forks      Include forks (default: skip).
#   --include-empty      Include repos with no primaryLanguage (default: skip).
#   --only <name>        Only process this single repo.
#
# Example:
#   scripts/rollout-lint-workflow.sh LukeEvansTech /Users/luke.evans/GIT/LukeEvansTech --dry-run

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

OWNER=""
BASE_DIR=""
DRY_RUN=0
INCLUDE_FORKS=0
INCLUDE_EMPTY=0
ONLY_REPO=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --include-forks) INCLUDE_FORKS=1; shift ;;
    --include-empty) INCLUDE_EMPTY=1; shift ;;
    --only) ONLY_REPO="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,/^set -euo pipefail/p' "$0" | sed 's/^# \?//' | head -n -1
      exit 0
      ;;
    -*) echo "Unknown flag: $1" >&2; exit 2 ;;
    *)
      if [[ -z "$OWNER" ]]; then OWNER="$1"
      elif [[ -z "$BASE_DIR" ]]; then BASE_DIR="$1"
      else echo "Unexpected arg: $1" >&2; exit 2
      fi
      shift ;;
  esac
done

if [[ -z "$OWNER" || -z "$BASE_DIR" ]]; then
  echo "Usage: $0 <owner> <local-base-dir> [--dry-run] [--include-forks] [--include-empty] [--only <repo>]" >&2
  exit 2
fi

mkdir -p "$BASE_DIR"

ONBOARDED=()
SKIPPED_ARCHIVED=()
SKIPPED_FORK=()
SKIPPED_EMPTY=()
SKIPPED_ALREADY_HAS=()
NEEDS_REVIEW=()
ERRORS=()

# Pick a descriptive filename for a renamed bespoke lint workflow,
# based on its content. Echoes the new basename (no path).
classify_bespoke_filename() {
  local file="$1"
  if grep -qiE '\b(tflint|terraform|terragrunt|terraform-docs|tfsec|terrascan)\b' "$file"; then
    echo "terraform-lint.yml"
  elif grep -qiE '\b(bicep|az[[:space:]]+bicep|psrule)\b' "$file"; then
    echo "bicep-lint.yml"
  elif grep -qiE '\b(psscriptanalyzer|powershell)\b' "$file"; then
    echo "powershell-lint.yml"
  elif grep -qiE '\b(eslint|prettier|stylelint)\b' "$file"; then
    echo "js-lint.yml"
  elif grep -qiE '\b(pylint|ruff|black|flake8|mypy)\b' "$file"; then
    echo "python-lint.yml"
  elif grep -qiE '\b(hadolint|dockerfile)\b' "$file"; then
    echo "dockerfile-lint.yml"
  elif grep -qiE '\b(markdownlint)\b' "$file"; then
    echo "markdown-lint.yml"
  elif grep -qiE '\b(ansible-lint|ansible)\b' "$file"; then
    echo "ansible-lint.yml"
  else
    echo "bespoke-lint.yml"
  fi
}

# Pick a descriptive workflow `name:` for a renamed bespoke workflow,
# based on the new filename.
classify_bespoke_name() {
  case "$1" in
    terraform-lint.yml) echo "Terraform Lint" ;;
    bicep-lint.yml)     echo "Bicep Lint" ;;
    powershell-lint.yml) echo "PowerShell Lint" ;;
    js-lint.yml)        echo "JavaScript Lint" ;;
    python-lint.yml)    echo "Python Lint" ;;
    dockerfile-lint.yml) echo "Dockerfile Lint" ;;
    markdown-lint.yml)  echo "Markdown Lint" ;;
    ansible-lint.yml)   echo "Ansible Lint" ;;
    *)                  echo "Bespoke Lint" ;;
  esac
}

echo "Listing repos for $OWNER..."
mapfile -t REPOS < <(gh repo list "$OWNER" --limit 200 \
  --json name,isArchived,isFork,defaultBranchRef,primaryLanguage \
  --jq '.[] | "\(.name)\t\(.isArchived)\t\(.isFork)\t\(.defaultBranchRef.name // "")\t\(.primaryLanguage.name // "")"')

echo "Found ${#REPOS[@]} repos."

# Central repo is special — it IS the workflow target, not a caller.
readonly CENTRAL_REPO="shared-workflows"

for line in "${REPOS[@]}"; do
  IFS=$'\t' read -r name archived fork default_branch primary_lang <<< "$line"

  if [[ -n "$ONLY_REPO" && "$name" != "$ONLY_REPO" ]]; then continue; fi

  if [[ "$name" == "$CENTRAL_REPO" ]]; then
    SKIPPED_ALREADY_HAS+=("$name (central repo — uses local self-reference)"); continue
  fi
  if [[ "$archived" == "true" ]]; then
    SKIPPED_ARCHIVED+=("$name"); continue
  fi
  if [[ "$fork" == "true" && "$INCLUDE_FORKS" -ne 1 ]]; then
    SKIPPED_FORK+=("$name"); continue
  fi
  if [[ -z "$primary_lang" && "$INCLUDE_EMPTY" -ne 1 ]]; then
    SKIPPED_EMPTY+=("$name"); continue
  fi
  if [[ -z "$default_branch" ]]; then
    ERRORS+=("$name (no default branch — repo possibly empty?)"); continue
  fi

  repo_dir="$BASE_DIR/$name"
  echo "--- $name (default branch: $default_branch, primary: ${primary_lang:-none})"

  # Clone if missing
  if [[ ! -d "$repo_dir" ]]; then
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "  [dry-run] would clone $OWNER/$name to $repo_dir"
      ONBOARDED+=("$name (dry-run, would clone)")
      continue
    fi
    if ! gh repo clone "$OWNER/$name" "$repo_dir" -- --quiet; then
      ERRORS+=("$name (clone failed)"); continue
    fi
  fi

  # Sync default branch
  if [[ "$DRY_RUN" -eq 0 ]]; then
    if ! ( cd "$repo_dir" && \
           git fetch origin --quiet && \
           git checkout "$default_branch" --quiet && \
           git pull --ff-only --quiet ); then
      ERRORS+=("$name (sync failed — possibly dirty tree or divergent history)"); continue
    fi
  fi

  # Already onboarded?
  if has_super_linter_caller "$repo_dir"; then
    SKIPPED_ALREADY_HAS+=("$name"); continue
  fi

  # Detect replaceable meta-linter workflows (read-only — safe in dry-run)
  replaceable=$(detect_replaceable_lint_workflows "$repo_dir" || true)

  # Dry-run summary path: classify but don't act
  if [[ "$DRY_RUN" -eq 1 ]]; then
    classification="would onboard cleanly"
    actions=()
    if [[ -n "$replaceable" ]]; then
      while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        actions+=("delete $(basename "$f")")
      done <<< "$replaceable"
    fi
    if [[ -f "$repo_dir/.github/workflows/lint.yml" ]] && \
         ! grep -q 'LukeEvansTech/shared-workflows' "$repo_dir/.github/workflows/lint.yml"; then
      if workflow_has_deploy_steps "$repo_dir/.github/workflows/lint.yml"; then
        actions+=("MANUAL: lint.yml has deploy steps")
      else
        new_name=$(classify_bespoke_filename "$repo_dir/.github/workflows/lint.yml")
        actions+=("rename lint.yml -> $new_name")
      fi
    fi
    if [[ ${#actions[@]} -gt 0 ]]; then
      classification="${actions[*]}"
    fi
    ONBOARDED+=("$name :: $classification")
    continue
  fi

  # Process: branch, replace MegaLinter, rename other bespoke, write caller
  (
    set -e
    cd "$repo_dir"

    # Reset any leftover branch state
    if git show-ref --verify --quiet refs/heads/chore/add-super-linter; then
      git checkout chore/add-super-linter --quiet
      git reset --hard "origin/$default_branch" --quiet
    else
      git checkout -b chore/add-super-linter --quiet
    fi

    mkdir -p .github/workflows

    # Auto-delete MegaLinter and other replaceable meta-linters
    if [[ -n "$replaceable" ]]; then
      while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        # Safety: never delete a workflow that ALSO contains deploy steps
        if workflow_has_deploy_steps "$f"; then
          echo "  WARN: $f contains deploy steps — leaving alone, will be flagged for review"
        else
          echo "  removing replaceable meta-linter: $f"
          git rm "$f" --quiet
        fi
      done <<< "$replaceable"
    fi

    # Handle filename collision at .github/workflows/lint.yml
    target_lint="$repo_dir/.github/workflows/lint.yml"
    if [[ -f "$target_lint" ]] && ! grep -q 'LukeEvansTech/shared-workflows' "$target_lint"; then
      if workflow_has_deploy_steps "$target_lint"; then
        echo "  ERROR: existing lint.yml contains deploy steps — manual review required"
        exit 99
      fi
      new_name=$(classify_bespoke_filename "$target_lint")
      new_path="$repo_dir/.github/workflows/$new_name"
      if [[ -e "$new_path" ]]; then
        new_name="bespoke-${new_name}"
        new_path="$repo_dir/.github/workflows/$new_name"
      fi
      echo "  renaming existing lint.yml -> $new_name"
      git mv "$target_lint" "$new_path"
      # Update its top-level name: to be distinguishable
      new_display_name=$(classify_bespoke_name "$new_name")
      # Replace exactly the first 'name:' line
      tmp=$(mktemp)
      awk -v new_name="$new_display_name" '
        BEGIN { replaced = 0 }
        /^name:/ && !replaced { print "name: " new_name; replaced = 1; next }
        { print }
      ' "$new_path" > "$tmp"
      mv "$tmp" "$new_path"
      git add "$new_path"
    fi

    # Write the caller
    render_caller_workflow "$default_branch" > "$repo_dir/.github/workflows/lint.yml"
    git add "$repo_dir/.github/workflows/lint.yml"

    # Commit
    if git diff --cached --quiet; then
      echo "  nothing to commit (already up-to-date)"
      exit 0
    fi
    if [[ -n "$replaceable" ]]; then
      git commit -m "ci: replace meta-linter with shared super-linter (soft launch)" --quiet
    else
      git commit -m "ci: add super-linter (soft launch via shared reusable workflow)" --quiet
    fi

    git push -u origin chore/add-super-linter --force-with-lease --quiet

    # Open PR (idempotent)
    pr_url=$(gh pr view chore/add-super-linter --json url --jq '.url' 2>/dev/null || true)
    if [[ -z "$pr_url" ]]; then
      pr_url=$(gh pr create \
        --title "ci: add super-linter (soft launch)" \
        --body "Adds soft-launched super-linter via the shared reusable workflow at \`LukeEvansTech/shared-workflows@v1\`. Lint findings appear in the workflow step summary and as a PR comment; failures do not block merges. See https://github.com/LukeEvansTech/shared-workflows/blob/main/docs/spec.md.")
    fi
    echo "  PR: $pr_url"
  ) || rc=$?
  rc=${rc:-0}

  if [[ $rc -eq 99 ]]; then
    NEEDS_REVIEW+=("$name :: lint.yml has deploy steps — manual review")
    rc=0
    continue
  fi
  if [[ $rc -ne 0 ]]; then
    ERRORS+=("$name (rollout failed with rc=$rc)")
    rc=0
    continue
  fi

  ONBOARDED+=("$name")
  rc=0
done

echo
echo "================ ROLLOUT SUMMARY ($OWNER) ================"
printf "Onboarded (%d):\n" "${#ONBOARDED[@]}";          printf "  %s\n" "${ONBOARDED[@]:-(none)}"
printf "\nSkipped — archived (%d):\n" "${#SKIPPED_ARCHIVED[@]}"; printf "  %s\n" "${SKIPPED_ARCHIVED[@]:-(none)}"
printf "\nSkipped — fork (%d):\n" "${#SKIPPED_FORK[@]}"; printf "  %s\n" "${SKIPPED_FORK[@]:-(none)}"
printf "\nSkipped — empty (%d):\n" "${#SKIPPED_EMPTY[@]}"; printf "  %s\n" "${SKIPPED_EMPTY[@]:-(none)}"
printf "\nSkipped — already onboarded (%d):\n" "${#SKIPPED_ALREADY_HAS[@]}"; printf "  %s\n" "${SKIPPED_ALREADY_HAS[@]:-(none)}"
printf "\nNeeds manual review (%d):\n" "${#NEEDS_REVIEW[@]}"; printf "  %s\n" "${NEEDS_REVIEW[@]:-(none)}"
printf "\nErrors (%d):\n" "${#ERRORS[@]}";           printf "  %s\n" "${ERRORS[@]:-(none)}"
echo "==========================================================="
