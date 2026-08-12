---
daik:
  schema_version: 1
  artifact: issue-event-spec
  ownership: daik
  user_action: reference
---

# daik issue event specification

Runtime state is recorded in the issue tracker as append-only JSON events. daik
does not persist workspace or agent-run state in `.daik/`.

## Envelope

Every event contains:

- `schema`: `daik.issue-event.v1`
- `kind`: event type
- `issue`: provider-native issue key supplied to daik
- `timestamp`: UTC RFC 3339 timestamp
- `data`: event-specific object

Post the complete JSON object to the issue without rewriting previous events.
Tracker packs define the provider-specific container used for the event.

## Event kinds

- `workspace.prepared`: worktrees were created
- `workspace.reused`: existing worktrees were verified and reused
- `workspace.inspected`: local workspace state was read
- `workspace.reconciled`: local state matched a previously recorded event
- `workspace.removed`: worktrees were removed; branches were retained
- `handoff`: one agent role handed work to another
- `workflow.started`: the Issue was claimed and entered its initial state
- `workflow.transitioned`: an allowed transition was atomically applied
- `workflow.awaiting_human`: execution stopped for an explicit human decision
- `workflow.finished`: a final state and outcome were committed
- `agent.started`: an agent-state invocation began
- `agent.completed`: an invocation selected a declared transition
- `agent.failed`: the command or its result protocol failed
- `validation`, `review`, `blocked`, `artifact.linked`, and `completed`: reserved
  for orchestrator and agent-run events

## Agent-run data

`agent.started` records `state`, `agent`, and `role`. `agent.completed` also records
the selected `transition`, target state in `to`, natural-language `reason`, and an
`evidence` list. The runner emits a `handoff` event after a successful invocation.

`agent.failed` records the state, profile, role, and a bounded diagnostic `error`.
Runner events are output records for the tracker joint to append; emitting an event
does not itself persist it.

## Workflow control data

`workflow.started` records `state`. `workflow.transitioned` records `from`, the named
`transition`, `to`, and monotonically increasing `transition_count`.
`workflow.awaiting_human` records `state` and `prompt`. `workflow.finished` records
`state` and `outcome`.

The tracker joint commits these events with an opaque compare-and-set control version.
Only committed control events determine the current workflow state.

## Workspace data

Workspace paths are site-relative. Each repository entry records `name`,
`source`, `worktree`, `branch`, `head`, and `base_revision`. Absolute local paths
must not be posted to the tracker.

## Handoff data

A handoff records `from_role`, `to_role`, `phase`, `summary`, `commits`,
`validation`, `decisions`, `risks`, and `next_actions`. Empty lists are retained
so the receiving agent can distinguish an intentionally empty section from an
older unstructured comment.
