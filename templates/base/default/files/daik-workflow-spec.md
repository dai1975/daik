---
daik:
  schema_version: 1
  artifact: workflow-spec
  ownership: daik
  user_action: reference
---

# daik workflow specification

Status: Draft v1

`.agents/daik-workflow.md` is the project-owned workflow given to coding agents that
process issues.

## Ownership

- `daik site init` creates the file only when it does not exist.
- After creation, the user owns the file and daik does not overwrite it.
- The file is generated from the selected workflow pack and references the
  separately generated `.agents/daik-tracker.md`.

## Front matter

The `daik` mapping records the workflow contract in machine-readable form:

- `schema_version`
- `language`
- `workflow_pack`
- `tracker_pack`
- `tracker_instructions`
- `phases`
- `issue_actions`

## Portable tracker operations

Workflow packs may require these provider-independent operations:

- `issue.list_ready`
- `issue.read`
- `issue.create`
- `issue.set_status`
- `issue.assign`
- `issue.add_dependency`
- `issue.remove_dependency`
- `issue.close`

Workflow packs may also request composed actions:

- `issue.claim`
- `issue.set_phase`
- `issue.comment`
- `issue.link`
- `issue.block`
- `issue.complete`

`issue.set_status` and `issue.set_phase` accept workflow-defined strings.
`issue.close` accepts `completed`, `duplicate`, `superseded`, or `cancelled`.
Tracker packs specify how
each operation and phase is represented by the selected tracker.

Provider-specific extensions use a provider namespace, such as
`github.request_review`.

## Tool binding

Tracker packs describe operations but do not install skills or MCP servers.
The user selects the actual tracker tool and replaces the
`<<DAIK:TRACKER_TOOL>>` placeholder in `.agents/daik-tracker.md`.

The tracker document front matter records its `tracker_pack` and `provides`
capabilities. Its Markdown body maps portable actions to provider operations.
