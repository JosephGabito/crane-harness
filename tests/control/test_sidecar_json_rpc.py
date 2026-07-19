"""Tests for the headless JSON-RPC control surface."""

import json
from io import StringIO
from pathlib import Path

from control.sidecar.main import build_server


# Test request
def request(
    *,
    request_id: object,
    method: str,
    params: object,
) -> str:
    """Build one JSON-RPC request."""
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
    )


# Message requests
def test_message_add_returns_an_accepted_inbox_snapshot(
    tmp_path: Path,
) -> None:
    response = build_server(tmp_path / "runtime.jsonl").handle_line(
        request(
            request_id="request-1",
            method="message.add",
            params={
                "sender": "user",
                "message": "Hello, agent.",
                "attachments": [],
            },
        )
    )

    assert response is not None
    assert json.loads(response) == {
        "jsonrpc": "2.0",
        "id": "request-1",
        "result": {
            "accepted": True,
            "snapshot": {
                "epoch": 0,
                "revision": 1,
                "status": "idle",
                "inbox": {
                    "messages": [
                        {
                            "sender": "user",
                            "message": "Hello, agent.",
                            "attachments": [],
                        }
                    ]
                },
                "thread": {"messages": []},
            },
        },
    }


# Runtime requests
def test_runtime_get_returns_the_complete_snapshot(tmp_path: Path) -> None:
    server = build_server(tmp_path / "runtime.jsonl")
    server.handle_line(
        request(
            request_id="add",
            method="message.add",
            params={
                "sender": "user",
                "message": "Queued",
                "attachments": [],
            },
        )
    )

    response = server.handle_line(
        request(request_id="get", method="runtime.get", params={})
    )

    assert response is not None
    result = json.loads(response)["result"]["snapshot"]
    assert result["inbox"]["messages"][0]["message"] == "Queued"
    assert result["thread"]["messages"] == []


def test_thread_clear_resets_inbox_thread_and_epoch(
    tmp_path: Path,
) -> None:
    server = build_server(tmp_path / "runtime.jsonl")
    server.handle_line(
        request(
            request_id="add",
            method="message.add",
            params={
                "sender": "user",
                "message": "Queued",
                "attachments": [],
            },
        )
    )

    response = server.handle_line(
        request(request_id="clear", method="thread.clear", params={})
    )

    assert response is not None
    assert json.loads(response)["result"] == {
        "cleared": True,
        "snapshot": {
            "epoch": 1,
            "revision": 0,
            "status": "idle",
            "inbox": {"messages": []},
            "thread": {"messages": []},
        },
    }


def test_runtime_ping_reports_readiness(tmp_path: Path) -> None:
    response = build_server(tmp_path / "runtime.jsonl").handle_line(
        request(request_id="runtime-1", method="runtime.ping", params={})
    )

    assert response is not None
    assert json.loads(response) == {
        "jsonrpc": "2.0",
        "id": "runtime-1",
        "result": {"ready": True},
    }


# Protocol errors
def test_invalid_json_returns_a_parse_error(tmp_path: Path) -> None:
    response = build_server(tmp_path / "runtime.jsonl").handle_line("{")

    assert response is not None
    assert json.loads(response)["error"] == {
        "code": -32700,
        "message": "Parse error",
    }


def test_unknown_method_returns_method_not_found(tmp_path: Path) -> None:
    response = build_server(tmp_path / "runtime.jsonl").handle_line(
        request(request_id="request-2", method="unknown", params={})
    )

    assert response is not None
    assert json.loads(response)["error"] == {
        "code": -32601,
        "message": "Method not found",
    }


def test_invalid_message_returns_invalid_params(tmp_path: Path) -> None:
    response = build_server(tmp_path / "runtime.jsonl").handle_line(
        request(
            request_id="request-3",
            method="message.add",
            params={"sender": "user"},
        )
    )

    assert response is not None
    assert json.loads(response)["error"]["code"] == -32602


# Push lifecycle
def test_server_pushes_runtime_snapshot_notifications(
    tmp_path: Path,
) -> None:
    input_stream = StringIO(
        request(
            request_id=1,
            method="message.add",
            params={
                "sender": "user",
                "message": "Hello",
                "attachments": [],
            },
        )
        + "\n"
    )
    output_stream = StringIO()

    build_server(tmp_path / "runtime.jsonl").serve(
        input_stream,
        output_stream,
    )

    payloads = [json.loads(line) for line in output_stream.getvalue().splitlines()]
    notifications = [
        payload for payload in payloads if payload.get("method") == "runtime.snapshot"
    ]
    responses = [payload for payload in payloads if payload.get("id") == 1]

    assert notifications
    assert notifications[0]["params"]["inbox"]["messages"][0]["message"] == ("Hello")
    assert responses[0]["result"]["accepted"] is True
