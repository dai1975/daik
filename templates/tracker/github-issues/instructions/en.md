## GitHub Issues operations

This project uses GitHub Issues as its issue tracker.

- `issue.read`: Read the issue body, comments, labels, and linked pull requests.
- `issue.create`: Create an issue with a title and acceptance criteria in its body.
- `issue.claim`: Remove `daik:ready` and add `daik:running`.
- `issue.set_phase(<phase>)`: Remove existing `daik:phase:*` labels and add
  `daik:phase:<phase>`.
- `issue.comment`: Add progress, decisions, and validation results as comments.
- `issue.link`: Add the artifact type and URL as a comment.
- `issue.block`: Remove `daik:running`, add `daik:blocked`, and comment with the
  reason and input required to resume.
- `issue.complete`: Comment with the change and validation results, remove work
  labels, and close the issue.

## Tracker tool

Use the following skill, MCP server, or CLI to read and write GitHub Issues:

<<DAIK:TRACKER_TOOL>>
