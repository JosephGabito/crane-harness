"""Tests for the inbox domain model."""

import pytest
from pydantic import ValidationError

from agent_loop.domain import Inbox, Message


# Construction
def test_inbox_preserves_message_order_and_duplicates() -> None:
    first = Message(sender="user", message="Hello.")
    second = Message(sender="user", message="Hello.")

    inbox = Inbox(messages=(first, second))

    assert inbox.messages == (first, second)


def test_inbox_defaults_to_no_messages() -> None:
    inbox = Inbox()

    assert inbox.messages == ()


def test_inbox_enqueues_and_removes_a_fifo_prefix_immutably() -> None:
    first = Message(sender="user", message="First.")
    second = Message(sender="user", message="Second.")

    inbox = Inbox().enqueue(first).enqueue(second)
    remaining = inbox.remove_prefix(1)

    assert inbox.messages == (first, second)
    assert remaining.messages == (second,)


def test_inbox_rejects_assistant_messages() -> None:
    with pytest.raises(ValueError, match="only user messages"):
        Inbox().enqueue(Message(sender="assistant", message="No."))


# Immutability
def test_inbox_cannot_be_changed() -> None:
    inbox = Inbox()

    with pytest.raises(ValidationError, match="Instance is frozen"):
        inbox.messages = (Message(sender="user", message="Changed."),)
