"""Run one coding-agent workflow state without persisting orchestration state."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Callable, Sequence

from daiklib.workspaces import event, handoff_event


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
        settings = config.get("agent")
        if not isinstance(settings, dict):
            raise RunnerError("agent configuration must be a mapping")
        command = settings.get("command")
        if not isinstance(command, list) or not command or not all(
            isinstance(item, str) and item for item in command
        ):
            raise RunnerError("agent.command must be a non-empty list of command arguments")
        self.command: Sequence[str] = command
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

    def _prompt(self, issue: str, state_name: str, state: dict[str, Any], profile: dict[str, Any]) -> str:
        transitions = state["transitions"]
        contract = {
            name: {
                "to": transition["to"],
                **({"when": transition["when"]} if "when" in transition else {"otherwise": True}),
            }
            for name, transition in transitions.items()
        }
        result_schema = {
            "transition": "one declared transition name",
            "reason": "concise rationale",
            "evidence": ["fact supporting the transition"],
            "summary": "handoff summary",
            "commits": ["commit id"],
            "validation": ["command=result"],
            "decisions": ["decision"],
            "risks": ["remaining risk"],
            "next_actions": ["next action"],
        }
        return "\n".join(
            (
                "You are one invocation in a daik coding workflow.",
                f"Issue: {issue}",
                f"Current state: {state_name}",
                f"Role: {profile['role']}",
                "",
                "Read AGENTS.md, .agents/daik-workflow.yaml, .agents/daik-tracker.md,",
                ".agents/daik-issue-event-spec.md, the issue, and its latest handoff events.",
                "Work from the site root. Modify only assigned checkouts under workspaces/.",
                "",
                "Role instructions:",
                profile["instructions"].strip(),
                "",
                "State task:",
                state["task"].strip(),
                "",
                "Declared transitions:",
                json.dumps(contract, ensure_ascii=False, indent=2),
                "",
                "Complete only this state's work. Do not perform the next state's work.",
                "Return exactly one JSON object on stdout and no other text.",
                "Select one declared transition; do not invent or skip a state.",
                "Result schema:",
                json.dumps(result_schema, ensure_ascii=False, indent=2),
            )
        )

    def run(
        self,
        issue: str,
        state_name: str,
        emit: Callable[[dict[str, Any]], None] | None = None,
    ) -> AgentRun:
        state, profile = self._state(state_name)
        profile_name = state["agent"]
        started = event(
            "agent.started",
            issue,
            {"state": state_name, "agent": profile_name, "role": profile["role"]},
        )
        if emit is not None:
            emit(started)

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
            if emit is not None:
                emit(failed)
            raise AgentExecutionError(message, started, failed)

        environment = dict(os.environ)
        environment.update(
            {
                "DAIK_ISSUE": issue,
                "DAIK_STATE": state_name,
                "DAIK_AGENT_PROFILE": profile_name,
            }
        )
        try:
            process = subprocess.run(
                list(self.command),
                cwd=self.site,
                input=self._prompt(issue, state_name, state, profile),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=self.timeout,
                env=environment,
            )
        except subprocess.TimeoutExpired as error:
            fail(f"agent command timed out after {self.timeout} seconds")
        except OSError as error:
            fail(f"could not start agent command: {error}")
        if process.returncode:
            detail = process.stderr.strip() or process.stdout.strip() or "no diagnostic output"
            fail(f"agent command exited with {process.returncode}: {detail[-1000:]}")
        try:
            result = json.loads(process.stdout)
        except json.JSONDecodeError:
            fail("agent stdout must contain exactly one JSON object")
        if not isinstance(result, dict):
            fail("agent stdout JSON root must be an object")
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
        if emit is not None:
            emit(completed)
            emit(handoff)
        return AgentRun(started, completed, handoff)
