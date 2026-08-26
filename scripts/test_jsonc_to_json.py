"""Tests for jsonc_to_json.py.

Every fixture below is a construct copied from a live caller's
`.renovaterc.json5`; the caller is named in the test so a future failure can
be checked against the real file.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("jsonc_to_json.py")


def _load():
    spec = importlib.util.spec_from_file_location("jsonc_to_json", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_plain_json_is_untouched():
    mod = _load()
    text = '{"extends": ["github>LukeEvansTech/renovate-config"], "a": [1, 2]}'
    assert mod.convert(text) == text
    assert mod.loads(text) == json.loads(text)


def test_single_quoted_string_with_embedded_double_quotes_and_braces():
    """talos-cluster: a customDatasources `transformTemplates` entry is a
    single-quoted JS string holding a JSONata expression full of `"` and `{}`.
    The previous stripper left the single quotes in place and json rejected it."""
    mod = _load()
    text = """{
      transformTemplates: [
        '{"releases": $map($filter(versions.*, function($v) { $not($contains($v, "-pre")) }), function($v) { {"version": $v} }), "sourceUrl": "https://papermc.io"}',
      ],
    }"""
    data = mod.loads(text)
    assert data["transformTemplates"] == [
        '{"releases": $map($filter(versions.*, function($v) { $not($contains($v, "-pre")) }), function($v) { {"version": $v} }), "sourceUrl": "https://papermc.io"}'
    ]


def test_single_quoted_keys_and_values():
    """tailscale-relay: the whole file is single-quoted, `$schema` included."""
    mod = _load()
    text = """{
  $schema: 'https://docs.renovatebot.com/renovate-schema.json',
  extends: ['github>LukeEvansTech/renovate-config'],
}"""
    assert mod.loads(text) == {
        "$schema": "https://docs.renovatebot.com/renovate-schema.json",
        "extends": ["github>LukeEvansTech/renovate-config"],
    }


def test_escaped_single_quote_inside_single_quoted_string():
    mod = _load()
    assert mod.loads("{a: 'it\\'s'}") == {"a": "it's"}


def test_inline_object_with_unquoted_keys():
    """apc-fleet / acinfinity-exporter / containers / redfish-fleet: prettier
    keeps short packageRules on one line, so the keys are not at line start
    and the old line-anchored regex never quoted them."""
    mod = _load()
    text = """{
  $schema: "https://docs.renovatebot.com/renovate-schema.json",
  extends: ["github>LukeEvansTech/renovate-config"],
  packageRules: [
    { matchManagers: ["pip_requirements"], groupName: "Python dependencies" },
  ],
}"""
    data = mod.loads(text)
    assert data["packageRules"] == [
        {"matchManagers": ["pip_requirements"], "groupName": "Python dependencies"}
    ]


def test_comments_are_string_aware_and_urls_survive():
    """shared-workflows' own regression (talos-cluster #3709): `/*` inside a
    glob string must not open a comment, and `//` inside a URL is not one."""
    mod = _load()
    text = """{
  ignorePaths: [".archive/**"], // trailing line comment
  extends: ["github>LukeEvansTech/renovate-config"],
  // per-app twins in kubernetes/**/ocirepository.yaml are exempt
  url: "https://example.com/a//b", /* block
  comment */
  rebaseWhen: "conflicted",
}"""
    data = mod.loads(text)
    assert data["ignorePaths"] == [".archive/**"]
    assert data["url"] == "https://example.com/a//b"
    assert data["rebaseWhen"] == "conflicted"
    assert "comment" not in mod.convert(text)


def test_trailing_commas_only_outside_strings():
    mod = _load()
    assert mod.loads('{a: [1, 2,], b: "x,]", c: {d: 1,},}') == {
        "a": [1, 2],
        "b": "x,]",
        "c": {"d": 1},
    }


def test_bare_literals_pass_through():
    mod = _load()
    assert mod.loads("{a: true, b: false, c: null, d: -1.5e3}") == {
        "a": True,
        "b": False,
        "c": None,
        "d": -1500.0,
    }


def test_cli_writes_json_and_fails_loudly(tmp_path):
    good = tmp_path / "good.json5"
    good.write_text("{extends: ['x'], // c\n}\n")
    res = subprocess.run(
        [sys.executable, str(SCRIPT), str(good)], capture_output=True, text=True, check=False
    )
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout) == {"extends": ["x"]}

    bad = tmp_path / "bad.json5"
    bad.write_text("{extends: [0x1F]}\n")
    res = subprocess.run(
        [sys.executable, str(SCRIPT), str(bad)], capture_output=True, text=True, check=False
    )
    assert res.returncode == 1
    assert "not parseable" in res.stderr


@pytest.mark.parametrize("argv", [[], ["a", "b"]])
def test_cli_usage(argv):
    res = subprocess.run(
        [sys.executable, str(SCRIPT), *argv], capture_output=True, text=True, check=False
    )
    assert res.returncode == 2
