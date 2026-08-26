"""JSON5/JSONC -> JSON conversion, stdlib only.

One implementation for every place this repository has to read a caller's
`.renovaterc.json5` without a JSON5 library: `zensical_drift.py` imports it,
and `renovate-review.yml` fetches this file at its own pinned commit and runs
it as a script (`python3 jsonc_to_json.py FILE` -> JSON on stdout).

It is a single string-aware pass, so nothing inside a string literal is ever
mistaken for syntax. It covers the constructs the estate's Renovate configs
actually use (each has a regression test naming the config it came from):

- `//` line comments and `/* */` block comments
- single-quoted strings, re-emitted as JSON double-quoted strings
  (`\\'` unescaped, bare `"` escaped)
- unquoted identifier keys anywhere, including inline
  `{ matchManagers: [...], groupName: "..." }` objects as prettier writes them
- trailing commas before `}` / `]`

Deliberately NOT covered, because no caller uses them: hex / `+` / `.5`
numbers, `Infinity`, `NaN`, backslash-newline string continuations.
"""

from __future__ import annotations

import json
import sys

_IDENT_START = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$")
_IDENT_CHARS = _IDENT_START | frozenset("0123456789")
_WS = frozenset(" \t\r\n")


def _read_string(text: str, i: int) -> tuple[str, int]:
    """Copy the string literal opening at text[i]; return (JSON token, index after it).

    Escapes are kept intact. A single-quoted JSON5 string becomes a
    double-quoted one, so an embedded bare `"` gains a backslash and `\\'`
    loses its own.
    """
    quote, j, buf = text[i], i + 1, []
    n = len(text)
    while j < n and text[j] != quote:
        if text[j] == "\\" and j + 1 < n:
            if quote == "'" and text[j + 1] == "'":
                buf.append("'")
            else:
                buf.append(text[j : j + 2])
            j += 2
            continue
        if quote == "'" and text[j] == '"':
            buf.append('\\"')
        else:
            buf.append(text[j])
        j += 1
    return '"' + "".join(buf) + '"', j + 1


def _read_word(text: str, i: int) -> tuple[str, int]:
    """Read the bare word at text[i]; quote it when it is an object key.

    A word is a key if the next non-blank character is `:`; otherwise it is a
    literal (true/false/null) passed through for json to judge.
    """
    n = len(text)
    j = i
    while j < n and text[j] in _IDENT_CHARS:
        j += 1
    k = j
    while k < n and text[k] in _WS:
        k += 1
    word = text[i:j]
    return ('"' + word + '"' if k < n and text[k] == ":" else word), j


def _skip_comment(text: str, i: int) -> int:
    """Return the index just past the comment opening at text[i], or i if none."""
    if text.startswith("//", i):
        j = text.find("\n", i)
        return len(text) if j == -1 else j
    if text.startswith("/*", i):
        j = text.find("*/", i + 2)
        return len(text) if j == -1 else j + 2
    return i


def _drop_trailing_comma(out: list[str]) -> None:
    """Remove a `,` separated from the closer about to be emitted only by whitespace.

    Every entry in `out` is either one character of syntax/whitespace or a
    whole string/word token, so a `,` entry is always structural.
    """
    k = len(out) - 1
    while k >= 0 and out[k] in _WS:
        k -= 1
    if k >= 0 and out[k] == ",":
        del out[k]


def convert(text: str) -> str:
    """Return `text` rewritten as strict JSON (still a string; not parsed)."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in "\"'":
            token, i = _read_string(text, i)
            out.append(token)
        elif c == "/" and (j := _skip_comment(text, i)) != i:
            i = j
        elif c in _IDENT_START:
            token, i = _read_word(text, i)
            out.append(token)
        else:
            if c in "}]":
                _drop_trailing_comma(out)
            out.append(c)
            i += 1
    return "".join(out)


def loads(text: str):
    """json.loads for JSON5/JSONC input: plain JSON is tried first, untouched."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(convert(text))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: jsonc_to_json.py FILE", file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8") as fh:
        raw = fh.read()
    try:
        data = loads(raw)
    except json.JSONDecodeError as exc:
        print(f"{argv[1]}: not parseable as JSON5/JSONC: {exc}", file=sys.stderr)
        return 1
    json.dump(data, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
