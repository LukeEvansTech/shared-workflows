#!/usr/bin/env python3
"""
In-place patch for existing chore/add-super-linter branches to:
  1. Move top-level write permissions to job level (zizmor
     excessive-permissions).
  2. Bump the shared-workflows SHA pin to current v1.

Idempotent: skips if the file already has job-level permissions.
"""
import re
import sys
from pathlib import Path

NEW_SHA = "57fff6deea8cdc1b42b62a16e72ce73df3b82f97"
USES_PATTERN = re.compile(
    r'^(\s+)uses: LukeEvansTech/shared-workflows/\.github/workflows/super-linter\.yml@[a-f0-9]+ # v1',
    re.MULTILINE,
)
JOB_PERMS_BLOCK_FORMAT = (
    "{indent}permissions:\n"
    "{indent}  contents: read\n"
    "{indent}  statuses: write\n"
    "{indent}  pull-requests: write\n"
)

def patch(path: Path) -> str:
    content = path.read_text()

    # Detect already-patched state: job-level permissions block adjacent to `uses:`
    # If there's a `permissions:` line within 4 lines above the `uses:` line, skip.
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if "uses: LukeEvansTech/shared-workflows" in line:
            # Look backwards for permissions: at the same indent as `uses:`
            uses_indent = len(line) - len(line.lstrip())
            for j in range(max(0, i - 6), i):
                if lines[j].lstrip().startswith("permissions:"):
                    perm_indent = len(lines[j]) - len(lines[j].lstrip())
                    if perm_indent == uses_indent:
                        return "already-job-level"

    # Step 1: collapse top-level permissions block
    old_perms_block = (
        "permissions:\n"
        "  contents: read\n"
        "  statuses: write\n"
        "  pull-requests: write"
    )
    new_perms_block = "permissions:\n  contents: read"
    new_content = content.replace(old_perms_block, new_perms_block, 1)

    # Step 2: insert job-level permissions before the `uses:` line and bump SHA
    def replace_uses(m):
        indent = m.group(1)
        block = JOB_PERMS_BLOCK_FORMAT.format(indent=indent)
        return (
            f"{block}{indent}uses: LukeEvansTech/shared-workflows/"
            f".github/workflows/super-linter.yml@{NEW_SHA} # v1"
        )

    new_content = USES_PATTERN.sub(replace_uses, new_content, count=1)
    if new_content == content:
        return "no-change"
    path.write_text(new_content)
    return "patched"


def main():
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} <repo-dir>")
    target = Path(sys.argv[1]) / ".github" / "workflows" / "lint.yml"
    if not target.is_file():
        print(f"  no lint.yml at {target}")
        return
    result = patch(target)
    print(f"  {target.relative_to(Path(sys.argv[1]))}: {result}")


if __name__ == "__main__":
    main()
