"""Tests for queue, read, and clear runtime use cases."""

from pathlib import Path

from agent_loop.application.use_cases import (
    ClearRuntimeUseCase,
    GetRuntimeSnapshotUseCase,
    SendMessageUseCase,
)
from agent_loop.domain import Message, RuntimeSnapshot
from agent_loop.infrastructure.adapters import (
    FilesystemRuntimeJournalAdapter,
    SnapshotBus,
)


# Test loop control
class RecordingLoopWakePort:
    """Record wake requests without starting a background loop."""

    def __init__(self) -> None:
        self.wake_count = 0

    def wake(self) -> None:
        """Record one wake request."""
        self.wake_count += 1


# Use-case behavior
def test_send_message_only_queues_and_wakes_the_loop(tmp_path: Path) -> None:
    state = FilesystemRuntimeJournalAdapter(tmp_path / "runtime.jsonl")
    wake = RecordingLoopWakePort()
    snapshots: list[RuntimeSnapshot] = []
    bus = SnapshotBus()
    bus.subscribe(snapshots.append)
    use_case = SendMessageUseCase(state, wake, bus)
    message = Message(sender="user", message="Queued")

    snapshot = use_case.execute(message)

    assert snapshot.inbox.messages == (message,)
    assert snapshot.thread.messages == ()
    assert wake.wake_count == 1
    assert snapshots == [snapshot]


def test_clear_runtime_resets_inbox_thread_and_epoch(tmp_path: Path) -> None:
    state = FilesystemRuntimeJournalAdapter(tmp_path / "runtime.jsonl")
    wake = RecordingLoopWakePort()
    bus = SnapshotBus()
    state.enqueue(Message(sender="user", message="Queued"))
    use_case = ClearRuntimeUseCase(state, wake, bus)

    snapshot = use_case.execute()

    assert snapshot == RuntimeSnapshot(epoch=1)
    assert GetRuntimeSnapshotUseCase(state).execute() == snapshot
    assert wake.wake_count == 1
