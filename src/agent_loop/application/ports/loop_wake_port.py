"""Port for waking the agent loop."""

from typing import Protocol


# Application port
class LoopWakePort(Protocol):
    """Wakes the model-owned lifecycle when new work is available."""

    def wake(self) -> None:
        """Wake the loop without waiting for model completion."""
        ...
