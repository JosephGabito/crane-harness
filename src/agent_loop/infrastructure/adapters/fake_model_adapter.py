"""Temporary model adapter for exercising the complete AgentLoop."""

from collections.abc import Callable
from secrets import choice
from time import sleep

from agent_loop.application.ports import ModelPort
from agent_loop.domain import Message, Thread

# Temporary model behavior
FAKE_MODEL_DELAY_SECONDS = 5.0
ASSISTANT_REPLIES = (
    "Interesting. Tell me more.",
    "Got it. What should we do next?",
    "I am only pretending to be intelligent, but I received your message.",
    "The loop is alive.",
)


# Infrastructure adapter
class FakeModelAdapter(ModelPort):
    """Return a random assistant message without an AI provider."""

    def __init__(
        self,
        delay_seconds: float = FAKE_MODEL_DELAY_SECONDS,
        sleep_function: Callable[[float], None] = sleep,
    ) -> None:
        self._delay_seconds = delay_seconds
        self._sleep_function = sleep_function

    def complete(self, thread: Thread) -> Message:
        """Complete the active user turn."""
        if not thread.messages or thread.messages[-1].sender != "user":
            raise ValueError("the fake model requires an active user turn")
        self._sleep_function(self._delay_seconds)
        return Message(sender="assistant", message=choice(ASSISTANT_REPLIES))
