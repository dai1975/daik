# Tracker contract

[日本語](trackers.ja.md)

The broker requests provider-independent issue operations. Tracker packs
map those operations to provider data while the user chooses the access method.

The provider-independent data operations are `issue.list_ready`, `issue.read`,
`issue.create`, `issue.set_status`, `issue.assign`, `issue.add_dependency`,
`issue.remove_dependency`, `issue.comment`, `issue.link`, and `issue.close`.
Close reasons are `completed`, `duplicate`, `superseded`, and `cancelled`.

Workflow actions such as `issue.claim`, `issue.set_phase`, `issue.block`, and
`issue.complete` are compositions of these data operations. Tracker packs map
both layers to provider data; they do not need to prescribe an access tool.

## GitHub Issues

The GitHub Issues pack specifies data-model changes and does not prescribe an
access method. The user configures a skill, MCP server, CLI, or another method
in `.agents/daik-tracker.md`.

| daik operation | GitHub representation |
| --- | --- |
| Ready queue | Open issues containing every configured required label |
| Status | Exactly one `daik:status:<status>` label |
| Assignment | GitHub assignee with broker-side claim serialization |
| Dependencies | Native blocked-by relationships |
| Claim | Assignment, `in_progress`, and work-label transition |
| Phase | Phase value in the daik status label |
| Comment/link | Issue comments |
| Block | Status, native dependencies, label, and reason comment |
| Close | GitHub state reason, summary comment, and daik close-reason label |

The generated `.daik/github-issues-spec.md` records REST API version
`2026-03-10` and required behavior. The
`daik-check-github-issues-compatibility` skill performs a read-only audit when
explicitly requested by the user.

## Beads

The Beads pack specifies data-model changes and does not prescribe an access
method. The user configures a skill, MCP server, CLI, or another method in
`.agents/daik-tracker.md`; an agent that understands that method performs the
required changes.

| daik operation | Beads representation |
| --- | --- |
| Ready queue | Unblocked beads containing every configured required label |
| Status | Exact daik workflow status in Beads `status` |
| Assignment | Beads `assignee`; claims must not steal an assignment |
| Dependencies | Directed blocking dependencies |
| Claim | Atomic assignment, `in_progress`, and work-label transition |
| Phase | Exact phase as status; optional mirrored phase label |
| Comment/link | Append to notes |
| Block | Status `blocked`, dependencies, label, and reason in notes |
| Close | Status `closed`, human summary, and `daik.close_reason` metadata |

The generated `.daik/beads-spec.md` records the reference Beads version and
required behavior. The `daik-check-beads-compatibility` skill performs a
read-only compatibility audit when explicitly requested by the user.
