"""Tests for the filesystem runtime journal."""

import json
from pathlib import Path

import pytest

from agent_loop.domain import Message, RuntimeSnapshot
from agent_loop.infrastructure.adapters import (
    FilesystemRuntimeJournalAdapter,
)


# Durable lifecycle
def test_journal_replays_queue_turn_and_completion(tmp_path: Path) -> None:
    path = tmp_path / "runtime.jsonl"
    adapter = FilesystemRuntimeJournalAdapter(path)
    first = Message(sender="user", message="First")
    second = Message(sender="user", message="Second")
    adapter.enqueue(first)
    adapter.enqueue(second)
    started = adapter.start_turn(
        epoch=0,
        message_count=2,
        user_message=Message(sender="user", message="First. Second"),
    )

    assert started is not None
    adapter.complete_turn(
        epoch=0,
        assistant_message=Message(sender="assistant", message="Done"),
    )

    replayed = FilesystemRuntimeJournalAdapter(path).load()
    assert replayed.status == "idle"
    assert replayed.inbox.messages == ()
    assert [message.message for message in replayed.thread.messages] == [
        "First. Second",
        "Done",
    ]


def test_journal_preserves_a_running_turn_for_recovery(
    tmp_path: Path,
) -> None:
    path = tmp_path / "runtime.jsonl"
    adapter = FilesystemRuntimeJournalAdapter(path)
    adapter.enqueue(Message(sender="user", message="Resume me"))
    adapter.start_turn(
        epoch=0,
        message_count=1,
        user_message=Message(sender="user", message="Resume me"),
    )

    recovered = FilesystemRuntimeJournalAdapter(path).load()

    assert recovered.status == "running"
    assert recovered.thread.messages[-1].message == "Resume me"


def test_clear_replaces_history_and_fences_stale_completion(
    tmp_path: Path,
) -> None:
    path = tmp_path / "runtime.jsonl"
    adapter = FilesystemRuntimeJournalAdapter(path)
    adapter.enqueue(Message(sender="user", message="Old"))
    adapter.start_turn(
        epoch=0,
        message_count=1,
        user_message=Message(sender="user", message="Old"),
    )

    cleared = adapter.clear()
    stale = adapter.complete_turn(
        epoch=0,
        assistant_message=Message(sender="assistant", message="Too late"),
    )

    assert cleared == RuntimeSnapshot(epoch=1)
    assert stale is None
    assert adapter.load() == cleared
    assert "Old" not in path.read_text(encoding="utf-8")


def test_journal_reads_legacy_completed_thread_records(
    tmp_path: Path,
) -> None:
    path = tmp_path / "runtime.jsonl"
    path.write_text(
        json.dumps(
            {
                "user_message": {
                    "sender": "user",
                    "message": "Legacy user",
                    "attachments": [],
                },
                "assistant_message": {
                    "sender": "assistant",
                    "message": "Legacy assistant",
                    "attachments": [],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    snapshot = FilesystemRuntimeJournalAdapter(path).load()

    assert [message.message for message in snapshot.thread.messages] == [
        "Legacy user",
        "Legacy assistant",
    ]


def test_journal_fails_closed_on_a_corrupt_record(tmp_path: Path) -> None:
    path = tmp_path / "runtime.jsonl"
    path.write_text("{\n", encoding="utf-8")

    with pytest.raises(ValueError, match="line 1"):
        FilesystemRuntimeJournalAdapter(path).load()


# Interrupted writes
def test_journal_ignores_an_uncommitted_final_record(
    tmp_path: Path,
) -> None:
    path = tmp_path / "runtime.jsonl"
    adapter = FilesystemRuntimeJournalAdapter(path)
    adapter.enqueue(Message(sender="user", message="Committed"))
    with path.open("ab") as journal:
        journal.write(b'{"type":"message_queued"')

    replayed = FilesystemRuntimeJournalAdapter(path).load()

    assert [message.message for message in replayed.inbox.messages] == ["Committed"]
    assert path.read_bytes().endswith(b'{"type":"message_queued"')


def test_journal_discards_an_uncommitted_tail_before_append(
    tmp_path: Path,
) -> None:
    path = tmp_path / "runtime.jsonl"
    adapter = FilesystemRuntimeJournalAdapter(path)
    adapter.enqueue(Message(sender="user", message="First"))
    with path.open("ab") as journal:
        journal.write(b"\xf0\x9f")

    recovered = FilesystemRuntimeJournalAdapter(path)
    recovered.enqueue(Message(sender="user", message="Second"))

    snapshot = recovered.load()
    assert [message.message for message in snapshot.inbox.messages] == [
        "First",
        "Second",
    ]
    assert path.read_bytes().endswith(b"\n")
    for line in path.read_bytes().splitlines():
        json.loads(line)
