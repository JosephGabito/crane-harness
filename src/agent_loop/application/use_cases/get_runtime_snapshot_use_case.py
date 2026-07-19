"""Use case for reading the complete runtime snapshot."""

from agent_loop.application.ports import RuntimeStatePort
from agent_loop.domain import RuntimeSnapshot


# Application use case
class GetRuntimeSnapshotUseCase:
    """Read the current Inbox, Thread, epoch, and loop status."""

    def __init__(self, runtime_state_port: RuntimeStatePort) -> None:
        self._runtime_state_port = runtime_state_port

    def execute(self) -> RuntimeSnapshot:
        """Return the current runtime snapshot without mutation."""
        return self._runtime_state_port.load()
