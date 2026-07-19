"""Tests for the temporary fake model."""

from agent_loop.domain import Message, Thread
from agent_loop.infrastructure.adapters.fake_model_adapter import (
    ASSISTANT_REPLIES,
    FAKE_MODEL_DELAY_SECONDS,
    FakeModelAdapter,
)


# Fake model behavior
def test_fake_model_waits_five_seconds_before_replying() -> None:
    delays: list[float] = []
    model = FakeModelAdapter(sleep_function=delays.append)

    reply = model.complete(Thread(messages=(Message(sender="user", message="Wait."),)))

    assert delays == [FAKE_MODEL_DELAY_SECONDS]
    assert FAKE_MODEL_DELAY_SECONDS == 5.0
    assert reply.sender == "assistant"
    assert reply.message in ASSISTANT_REPLIES
