"""Tests for the thread domain model."""

import pytest
from pydantic import ValidationError

from agent_loop.domain import Message, Thread


# Test messages
def user_message() -> Message:
    """Build a valid user message."""
    return Message(sender="user", message="Build the loop.")


def assistant_message() -> Message:
    """Build a valid assistant message."""
    return Message(sender="assistant", message="Loop ready.")


# Construction
def test_thread_contains_ordered_messages() -> None:
    thread = Thread(messages=(user_message(), assistant_message()))

    assert thread.messages == (user_message(), assistant_message())


def test_thread_allows_an_active_user_turn() -> None:
    thread = Thread(messages=(user_message(),))

    assert thread.messages == (user_message(),)


def test_thread_requires_alternating_senders() -> None:
    with pytest.raises(
        ValidationError,
        match="messages must alternate",
    ):
        Thread(
            messages=(
                user_message(),
                Message(sender="user", message="Wrong role."),
            ),
        )


# Evolution
def test_thread_appends_messages_immutably() -> None:
    thread = Thread(messages=(user_message(), assistant_message()))
    additional_messages = (
        Message(sender="user", message="Again."),
        Message(sender="assistant", message="Again ready."),
    )

    updated_thread = thread.append(additional_messages)

    assert thread.messages == (user_message(), assistant_message())
    assert updated_thread.messages == thread.messages + additional_messages


# Immutability
def test_thread_cannot_be_changed() -> None:
    thread = Thread(messages=(user_message(), assistant_message()))

    with pytest.raises(ValidationError, match="Instance is frozen"):
        thread.messages = ()
