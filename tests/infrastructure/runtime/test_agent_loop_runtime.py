"""Tests for the background AgentLoop host."""

from pathlib import Path
from threading import Event

from agent_loop.application.agent_loop import AgentLoop
from agent_loop.domain import Message, RuntimeSnapshot, Thread
from agent_loop.infrastructure.adapters import (
    FilesystemRuntimeJournalAdapter,
    SnapshotBus,
)
from agent_loop.infrastructure.runtime import AgentLoopRuntime


# Test model
class DeterministicModel:
    """Complete a recovered user turn without external effects."""

    def complete(self, thread: Thread) -> Message:
        """Return one deterministic assistant message."""
        return Message(sender="assistant", message="Recovered.")


# Recoverable model failure
class FailOnceModel:
    """Raise once so the runtime retry boundary can be exercised."""

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, thread: Thread) -> Message:
        """Fail the first attempt and complete the next one."""
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary model failure")
        return Message(sender="assistant", message="Retried.")


# Recovery lifecycle
def test_runtime_resumes_a_pre_effect_turn_on_start(tmp_path: Path) -> None:
    state = FilesystemRuntimeJournalAdapter(tmp_path / "runtime.jsonl")
    state.enqueue(Message(sender="user", message="Resume"))
    state.start_turn(
        epoch=0,
        message_count=1,
        user_message=Message(sender="user", message="Resume"),
    )
    completed = Event()
    snapshots: list[RuntimeSnapshot] = []
    bus = SnapshotBus()

    def record(snapshot: RuntimeSnapshot) -> None:
        snapshots.append(snapshot)
        if snapshot.status == "idle" and snapshot.thread.messages:
            completed.set()

    bus.subscribe(record)
    runtime = AgentLoopRuntime(
        AgentLoop(state, DeterministicModel(), bus),
    )

    runtime.start()
    assert completed.wait(timeout=1)
    runtime.stop()

    assert snapshots[-1].thread.messages[-1].message == "Recovered."


def test_runtime_survives_a_model_failure_until_the_next_wake(
    tmp_path: Path,
) -> None:
    state = FilesystemRuntimeJournalAdapter(tmp_path / "runtime.jsonl")
    state.enqueue(Message(sender="user", message="Retry me"))
    state.start_turn(
        epoch=0,
        message_count=1,
        user_message=Message(sender="user", message="Retry me"),
    )
    failed = Event()
    completed = Event()
    errors: list[Exception] = []
    bus = SnapshotBus()

    def record_error(error: Exception) -> None:
        errors.append(error)
        failed.set()

    def record_snapshot(snapshot: RuntimeSnapshot) -> None:
        if snapshot.status == "idle":
            completed.set()

    bus.subscribe(record_snapshot)
    model = FailOnceModel()
    runtime = AgentLoopRuntime(
        AgentLoop(state, model, bus),
        error_handler=record_error,
    )

    runtime.start()
    assert failed.wait(timeout=1)
    assert state.load().status == "running"

    runtime.wake()
    assert completed.wait(timeout=1)
    runtime.stop()

    assert model.calls == 2
    assert len(errors) == 1
    assert state.load().thread.messages[-1].message == "Retried."
