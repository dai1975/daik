---
daik:
  schema_version: 1
  artifact: tracker-joint-spec
  ownership: daik
  user_action: reference
---

# daik tracker joint protocol

Status: Draft v1

A tracker joint maps daik's semantic Issue control operations to one concrete tracker.
It is an external command, runs from the site root, reads one JSON request from stdin,
and writes one JSON response to stdout. Diagnostics go to stderr.

## Envelope

Requests use `protocol_version: daik.tracker-joint.v1`, an `operation`, and a
provider-native `issue` key. Responses use
`protocol_version: daik.tracker-joint-result.v1` and `status` equal to `ok`, `error`,
or `conflict`.

## Control version

`control_version` is an opaque compare-and-set token for broker-owned data. It
must change after every successful `issue.commit_control`. Worker comments and other
substantive Issue edits must not invalidate this token. This permits workers to write
their findings directly while serializing claim and workflow transitions.

## `issue.read_control`

The successful response contains the current `control_version` and all append-only
`daik.issue-event.v1` control events in order.

## `issue.commit_control`

The request contains `expected_control_version`, an `events` list, and optional
`status`, `claim`, and `close_reason`. The joint applies them as one control operation.
It must not replace an existing incompatible claim. On a stale token or claim race it
returns `status: conflict` without applying a partial update. Success returns the new
`control_version`.

`status` maps to the provider representation defined by `.agents/daik-tracker.md`.
`close_reason` is one of the portable reasons from the workflow specification.

## Idempotency and history

Issue events are append-only and retain complete JSON envelopes. A joint should reject
duplicate event identities when it can do so, and must preserve event ordering within
one commit. The Issue tracker remains the source of workflow state; local Invocation
logs are diagnostic artifacts only.
