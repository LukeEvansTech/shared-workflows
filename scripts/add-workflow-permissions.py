#!/usr/bin/env python3
"""
Scan a repo's .github/workflows/*.yml files. For any workflow lacking a
top-level `permissions:` block, insert `permissions: { contents: read }`
just before the `jobs:` line.

This satisfies CHECKOV CKV2_GHA_1 (`Ensure top-level permissions are not
set to write-all`) by being explicit about the permission scope.

Conservative:
  - Skips files that already have a top-level `permissions:` line.
  - Only inserts the block before the FIRST `^jobs:` line.
  - Files where `^jobs:` isn't found are left alone with a warning.
  - Idempotent — running again produces no changes.

Per-job permissions overrides remain intact and take precedence over the
top-level default at runtime, so workflows that previously relied on
write-all defaults will need per-job adjustments. Those manifest as run
failures, which we'll surface and fix individually.
"""
import sys
from pathlib import Path

PERMISSIONS_BLOCK = """permissions:
  contents: read

"""

def has_top_level_permissions(content: str) -> bool:
    """True if any line is exactly `permissions:` at column 0."""
    for line in content.splitlines():
        stripped = line.rstrip()
        if stripped == "permissions:" or stripped.startswith("permissions:") and not line.startswith(" "):
            # Top-level (column 0) permissions line
            if not line.startswith(" ") and not line.startswith("\t"):
                return True
    return False

def patch_workflow(path: Path) -> str:
    content = path.read_text()
    if has_top_level_permissions(content):
        return "skip-has-permissions"

    lines = content.splitlines(keepends=True)

    # Find the first `^jobs:` line
    jobs_idx = None
    for i, line in enumerate(lines):
        if line.startswith("jobs:"):
            jobs_idx = i
            break
    if jobs_idx is None:
        return "skip-no-jobs-line"

    # Insert the permissions block immediately before `jobs:`
    new_lines = lines[:jobs_idx] + [PERMISSIONS_BLOCK] + lines[jobs_idx:]
    path.write_text("".join(new_lines))
    return "patched"

def main():
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} <repo-dir>")
    root = Path(sys.argv[1])
    workflows_dir = root / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return  # no workflows; nothing to do

    for f in sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml")):
        # Skip the lint.yml caller — it already has permissions
        if f.name == "lint.yml":
            continue
        result = patch_workflow(f)
        print(f"  {f.relative_to(root)}: {result}")

if __name__ == "__main__":
    main()
