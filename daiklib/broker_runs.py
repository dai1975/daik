"""Local structured records for broker processes."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
from typing import Any
import uuid

from daiklib.invocations import (
    InvocationError,
    ensure_private_directory,
    replace_private_json,
    site_state_directory,
    write_private_json,
    write_private_text,
)


class BrokerRunError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class BrokerRunLog:
    def __init__(self, site: Path, mode: str, concurrency: int):
        try:
            parent = site_state_directory(site) / "broker-runs"
            ensure_private_directory(parent)
            self.run_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            self.directory = parent / f"{timestamp}-{self.run_id}"
            self.directory.mkdir(mode=0o700)
            self.events_path = self.directory / "events.ndjson"
            write_private_text(self.events_path, "")
            self.metadata_path = self.directory / "metadata.json"
            self.metadata: dict[str, Any] = {
                "schema": "daik.broker-run.v1",
                "broker_run_id": self.run_id,
                "mode": mode,
                "pid": os.getpid(),
                "started_at": utc_now(),
                "finished_at": None,
                "status": "running",
                "concurrency": concurrency,
            }
            write_private_json(self.metadata_path, self.metadata)
        except (InvocationError, OSError) as error:
            raise BrokerRunError(str(error)) from error
        self._lock = threading.Lock()

    def append(self, item: dict[str, Any]) -> dict[str, Any]:
        record = dict(item)
        record.setdefault("broker_run_id", self.run_id)
        record.setdefault("timestamp", utc_now())
        try:
            with self._lock, self.events_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                stream.flush()
        except OSError as error:
            raise BrokerRunError(f"could not append broker event: {error}") from error
        return record

    def record(self, kind: str, **data: Any) -> dict[str, Any]:
        return self.append(
            {"schema": "daik.broker-event.v1", "kind": kind, "data": data}
        )

    def finish(self, status: str, **result: Any) -> None:
        with self._lock:
            self.metadata.update(
                {"finished_at": utc_now(), "status": status, **result}
            )
            try:
                replace_private_json(self.metadata_path, self.metadata)
            except (InvocationError, OSError) as error:
                raise BrokerRunError(f"could not finalize broker run: {error}") from error


def _run_parent(site: Path) -> Path:
    try:
        return site_state_directory(site) / "broker-runs"
    except InvocationError as error:
        raise BrokerRunError(str(error)) from error


def _load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise BrokerRunError(f"broker run file must not be a symlink: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BrokerRunError(f"could not read {path}: {error}") from error
    if not isinstance(value, dict):
        raise BrokerRunError(f"broker run file root must be an object: {path}")
    return value


def select_broker_run(site: Path, run_id: str | None = None) -> Path:
    parent = _run_parent(site)
    if not parent.is_dir() or parent.is_symlink():
        raise BrokerRunError("no broker runs were found for this site")
    candidates = [
        path for path in parent.iterdir() if path.is_dir() and not path.is_symlink()
    ]
    if run_id is None:
        if not candidates:
            raise BrokerRunError("no broker runs were found for this site")
        return max(
            candidates,
            key=lambda path: str(_load_json(path / "metadata.json").get("started_at", "")),
        )
    matches = [
        path
        for path in candidates
        if path.name == run_id
        or _load_json(path / "metadata.json").get("broker_run_id") == run_id
    ]
    if len(matches) != 1:
        raise BrokerRunError(f"broker run was not found: {run_id}")
    return matches[0]


def _pid_alive(pid: Any) -> bool:
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def broker_run_status(site: Path, run_id: str | None = None) -> dict[str, Any]:
    directory = select_broker_run(site, run_id)
    metadata = _load_json(directory / "metadata.json")
    if metadata.get("schema") != "daik.broker-run.v1":
        raise BrokerRunError("broker metadata uses an unsupported schema")
    events: list[dict[str, Any]] = []
    events_path = directory / "events.ndjson"
    if events_path.is_symlink():
        raise BrokerRunError("broker events file must not be a symlink")
    number = 0
    try:
        for number, line in enumerate(events_path.read_text(encoding="utf-8").splitlines(), 1):
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("event root is not an object")
            events.append(value)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise BrokerRunError(f"could not read broker event log at line {number}: {error}") from error

    work: dict[str, dict[str, Any]] = {}
    for item in events:
        kind = item.get("kind")
        data = item.get("data")
        if not isinstance(data, dict):
            continue
        issue = data.get("issue")
        if not isinstance(issue, str):
            continue
        if kind == "work.submitted":
            work[issue] = {"issue": issue, "status": "running", "attempt": 1}
        elif kind == "work.event":
            nested = data.get("event")
            nested_data = nested.get("data") if isinstance(nested, dict) else None
            if issue not in work:
                work[issue] = {"issue": issue, "status": "running", "attempt": 1}
            if isinstance(nested_data, dict):
                if nested.get("kind") == "workflow.started":
                    work[issue]["state"] = nested_data.get("state")
                elif nested.get("kind") == "workflow.transitioned":
                    work[issue]["state"] = nested_data.get("to")
                elif nested.get("kind") == "workflow.awaiting_human":
                    work[issue]["state"] = nested_data.get("state")
                elif nested.get("kind") == "workflow.finished":
                    work[issue]["state"] = nested_data.get("state")
        elif kind == "work.retrying":
            work[issue] = {
                "issue": issue,
                "status": "retrying",
                "attempt": data.get("attempt", 1) + 1,
                "delay_ms": data.get("delay_ms"),
                "error": data.get("error"),
            }
        elif kind in {"work.stopped", "work.failed", "work.skipped"}:
            work[issue] = {
                "issue": issue,
                "status": kind.removeprefix("work."),
                **{key: value for key, value in data.items() if key != "issue"},
            }
    effective_status = metadata.get("status")
    if effective_status == "running" and not _pid_alive(metadata.get("pid")):
        effective_status = "interrupted"
    return {
        **metadata,
        "status": effective_status,
        "directory": directory.name,
        "event_count": len(events),
        "work": [work[issue] for issue in sorted(work)],
    }
