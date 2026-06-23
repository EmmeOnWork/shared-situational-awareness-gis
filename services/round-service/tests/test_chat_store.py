"""Unit tests for the per-Bene anonymous Chat store (pure core).

Pure style (no DB, no WebSocket): drive the Round engine to establish round facts
(who has voted, the current Round, the phase), then exercise the Chat's public
``append`` / ``read`` through that ``ProcessState``. Covers the post-vote write-gate
that preserves Vote independence, total anonymisation of the read/broadcast shape,
continuity of the stream across Rounds, and the live MessagePosted fan-out
(PRD module 4; service CONTEXT "Chat"; task 06).
"""

from datetime import datetime, timezone

import pytest

from src.engine.round_engine import (
    Join,
    Ready,
    OpenRound,
    CastVote,
    initial_state,
    apply,
)
from src.chat.chat_store import (
    empty_chat,
    append,
    read,
    AnonymousMessage,
    MessagePosted,
)


def _drive(state, events):
    for event in events:
        state, _ = apply(state, event)
    return state


def _opened(*ready_users):
    """A Bene with the given users joined, ready, and Round 1 open (roster = N)."""
    events = []
    for u in ready_users:
        events += [Join(u, "tecnico"), Ready(u)]
    events.append(OpenRound())
    return _drive(initial_state("bene-1"), events)


def _at(second):
    return datetime(2026, 6, 21, 12, 0, second, tzinfo=timezone.utc)


# --- Inner unit cycles -------------------------------------------------------


def test_append_rejected_when_author_has_not_voted():
    """The write-gate preserves Vote independence: a roster member who has not yet
    cast their Vote in the current Round cannot append (ValueError), so they cannot
    read others' arguments before voting."""
    state = _opened("u1", "u2")  # Round open, nobody has voted

    with pytest.raises(ValueError):
        append(empty_chat("bene-1"), state, "u1", "voto X", now=_at(1))


def test_append_accepted_once_author_has_voted():
    """Write access unlocks the moment the author has cast their Vote: the message
    is recorded against the current Round and the log grows by one."""
    state = _opened("u1", "u2")
    state, _ = apply(state, CastVote("u1", "casa-popolare"))

    chat, _ = append(empty_chat("bene-1"), state, "u1", "io voto casa popolare", now=_at(1))

    assert len(chat.messages) == 1
    assert chat.messages[0].body == "io voto casa popolare"
    assert chat.messages[0].round_number == 1


def test_read_is_fully_anonymised():
    """Reads never surface any author identity: the read shape carries the Round
    number, timestamp and body only — the internal author id is excluded entirely,
    even though it is retained on the internal record for abuse control."""
    state = _opened("u1", "u2")
    state, _ = apply(state, CastVote("u1", "casa-popolare"))
    chat, _ = append(empty_chat("bene-1"), state, "u1", "io voto casa popolare", now=_at(7))

    msgs = read(chat)

    assert msgs == (
        AnonymousMessage(round_number=1, body="io voto casa popolare", timestamp=_at(7)),
    )
    assert not hasattr(msgs[0], "author_id")
    # The internal record still keeps the author for abuse control.
    assert chat.messages[0].author_id == "u1"


def test_append_rejected_in_recap_phase():
    """The Chat stays read-only in the recap (phase 3): once the Round has closed,
    even a participant who voted cannot append (ValueError) — although their
    user_id is still in the closed Round's votes."""
    state = _opened("u1", "u2")
    state, _ = apply(state, CastVote("u1", "casa-popolare"))
    state, _ = apply(state, CastVote("u2", "spazio-culturale"))  # N/N → recap
    assert state.phase == "recap"
    assert "u1" in state.votes

    with pytest.raises(ValueError):
        append(empty_chat("bene-1"), state, "u1", "il round è chiuso", now=_at(9))


def test_stream_is_continuous_across_rounds():
    """The Chat spans *all* of a Bene's Rounds: a message posted in Round 1 is still
    in the stream after a new Round opens (even though the engine resets the Round's
    votes), tagged with the Round it was posted in."""
    state = _opened("u1", "u2")
    state, _ = apply(state, CastVote("u1", "casa-popolare"))
    chat, _ = append(empty_chat("bene-1"), state, "u1", "messaggio del round 1", now=_at(1))

    # Close Round 1 and reopen Round 2 through the same ready-gate.
    state, _ = apply(state, CastVote("u2", "spazio-culturale"))
    state = _drive(state, [Ready("u1"), Ready("u2"), OpenRound()])
    assert state.round_number == 2 and state.votes == {}

    msgs = read(chat)
    assert [m.body for m in msgs] == ["messaggio del round 1"]
    assert msgs[0].round_number == 1


def test_append_emits_anonymised_message_posted_effect():
    """A successful append emits a MessagePosted side-effect carrying the Bene and
    the **anonymised** message — the seam the room layer fans out so new messages
    appear live over the Bene's WS room without ever broadcasting an author."""
    state = _opened("u1", "u2")
    state, _ = apply(state, CastVote("u1", "casa-popolare"))

    _, effects = append(empty_chat("bene-1"), state, "u1", "ciao a tutti", now=_at(3))

    assert effects == [
        MessagePosted(
            poi_id="bene-1",
            message=AnonymousMessage(round_number=1, body="ciao a tutti", timestamp=_at(3)),
        )
    ]


# --- Acceptance test (outer tracer): a continuous chat across two Rounds -----


def test_chat_is_continuous_and_gated_across_rounds():
    """Two-Round deliberation: in Round 1 only a participant who has voted may
    append, a non-voter is rejected, and once the Round closes the Chat is
    read-only. Round 2 reopens (votes reset) and the Round-1 message is still
    readable — anonymised — while appending again requires re-voting in Round 2."""
    state = _opened("u1", "u2")
    chat = empty_chat("bene-1")

    # Round 1: u1 votes, then may deliberate; u2 hasn't voted → rejected.
    state, _ = apply(state, CastVote("u1", "casa-popolare"))
    chat, _ = append(chat, state, "u1", "io voto casa popolare", now=_at(1))
    with pytest.raises(ValueError):
        append(chat, state, "u2", "non ho ancora votato", now=_at(2))

    # u2 votes → N/N closes the Round (phase recap); Chat is now read-only.
    state, _ = apply(state, CastVote("u2", "spazio-culturale"))
    with pytest.raises(ValueError):
        append(chat, state, "u1", "il round è chiuso", now=_at(3))

    # Round 2 reopens through the same ready-gate; votes reset to empty.
    state = _drive(state, [Ready("u1"), Ready("u2"), OpenRound()])
    assert state.round_number == 2

    # The Round-1 message is still in the stream and never names its author.
    msgs = read(chat)
    assert msgs == (
        AnonymousMessage(round_number=1, body="io voto casa popolare", timestamp=_at(1)),
    )

    # In Round 2 you must vote again before you can deliberate again.
    with pytest.raises(ValueError):
        append(chat, state, "u1", "ho cambiato idea", now=_at(4))
    state, _ = apply(state, CastVote("u1", "spazio-culturale"))
    chat, _ = append(chat, state, "u1", "ho cambiato idea", now=_at(5))

    bodies = [m.body for m in read(chat)]
    assert bodies == ["io voto casa popolare", "ho cambiato idea"]
    assert [m.round_number for m in read(chat)] == [1, 2]
