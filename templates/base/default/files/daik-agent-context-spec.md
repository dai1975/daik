---
daik:
  schema_version: 1
  artifact: agent-context-spec
  ownership: daik
  user_action: reference
---

# daik agent context and CLI wrapper protocol

Status: Draft v1

daik depends on a semantic Invocation contract, not on features shared by coding-agent
products. An agent CLI wrapper translates that contract to one product's command-line
interface and normalizes its result. A CLI wrapper does not interpret workflow or
tracker semantics.

## Static and dynamic context

Static, site-owned context consists of `AGENTS.md`, `.agents/daik-worker.md`,
`.agents/daik-workflow.yaml`, and `.agents/daik-tracker.md`. Dynamic context is created
for one Issue and state and is not deployed as a site file.

## Invocation input

A CLI wrapper reads exactly one JSON object from stdin. Its `protocol_version` is
`daik.agent-invocation.v1`. Required data includes:

- `invocation_id`, `issue`, `state`, `site_root`, and local `log_directory`
- `profile`: stable name, role, and instructions
- `task` and the complete mapping of allowed `transitions`
- `context`: paths to applicable site documents
- `workspace`: the Issue workspace and repository locations known by daik
- `wrapper_options`: opaque product-specific configuration

`site_root` and `log_directory` are local absolute paths. A CLI wrapper must not place
them in worker reports, handoffs, or Issue events. daik also supplies
`DAIK_INVOCATION_ID` and `DAIK_LOG_DIRECTORY` to the wrapper environment.

## Wrapper result

A successful CLI wrapper writes exactly one JSON object to stdout with
`protocol_version: daik.cli-wrapper-result.v1`. It contains:

- `wrapper`: wrapper name and non-secret product invocation identifiers
- `agent_result`: the structured worker result required by the workflow specification
- `native_artifacts`: local-only references such as a product-native session transcript

All diagnostics go to stderr. A nonzero exit means that the product invocation or
wrapper protocol failed; daik must not apply a transition from that invocation.

## Native session artifacts

A session artifact has `type: session`, a product-native `id`, and an absolute local
`path`. The CLI wrapper owns product-specific session discovery. daik validates the
reference and may create a fixed-name symbolic link in its Invocation log directory.
The native path and link are never tracker data.

Tracker access is a separate semantic boundary implemented by a joint. Its protocol
is defined in `.agents/daik-tracker-joint-spec.md`; a CLI wrapper must not implement
orchestrator control updates.

## Codex CLI wrapper

The built-in Codex wrapper uses non-interactive `codex exec`. It requests JSONL native
events, a JSON Schema constrained final response, and a separate last-message file.
It obtains the native thread ID from `thread.started`. Locating the corresponding
session file is best effort because the on-disk session layout is not part of this
daik protocol.
