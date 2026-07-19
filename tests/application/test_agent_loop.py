"""Tests for the provider-neutral AgentLoop."""

from pathlib import Path
from threading import Event
from threading import Thread as WorkerThread

from agent_loop.application.agent_loop import AgentLoop, join_inbox_messages
from agent_loop.domain import Message, RuntimeSnapshot, Thread
from agent_loop.infrastructure.adapters import (
    FilesystemRuntimeJournalAdapter,
    SnapshotBus,
)


# Test model
class BlockingModel:
    """Block completion so tests can queue checkpoint steering."""

    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()
        self.inputs: list[Thread] = []

    def complete(self, thread: Thread) -> Message:
        """Record the Thread and wait for the test checkpoint."""
        self.inputs.append(thread)
        self.started.set()
        if not self.release.wait(timeout=2):
            raise TimeoutError("test model was not released")
        self.release.clear()
        self.started.clear()
        return Message(sender="assistant", message="Done.")


# Coherent projection
def test_join_inbox_messages_preserves_order_and_attachments() -> None:
    combined = join_inbox_messages(
        (
            Message(
                sender="user",
                message="  Check tests  ",
                attachments=("first.txt",),
            ),
            Message(
                sender="user",
                message="Do not touch UI",
                attachments=("second.txt", "first.txt"),
            ),
        )
    )

    assert combined == Message(
        sender="user",
        message="Check tests. Do not touch UI",
        attachments=("first.txt", "second.txt", "first.txt"),
    )


# Checkpoint lifecycle
def test_loop_joins_messages_queued_during_an_active_turn(
    tmp_path: Path,
) -> None:
    state = FilesystemRuntimeJournalAdapter(tmp_path / "runtime.jsonl")
    snapshots: list[RuntimeSnapshot] = []
    bus = SnapshotBus()
    bus.subscribe(snapshots.append)
    model = BlockingModel()
    loop = AgentLoop(state, model, bus)

    state.enqueue(Message(sender="user", message="Initial"))
    assert loop.advance() is True
    worker = WorkerThread(target=loop.advance)
    worker.start()
    assert model.started.wait(timeout=1)

    state.enqueue(Message(sender="user", message="Message A"))
    state.enqueue(Message(sender="user", message="Message B"))
    state.enqueue(Message(sender="user", message="Message C"))
    model.release.set()
    worker.join(timeout=2)

    assert loop.advance() is True
    assert state.load().thread.messages[-1] == Message(
        sender="user",
        message="Message A. Message B. Message C",
    )
    assert state.load().inbox.messages == ()


def test_loop_discards_a_completion_from_a_cleared_epoch(
    tmp_path: Path,
) -> None:
    state = FilesystemRuntimeJournalAdapter(tmp_path / "runtime.jsonl")
    bus = SnapshotBus()
    model = BlockingModel()
    loop = AgentLoop(state, model, bus)

    state.enqueue(Message(sender="user", message="Old work"))
    assert loop.advance() is True
    worker = WorkerThread(target=loop.advance)
    worker.start()
    assert model.started.wait(timeout=1)

    cleared = state.clear()
    model.release.set()
    worker.join(timeout=2)

    assert cleared.epoch == 1
    assert state.load() == RuntimeSnapshot(epoch=1)
