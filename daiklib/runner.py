"""Run one coding-agent workflow state without persisting orchestration state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Sequence

from daiklib.invocations import (
    InvocationError,
    create_log_directory,
    link_native_artifacts,
    write_private_json,
    write_private_text,
)
from daiklib.workspaces import event, handoff_event, safe_slug


class RunnerError(RuntimeError):
    pass


class AgentExecutionError(RunnerError):
    def __init__(self, message: str, started: dict[str, Any], failed: dict[str, Any]):
        super().__init__(message)
        self.started = started
        self.failed = failed


@dataclass(frozen=True)
class AgentRun:
    started: dict[str, Any]
    completed: dict[str, Any]
    handoff: dict[str, Any]
    log_directory: Path


def _strings(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RunnerError(f"agent result {field} must be a list of strings")
    return value


class AgentRunner:
    def __init__(self, site: Path, config: dict[str, Any], workflow: dict[str, Any]):
        self.site = site.resolve()
        self.workflow = workflow
        repositories = config.get("repositories", {})
        self.repositories = repositories if isinstance(repositories, dict) else {}
        settings = config.get("agent")
        if not isinstance(settings, dict):
            raise RunnerError("agent configuration must be a mapping")
        wrapper_name = settings.get("cli_wrapper")
        command = settings.get("command")
        if wrapper_name is not None and command is not None:
            raise RunnerError("configure only one of agent.cli_wrapper or agent.command")
        if wrapper_name == "codex":
            command = [
                sys.executable,
                str(
                    Path(__file__).resolve().parents[1]
                    / "cli-wrappers/codex/daik-cli-wrapper-codex"
                ),
            ]
        elif wrapper_name is not None:
            raise RunnerError(f"unknown built-in agent CLI wrapper: {wrapper_name}")
        if not isinstance(command, list) or not command or not all(
            isinstance(item, str) and item for item in command
        ):
            raise RunnerError(
                "agent.cli_wrapper or agent.command must configure an agent CLI wrapper"
            )
        self.command: Sequence[str] = command
        options = settings.get("wrapper_options", {})
        if not isinstance(options, dict):
            raise RunnerError("agent.wrapper_options must be a mapping")
        self.wrapper_options = options
        timeout = settings.get("timeout_seconds", 3600)
        if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
            raise RunnerError("agent.timeout_seconds must be a positive integer")
        self.timeout = timeout

    def _state(self, name: str) -> tuple[dict[str, Any], dict[str, Any]]:
        states = self.workflow.get("states")
        profiles = self.workflow.get("agents")
        state = states.get(name) if isinstance(states, dict) else None
        if not isinstance(state, dict):
            raise RunnerError(f"unknown workflow state: {name}")
        if state.get("type") != "agent":
            raise RunnerError(f"workflow state is not an agent state: {name}")
        profile_name = state.get("agent")
        profile = profiles.get(profile_name) if isinstance(profiles, dict) else None
        if not isinstance(profile, dict):
            raise RunnerError(f"state {name} references an unknown agent profile")
        return state, profile

    def _invocation(
        self,
        invocation_id: str,
        log_directory: Path,
        issue: str,
        state_name: str,
        state: dict[str, Any],
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        transitions = state["transitions"]
        contract = {
            name: {
                "to": transition["to"],
                **({"when": transition["when"]} if "when" in transition else {"otherwise": True}),
            }
            for name, transition in transitions.items()
        }
        return {
            "protocol_version": "daik.agent-invocation.v1",
            "invocation_id": invocation_id,
            "issue": issue,
            "state": state_name,
            "site_root": str(self.site),
            "log_directory": str(log_directory),
            "profile": {
                "name": state["agent"],
                "role": profile["role"],
                "instructions": profile["instructions"],
            },
            "task": state["task"],
            "context": {
                "site_instructions": "AGENTS.md",
                "worker_policy": ".agents/daik-worker.md",
                "workflow": ".agents/daik-workflow.yaml",
                "tracker": ".agents/daik-tracker.md",
                "issue_events": ".agents/daik-issue-event-spec.md",
            },
            "workspace": {
                "root": "workspaces",
                "issue_directory": f"workspaces/{safe_slug(issue)}",
                "repositories": {
                    name: f"workspaces/{safe_slug(issue)}/{name}"
                    for name in sorted(self.repositories)
                },
            },
            "transitions": contract,
            "wrapper_options": self.wrapper_options,
        }

    def run(
        self,
        issue: str,
        state_name: str,
        emit: Callable[[dict[str, Any]], None] | None = None,
    ) -> AgentRun:
        state, profile = self._state(state_name)
        profile_name = state["agent"]
        try:
            invocation_id, log_directory = create_log_directory(self.site, issue)
        except InvocationError as error:
            raise RunnerError(str(error)) from error
        invocation = self._invocation(
            invocation_id, log_directory, issue, state_name, state, profile
        )
        write_private_json(log_directory / "invocation.json", invocation)
        event_path = log_directory / "events.ndjson"
        write_private_text(event_path, "")
        started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        def record(item: dict[str, Any]) -> None:
            with event_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
            if emit is not None:
                emit(item)

        started = event(
            "agent.started",
            issue,
            {"state": state_name, "agent": profile_name, "role": profile["role"]},
        )
        record(started)

        def fail(message: str) -> None:
            failed = event(
                "agent.failed",
                issue,
                {
                    "state": state_name,
                    "agent": profile_name,
                    "role": profile["role"],
                    "error": message[-1000:],
                },
            )
            record(failed)
            raise AgentExecutionError(message, started, failed)

        environment = dict(os.environ)
        environment.update(
            {
                "DAIK_ISSUE": issue,
                "DAIK_STATE": state_name,
                "DAIK_AGENT_PROFILE": profile_name,
                "DAIK_INVOCATION_ID": invocation_id,
                "DAIK_LOG_DIRECTORY": str(log_directory),
            }
        )
        process: subprocess.CompletedProcess[str] | None = None
        try:
            process = subprocess.run(
                list(self.command),
                cwd=self.site,
                input=json.dumps(invocation, ensure_ascii=False),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=self.timeout,
                env=environment,
            )
        except subprocess.TimeoutExpired as error:
            stdout = error.stdout if isinstance(error.stdout, str) else ""
            stderr = error.stderr if isinstance(error.stderr, str) else ""
            write_private_text(log_directory / "wrapper.stdout.log", stdout)
            write_private_text(log_directory / "wrapper.stderr.log", stderr)
            write_private_json(
                log_directory / "metadata.json",
                {
                    "invocation_id": invocation_id,
                    "started_at": started_at,
                    "finished_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "status": "timed_out",
                    "wrapper_executable": self.command[0],
                },
            )
            fail(f"agent command timed out after {self.timeout} seconds")
        except OSError as error:
            write_private_json(
                log_directory / "metadata.json",
                {
                    "invocation_id": invocation_id,
                    "started_at": started_at,
                    "finished_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "status": "start_failed",
                    "wrapper_executable": self.command[0],
                },
            )
            fail(f"could not start agent command: {error}")
        write_private_text(log_directory / "wrapper.stdout.log", process.stdout)
        write_private_text(log_directory / "wrapper.stderr.log", process.stderr)
        write_private_json(
            log_directory / "metadata.json",
            {
                "invocation_id": invocation_id,
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "status": "completed" if process.returncode == 0 else "failed",
                "exit_code": process.returncode,
                "wrapper_executable": self.command[0],
            },
        )
        if process.returncode:
            detail = process.stderr.strip() or process.stdout.strip() or "no diagnostic output"
            fail(f"agent command exited with {process.returncode}: {detail[-1000:]}")
        try:
            wrapper_result = json.loads(process.stdout)
        except json.JSONDecodeError:
            fail("agent stdout must contain exactly one JSON object")
        if not isinstance(wrapper_result, dict):
            fail("CLI wrapper stdout JSON root must be an object")
        if wrapper_result.get("protocol_version") != "daik.cli-wrapper-result.v1":
            fail("CLI wrapper returned an unsupported protocol_version")
        result = wrapper_result.get("agent_result")
        if not isinstance(result, dict):
            fail("CLI wrapper result must contain an agent_result object")
        try:
            linked_artifacts = link_native_artifacts(
                log_directory, wrapper_result.get("native_artifacts")
            )
        except InvocationError as error:
            fail(str(error))
        write_private_json(
            log_directory / "result.json",
            {**wrapper_result, "native_artifacts": linked_artifacts},
        )
        transition_name = result.get("transition")
        transition = state["transitions"].get(transition_name)
        if not isinstance(transition_name, str) or not isinstance(transition, dict):
            fail(f"agent selected undeclared transition: {transition_name!r}")
        reason = result.get("reason")
        summary = result.get("summary")
        if not isinstance(reason, str) or not reason.strip():
            fail("agent result reason must be a non-empty string")
        if not isinstance(summary, str) or not summary.strip():
            fail("agent result summary must be a non-empty string")
        try:
            evidence = _strings(result.get("evidence"), "evidence")
            commits = _strings(result.get("commits"), "commits")
            validation = _strings(result.get("validation"), "validation")
            decisions = _strings(result.get("decisions"), "decisions")
            risks = _strings(result.get("risks"), "risks")
            next_actions = _strings(result.get("next_actions"), "next_actions")
        except RunnerError as error:
            fail(str(error))
        target = transition["to"]
        completed = event(
            "agent.completed",
            issue,
            {
                "state": state_name,
                "agent": profile_name,
                "role": profile["role"],
                "transition": transition_name,
                "to": target,
                "reason": reason,
                "evidence": evidence,
            },
        )
        target_state = self.workflow["states"][target]
        target_profile = target_state.get("agent")
        if isinstance(target_profile, str):
            target_role = self.workflow["agents"][target_profile]["role"]
        else:
            target_role = target_state.get("type", "unknown")
        handoff = handoff_event(
            issue,
            profile["role"],
            target_role,
            target,
            summary,
            commits,
            validation,
            decisions,
            risks,
            next_actions,
        )
        record(completed)
        record(handoff)
        return AgentRun(started, completed, handoff, log_directory)
