"""Port for producing an assistant message."""

from typing import Protocol

from agent_loop.domain import Message, Thread


# Application port
class ModelPort(Protocol):
    """Produces one complete assistant message from a Thread."""

    def complete(self, thread: Thread) -> Message:
        """Return the model's next complete assistant message."""
        ...
