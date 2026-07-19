"""Inbox domain model."""

from pydantic import BaseModel, ConfigDict

from agent_loop.domain.message import Message


# Domain model
class Inbox(BaseModel):
    """An immutable FIFO queue of user messages."""

    model_config = ConfigDict(frozen=True)

    messages: tuple[Message, ...] = ()

    def enqueue(self, message: Message) -> "Inbox":
        """Return an Inbox containing the newly queued message."""
        if message.sender != "user":
            raise ValueError("only user messages can enter the Inbox")
        return type(self)(messages=(*self.messages, message))

    def remove_prefix(self, message_count: int) -> "Inbox":
        """Return an Inbox without its consumed FIFO prefix."""
        if message_count < 1 or message_count > len(self.messages):
            raise ValueError("message_count must identify an Inbox prefix")
        return type(self)(messages=self.messages[message_count:])
