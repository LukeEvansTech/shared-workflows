#!/usr/bin/env python3
"""Propagate templates/.markdownlint.yml to all 18 zensical docs repos.

Run after editing the canonical template. Idempotent.
"""
import base64
import json
import subprocess
import sys
from pathlib import Path

CANONICAL = Path(__file__).parent.parent / "templates" / ".markdownlint.yml"

REPOS = [
    "LukeEvansTech/PSReddit",
    "LukeEvansTech/copilot-kql-library",
    "LukeEvansTech/col-entra-id",
    "LukeEvansTech/acinfinity-exporter",
    "LukeEvansTech/github-infrastructure",
    "LukeEvansTech/entra-ca-templates",
    "LukeEvansTech/maester-copilot-tests",
    "LukeEvansTech/copilot-security-checker",
    "LukeEvansTech/purview-content-explorer-helpers",
    "LukeEvansTech/purview-content-explorer-export",
    "LukeEvansTech/purview-dlp-export",
    "LukeEvansTech/defender-device-control-unmanaged",
    "LukeEvansTech/lgwebos",
    "LukeEvansTech/stwt-m365-consolidation",
    "LukeEvansTech/M365LabelSync",
    "LukeEvansTech/dotfiles",
    "LukeEvansTech/network-ops",
    "LukeEvansTech/terraform-dns",
]


def gh(args):
    return subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=30)


def main() -> int:
    canonical_text = CANONICAL.read_text()
    canonical_b64 = base64.b64encode(canonical_text.encode()).decode()
    for repo in REPOS:
        r = gh(["api", f"repos/{repo}/contents/.markdownlint.yml"])
        if r.returncode == 0:
            data = json.loads(r.stdout)
            current = base64.b64decode(data["content"]).decode()
            if current == canonical_text:
                print(f"{repo}: NO-CHANGE")
                continue
            sha = data["sha"]
            r = gh(["api", "-X", "PUT", f"repos/{repo}/contents/.markdownlint.yml",
                    "-f", "message=chore: sync canonical markdownlint config",
                    "-f", f"content={canonical_b64}",
                    "-f", f"sha={sha}"])
        else:
            r = gh(["api", "-X", "PUT", f"repos/{repo}/contents/.markdownlint.yml",
                    "-f", "message=chore: add canonical markdownlint config",
                    "-f", f"content={canonical_b64}"])
        if r.returncode == 0:
            sha = json.loads(r.stdout)["commit"]["sha"][:7]
            print(f"{repo}: OK {sha}")
        else:
            print(f"{repo}: FAIL — {r.stderr.strip()[:200]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
