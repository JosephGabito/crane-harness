"""Port for publishing runtime snapshots."""

from typing import Protocol

from agent_loop.domain import RuntimeSnapshot


# Application port
class RuntimeSnapshotPublisherPort(Protocol):
    """Publishes lifecycle changes to interested control surfaces."""

    def publish(self, snapshot: RuntimeSnapshot) -> None:
        """Publish the latest complete runtime snapshot."""
        ...
