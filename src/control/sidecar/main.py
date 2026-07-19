"""Composition root for the headless sidecar."""

import os
import sys
from pathlib import Path

from agent_loop.application.agent_loop import AgentLoop
from agent_loop.application.ports import RuntimeStatePort
from agent_loop.application.use_cases import (
    ClearRuntimeUseCase,
    GetRuntimeSnapshotUseCase,
    SendMessageUseCase,
)
from agent_loop.infrastructure.adapters import (
    FakeModelAdapter,
    FilesystemRuntimeJournalAdapter,
    SnapshotBus,
)
from agent_loop.infrastructure.runtime import AgentLoopRuntime
from control.sidecar.json_rpc import JsonRpcServer

# Runtime configuration
THREAD_PATH_ENVIRONMENT_VARIABLE = "AGENT_LOOP_THREAD_PATH"
DEFAULT_THREAD_PATH = Path("data") / "thread.jsonl"


# Composition root
def build_server(thread_path: str | Path | None = None) -> JsonRpcServer:
    """Build the sidecar with its production dependencies."""
    configured_path: str | Path
    if thread_path is None:
        configured_path = os.environ.get(
            THREAD_PATH_ENVIRONMENT_VARIABLE,
            str(DEFAULT_THREAD_PATH),
        )
    else:
        configured_path = thread_path

    runtime_state_port: RuntimeStatePort = FilesystemRuntimeJournalAdapter(
        configured_path
    )
    runtime_state_port.load()
    snapshot_bus = SnapshotBus()
    agent_loop = AgentLoop(
        runtime_state_port=runtime_state_port,
        model_port=FakeModelAdapter(),
        snapshot_publisher_port=snapshot_bus,
    )
    loop_runtime = AgentLoopRuntime(agent_loop)

    return JsonRpcServer(
        send_message_use_case=SendMessageUseCase(
            runtime_state_port=runtime_state_port,
            loop_wake_port=loop_runtime,
            snapshot_publisher_port=snapshot_bus,
        ),
        clear_runtime_use_case=ClearRuntimeUseCase(
            runtime_state_port=runtime_state_port,
            loop_wake_port=loop_runtime,
            snapshot_publisher_port=snapshot_bus,
        ),
        get_runtime_snapshot_use_case=GetRuntimeSnapshotUseCase(
            runtime_state_port=runtime_state_port,
        ),
        snapshot_bus=snapshot_bus,
        loop_runtime=loop_runtime,
    )


def main() -> None:
    """Serve JSON-RPC requests over standard input and output."""
    build_server().serve(sys.stdin, sys.stdout)


if __name__ == "__main__":
    main()
