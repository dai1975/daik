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
- `agent.started`, `validation`, `review`, `blocked`, `artifact.linked`, and
  `completed`: reserved for orchestrator and agent-run events

## Workspace data

Workspace paths are site-relative. Each repository entry records `name`,
`source`, `worktree`, `branch`, `head`, and `base_revision`. Absolute local paths
must not be posted to the tracker.

## Handoff data

A handoff records `from_role`, `to_role`, `phase`, `summary`, `commits`,
`validation`, `decisions`, `risks`, and `next_actions`. Empty lists are retained
so the receiving agent can distinguish an intentionally empty section from an
older unstructured comment.
