"""Thread-safe runtime snapshot broadcaster."""

from collections.abc import Callable
from threading import Lock

from agent_loop.application.ports import RuntimeSnapshotPublisherPort
from agent_loop.domain import RuntimeSnapshot

SnapshotSubscriber = Callable[[RuntimeSnapshot], None]


# Infrastructure adapter
class SnapshotBus(RuntimeSnapshotPublisherPort):
    """Publish snapshots to control-surface subscribers."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._subscribers: list[SnapshotSubscriber] = []

    def publish(self, snapshot: RuntimeSnapshot) -> None:
        """Publish a snapshot to the current subscriber set."""
        with self._lock:
            subscribers = tuple(self._subscribers)

        for subscriber in subscribers:
            try:
                subscriber(snapshot)
            except Exception:
                continue

    def subscribe(self, subscriber: SnapshotSubscriber) -> Callable[[], None]:
        """Register a subscriber and return its unsubscribe callback."""
        with self._lock:
            self._subscribers.append(subscriber)

        def unsubscribe() -> None:
            with self._lock:
                if subscriber in self._subscribers:
                    self._subscribers.remove(subscriber)

        return unsubscribe
