## Beads tracker mapping

This project uses Beads as its issue tracker. These instructions define the
required Beads data changes, not how to perform them. Use the user-configured
skill, MCP server, or other access method below.

<<DAIK:TRACKER_TOOL>>

### daik operations and Beads representation

- `issue.list_ready`: Select non-closed, unblocked beads that contain every
  configured required label and whose dependencies are satisfied.
- `issue.read`: Read the bead's ID, title, description, status, assignee,
  labels, dependencies, notes, external references, and close information.
- `issue.create`: Create a bead with the requested title and description. Add
  labels, assignee, and dependencies when supplied.
- `issue.set_status(<status>)`: Store the exact workflow-defined value in the
  Beads `status` field. The Beads project must declare non-built-in values as
  custom statuses.
- `issue.assign(<actor>)`: Set the Beads `assignee`. Assignment used as a claim
  must fail rather than replace a different current assignee.
- `issue.add_dependency(<blocker>)`: Add a blocking dependency in which the
  current bead depends on `<blocker>`.
- `issue.remove_dependency(<blocker>)`: Remove that blocking dependency.
- `issue.comment(<message>)`: Append the message to Beads notes or the
  configured append-only discussion field; do not replace earlier content.
- `issue.link(<kind>, <url>)`: Preserve the artifact kind and URL in external
  references or append-only notes. Do not overwrite an unrelated existing link.
- `issue.close(<reason>, <summary>)`: Set status to `closed`, retain the summary
  as the human-readable close reason, and store the daik reason in metadata as
  `daik.close_reason`. Allowed reasons are `completed`, `duplicate`,
  `superseded`, and `cancelled`.

The standard workflow's higher-level actions are compositions:

- `issue.claim`: atomically assign the worker, set status to `in_progress`,
  remove `daik:ready`, and add `daik:running`.
- `issue.set_phase(<phase>)`: set status to the exact phase value. A site may
  additionally mirror it in a `daik:phase:<phase>` label.
- `issue.block`: set status to `blocked`, record blocking dependencies when
  known, replace `daik:running` with `daik:blocked`, and append the reason.
- `issue.complete`: call `issue.close(completed, <summary>)` and remove transient
  daik work labels.

