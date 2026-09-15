"""The API documentation must reach the prompt as documentation, not as a digest.

This guards the most expensive defect of the 2026-09-15 pilot. `api_docs_digest` is a
sha256 manifest fingerprint, and it was being passed where the prompt expected docs. The
model was handed 64 hex characters, concluded the task was impossible -- "the Spotify
plugin is not installed" -- and every arm scored a uniform 0.0. Nothing crashed, and a
table of zeros looks like a finding rather than a bug.

These tests never import AppWorld: `_summarise_api_docs` takes any mapping, and the loop
side is checked through MockEnv, which is the whole reason MockEnv carries api docs.
"""
from __future__ import annotations

import re

from sidekick.environments.appworld_env import _summarise_api_docs
from sidekick.environments.mock_env import _API_DOCS, MockEnv

SHA256 = re.compile(r"^[0-9a-f]{64}$")


class _Doc(dict):
    """Stands in for AppWorld's ApiDocCollection: a mapping, and attribute access on an
    unknown key raises rather than returning None (there it is a fastapi HTTPException),
    which is why the summariser must only use .keys() and [key]."""

    def __getattr__(self, name: str):
        raise RuntimeError(f"attribute probing is not supported: {name!r}")


def _docs() -> _Doc:
    return _Doc(
        spotify=_Doc(
            show_song_library=_Doc(description="Show the songs in the user's library."),
            play_song=_Doc(description="Play a song."),
        ),
        gmail=_Doc(send_email=_Doc(description="Send an email.")),
    )


def test_summary_names_apps_and_apis_in_callable_form():
    text = _summarise_api_docs(_docs())
    # Fully qualified: a bare "show_song_library(...)" is a NameError in AppWorld, which
    # is exactly what the executor emitted before the names were qualified.
    assert "apis.spotify.show_song_library" in text
    assert "apis.gmail.send_email" in text
    assert "Show the songs in the user's library." in text


def test_summary_carries_the_usage_preamble():
    text = _summarise_api_docs(_docs())
    lowered = text.lower()
    assert "apis." in text
    # The preamble is what tells the model it is inside AppWorld at all.
    assert "print" in lowered
    assert "complete" in lowered


def test_summary_is_not_a_digest():
    text = _summarise_api_docs(_docs())
    assert not SHA256.match(text.strip())
    assert len(text) > 200


def test_mock_env_prompt_is_the_docs_not_the_digest():
    env = MockEnv()
    assert env.api_docs_prompt == _API_DOCS
    assert SHA256.match(env.api_docs_digest)
    assert env.api_docs_prompt != env.api_docs_digest
