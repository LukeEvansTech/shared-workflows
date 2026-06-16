#!/usr/bin/env python3
"""Enable Mermaid in every zensical docs repo's docs/zensical.toml.

The canonical standard historically shipped the INLINE form `superfences = {}`
under [markdown_extensions.pymdownx], which silently does NOT register custom
fences — so ```mermaid blocks pass through unrendered on the built site. This
script rewrites that to the TABLE form with a mermaid custom_fence:

    [markdown_extensions.pymdownx.superfences]
    custom_fences = [{ name = "mermaid", class = "mermaid",
                       format = "pymdownx.superfences.fence_code_format" }]

Verified (2026-06-16, zensical 0.0.45): the table form makes the block build to
<pre class="mermaid"> and the Material theme auto-injects mermaid.js (fetched
from the unpkg CDN at runtime — rendering needs browser network access).

Idempotent + TOML-safe: skips repos already enabled, validates the rewritten
TOML with tomllib before committing, and skips (does not corrupt) anything it
can't transform cleanly. Mirrors sync_markdownlint.py (commits via the gh API).

Usage:
    python3 scripts/sync_mermaid_superfences.py [--dry-run]
"""

import base64
import json
import re
import subprocess
import sys
import tomllib

from audit_zensical_standard import REPOS_BUILD_ONLY, REPOS_PUBLISHING

REPOS = REPOS_PUBLISHING + REPOS_BUILD_ONLY

CUSTOM_FENCES = (
    'custom_fences = [{ name = "mermaid", class = "mermaid", '
    'format = "pymdownx.superfences.fence_code_format" }]'
)
TABLE_BLOCK = "\n[markdown_extensions.pymdownx.superfences]\n" + CUSTOM_FENCES + "\n"


def gh(args):
    return subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=30)


def already_enabled(text: str) -> bool:
    data = tomllib.loads(text)
    sf = data.get("markdown_extensions", {}).get("pymdownx", {}).get("superfences", {})
    return isinstance(sf, dict) and bool(sf.get("custom_fences"))


def enable_mermaid(text: str) -> str | None:
    """Return rewritten TOML enabling mermaid, or None if already enabled.

    Raises ValueError if the result would be invalid TOML (caller skips it).
    """
    if already_enabled(text):
        return None
    # Drop the inline `superfences = ...` key line(s) under pymdownx, then append
    # the fully-qualified table at EOF (TOML headers are absolute, so position is
    # irrelevant and EOF append can't capture later bare keys).
    lines = [ln for ln in text.splitlines() if not re.match(r"\s*superfences\s*=", ln)]
    new = "\n".join(lines).rstrip() + "\n" + TABLE_BLOCK
    tomllib.loads(new)  # validate; raises on malformed result
    if not already_enabled(new):
        raise ValueError("transform did not register the mermaid custom_fence")
    return new


def main() -> int:
    dry = "--dry-run" in sys.argv
    rc = 0
    for repo in REPOS:
        r = gh(["api", f"repos/{repo}/contents/docs/zensical.toml"])
        if r.returncode != 0:
            print(f"{repo}: SKIP (no docs/zensical.toml)")
            continue
        data = json.loads(r.stdout)
        current = base64.b64decode(data["content"]).decode()
        try:
            updated = enable_mermaid(current)
        except (tomllib.TOMLDecodeError, ValueError) as e:
            print(f"{repo}: SKIP (cannot transform safely: {e})", file=sys.stderr)
            rc = 1
            continue
        if updated is None:
            print(f"{repo}: NO-CHANGE (already enabled)")
            continue
        if dry:
            print(f"{repo}: WOULD UPDATE")
            continue
        content_b64 = base64.b64encode(updated.encode()).decode()
        w = gh(
            [
                "api",
                "-X",
                "PUT",
                f"repos/{repo}/contents/docs/zensical.toml",
                "-f",
                "message=feat(docs): enable mermaid via superfences custom_fences",
                "-f",
                f"content={content_b64}",
                "-f",
                f"sha={data['sha']}",
            ]
        )
        if w.returncode == 0:
            print(f"{repo}: OK {json.loads(w.stdout)['commit']['sha'][:7]}")
        else:
            print(f"{repo}: FAIL — {w.stderr.strip()[:200]}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
