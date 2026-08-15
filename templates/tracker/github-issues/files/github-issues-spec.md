---
daik:
  schema_version: 1
  artifact: github-issues-compatibility-spec
  ownership: daik
  user_action: reference
  tracker_pack: daik.tracker.github-issues
  contract_revision: 2
  reference_api_version: "2026-03-10"
---

# GitHub Issues compatibility contract for daik

This file records the GitHub Issues behavior assumed by
`daik.tracker.github-issues`. GitHub REST API version `2026-03-10` is the
reference API version used when this contract was written. Access may use a
skill, MCP server, CLI, GraphQL, REST, or another mechanism; it need not expose
the REST API directly if it provides equivalent behavior.

## Required issue data

- stable repository identity and issue number or node ID
- title and body text
- open/closed state and close state reason
- zero or more assignees
- arbitrary repository labels, including `daik:*` labels
- native blocked-by and blocking issue dependencies
- append-only issue comments
- linked pull requests or another non-destructive representation of typed URLs

## daik status and close reason

GitHub's open/closed state is not used for intermediate workflow status.
Exactly one `daik:status:<status>` label stores the current daik status.

Exactly one `daik:close-reason:<reason>` label stores one of:

- `completed`: requested work and validation finished
- `duplicate`: another issue represents the same work
- `superseded`: another issue or design replaced this work
- `cancelled`: the work was intentionally abandoned

Use GitHub state reason `completed` for daik `completed`, and `not_planned` for
the other three reasons. Preserve the human summary in a close comment.

## Required behavior

- Ready selection requires open state, all configured required labels, a
  non-blocked daik status, and no unresolved blocked-by dependencies. Broker polling
  also includes non-final daik work eligible for crash recovery.
- Claiming is serialized by the broker and verifies that it did not replace
  a different assignee; GitHub assignment alone is not treated as atomic.
- Replacing a status or close-reason label removes other labels in the same
  namespace without disturbing unrelated labels.
- Adding and removing one native dependency does not disturb unrelated ones.
- Comments and artifact links are appended without replacing history.
- Closing preserves GitHub state reason, enumerated daik reason, and summary.

## Compatibility policy

- `PASS`: the configured access method supports every required read and write
  capability for the target repository.
- `FAIL`: at least one required capability or permission is absent.
- `UNKNOWN`: access is insufficient to verify a requirement without mutation.

Do not infer compatibility from API version alone. Do not mutate a live
repository merely to perform a check.

## Built-in `gh` wrapper

The `github-gh` tracker wrapper uses the authenticated GitHub CLI account. It
resolves every configured source checkout with `gh repo view`, selects work with
`gh issue list`, and stores control events in append-only Issue comments. Dynamic
`daik:*` labels are created when first needed.

The wrapper requires GitHub CLI 2.94.0 or newer. That release added the Issue 2.0
dependency fields and commands used to read `blockedBy` and manage blocked-by and
blocking relationships. `daik site doctor` reports an error for an older or
unparseable `gh` version. Relationships require GitHub.com or GitHub Enterprise
Server 3.19 or newer; the compatibility skill verifies the server separately.

The wrapper checks the event-derived control version immediately before writing and
rejects an Issue assigned to a different actor. GitHub does not provide one atomic
compare-and-set operation spanning comments, labels, assignees, and Issue state, so
only one broker using the same GitHub account should control a site at a time. Event
comments remain authoritative if a later mirror update fails.
