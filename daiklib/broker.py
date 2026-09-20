"""Deterministic Agent Work Broker for one Issue."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from daiklib.tracker_wrapper import ControlConflict, TrackerWrapperError, TrackerWrapper
from daiklib.program import ProgramRunner, ProgramRunnerError
from daiklib.runner import AgentExecutionError, AgentRunner, RunnerError
from daiklib.workspaces import WorkspaceError, WorkspaceManager, event


class BrokerError(RuntimeError):
    pass


class BrokerConflict(BrokerError):
    pass


@dataclass
class ControlState:
    state: str
    transitions: int
    visits: dict[str, int]
    terminal: bool = False


def reconstruct(issue: str, events: list[dict[str, Any]], initial: str) -> ControlState:
    control = ControlState(initial, 0, {})
    started = False
    for item in events:
        if item.get("schema") != "daik.issue-event.v1" or item.get("issue") != issue:
            continue
        data = item.get("data")
        if not isinstance(data, dict):
            continue
        if item.get("kind") == "workflow.started":
            state = data.get("state")
            if isinstance(state, str):
                control = ControlState(state, 0, {state: 1})
                started = True
        elif started and item.get("kind") == "workflow.transitioned":
            target = data.get("to")
            count = data.get("transition_count")
            if isinstance(target, str) and isinstance(count, int):
                control.state = target
                control.transitions = count
                control.visits[target] = control.visits.get(target, 0) + 1
        elif started and item.get("kind") == "workflow.finished":
            control.terminal = True
    return control


def pending_agent_completion(
    issue: str, events: list[dict[str, Any]], state: str
) -> dict[str, Any] | None:
    pending: dict[str, Any] | None = None
    for item in events:
        if item.get("schema") != "daik.issue-event.v1" or item.get("issue") != issue:
            continue
        if item.get("kind") in {"workflow.started", "workflow.transitioned"}:
            pending = None
        elif item.get("kind") == "agent.completed":
            data = item.get("data")
            if isinstance(data, dict) and data.get("state") == state:
                pending = data
        elif item.get("kind") == "agent.failed":
            pending = None
    return pending


def pending_program_completion(
    issue: str, events: list[dict[str, Any]], state: str
) -> dict[str, Any] | None:
    pending: dict[str, Any] | None = None
    for item in events:
        if item.get("schema") != "daik.issue-event.v1" or item.get("issue") != issue:
            continue
        if item.get("kind") in {"workflow.started", "workflow.transitioned"}:
            pending = None
        elif item.get("kind") == "program.completed":
            data = item.get("data")
            if isinstance(data, dict) and data.get("state") == state:
                pending = data
    return pending


class Broker:
    def __init__(
        self,
        site: Path,
        config: dict[str, Any],
        workflow: dict[str, Any],
        wrapper: TrackerWrapper,
    ):
        self.site = site
        self.config = config
        self.workflow = workflow
        self.wrapper = wrapper
        self.states = workflow["states"]
        self.initial = workflow["initial"]
        self.max_transitions = workflow["limits"]["max_transitions"]
        self.global_limit_target = workflow["limits"]["on_limit"]

    def _commit(
        self,
        issue: str,
        version: str,
        events: list[dict[str, Any]],
        **control: Any,
    ) -> str:
        try:
            return self.wrapper.commit(issue, version, events, **control)
        except ControlConflict as error:
            raise BrokerConflict(
                "tracker control changed concurrently; reload the Issue before retrying"
            ) from error
        except TrackerWrapperError as error:
            raise BrokerError(str(error)) from error

    def _transition_event(
        self, issue: str, source: str, transition: str, target: str, count: int
    ) -> dict[str, Any]:
        return event(
            "workflow.transitioned",
            issue,
            {
                "from": source,
                "transition": transition,
                "to": target,
                "transition_count": count,
            },
        )

    def run(
        self,
        issue: str,
        emit: Callable[[dict[str, Any]], None] | None = None,
        human_transition: str | None = None,
    ) -> str:
        try:
            snapshot = self.wrapper.read(issue)
        except TrackerWrapperError as error:
            raise BrokerError(str(error)) from error
        version = snapshot["control_version"]
        history = snapshot["events"]
        has_started = any(
            item.get("schema") == "daik.issue-event.v1"
            and item.get("issue") == issue
            and item.get("kind") == "workflow.started"
            for item in history
        )
        if not has_started:
            try:
                workspace = WorkspaceManager(self.site, self.config).create(issue, ())
            except WorkspaceError as error:
                raise BrokerError(str(error)) from error
            started = event("workflow.started", issue, {"state": self.initial})
            version = self._commit(
                issue,
                version,
                [workspace, started],
                status=self.initial,
                claim=True,
            )
            history.extend((workspace, started))
            for item in (workspace, started):
                if emit:
                    emit(item)
        control = reconstruct(issue, history, self.initial)
        if control.terminal:
            return control.state

        while True:
            state_name = control.state
            state = self.states[state_name]
            state_type = state["type"]
            if state_type == "final":
                outcome = state["outcome"]
                finished = event(
                    "workflow.finished", issue, {"state": state_name, "outcome": outcome}
                )
                close_reason = {
                    "success": "completed",
                    "failure": None,
                    "cancelled": "cancelled",
                }[outcome]
                version = self._commit(
                    issue,
                    version,
                    [finished],
                    status=state_name,
                    close_reason=close_reason,
                )
                if emit:
                    emit(finished)
                return state_name
            if state_type == "human":
                if human_transition is not None:
                    selected = state["transitions"].get(human_transition)
                    if not isinstance(selected, dict):
                        raise BrokerError(
                            f"undeclared human transition for {state_name}: {human_transition}"
                        )
                    control.transitions += 1
                    target = selected["to"]
                    transitioned = self._transition_event(
                        issue, state_name, human_transition, target, control.transitions
                    )
                    version = self._commit(issue, version, [transitioned], status=target)
                    if emit:
                        emit(transitioned)
                    control.state = target
                    control.visits[target] = control.visits.get(target, 0) + 1
                    human_transition = None
                    continue
                waiting = event(
                    "workflow.awaiting_human",
                    issue,
                    {"state": state_name, "prompt": state["prompt"]},
                )
                self._commit(issue, version, [waiting], status=state_name)
                if emit:
                    emit(waiting)
                return state_name
            if state_type == "program":
                if control.transitions >= self.max_transitions:
                    transition_name = "global_limit"
                    target = self.global_limit_target
                    pending = None
                else:
                    pending = pending_program_completion(issue, history, state_name)
                if control.transitions < self.max_transitions and pending is None:
                    def capture_program(item: dict[str, Any]) -> None:
                        nonlocal version
                        version = self._commit(issue, version, [item], status=state_name)
                        history.append(item)
                        if emit:
                            emit(item)

                    try:
                        result = ProgramRunner(self.site, self.config, self.workflow).run(
                            issue, state_name, capture_program
                        )
                    except ProgramRunnerError as error:
                        raise BrokerError(str(error)) from error
                    pending = result.completed["data"]
                if pending is not None:
                    transition_name = pending.get("transition")
                    transition = state["transitions"].get(transition_name)
                    if (
                        not isinstance(transition, dict)
                        or transition.get("to") != pending.get("to")
                    ):
                        raise BrokerError(
                            "recorded program completion is not valid for current state"
                        )
                    target = transition["to"]
                control.transitions += 1
                transitioned = self._transition_event(
                    issue, state_name, transition_name, target, control.transitions
                )
                version = self._commit(issue, version, [transitioned], status=target)
                if emit:
                    emit(transitioned)
                history.append(transitioned)
                control.state = target
                control.visits[target] = control.visits.get(target, 0) + 1
                continue
            if state_type != "agent":
                raise BrokerError(f"unsupported workflow state type: {state_type}")

            visits = control.visits.get(state_name, 0)
            if visits > state["max_visits"]:
                transition_name = "on_limit"
                target = state["on_limit"]["to"]
            elif control.transitions >= self.max_transitions:
                transition_name = "global_limit"
                target = self.global_limit_target
            else:
                pending = pending_agent_completion(issue, history, state_name)
                if pending is not None:
                    transition_name = pending.get("transition")
                    transition = state["transitions"].get(transition_name)
                    if not isinstance(transition, dict) or transition.get("to") != pending.get("to"):
                        raise BrokerError("recorded agent completion is not valid for current state")
                    target = transition["to"]
                else:
                    captured: list[dict[str, Any]] = []

                    def capture(item: dict[str, Any]) -> None:
                        nonlocal version
                        captured.append(item)
                        version = self._commit(issue, version, [item], status=state_name)
                        history.append(item)
                        if emit:
                            emit(item)

                    try:
                        result = AgentRunner(self.site, self.config, self.workflow).run(
                            issue, state_name, capture
                        )
                    except AgentExecutionError:
                        transition_name = "on_error"
                        target = state["on_error"]["to"]
                    except RunnerError as error:
                        raise BrokerError(str(error)) from error
                    else:
                        transition_name = result.completed["data"]["transition"]
                        target = result.completed["data"]["to"]
            control.transitions += 1
            transitioned = self._transition_event(
                issue, state_name, transition_name, target, control.transitions
            )
            version = self._commit(issue, version, [transitioned], status=target)
            if emit:
                emit(transitioned)
            history.append(transitioned)
            control.state = target
            control.visits[target] = control.visits.get(target, 0) + 1
