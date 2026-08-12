## GitHub Issues tracker mapping

This project uses GitHub Issues as its issue tracker. These instructions define
the required GitHub data changes, not how to perform them. Use the
user-configured skill, MCP server, CLI, or other access method below.

<<DAIK:TRACKER_TOOL>>

### daik operations and GitHub representation

- `issue.list_ready`: Select open issues that contain every configured required
  label, are not in a blocked daik status, and have no unresolved blocked-by
  dependencies.
- `issue.read`: Read repository and issue identity, title, body, open/closed
  state, state reason, assignees, labels, dependencies, comments, and linked
  development artifacts.
- `issue.create`: Create an issue in the configured repository with the
  requested title and body. Add labels, assignees, and dependencies when given.
- `issue.set_status(<status>)`: Remove any existing `daik:status:*` label and add
  exactly one `daik:status:<status>` label. Keep the GitHub issue open unless the
  operation is `issue.close`.
- `issue.assign(<actor>)`: Set the GitHub assignee. Assignment used as a claim
  must not silently replace another worker; the broker must serialize and
  verify claims because GitHub assignment itself is not compare-and-set.
- `issue.add_dependency(<blocker>)`: Add a native blocked-by dependency from the
  current issue to `<blocker>`.
- `issue.remove_dependency(<blocker>)`: Remove that native dependency.
- `issue.comment(<message>)`: Append an issue comment.
- `issue.link(<kind>, <url>)`: Preserve the artifact kind and URL through a
  native development link when available, otherwise append a typed comment.
- `issue.close(<reason>, <summary>)`: Comment with the summary, close the issue,
  and preserve the daik reason in exactly one `daik:close-reason:<reason>` label.
  Map `completed` to GitHub state reason `completed`; map `duplicate`,
  `superseded`, and `cancelled` to `not_planned`.

Allowed daik close reasons are `completed`, `duplicate`, `superseded`, and
`cancelled`.

The standard workflow's higher-level actions are compositions:

- `issue.claim`: assign the worker, set daik status to `in_progress`, remove
  `daik:ready`, and add `daik:running`, with broker-side claim serialization.
- `issue.set_phase(<phase>)`: call `issue.set_status(<phase>)`. A site may also
  mirror it in a `daik:phase:<phase>` label for presentation.
- `issue.block`: set daik status to `blocked`, add native dependencies when
  known, replace `daik:running` with `daik:blocked`, and comment with the reason.
- `issue.complete`: call `issue.close(completed, <summary>)` and remove transient
  daik work labels.

### daik issue events

Append every `daik.issue-event.v1` object produced by daik as an issue comment.
Put `<!-- daik:issue-event:v1 -->` immediately before a fenced `json` block
containing the complete object. Never edit or replace earlier event comments.
Labels and assignees mirror current state for queries; event comments remain the
authoritative handoff and workspace history. Before starting work, read the
latest workspace event and latest `handoff` event.
