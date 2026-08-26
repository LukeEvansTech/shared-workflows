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


def convert(text: str) -> str:
    """Return `text` rewritten as strict JSON (still a string; not parsed)."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]

        if c in "\"'":
            # String literal: copy through, keeping escapes intact. A
            # single-quoted JSON5 string becomes a double-quoted one, so an
            # embedded bare `"` gains a backslash and `\'` loses its own.
            quote, j, buf = c, i + 1, []
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
            out.append('"' + "".join(buf) + '"')
            i = j + 1
            continue

        if c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            i = n if j == -1 else j
            continue

        if c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue

        if c in _IDENT_START:
            # Bare word: a key if the next non-blank character is `:`, else a
            # literal (true/false/null) passed through for json to judge.
            j = i
            while j < n and text[j] in _IDENT_CHARS:
                j += 1
            k = j
            while k < n and text[k] in _WS:
                k += 1
            word = text[i:j]
            out.append('"' + word + '"' if k < n and text[k] == ":" else word)
            i = j
            continue

        if c in "}]":
            # Trailing comma: every entry in `out` is either one character of
            # syntax/whitespace or a whole string/word token, so a `,` entry
            # separated from this closer only by whitespace is structural.
            k = len(out) - 1
            while k >= 0 and out[k] in _WS:
                k -= 1
            if k >= 0 and out[k] == ",":
                del out[k]
            out.append(c)
            i += 1
            continue

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
