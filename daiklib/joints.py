"""Process boundary for tracker joints."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any, Sequence


class JointError(RuntimeError):
    pass


class ControlConflict(JointError):
    pass


class TrackerJoint:
    def __init__(self, site: Path, command: Sequence[str], timeout_seconds: int = 30):
        self.site = site
        self.command = list(command)
        self.timeout = timeout_seconds

    def call(self, operation: str, issue: str, **arguments: Any) -> dict[str, Any]:
        request = {
            "protocol_version": "daik.tracker-joint.v1",
            "operation": operation,
            "issue": issue,
            **arguments,
        }
        try:
            process = subprocess.run(
                self.command,
                cwd=self.site,
                input=json.dumps(request, ensure_ascii=False),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise JointError(f"tracker joint timed out after {self.timeout} seconds") from error
        except OSError as error:
            raise JointError(f"could not start tracker joint: {error}") from error
        try:
            response = json.loads(process.stdout)
        except json.JSONDecodeError as error:
            detail = process.stderr.strip() or process.stdout.strip()
            raise JointError(f"tracker joint returned invalid JSON: {detail[-1000:]}") from error
        if not isinstance(response, dict):
            raise JointError("tracker joint response root must be an object")
        if response.get("protocol_version") != "daik.tracker-joint-result.v1":
            raise JointError("tracker joint returned an unsupported protocol_version")
        if response.get("status") == "conflict":
            raise ControlConflict(response.get("message", "tracker control version conflict"))
        if process.returncode or response.get("status") != "ok":
            message = response.get("message") or process.stderr.strip() or "tracker joint failed"
            raise JointError(str(message)[-1000:])
        return response

    def read(self, issue: str) -> dict[str, Any]:
        response = self.call("issue.read_control", issue)
        control_version = response.get("control_version")
        events = response.get("events")
        if not isinstance(control_version, str) or not isinstance(events, list):
            raise JointError("issue.read_control must return control_version and events")
        if not all(isinstance(item, dict) for item in events):
            raise JointError("issue.read_control events must be objects")
        return response

    def commit(
        self,
        issue: str,
        control_version: str,
        events: list[dict[str, Any]],
        status: str | None = None,
        claim: bool = False,
        close_reason: str | None = None,
    ) -> str:
        response = self.call(
            "issue.commit_control",
            issue,
            expected_control_version=control_version,
            events=events,
            status=status,
            claim=claim,
            close_reason=close_reason,
        )
        updated = response.get("control_version")
        if not isinstance(updated, str):
            raise JointError("issue.commit_control must return control_version")
        return updated
