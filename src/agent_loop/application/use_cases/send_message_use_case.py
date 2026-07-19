"""Use case for queueing a user message."""

from agent_loop.application.ports import (
    LoopWakePort,
    RuntimeSnapshotPublisherPort,
    RuntimeStatePort,
)
from agent_loop.domain import Message, RuntimeSnapshot


# Application use case
class SendMessageUseCase:
    """Durably queue a user message and wake the AgentLoop."""

    def __init__(
        self,
        runtime_state_port: RuntimeStatePort,
        loop_wake_port: LoopWakePort,
        snapshot_publisher_port: RuntimeSnapshotPublisherPort,
    ) -> None:
        self._runtime_state_port = runtime_state_port
        self._loop_wake_port = loop_wake_port
        self._snapshot_publisher_port = snapshot_publisher_port

    def execute(self, message: Message) -> RuntimeSnapshot:
        """Queue the message without waiting for model completion."""
        snapshot = self._runtime_state_port.enqueue(message)
        self._snapshot_publisher_port.publish(snapshot)
        self._loop_wake_port.wake()
        return snapshot
