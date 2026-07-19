"""Message domain model."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


# Domain model
class Message(BaseModel):
    """An immutable message exchanged with the agent."""

    model_config = ConfigDict(frozen=True)

    sender: Literal["user", "assistant"]
    message: str
    attachments: tuple[str, ...] = ()

    @field_validator("message")
    @classmethod
    def validate_message(cls, message: str) -> str:
        """Reject messages that contain no visible content."""
        if not message.strip():
            raise ValueError("message must not be empty")
        return message
