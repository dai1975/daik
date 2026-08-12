---
daik:
  schema_version: 1
  artifact: workflow-spec
  ownership: daik
  user_action: reference
---

# daik workflow specification

Status: Draft v1alpha1

`.agents/daik-workflow.yaml` is a deterministic state machine for processing one
issue. The graph is fixed before execution; an agent may interpret a natural-language
condition, but may only select one of the transitions declared for the current state.

## Ownership and document identity

`daik site init` creates the workflow only when it does not exist. The user owns and
may customize it. The YAML document contains:

- `daik`: generated pack, language, tracker, and portable-action metadata
- `api_version`: `daik.dev/v1alpha1`
- `kind`: `coding-workflow`
- `initial`: the first state name
- `limits.max_transitions`: maximum transitions for the entire run
- `limits.on_limit`: declared state entered when that global limit is reached
- `agents`: named agent profiles
- `states`: named states and their declared outgoing edges

Mappings are keyed by stable names. Sequence order has no execution meaning.

## Agent profiles

Each entry under `agents` has a non-empty `role` and `instructions`. An agent state
references one profile by name. A runner starts a fresh agent invocation whenever it
enters an agent state, even if the previous state used the same profile.

The new agent reads the issue and the latest structured handoff events before acting.
It records its results and a handoff event in the issue tracker before selecting a
transition. The issue tracker, not local daik state, is the durable source of run and
handoff information.

## Agent CLI wrapper

`agent.cli_wrapper` selects a built-in CLI wrapper. Alternatively, `agent.command`
defines a third-party wrapper as a non-empty sequence of argv values. The runner
executes it directly without a shell from the site root and sends a
`daik.agent-invocation.v1` object on stdin. The complete boundary is defined in
`.agents/daik-agent-context-spec.md`.

The normalized worker result contains:

- required strings: `transition`, `reason`, and `summary`
- string lists: `evidence`, `commits`, `validation`, `decisions`, `risks`, and
  `next_actions`; omitted lists are treated as empty

The runner rejects undeclared transitions and malformed output. Successful execution
emits newline-delimited `agent.started`, `agent.completed`, and `handoff` issue events.
Execution or protocol failure emits `agent.started` and `agent.failed` and exits with
status 1. The runner does not post events. Local Invocation logs are diagnostic
artifacts and are not the source of workflow state.

## State types

### `agent`

An agent state requires `agent`, `task`, `max_visits`, `transitions`, `on_error`, and
`on_limit`. `max_visits` bounds repeated entry to that state. `on_error.to` is used
when the invocation cannot evaluate normal transitions. `on_limit.to` is used before
starting an invocation that would exceed `max_visits`.

### `human`

A human state requires `prompt` and `transitions`. The runner records the request in
the issue and waits. After an explicit human response, an agent evaluates only the
declared transitions against that response.

### `final`

A final state requires an `outcome` of `success`, `failure`, or `cancelled`, and has
no transitions. A workflow defines at least one final state for each outcome.

## Transitions

`transitions` is a mapping keyed by transition name. Each transition has `to` and
exactly one selector:

- `when`: a non-empty natural-language condition
- `otherwise: true`: the fallback when no `when` condition is satisfied

Every non-final state has exactly one `otherwise` transition. The evaluating agent
must select exactly one declared transition and return its name, rationale, and
evidence. It must not invent a target, skip a state, or perform work belonging to the
next state. If more than one `when` appears true, the agent must use `on_error` rather
than choose arbitrarily.

## Limits and exceptional flow

The runner counts every state transition and stops normal execution before
`limits.max_transitions` would be exceeded. It records the reason and routes to
`limits.on_limit`. Agent-state visit limits are handled by the state's `on_limit`.
Invocation or condition-evaluation failures are handled by `on_error`.

These paths are part of the graph and are validated like normal transition targets.
All states must be reachable from `initial` through normal or exceptional edges.

## Portable tracker operations

Workflow metadata may require these provider-independent operations:

- `issue.list_ready`
- `issue.read`
- `issue.create`
- `issue.set_status`
- `issue.assign`
- `issue.add_dependency`
- `issue.remove_dependency`
- `issue.close`
- `issue.claim`
- `issue.set_phase`
- `issue.comment`
- `issue.link`
- `issue.block`
- `issue.complete`

`issue.set_status` and `issue.set_phase` accept workflow-defined strings.
`issue.close` accepts `completed`, `duplicate`, `superseded`, or `cancelled`.
Provider-specific extensions use a provider namespace, such as
`github.request_review`.

The selected tracker pack describes the concrete mappings in
`.agents/daik-tracker.md`. It does not choose or install a CLI, skill, or MCP server;
the user supplies that binding.
