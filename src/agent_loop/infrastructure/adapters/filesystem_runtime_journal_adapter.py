"""Filesystem journal for the complete agent-loop runtime."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from typing import Any

from pydantic import ValidationError

from agent_loop.application.ports import RuntimeStatePort
from agent_loop.domain import Message, RuntimeSnapshot, Thread

# Journal event names
MESSAGE_QUEUED = "message_queued"
TURN_STARTED = "turn_started"
ASSISTANT_COMPLETED = "assistant_completed"
RUNTIME_RESET = "runtime_reset"


# Journal replay result
@dataclass(frozen=True)
class _JournalReplay:
    """Hold committed state and the start of an interrupted final write."""

    snapshot: RuntimeSnapshot
    uncommitted_tail_offset: int | None = None


# Infrastructure adapter
class FilesystemRuntimeJournalAdapter(RuntimeStatePort):
    """Persist Inbox and Thread transitions in one append-only journal."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = Lock()

    def load(self) -> RuntimeSnapshot:
        """Replay the complete runtime without mutating its journal."""
        with self._lock:
            return self._load()

    def enqueue(self, message: Message) -> RuntimeSnapshot:
        """Durably append a user message to the Inbox."""
        if message.sender != "user":
            raise ValueError("only user messages can enter the Inbox")

        with self._lock:
            snapshot = self._load_for_update()
            self._append_event(
                {
                    "type": MESSAGE_QUEUED,
                    "epoch": snapshot.epoch,
                    "message": message.model_dump(mode="json"),
                }
            )
            return snapshot.model_copy(
                update={
                    "revision": snapshot.revision + 1,
                    "inbox": snapshot.inbox.enqueue(message),
                }
            )

    def start_turn(
        self,
        *,
        epoch: int,
        message_count: int,
        user_message: Message,
    ) -> RuntimeSnapshot | None:
        """Atomically consume an Inbox prefix and append one user turn."""
        if user_message.sender != "user":
            raise ValueError("a turn must start with a user message")

        with self._lock:
            snapshot = self._load_for_update()
            if snapshot.epoch != epoch:
                return None
            if snapshot.status != "idle":
                raise ValueError("the runtime already has an active turn")

            inbox = snapshot.inbox.remove_prefix(message_count)
            thread = snapshot.thread.append((user_message,))
            self._append_event(
                {
                    "type": TURN_STARTED,
                    "epoch": epoch,
                    "message_count": message_count,
                    "message": user_message.model_dump(mode="json"),
                }
            )
            return RuntimeSnapshot(
                epoch=epoch,
                revision=snapshot.revision + 1,
                status="running",
                inbox=inbox,
                thread=thread,
            )

    def complete_turn(
        self,
        *,
        epoch: int,
        assistant_message: Message,
    ) -> RuntimeSnapshot | None:
        """Complete the current epoch and reject stale model output."""
        if assistant_message.sender != "assistant":
            raise ValueError("a turn must complete with an assistant message")

        with self._lock:
            snapshot = self._load_for_update()
            if snapshot.epoch != epoch:
                return None
            if snapshot.status != "running":
                raise ValueError("the runtime has no active turn")

            thread = snapshot.thread.append((assistant_message,))
            self._append_event(
                {
                    "type": ASSISTANT_COMPLETED,
                    "epoch": epoch,
                    "message": assistant_message.model_dump(mode="json"),
                }
            )
            return RuntimeSnapshot(
                epoch=epoch,
                revision=snapshot.revision + 1,
                status="idle",
                inbox=snapshot.inbox,
                thread=thread,
            )

    def clear(self) -> RuntimeSnapshot:
        """Atomically replace the journal with a new empty epoch."""
        with self._lock:
            current = self._load()
            snapshot = RuntimeSnapshot(epoch=current.epoch + 1)
            self._replace_journal(
                {
                    "type": RUNTIME_RESET,
                    "epoch": snapshot.epoch,
                }
            )
            return snapshot

    def _append_event(self, event: dict[str, object]) -> None:
        """Append and fsync one complete journal event."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(event, separators=(",", ":"))
        with self._path.open("a", encoding="utf-8") as journal:
            journal.write(f"{payload}\n")
            journal.flush()
            os.fsync(journal.fileno())

    def _replace_journal(self, event: dict[str, object]) -> None:
        """Replace the journal and fsync its containing directory."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(event, separators=(",", ":"))
        with NamedTemporaryFile(
            "w",
            dir=self._path.parent,
            encoding="utf-8",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(f"{payload}\n")
            temporary.flush()
            os.fsync(temporary.fileno())

        try:
            os.replace(temporary_path, self._path)
            if os.name != "nt":
                directory_descriptor = os.open(
                    self._path.parent,
                    os.O_RDONLY,
                )
                try:
                    os.fsync(directory_descriptor)
                finally:
                    os.close(directory_descriptor)
        finally:
            temporary_path.unlink(missing_ok=True)

    def _load(self) -> RuntimeSnapshot:
        """Replay committed records without modifying the journal."""
        return self._replay().snapshot

    def _load_for_update(self) -> RuntimeSnapshot:
        """Replay state and remove an interrupted tail before a write."""
        replay = self._replay()
        if replay.uncommitted_tail_offset is not None:
            self._discard_uncommitted_tail(replay.uncommitted_tail_offset)
        return replay.snapshot

    def _replay(self) -> _JournalReplay:
        """Replay newline-committed events and legacy Thread records."""
        snapshot = RuntimeSnapshot()
        if not self._path.exists():
            return _JournalReplay(snapshot)

        committed_offset = 0
        with self._path.open("rb") as journal:
            for line_number, line in enumerate(journal, start=1):
                if not line.endswith(b"\n"):
                    return _JournalReplay(snapshot, committed_offset)

                committed_offset += len(line)
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    snapshot = self._apply_record(snapshot, record)
                except (
                    UnicodeDecodeError,
                    json.JSONDecodeError,
                    TypeError,
                    ValidationError,
                    ValueError,
                ) as error:
                    raise ValueError(
                        f"Invalid runtime record at line {line_number}."
                    ) from error
        return _JournalReplay(snapshot)

    def _discard_uncommitted_tail(self, offset: int) -> None:
        """Truncate bytes after the final newline commit marker."""
        with self._path.open("r+b") as journal:
            journal.truncate(offset)
            journal.flush()
            os.fsync(journal.fileno())

    def _apply_record(
        self,
        snapshot: RuntimeSnapshot,
        record: object,
    ) -> RuntimeSnapshot:
        """Apply one current journal event or legacy Thread record."""
        if not isinstance(record, dict):
            raise TypeError("runtime record must be an object")

        event_type = record.get("type")
        if event_type is None:
            return self._apply_legacy_thread_record(snapshot, record)

        epoch = self._require_epoch(record)
        if event_type == RUNTIME_RESET:
            return RuntimeSnapshot(epoch=epoch)
        if epoch != snapshot.epoch:
            raise ValueError("runtime event epoch does not match")

        if event_type == MESSAGE_QUEUED:
            message = Message.model_validate(record.get("message"))
            return snapshot.model_copy(
                update={
                    "revision": snapshot.revision + 1,
                    "inbox": snapshot.inbox.enqueue(message),
                }
            )

        if event_type == TURN_STARTED:
            if snapshot.status != "idle":
                raise ValueError("turn_started requires an idle runtime")
            message_count = record.get("message_count")
            if not isinstance(message_count, int):
                raise TypeError("message_count must be an integer")
            message = Message.model_validate(record.get("message"))
            return RuntimeSnapshot(
                epoch=epoch,
                revision=snapshot.revision + 1,
                status="running",
                inbox=snapshot.inbox.remove_prefix(message_count),
                thread=snapshot.thread.append((message,)),
            )

        if event_type == ASSISTANT_COMPLETED:
            if snapshot.status != "running":
                raise ValueError("assistant_completed requires a running runtime")
            message = Message.model_validate(record.get("message"))
            return RuntimeSnapshot(
                epoch=epoch,
                revision=snapshot.revision + 1,
                status="idle",
                inbox=snapshot.inbox,
                thread=snapshot.thread.append((message,)),
            )

        raise ValueError("runtime record has an unknown event type")

    @staticmethod
    def _require_epoch(record: dict[str, Any]) -> int:
        """Read a non-negative integer epoch."""
        epoch = record.get("epoch")
        if not isinstance(epoch, int) or epoch < 0:
            raise TypeError("epoch must be a non-negative integer")
        return epoch

    @staticmethod
    def _apply_legacy_thread_record(
        snapshot: RuntimeSnapshot,
        record: dict[str, Any],
    ) -> RuntimeSnapshot:
        """Project the previous completed-segment schemas into Thread."""
        if snapshot.status != "idle" or snapshot.inbox.messages:
            raise ValueError("legacy Thread records must precede runtime events")

        if "messages" in record:
            messages = Thread.model_validate(record).messages
        elif "user_message" in record and "assistant_message" in record:
            messages = (
                Message.model_validate(record["user_message"]),
                Message.model_validate(record["assistant_message"]),
            )
        else:
            raise ValueError("runtime record has an unknown schema")

        if len(messages) % 2:
            raise ValueError("legacy Thread records must contain completed turns")
        return snapshot.model_copy(
            update={
                "revision": snapshot.revision + 1,
                "thread": snapshot.thread.append(messages),
            }
        )
