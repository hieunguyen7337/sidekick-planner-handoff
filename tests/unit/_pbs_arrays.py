"""Read a bash array literal (e.g. FREE_ARMS in scripts/pbs/hj12_prefix.pbs) the way bash does.

The earlier per-test parsers cut the array at the first ")" in the file after `NAME=(`. The HJ-19
comment inside FREE_ARMS contains "(no chat_template_kwargs)", so every entry after it -- HJ-19,
HJ-18 and all twelve LP arms -- was never checked, and the tests still passed. The closing
parenthesis of a multi-line array is a line holding nothing but ")", so that is the only thing
treated as the end here. A line that is neither blank, a comment, nor one quoted entry raises
instead of being skipped: a parser that quietly drops what it does not understand is the defect
this module exists to remove.
"""
from __future__ import annotations

import re
from pathlib import Path

# One quoted entry per line, optionally followed by a trailing comment. Double or single quotes.
_ENTRY = re.compile(r"""^\s*(?:"([^"]*)"|'([^']*)')\s*(?:#.*)?$""")


def read_bash_array(path: str | Path, name: str) -> list[str]:
    """Return the entries of the multi-line bash array `name=( ... )` in `path`, unexpanded.

    `${REPO}` and other expansions are returned literally; callers substitute what they need.
    Raises ValueError if the array is absent, declared more than once, unterminated, or holds a
    line that is not a quoted entry.
    """
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    opener = re.compile(rf"^\s*{re.escape(name)}=\(\s*$")
    starts = [i for i, line in enumerate(lines) if opener.match(line)]
    if len(starts) != 1:
        raise ValueError(f"{path}: expected exactly one '{name}=(' line, found {len(starts)}")
    entries: list[str] = []
    for lineno, line in enumerate(lines[starts[0] + 1 :], start=starts[0] + 2):
        stripped = line.strip()
        if stripped == ")":
            return entries
        if not stripped or stripped.startswith("#"):
            continue
        m = _ENTRY.match(line)
        if m is None:
            raise ValueError(f"{path}:{lineno}: not a quoted {name} entry: {line!r}")
        entries.append(m.group(1) if m.group(1) is not None else m.group(2))
    raise ValueError(f"{path}: '{name}=(' at line {starts[0] + 1} is never closed by a ')' line")
