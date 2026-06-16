"""Tests for the inline->table superfences transform in sync_mermaid_superfences.py.

Guards the mermaid-enablement rewrite: it must register a real custom_fence,
produce valid TOML, and be idempotent. See memory project_zensical_mermaid_support.
"""

import tomllib

from sync_mermaid_superfences import already_enabled, enable_mermaid

INLINE = """\
[markdown_extensions.pymdownx]
highlight = { anchor_linenums = true }
inlinehilite = {}
snippets = {}
superfences = {}
"""

# pymdownx block is NOT last in the file — superfences removal happens mid-file,
# table is appended at EOF; must still parse and register correctly.
INLINE_NOT_LAST = """\
[markdown_extensions.pymdownx]
superfences = {}

[project]
site_name = "X"
"""


def test_inline_is_not_already_enabled():
    assert already_enabled(INLINE) is False


def test_transform_registers_custom_fence_and_is_valid_toml():
    out = enable_mermaid(INLINE)
    assert out is not None
    tomllib.loads(out)  # raises if malformed
    assert already_enabled(out) is True
    assert "[markdown_extensions.pymdownx.superfences]" in out
    assert "mermaid" in out


def test_transform_is_idempotent():
    out = enable_mermaid(INLINE)
    assert out is not None
    assert enable_mermaid(out) is None


def test_transform_handles_superfences_not_at_eof():
    out = enable_mermaid(INLINE_NOT_LAST)
    assert out is not None
    data = tomllib.loads(out)
    assert data["project"]["site_name"] == "X"  # unrelated table preserved
    assert already_enabled(out) is True


def test_already_enabled_table_form_is_noop():
    enabled = enable_mermaid(INLINE)
    assert enabled is not None
    assert already_enabled(enabled) is True
    assert enable_mermaid(enabled) is None
