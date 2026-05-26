#!/usr/bin/env python3
"""Run zensical drift check against all 18 repos and report a summary.

Clones each into a temp dir, runs zensical_drift.py against it, collects results.
"""
import subprocess, tempfile, sys
from pathlib import Path

REPOS_PUBLISHING = [
    "LukeEvansTech/PSReddit",
    "LukeEvansTech/copilot-kql-library",
    "LukeEvansTech/acinfinity-exporter",
    "LukeEvansTech/entra-ca-templates",
    "LukeEvansTech/maester-copilot-tests",
    "LukeEvansTech/copilot-security-checker",
    "LukeEvansTech/purview-content-explorer-helpers",
    "LukeEvansTech/purview-content-explorer-export",
    "LukeEvansTech/purview-dlp-export",
    "LukeEvansTech/defender-device-control-unmanaged",
    "LukeEvansTech/M365LabelSync",
    "LukeEvansTech/dotfiles",
]
REPOS_BUILD_ONLY = [
    "LukeEvansTech/lgwebos",
    "LukeEvansTech/stwt-m365-consolidation",
    "LukeEvansTech/col-entra-id",
    "LukeEvansTech/github-infrastructure",
    "LukeEvansTech/network-ops",
    "LukeEvansTech/terraform-dns",
]
DRIFT = Path(__file__).parent / "zensical_drift.py"


def audit(repo: str, allow_no_pages: bool) -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run(["gh", "repo", "clone", repo, tmp, "--", "--depth=1"], capture_output=True, text=True)
        if r.returncode != 0:
            return 1, f"clone failed: {r.stderr.strip()}"
        args = ["python3", str(DRIFT), "--repo-root", tmp, "--repo", repo]
        if allow_no_pages:
            args.append("--allow-no-pages")
        r = subprocess.run(args, capture_output=True, text=True)
        return r.returncode, (r.stdout + r.stderr).strip()


def main() -> int:
    overall = 0
    print(f"{'Repo':45}  {'Result'}")
    print("-" * 80)
    for repo in REPOS_PUBLISHING:
        rc, out = audit(repo, allow_no_pages=False)
        status = "PASS" if rc == 0 else "FAIL"
        print(f"{repo:45}  {status}")
        if rc != 0:
            for line in out.splitlines()[-5:]:
                print(f"    {line}")
            overall = 1
    for repo in REPOS_BUILD_ONLY:
        rc, out = audit(repo, allow_no_pages=True)
        status = "PASS" if rc == 0 else "FAIL"
        print(f"{repo:45}  {status} (build-only)")
        if rc != 0:
            for line in out.splitlines()[-5:]:
                print(f"    {line}")
            overall = 1
    print()
    print("OVERALL:", "GREEN" if overall == 0 else "RED")
    return overall


if __name__ == "__main__":
    sys.exit(main())
