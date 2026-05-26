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


def gh(args: list[str], input: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["gh"] + args, capture_output=True, text=True, input=input, timeout=30)


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
    api_args = ["api", "-X", "PUT", f"repos/{repo}/contents/{path}",
                "-f", f"message={message}",
                "-f", f"content={new_b64}"]
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
    r = gh(["api", "-X", "DELETE", f"repos/{repo}/contents/{path}",
            "-f", f"message={message}",
            "-f", f"sha={sha}"])
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
        delete_file(repo, path, "ci: remove superseded workflow (replaced by canonical docs.yml/lint.yml)", dry_run)

    upsert_file(repo, ".github/workflows/docs.yml",
                render_template("docs.yml", sha, publish, allow_no_pages),
                "ci(docs): adopt canonical docs workflow", dry_run)
    upsert_file(repo, ".github/workflows/lint.yml",
                render_template("lint.yml", sha, publish, allow_no_pages),
                "ci(lint): adopt canonical lint workflow", dry_run)
    upsert_file(repo, ".github/workflows/docs-standard-check.yml",
                render_template("docs-standard-check.yml", sha, publish, allow_no_pages),
                "ci(docs): adopt drift-check workflow", dry_run)

    upsert_file(repo, ".markdownlint.yml",
                (TEMPLATES / ".markdownlint.yml").read_text(),
                "chore: adopt canonical markdownlint config", dry_run)

    update_renovate(repo, dry_run)


def update_renovate(repo: str, dry_run: bool) -> None:
    r = gh(["api", f"repos/{repo}/contents/renovate.json"])
    canonical_text = (TEMPLATES / "renovate.json").read_text()
    canonical = json.loads(canonical_text)
    if r.returncode != 0:
        # No renovate.json yet — write canonical verbatim
        upsert_file(repo, "renovate.json", canonical_text,
                    "chore: add canonical renovate.json", dry_run)
        return
    existing_raw = base64.b64decode(json.loads(r.stdout)["content"]).decode()
    try:
        existing = json.loads(existing_raw)
    except json.JSONDecodeError:
        print(f"  renovate.json: BAILING — existing file is not valid JSON", file=sys.stderr)
        return
    extends = existing.get("extends", [])
    changed = False
    for required in canonical["extends"]:
        if required not in extends:
            extends.append(required)
            changed = True
    if not changed:
        print(f"  renovate.json: NO-CHANGE")
        return
    existing["extends"] = extends
    # If the only keys are $schema + extends with values matching canonical, write canonical verbatim
    # (this is the common case for all 18 repos and avoids prettier formatting drift)
    if set(existing.keys()) <= {"$schema", "extends"} and existing.get("$schema") == canonical.get("$schema") and existing["extends"] == canonical["extends"]:
        new_content = canonical_text
    else:
        # Repo has custom keys — preserve them, format extends inline to match prettier
        # Use json.dumps then post-process to inline short arrays
        new_content = _format_renovate(existing)
    upsert_file(repo, "renovate.json", new_content,
                "chore(renovate): add helpers:pinGitHubActionDigests", dry_run)


def _format_renovate(data: dict) -> str:
    """Format renovate.json matching prettier defaults: 2-space indent, short arrays inline.

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
            line = f'  {json.dumps(k)}: {inline}'
        else:
            # Generic JSON encode, indent=2 then re-indent
            encoded = json.dumps(v, indent=2)
            # Re-indent every line by 2 spaces after the first
            encoded_lines = encoded.splitlines()
            encoded_lines = [encoded_lines[0]] + ["  " + l for l in encoded_lines[1:]]
            line = f'  {json.dumps(k)}: ' + "\n".join(encoded_lines)
        if i < len(keys) - 1:
            line += ","
        lines.append(line)
    lines.append("}")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True, help="owner/name")
    publish_group = p.add_mutually_exclusive_group()
    publish_group.add_argument("--publish", dest="publish", action="store_true", default=True)
    publish_group.add_argument("--no-publish", dest="publish", action="store_false")
    p.add_argument("--allow-no-pages", action="store_true",
                   help="add `allow-no-pages: true` to drift-check caller (for build-only repos)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    apply(args.repo, args.publish, args.allow_no_pages, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
