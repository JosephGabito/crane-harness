"""JSON-RPC 2.0 transport for the headless control surface."""

import json
from dataclasses import dataclass
from threading import Lock
from typing import Any, TextIO

from pydantic import ValidationError

from agent_loop.application.use_cases import (
    ClearRuntimeUseCase,
    GetRuntimeSnapshotUseCase,
    SendMessageUseCase,
)
from agent_loop.domain import Message
from agent_loop.infrastructure.adapters import SnapshotBus
from agent_loop.infrastructure.runtime import AgentLoopRuntime

# Protocol constants
JSON_RPC_VERSION = "2.0"
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


# Protocol errors
@dataclass(frozen=True)
class JsonRpcError(Exception):
    """A structured JSON-RPC error."""

    code: int
    message: str
    data: object | None = None


# Protocol server
class JsonRpcServer:
    """Serve application use cases over newline-delimited JSON-RPC."""

    def __init__(
        self,
        send_message_use_case: SendMessageUseCase,
        clear_runtime_use_case: ClearRuntimeUseCase,
        get_runtime_snapshot_use_case: GetRuntimeSnapshotUseCase,
        snapshot_bus: SnapshotBus,
        loop_runtime: AgentLoopRuntime,
    ) -> None:
        self._send_message_use_case = send_message_use_case
        self._clear_runtime_use_case = clear_runtime_use_case
        self._get_runtime_snapshot_use_case = get_runtime_snapshot_use_case
        self._snapshot_bus = snapshot_bus
        self._loop_runtime = loop_runtime

    def handle_line(self, line: str) -> str | None:
        """Handle one newline-delimited JSON-RPC request."""
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return self._error_response(None, PARSE_ERROR, "Parse error")

        if not isinstance(payload, dict):
            return self._error_response(None, INVALID_REQUEST, "Invalid Request")

        request_id = payload.get("id")
        is_notification = "id" not in payload

        try:
            self._validate_request(payload)
            result = self._dispatch(payload["method"], payload.get("params", {}))
        except JsonRpcError as error:
            if is_notification:
                return None
            return self._error_response(
                request_id,
                error.code,
                error.message,
                error.data,
            )
        except Exception:
            if is_notification:
                return None
            return self._error_response(
                request_id,
                INTERNAL_ERROR,
                "Internal error",
            )

        if is_notification:
            return None

        return json.dumps(
            {
                "jsonrpc": JSON_RPC_VERSION,
                "id": request_id,
                "result": result,
            },
            separators=(",", ":"),
        )

    def serve(self, input_stream: TextIO, output_stream: TextIO) -> None:
        """Serve requests until the input stream closes."""
        output_lock = Lock()

        def write_line(payload: str) -> None:
            with output_lock:
                output_stream.write(f"{payload}\n")
                output_stream.flush()

        unsubscribe = self._snapshot_bus.subscribe(
            lambda snapshot: write_line(
                self._snapshot_notification(
                    snapshot.model_dump(mode="json"),
                )
            )
        )
        self._loop_runtime.start()

        try:
            for line in input_stream:
                response = self.handle_line(line)
                if response is not None:
                    write_line(response)
        finally:
            unsubscribe()
            self._loop_runtime.stop()

    def _validate_request(self, payload: dict[str, Any]) -> None:
        """Validate the JSON-RPC request envelope."""
        if payload.get("jsonrpc") != JSON_RPC_VERSION:
            raise JsonRpcError(INVALID_REQUEST, "Invalid Request")

        if not isinstance(payload.get("method"), str):
            raise JsonRpcError(INVALID_REQUEST, "Invalid Request")

    def _dispatch(self, method: str, params: object) -> dict[str, object]:
        """Dispatch a request to its application use case."""
        if method == "runtime.ping":
            if not isinstance(params, dict):
                raise JsonRpcError(INVALID_PARAMS, "Invalid params")
            return {"ready": True}

        if method == "thread.clear":
            if not isinstance(params, dict):
                raise JsonRpcError(INVALID_PARAMS, "Invalid params")

            snapshot = self._clear_runtime_use_case.execute()
            return {
                "cleared": True,
                "snapshot": snapshot.model_dump(mode="json"),
            }

        if method == "runtime.get":
            if not isinstance(params, dict):
                raise JsonRpcError(INVALID_PARAMS, "Invalid params")
            snapshot = self._get_runtime_snapshot_use_case.execute()
            return {"snapshot": snapshot.model_dump(mode="json")}

        if method == "message.add":
            if not isinstance(params, dict):
                raise JsonRpcError(INVALID_PARAMS, "Invalid params")

            try:
                message = Message.model_validate(params)
            except ValidationError as error:
                raise JsonRpcError(
                    INVALID_PARAMS,
                    "Invalid params",
                    error.errors(include_url=False),
                ) from error

            snapshot = self._send_message_use_case.execute(message)
            return {
                "accepted": True,
                "snapshot": snapshot.model_dump(mode="json"),
            }

        raise JsonRpcError(METHOD_NOT_FOUND, "Method not found")

    @staticmethod
    def _error_response(
        request_id: object,
        code: int,
        message: str,
        data: object | None = None,
    ) -> str:
        """Build a JSON-RPC error response."""
        error: dict[str, object] = {
            "code": code,
            "message": message,
        }
        if data is not None:
            error["data"] = data

        return json.dumps(
            {
                "jsonrpc": JSON_RPC_VERSION,
                "id": request_id,
                "error": error,
            },
            separators=(",", ":"),
        )

    @staticmethod
    def _snapshot_notification(snapshot: dict[str, object]) -> str:
        """Build one pushed runtime snapshot notification."""
        return json.dumps(
            {
                "jsonrpc": JSON_RPC_VERSION,
                "method": "runtime.snapshot",
                "params": snapshot,
            },
            separators=(",", ":"),
        )
