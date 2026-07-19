"""Background host for the application AgentLoop."""

from collections.abc import Callable
from threading import Event, Thread
from traceback import print_exception

from agent_loop.application.agent_loop import AgentLoop
from agent_loop.application.ports import LoopWakePort

# Runtime error reporting
RuntimeErrorHandler = Callable[[Exception], None]


def _print_runtime_error(error: Exception) -> None:
    """Report an unhandled loop error without terminating its host."""
    print_exception(type(error), error, error.__traceback__)


# Infrastructure runtime
class AgentLoopRuntime(LoopWakePort):
    """Host the AgentLoop without becoming an Inbox consumer."""

    def __init__(
        self,
        agent_loop: AgentLoop,
        error_handler: RuntimeErrorHandler = _print_runtime_error,
    ) -> None:
        self._agent_loop = agent_loop
        self._error_handler = error_handler
        self._wake_event = Event()
        self._stop_event = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        """Start the background lifecycle and recover pending work."""
        if self._thread is not None:
            return

        self._thread = Thread(
            target=self._run,
            name="agent-loop",
            daemon=True,
        )
        self._thread.start()
        self.wake()

    def wake(self) -> None:
        """Wake the AgentLoop without waiting for it."""
        self._wake_event.set()

    def stop(self) -> None:
        """Stop the background lifecycle after its current model call."""
        self._stop_event.set()
        self._wake_event.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=1)
        self._thread = None

    def _run(self) -> None:
        """Advance until idle whenever the lifecycle is awakened."""
        while not self._stop_event.is_set():
            self._wake_event.wait()
            self._wake_event.clear()

            try:
                while not self._stop_event.is_set() and self._agent_loop.advance():
                    continue
            except Exception as error:
                self._report_error(error)

    def _report_error(self, error: Exception) -> None:
        """Keep reporting failures from becoming lifecycle failures."""
        try:
            self._error_handler(error)
        except Exception as handler_error:
            _print_runtime_error(error)
            _print_runtime_error(handler_error)
