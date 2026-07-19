"""Provider-neutral agent-loop lifecycle."""

from agent_loop.application.ports import (
    ModelPort,
    RuntimeSnapshotPublisherPort,
    RuntimeStatePort,
)
from agent_loop.domain import Message


# Coherent Inbox projection
def join_inbox_messages(messages: tuple[Message, ...]) -> Message:
    """Join one FIFO Inbox snapshot into a coherent user message."""
    if not messages:
        raise ValueError("at least one Inbox message is required")

    return Message(
        sender="user",
        message=". ".join(message.message.strip() for message in messages),
        attachments=tuple(
            attachment for message in messages for attachment in message.attachments
        ),
    )


# Application lifecycle
class AgentLoop:
    """Advance the model-owned lifecycle by one durable transition."""

    def __init__(
        self,
        runtime_state_port: RuntimeStatePort,
        model_port: ModelPort,
        snapshot_publisher_port: RuntimeSnapshotPublisherPort,
    ) -> None:
        self._runtime_state_port = runtime_state_port
        self._model_port = model_port
        self._snapshot_publisher_port = snapshot_publisher_port

    def advance(self) -> bool:
        """Advance once and report whether another transition is available."""
        snapshot = self._runtime_state_port.load()

        if snapshot.status == "running":
            assistant_message = self._model_port.complete(snapshot.thread)
            if assistant_message.sender != "assistant":
                raise ValueError("the model must return an assistant message")

            completed = self._runtime_state_port.complete_turn(
                epoch=snapshot.epoch,
                assistant_message=assistant_message,
            )
            if completed is not None:
                self._snapshot_publisher_port.publish(completed)
                return bool(completed.inbox.messages)

            current = self._runtime_state_port.load()
            return current.status == "running" or bool(current.inbox.messages)

        if not snapshot.inbox.messages:
            return False

        inbox_messages = snapshot.inbox.messages
        started = self._runtime_state_port.start_turn(
            epoch=snapshot.epoch,
            message_count=len(inbox_messages),
            user_message=join_inbox_messages(inbox_messages),
        )
        if started is None:
            return True

        self._snapshot_publisher_port.publish(started)
        return True
