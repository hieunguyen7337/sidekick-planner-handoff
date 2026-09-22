"""tests/unit/_pbs_arrays.read_bash_array: the shared FREE_ARMS reader.

The parsers it replaced stopped at the ")" inside the HJ-19 comment, so no HJ-19, HJ-18 or LP
entry was ever checked while every test stayed green. These pin that the reader reaches the real
end of the array, and that it refuses shapes it does not understand instead of skipping them.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from _pbs_arrays import read_bash_array

REPO = Path(__file__).resolve().parents[2]
PBS = REPO / "scripts" / "pbs" / "hj12_prefix.pbs"


def test_free_arms_reaches_the_last_entry_past_the_parenthesised_comment() -> None:
    arms = read_bash_array(PBS, "FREE_ARMS")
    # The last entry of the array is an LP-2 replay; stopping early would end on hj16/hj19.
    assert arms[-1] == "prefix_handoff|${REPO}/configs/lp2_prefix_bplus_m11.yaml|lp2_prefix_bplus_m11"
    stems = [entry.split("|")[2] for entry in arms]
    for rx in ("zs", "bplus"):
        for m in (6, 9, 11):
            assert f"hj18_prefix_c81s3_{rx}_m{m}" in stems
            assert f"lp1_prefix_{rx}_m{m}" in stems
            assert f"lp2_prefix_{rx}_m{m}" in stems
    assert "hj19_prefix_m11_qwen_notk" in stems
    assert "hj19_sft_plan_qwen_notk" in stems
    # Every data line between "FREE_ARMS=(" and its closing ")" is an entry; comments are not.
    text = PBS.read_text(encoding="utf-8").splitlines()
    start = text.index("FREE_ARMS=(")
    end = text.index(")", start)
    n_data = sum(1 for line in text[start + 1 : end] if line.strip() and not line.strip().startswith("#"))
    assert len(arms) == n_data
    assert len(stems) == len(set(stems)), "a FREE_ARMS stem is registered twice"


def test_comment_parenthesis_trailing_comment_and_single_quotes(tmp_path) -> None:
    script = tmp_path / "a.sh"
    script.write_text(
        "X=(\n"
        '  "one|a"\n'
        "  # a comment (with a paren) ) that used to end the array\n"
        "\n"
        "  'two|b'   # trailing comment\n"
        '  "three|c"\n'
        ")\n"
        'Y=("${X[@]}")\n',
        encoding="utf-8",
    )
    assert read_bash_array(script, "X") == ["one|a", "two|b", "three|c"]


@pytest.mark.parametrize(
    "body, message",
    [
        ('X=(\n  "a"\n', "never closed"),
        ('X=(\n  "a"\n  unquoted|entry\n)\n', "not a quoted X entry"),
        ('Y=(\n  "a"\n)\n', "found 0"),
        ('X=(\n)\nX=(\n)\n', "found 2"),
    ],
    ids=["unterminated", "unquoted", "absent", "declared_twice"],
)
def test_refuses_what_it_cannot_parse(tmp_path, body, message) -> None:
    script = tmp_path / "b.sh"
    script.write_text(body, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        read_bash_array(script, "X")
