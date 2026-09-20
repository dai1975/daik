"""Process boundary for tracker wrappers."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any, Mapping, Sequence

from daiklib.processes import redact, redact_value


class TrackerWrapperError(RuntimeError):
    pass


class ControlConflict(TrackerWrapperError):
    pass


class TrackerWrapper:
    def __init__(
        self,
        site: Path,
        command: Sequence[str],
        timeout_seconds: int = 30,
        environment: Mapping[str, str] | None = None,
        secrets: tuple[str, ...] = (),
    ):
        self.site = site
        self.command = list(command)
        self.timeout = timeout_seconds
        self.environment = dict(environment) if environment is not None else None
        self.secrets = secrets

    def call(
        self, operation: str, issue: str | None = None, **arguments: Any
    ) -> dict[str, Any]:
        request = {
            "protocol_version": "daik.tracker-wrapper.v1",
            "operation": operation,
            **arguments,
        }
        if issue is not None:
            request["issue"] = issue
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
                env=self.environment,
            )
        except subprocess.TimeoutExpired as error:
            raise TrackerWrapperError(f"tracker wrapper timed out after {self.timeout} seconds") from error
        except OSError as error:
            raise TrackerWrapperError(f"could not start tracker wrapper: {error}") from error
        try:
            response = redact_value(json.loads(process.stdout), self.secrets)
        except json.JSONDecodeError as error:
            detail = redact(process.stderr.strip() or process.stdout.strip(), self.secrets)
            raise TrackerWrapperError(f"tracker wrapper returned invalid JSON: {detail[-1000:]}") from error
        if not isinstance(response, dict):
            raise TrackerWrapperError("tracker wrapper response root must be an object")
        if response.get("protocol_version") != "daik.tracker-wrapper-result.v1":
            raise TrackerWrapperError("tracker wrapper returned an unsupported protocol_version")
        if response.get("status") == "conflict":
            raise ControlConflict(
                redact(
                    str(response.get("message", "tracker control version conflict")),
                    self.secrets,
                )
            )
        if process.returncode or response.get("status") != "ok":
            message = response.get("message") or process.stderr.strip() or "tracker wrapper failed"
            raise TrackerWrapperError(redact(str(message), self.secrets)[-1000:])
        return response

    def list_ready(self, limit: int, exclude: Sequence[str] = ()) -> list[str]:
        response = self.call("work.list_ready", limit=limit, exclude=list(exclude))
        issues = response.get("issues")
        if not isinstance(issues, list) or not all(
            isinstance(issue, str) and issue for issue in issues
        ):
            raise TrackerWrapperError("work.list_ready must return a list of non-empty issue IDs")
        if len(issues) > limit:
            raise TrackerWrapperError("work.list_ready returned more issues than requested")
        if len(set(issues)) != len(issues):
            raise TrackerWrapperError("work.list_ready returned duplicate issue IDs")
        if set(issues) & set(exclude):
            raise TrackerWrapperError("work.list_ready returned an excluded issue ID")
        return issues

    def read(self, issue: str) -> dict[str, Any]:
        response = self.call("issue.read_control", issue)
        control_version = response.get("control_version")
        events = response.get("events")
        if not isinstance(control_version, str) or not isinstance(events, list):
            raise TrackerWrapperError("issue.read_control must return control_version and events")
        if not all(isinstance(item, dict) for item in events):
            raise TrackerWrapperError("issue.read_control events must be objects")
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
            raise TrackerWrapperError("issue.commit_control must return control_version")
        return updated
