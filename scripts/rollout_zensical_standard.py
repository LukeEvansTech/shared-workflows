#!/usr/bin/env python3
"""Apply the zensical docs standard to one repo.

Usage:
    python3 scripts/rollout_zensical_standard.py --repo owner/name [--publish/--no-publish] [--allow-no-pages] [--dry-run]

Idempotent: re-running produces no commits if everything is already conformant.
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path

TEMPLATES = Path(__file__).parent.parent / "templates"
SHARED_WORKFLOWS_REPO = "LukeEvansTech/shared-workflows"

# Single source of truth for which repos are build-only. Build-only repos must
# roll out with publish=false + allow-no-pages=true; forgetting the flags
# silently regressed 5 of 6 of them on 2026-06-07 (the publishing default ran
# Configure Pages, which fails when Pages is disabled). resolve_publish_flags()
# auto-applies the right defaults so an operator can't forget.
from audit_zensical_standard import REPOS_BUILD_ONLY
from zensical_drift import _strip_jsonc

# Renovate config filenames: `.renovaterc.json5` is the house standard, with the
# legacy `renovate.json` migrated away on next rollout.
RENOVATE_TARGET = ".renovaterc.json5"
RENOVATE_LEGACY = "renovate.json"


def resolve_publish_flags(
    repo: str, publish_arg: bool | None, allow_no_pages_arg: bool
) -> tuple[bool, bool]:
    """Resolve the effective (publish, allow_no_pages) for a repo.

    Build-only repos (REPOS_BUILD_ONLY) default to publish=false and always get
    allow-no-pages=true. An explicit --publish/--no-publish (publish_arg is not
    None) still wins. Unknown repos preserve the historical publish=true default.
    """
    is_build_only = repo in REPOS_BUILD_ONLY
    publish = (not is_build_only) if publish_arg is None else publish_arg
    allow_no_pages = bool(allow_no_pages_arg) or is_build_only
    return publish, allow_no_pages


def gh(args: list[str], stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["gh"] + args, capture_output=True, text=True, input=stdin, timeout=30, check=False
    )


def get_latest_sha() -> str:
    """Get the latest SHA on shared-workflows main."""
    r = gh(["api", f"repos/{SHARED_WORKFLOWS_REPO}/commits/main"])
    if r.returncode != 0:
        raise SystemExit(f"could not fetch shared-workflows SHA: {r.stderr}")
    return json.loads(r.stdout)["sha"]


def render_template(name: str, sha: str, publish: bool, allow_no_pages: bool) -> str:
    text = (TEMPLATES / name).read_text()
    text = text.replace("<SHA>", sha)
    if name == "docs.yml" and not publish:
        # Build-only override: replace the `with:` block
        text = text.replace(
            "with:\n      publish: ${{ github.event_name != 'pull_request' }}",
            "with:\n      publish: false",
        )
    if name == "docs-standard-check.yml" and allow_no_pages:
        text = text.replace(
            f"uses: LukeEvansTech/shared-workflows/.github/workflows/zensical-drift-check.yml@{sha} # v1",
            f"uses: LukeEvansTech/shared-workflows/.github/workflows/zensical-drift-check.yml@{sha} # v1\n    with:\n      allow-no-pages: true",
        )
    return text


def upsert_file(repo: str, path: str, content: str, message: str, dry_run: bool) -> None:
    r = gh(["api", f"repos/{repo}/contents/{path}"])
    if r.returncode == 0:
        existing = json.loads(r.stdout)
        sha = existing["sha"]
        current_text = base64.b64decode(existing["content"]).decode()
        if current_text == content:
            print(f"  {path}: NO-CHANGE")
            return
    else:
        sha = None
    if dry_run:
        print(f"  {path}: WOULD WRITE ({'create' if sha is None else 'update'})")
        return
    new_b64 = base64.b64encode(content.encode()).decode()
    api_args = [
        "api",
        "-X",
        "PUT",
        f"repos/{repo}/contents/{path}",
        "-f",
        f"message={message}",
        "-f",
        f"content={new_b64}",
    ]
    if sha:
        api_args.extend(["-f", f"sha={sha}"])
    r = gh(api_args)
    if r.returncode == 0:
        commit_sha = json.loads(r.stdout)["commit"]["sha"][:7]
        print(f"  {path}: OK {commit_sha}")
    else:
        print(f"  {path}: FAIL — {r.stderr.strip()[:200]}", file=sys.stderr)
        raise SystemExit(1)


def delete_file(repo: str, path: str, message: str, dry_run: bool) -> None:
    r = gh(["api", f"repos/{repo}/contents/{path}"])
    if r.returncode != 0:
        return  # already absent
    sha = json.loads(r.stdout)["sha"]
    if dry_run:
        print(f"  {path}: WOULD DELETE")
        return
    r = gh(
        [
            "api",
            "-X",
            "DELETE",
            f"repos/{repo}/contents/{path}",
            "-f",
            f"message={message}",
            "-f",
            f"sha={sha}",
        ]
    )
    if r.returncode == 0:
        print(f"  {path}: DELETED")
    else:
        print(f"  {path}: DELETE FAIL — {r.stderr.strip()[:200]}", file=sys.stderr)


SUPERSEDED_DEPLOY_WORKFLOWS = [
    ".github/workflows/deploy-docs.yml",
    ".github/workflows/psreddit-deploy-docs.yml",
    ".github/workflows/ddcu-deploy-docs.yml",
]
SUPERSEDED_LINT_WORKFLOWS = [
    ".github/workflows/ddcu-lint.yml",
]


def apply(repo: str, publish: bool, allow_no_pages: bool, dry_run: bool) -> None:
    sha = get_latest_sha()
    print(f"shared-workflows SHA: {sha}")
    print(f"Applying standard to {repo} (publish={publish}, allow_no_pages={allow_no_pages})")

    for path in SUPERSEDED_DEPLOY_WORKFLOWS + SUPERSEDED_LINT_WORKFLOWS:
        delete_file(
            repo,
            path,
            "ci: remove superseded workflow (replaced by canonical docs.yml/lint.yml)",
            dry_run,
        )

    upsert_file(
        repo,
        ".github/workflows/docs.yml",
        render_template("docs.yml", sha, publish, allow_no_pages),
        "ci(docs): adopt canonical docs workflow",
        dry_run,
    )
    upsert_file(
        repo,
        ".github/workflows/lint.yml",
        render_template("lint.yml", sha, publish, allow_no_pages),
        "ci(lint): adopt canonical lint workflow",
        dry_run,
    )
    upsert_file(
        repo,
        ".github/workflows/docs-standard-check.yml",
        render_template("docs-standard-check.yml", sha, publish, allow_no_pages),
        "ci(docs): adopt drift-check workflow",
        dry_run,
    )

    upsert_file(
        repo,
        ".markdownlint.yml",
        (TEMPLATES / ".markdownlint.yml").read_text(),
        "chore: adopt canonical markdownlint config",
        dry_run,
    )

    # Verbatim copy (no <SHA> placeholder), like .markdownlint.yml. Pins shell
    # indent so super-linter's SHELL_SHFMT matches the fleet's 2-space scripts.
    upsert_file(
        repo,
        ".editorconfig",
        (TEMPLATES / ".editorconfig").read_text(),
        "chore: adopt canonical .editorconfig (shfmt indent)",
        dry_run,
    )

    update_renovate(repo, dry_run)


def _read_remote_renovate(repo: str) -> tuple[str | None, str | None]:
    """Return (path, raw_text) of the repo's Renovate config, preferring
    `.renovaterc.json5` over the legacy `renovate.json`. (None, None) if absent."""
    for path in (RENOVATE_TARGET, RENOVATE_LEGACY):
        r = gh(["api", f"repos/{repo}/contents/{path}"])
        if r.returncode == 0:
            return path, base64.b64decode(json.loads(r.stdout)["content"]).decode()
    return None, None


def update_renovate(repo: str, dry_run: bool) -> None:
    canonical_text = (TEMPLATES / RENOVATE_TARGET).read_text()
    # Template is JSON5 (house idiom: unquoted keys); parse tolerantly.
    canonical = json.loads(_strip_jsonc(canonical_text))
    existing_path, existing_raw = _read_remote_renovate(repo)
    if existing_raw is None:
        # No config yet — write canonical verbatim
        upsert_file(
            repo, RENOVATE_TARGET, canonical_text, "chore: add canonical .renovaterc.json5", dry_run
        )
        return
    try:
        existing = json.loads(existing_raw)
    except json.JSONDecodeError:
        try:
            existing = json.loads(_strip_jsonc(existing_raw))
        except json.JSONDecodeError:
            print(f"  {existing_path}: BAILING — existing file is not parseable", file=sys.stderr)
            return
    extends = existing.get("extends", [])
    changed = False
    for required in canonical["extends"]:
        if required not in extends:
            extends.append(required)
            changed = True
    existing["extends"] = extends
    # A legacy renovate.json gets migrated to .renovaterc.json5 even when its
    # extends are already conformant.
    migrating = existing_path == RENOVATE_LEGACY
    if not changed and not migrating:
        print(f"  {existing_path}: NO-CHANGE")
        return
    # If the only keys are $schema + extends with values matching canonical, write canonical verbatim
    # (the common case; avoids prettier formatting drift)
    if (
        set(existing.keys()) <= {"$schema", "extends"}
        and existing.get("$schema") == canonical.get("$schema")
        and existing["extends"] == canonical["extends"]
    ):
        new_content = canonical_text
    else:
        # Repo has custom keys — preserve them, format extends inline to match prettier
        new_content = _format_renovate(existing)
    upsert_file(
        repo,
        RENOVATE_TARGET,
        new_content,
        "chore(renovate): standardize on shared LukeEvansTech/renovate-config preset",
        dry_run,
    )
    if migrating:
        delete_file(
            repo,
            RENOVATE_LEGACY,
            "chore(renovate): remove legacy renovate.json (renamed to .renovaterc.json5)",
            dry_run,
        )


def _format_renovate(data: dict) -> str:
    """Format .renovaterc.json5 matching prettier defaults: 2-space indent, short arrays inline.

    Specifically inlines top-level `extends` array since prettier collapses arrays
    that fit within the default print width (80 chars).
    """
    # Build manually: each top-level key on its own line, extends inline if short
    lines = ["{"]
    keys = list(data.keys())
    for i, k in enumerate(keys):
        v = data[k]
        # Format value
        if k == "extends" and isinstance(v, list) and all(isinstance(x, str) for x in v):
            inline = "[" + ", ".join(json.dumps(x) for x in v) + "]"
            line = f"  {json.dumps(k)}: {inline}"
        else:
            # Generic JSON encode, indent=2 then re-indent
            encoded = json.dumps(v, indent=2)
            # Re-indent every line by 2 spaces after the first
            encoded_lines = encoded.splitlines()
            encoded_lines = [encoded_lines[0]] + ["  " + ln for ln in encoded_lines[1:]]
            line = f"  {json.dumps(k)}: " + "\n".join(encoded_lines)
        if i < len(keys) - 1:
            line += ","
        lines.append(line)
    lines.append("}")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True, help="owner/name")
    publish_group = p.add_mutually_exclusive_group()
    publish_group.add_argument(
        "--publish",
        dest="publish",
        action="store_const",
        const=True,
        default=None,
        help="force publish=true. Default: auto (false for build-only repos)",
    )
    publish_group.add_argument(
        "--no-publish",
        dest="publish",
        action="store_const",
        const=False,
        help="force publish=false (build-only)",
    )
    p.add_argument(
        "--allow-no-pages",
        action="store_true",
        help="add `allow-no-pages: true` to drift-check caller (auto-enabled for build-only repos)",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    publish, allow_no_pages = resolve_publish_flags(args.repo, args.publish, args.allow_no_pages)
    if args.repo in REPOS_BUILD_ONLY and args.publish is None:
        print(f"note: {args.repo} is build-only -> publish=false, allow-no-pages=true (auto)")
    elif args.repo in REPOS_BUILD_ONLY and args.publish is True:
        print(
            f"WARNING: --publish forced on build-only repo {args.repo}; "
            "Configure Pages will fail unless Pages is enabled"
        )
    apply(args.repo, publish, allow_no_pages, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
