"""Use case for clearing the complete runtime."""

from agent_loop.application.ports import (
    LoopWakePort,
    RuntimeSnapshotPublisherPort,
    RuntimeStatePort,
)
from agent_loop.domain import RuntimeSnapshot


# Application use case
class ClearRuntimeUseCase:
    """Clear Inbox and Thread while fencing active work."""

    def __init__(
        self,
        runtime_state_port: RuntimeStatePort,
        loop_wake_port: LoopWakePort,
        snapshot_publisher_port: RuntimeSnapshotPublisherPort,
    ) -> None:
        self._runtime_state_port = runtime_state_port
        self._loop_wake_port = loop_wake_port
        self._snapshot_publisher_port = snapshot_publisher_port

    def execute(self) -> RuntimeSnapshot:
        """Clear the runtime, publish its state, and wake the loop."""
        snapshot = self._runtime_state_port.clear()
        self._snapshot_publisher_port.publish(snapshot)
        self._loop_wake_port.wake()
        return snapshot
