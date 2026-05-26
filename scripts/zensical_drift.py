#!/usr/bin/env python3
"""Drift check for zensical docs standard.

Run with --repo-root <path> to check a target repo's conformance.
Emits GitHub annotations and exits non-zero on any violation.

Spec: docs/superpowers/specs/2026-05-26-zensical-docs-standard-design.md
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FAILURES: list[str] = []


def fail(check: str, file: str, message: str) -> None:
    FAILURES.append(f"::error file={file}::[{check}] {message}")
    print(f"FAIL [{check}] {file}: {message}", file=sys.stderr)


def check_pin(repo_root: Path) -> None:
    req = repo_root / "docs" / "requirements.txt"
    if not req.exists():
        fail("pin", str(req), "docs/requirements.txt is missing")
        return
    lines = [l.strip() for l in req.read_text().splitlines() if l.strip() and not l.startswith("#")]
    if not lines:
        fail("pin", str(req), "docs/requirements.txt has no non-comment lines")
        return
    if len(lines) > 1:
        fail("pin", str(req), f"docs/requirements.txt should contain only `zensical==X.Y.Z`; found {len(lines)} non-comment lines")
        return
    pin = lines[0]
    if not re.fullmatch(r"zensical==\d+\.\d+\.\d+", pin):
        fail("pin", str(req), f"pin must use exact version (`zensical==X.Y.Z`); found `{pin}`")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    args = parser.parse_args()
    check_pin(args.repo_root)
    for line in FAILURES:
        print(line)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
