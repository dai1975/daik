"""Run one deterministic program workflow state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Callable

from daiklib.invocations import (
    InvocationError,
    create_invocation_directory,
    write_private_json,
    write_private_text,
)
from daiklib.workspaces import event, safe_slug


class ProgramRunnerError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProgramRun:
    started: dict[str, Any]
    completed: dict[str, Any]
    log_directory: Path


def _summary(stdout: str, stderr: str, limit: int = 1000) -> str:
    text = stderr.strip() or stdout.strip() or "no output"
    if len(text) <= limit:
        return text
    return text[-limit:]


class ProgramRunner:
    def __init__(self, site: Path, config: dict[str, Any], workflow: dict[str, Any]):
        self.site = site.resolve()
        self.config = config
        self.workflow = workflow

    def _state(self, name: str) -> dict[str, Any]:
        states = self.workflow.get("states")
        state = states.get(name) if isinstance(states, dict) else None
        if not isinstance(state, dict):
            raise ProgramRunnerError(f"unknown workflow state: {name}")
        if state.get("type") != "program":
            raise ProgramRunnerError(f"workflow state is not a program state: {name}")
        return state

    def _working_directory(self, issue: str, repository: str) -> Path:
        repositories = self.config.get("repositories")
        if not isinstance(repositories, dict) or repository not in repositories:
            raise ProgramRunnerError(f"program state references unknown repository: {repository}")
        workspace = self.config.get("workspace")
        root_name = workspace.get("root") if isinstance(workspace, dict) else None
        if not isinstance(root_name, str) or not root_name:
            raise ProgramRunnerError("workspace.root must be configured")
        root = (self.site / root_name / safe_slug(issue)).resolve()
        try:
            root.relative_to(self.site)
        except ValueError as error:
            raise ProgramRunnerError("Issue workspace escapes the site") from error
        directory = (root / repository).resolve()
        try:
            directory.relative_to(root)
        except ValueError as error:
            raise ProgramRunnerError("program working directory escapes the Issue workspace") from error
        if not directory.is_dir():
            raise ProgramRunnerError(f"program working directory is missing: {directory}")
        return directory

    def run(
        self,
        issue: str,
        state_name: str,
        emit: Callable[[dict[str, Any]], None] | None = None,
    ) -> ProgramRun:
        state = self._state(state_name)
        command = state["command"]
        repository = state["repository"]
        timeout = state["timeout_seconds"]
        try:
            invocation_id, log_directory = create_invocation_directory(self.site, issue)
        except InvocationError as error:
            raise ProgramRunnerError(str(error)) from error

        started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        started = event(
            "program.started",
            issue,
            {
                "invocation_id": invocation_id,
                "state": state_name,
                "repository": repository,
                "command": command,
            },
        )
        if emit:
            emit(started)
        start = time.monotonic()
        stdout = ""
        stderr = ""
        exit_code: int | None = None
        diagnostic: str | None = None
        try:
            directory = self._working_directory(issue, repository)
            environment = dict(os.environ)
            environment.update(
                {
                    "DAIK_ISSUE": issue,
                    "DAIK_STATE": state_name,
                    "DAIK_INVOCATION_ID": invocation_id,
                    "DAIK_LOG_DIRECTORY": str(log_directory),
                }
            )
            process = subprocess.run(
                command,
                cwd=directory,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=timeout,
                env=environment,
            )
            stdout = process.stdout
            stderr = process.stderr
            exit_code = process.returncode
            result = "succeeded" if exit_code == 0 else "failed"
        except subprocess.TimeoutExpired as error:
            stdout = error.stdout if isinstance(error.stdout, str) else ""
            stderr = error.stderr if isinstance(error.stderr, str) else ""
            result = "error"
            diagnostic = f"command timed out after {timeout} seconds"
        except OSError as error:
            result = "error"
            diagnostic = f"could not start command: {error}"
        except ProgramRunnerError as error:
            result = "error"
            diagnostic = str(error)

        duration_ms = round((time.monotonic() - start) * 1000)
        write_private_text(log_directory / "program.stdout.log", stdout)
        write_private_text(log_directory / "program.stderr.log", stderr)
        write_private_json(
            log_directory / "metadata.json",
            {
                "invocation_id": invocation_id,
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "status": result,
                "exit_code": exit_code,
                "executable": command[0],
                "repository": repository,
                "duration_ms": duration_ms,
                **({"error": diagnostic} if diagnostic else {}),
            },
        )
        transition = state["transitions"][result]
        completed = event(
            "program.completed",
            issue,
            {
                "invocation_id": invocation_id,
                "state": state_name,
                "result": result,
                "transition": result,
                "to": transition["to"],
                "exit_code": exit_code,
                "duration_ms": duration_ms,
                "summary": diagnostic or _summary(stdout, stderr),
            },
        )
        if emit:
            emit(completed)
        return ProgramRun(started, completed, log_directory)
