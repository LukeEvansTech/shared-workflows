"""Tests for the inline->table superfences transform in sync_mermaid_superfences.py.

Guards the mermaid-enablement rewrite: it must register a real custom_fence,
produce valid TOML, and be idempotent. See memory project_zensical_mermaid_support.
"""

import tomllib

import pytest  # pylint: disable=import-error  # present at runtime, not in the lint env
from sync_mermaid_superfences import already_enabled, enable_mermaid

INLINE = """\
[project]
site_name = "X"

[project.markdown_extensions.pymdownx]
highlight = { anchor_linenums = true }
inlinehilite = {}
snippets = {}
superfences = {}
"""

# pymdownx block is NOT last in the file — superfences removal happens mid-file,
# table is appended at EOF; must still parse and register correctly.
INLINE_NOT_LAST = """\
[project]
site_name = "X"

[project.markdown_extensions.pymdownx]
superfences = {}

[project.theme]
name = "material"
"""


def test_inline_is_not_already_enabled():
    assert already_enabled(INLINE) is False


def test_transform_registers_custom_fence_and_is_valid_toml():
    out = enable_mermaid(INLINE)
    assert out is not None
    tomllib.loads(out)  # raises if malformed
    assert already_enabled(out) is True
    assert "[project.markdown_extensions.pymdownx.superfences]" in out
    assert "mermaid" in out


def test_transform_is_idempotent():
    out = enable_mermaid(INLINE)
    assert out is not None
    assert enable_mermaid(out) is None


def test_transform_handles_superfences_not_at_eof():
    out = enable_mermaid(INLINE_NOT_LAST)
    assert out is not None
    data = tomllib.loads(out)
    assert data["project"]["theme"]["name"] == "material"  # unrelated table preserved
    assert already_enabled(out) is True


def test_already_enabled_table_form_is_noop():
    enabled = enable_mermaid(INLINE)
    assert enabled is not None
    assert already_enabled(enabled) is True
    assert enable_mermaid(enabled) is None


def test_no_extension_table_is_left_on_defaults():
    # zensical's defaults already render mermaid; adding a table would replace them
    assert enable_mermaid('[project]\nsite_name = "X"\n') is None


def test_unscoped_tables_are_refused():
    with pytest.raises(ValueError, match="outside"):
        enable_mermaid(
            "[project]\n\n[markdown_extensions.pymdownx]\nsuperfences = {}\n"
        )


def test_list_form_is_refused():
    with pytest.raises(ValueError, match="list"):
        enable_mermaid('[project]\nmarkdown_extensions = ["admonition"]\n')


def test_dotted_superfences_key_is_replaced():
    out = enable_mermaid(
        "[project]\n\n[project.markdown_extensions]\nadmonition = {}\npymdownx.superfences = {}\n"
    )
    assert out is not None
    assert already_enabled(out) is True
