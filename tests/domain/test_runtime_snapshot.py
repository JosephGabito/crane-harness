"""Tests for the runtime snapshot domain model."""

from agent_loop.domain import Inbox, RuntimeSnapshot, Thread


# Construction
def test_runtime_snapshot_defaults_to_an_empty_idle_lifecycle() -> None:
    snapshot = RuntimeSnapshot()

    assert snapshot == RuntimeSnapshot(
        epoch=0,
        status="idle",
        inbox=Inbox(),
        thread=Thread(),
    )
