---
daik:
  schema_version: 1
  artifact: beads-compatibility-spec
  ownership: daik
  user_action: reference
  tracker_pack: daik.tracker.beads
  contract_revision: 1
  reference_version: "1.0.4"
---

# Beads compatibility contract for daik

This file records the Beads behavior assumed by `daik.tracker.beads`. Version
`1.0.4` is the reference version used when this contract was written. Version
comparison alone does not establish compatibility; compatible installations
must satisfy the capabilities below.

## Required issue data

- stable string issue ID
- title and description text
- status supporting `open`, `in_progress`, `blocked`, and `closed`
- project-defined custom statuses for every workflow phase not built into Beads
- optional assignee with a conditional or atomic claim that does not steal an
  existing assignment
- labels, including arbitrary `daik:*` values
- directed blocking dependencies
- append-only notes or an equivalent discussion history
- external references or another non-destructive place for typed artifact URLs
- human-readable close summary
- arbitrary metadata containing the string key `daik.close_reason`

## Required close reasons

`daik.close_reason` must accept exactly these contract values:

- `completed`: requested work and validation finished
- `duplicate`: another issue represents the same work
- `superseded`: another issue or design replaced this work
- `cancelled`: the work was intentionally abandoned

Provider-native close text may contain a longer explanation, but it must not
replace the machine-readable daik reason.

## Required behavior

- Ready selection excludes closed, blocked, deferred, and dependency-blocked
  issues, then applies all configured required labels.
- Assignment used for claiming is race-safe and cannot silently overwrite a
  different assignee.
- Status stores the exact workflow value rather than a lossy approximation.
- Adding and removing one dependency does not disturb unrelated dependencies.
- Appending a comment or link does not replace existing notes or links.
- Closing preserves both the enumerated daik reason and human summary.

## Compatibility policy

- `PASS`: observed version and all required data and behavior are supported.
- `FAIL`: at least one required capability is absent or behaves incompatibly.
- `UNKNOWN`: access is insufficient to verify a requirement without mutation.

Do not infer compatibility solely because the installed version is newer than
the reference version. Do not mutate a live tracker merely to perform a check.

