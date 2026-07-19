"""Port for durable runtime state transitions."""

from typing import Protocol

from agent_loop.domain import Message, RuntimeSnapshot


# Application port
class RuntimeStatePort(Protocol):
    """Persists Inbox and Thread transitions as one lifecycle."""

    def load(self) -> RuntimeSnapshot:
        """Load the complete current runtime state."""
        ...

    def enqueue(self, message: Message) -> RuntimeSnapshot:
        """Durably append one user message to the Inbox."""
        ...

    def start_turn(
        self,
        *,
        epoch: int,
        message_count: int,
        user_message: Message,
    ) -> RuntimeSnapshot | None:
        """Consume an Inbox prefix and start one coherent user turn."""
        ...

    def complete_turn(
        self,
        *,
        epoch: int,
        assistant_message: Message,
    ) -> RuntimeSnapshot | None:
        """Complete the active turn unless its epoch became stale."""
        ...

    def clear(self) -> RuntimeSnapshot:
        """Clear Inbox and Thread while advancing the runtime epoch."""
        ...
