"""Tests for the message domain model."""

import pytest
from pydantic import ValidationError

from agent_loop.domain import Message


# Construction
def test_message_contains_sender_message_and_attachments() -> None:
    message = Message.model_validate(
        {
            "sender": "user",
            "message": "Build an agent loop.",
            "attachments": ["requirements.md"],
        }
    )

    assert message == Message(
        sender="user",
        message="Build an agent loop.",
        attachments=("requirements.md",),
    )


def test_message_defaults_to_no_attachments() -> None:
    message = Message(sender="user", message="Hello.")

    assert message.attachments == ()


def test_message_rejects_empty_content() -> None:
    with pytest.raises(ValidationError, match="message must not be empty"):
        Message(sender="user", message="  ")


# Immutability
def test_message_cannot_be_changed() -> None:
    message = Message(sender="user", message="Hello.")

    with pytest.raises(ValidationError, match="Instance is frozen"):
        message.message = "Changed."
