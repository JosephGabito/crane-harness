"""Runtime snapshot domain model."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from agent_loop.domain.inbox import Inbox
from agent_loop.domain.thread import Thread


# Domain model
class RuntimeSnapshot(BaseModel):
    """An immutable projection of the complete agent-loop lifecycle."""

    model_config = ConfigDict(frozen=True)

    epoch: int = 0
    revision: int = 0
    status: Literal["idle", "running"] = "idle"
    inbox: Inbox = Inbox()
    thread: Thread = Thread()
