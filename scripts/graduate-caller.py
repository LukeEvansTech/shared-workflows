#!/usr/bin/env python3
"""
Edit a repo's .github/workflows/lint.yml to add `soft-launch: false`,
graduating it from soft-launch to blocking.

Idempotent — won't add the line if already present.
"""
import sys
from pathlib import Path

if len(sys.argv) != 2:
    sys.exit(f"usage: {sys.argv[0]} <path-to-lint.yml>")

path = Path(sys.argv[1])
content = path.read_text()
lines = content.splitlines()

# Already graduated?
if any("soft-launch: false" in line for line in lines):
    print(f"{path}: already graduated, skipping")
    sys.exit(0)

# Find the line containing 'uses: ...super-linter.yml@'
out = []
i = 0
inserted = False
while i < len(lines):
    line = lines[i]
    out.append(line)
    if "super-linter.yml@" in line and "uses:" in line:
        # Look at the next non-blank line. If it starts with 'with:'
        # at the same indentation as 'uses:' minus 2 (i.e. job-step indent),
        # we append to existing with: block. Otherwise we add a new block.
        next_idx = i + 1
        while next_idx < len(lines) and lines[next_idx].strip() == "":
            next_idx += 1
        if next_idx < len(lines) and lines[next_idx].lstrip().startswith("with:"):
            # Existing with: block — copy it through and append our key
            i += 1
            # Copy any blank lines we skipped
            while i < next_idx:
                out.append(lines[i])
                i += 1
            out.append(lines[i])  # the "    with:" line
            i += 1
            # Now copy any existing "with:" entries (indented further)
            # Capture indent from existing with: line
            with_indent = len(lines[next_idx]) - len(lines[next_idx].lstrip())
            entry_indent = with_indent + 2
            while i < len(lines):
                if lines[i].strip() == "":
                    out.append(lines[i])
                    i += 1
                    continue
                cur_indent = len(lines[i]) - len(lines[i].lstrip())
                if cur_indent >= entry_indent:
                    out.append(lines[i])
                    i += 1
                else:
                    break
            # Now insert our new entry at entry_indent
            out.append(" " * entry_indent + "soft-launch: false")
            inserted = True
            continue
        else:
            # No with: block — add one
            uses_indent = len(line) - len(line.lstrip())
            with_indent = uses_indent
            entry_indent = with_indent + 2
            out.append(" " * with_indent + "with:")
            out.append(" " * entry_indent + "soft-launch: false")
            inserted = True
    i += 1

if not inserted:
    sys.exit(f"{path}: could not find 'uses: ...super-linter.yml@' line")

# Preserve trailing newline
suffix = "\n" if content.endswith("\n") else ""
path.write_text("\n".join(out) + suffix)
print(f"{path}: graduated")
