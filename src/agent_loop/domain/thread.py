"""Thread domain model."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from agent_loop.domain.message import Message


# Domain model
class Thread(BaseModel):
    """An immutable ordered conversation history."""

    model_config = ConfigDict(frozen=True)

    messages: tuple[Message, ...] = ()

    @model_validator(mode="after")
    def validate_message_order(self) -> Self:
        """Require alternating messages while allowing an active user turn."""
        for index, message in enumerate(self.messages):
            expected_sender = "user" if index % 2 == 0 else "assistant"
            if message.sender != expected_sender:
                raise ValueError("messages must alternate between user and assistant")

        return self

    def append(self, messages: tuple[Message, ...]) -> Self:
        """Return a new thread containing the additional messages."""
        return type(self)(messages=self.messages + messages)
