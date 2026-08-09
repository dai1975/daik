---
name: daik-check-github-issues-compatibility
description: Check whether the GitHub Issues repository and access method selected by a daik site satisfy daik's recorded GitHub Issues contract. Use only when the user explicitly asks to check, verify, audit, or diagnose GitHub Issues compatibility for the site.
---

# Check daik GitHub Issues compatibility

Perform a read-only, evidence-based compatibility audit. Do not assume `gh` is
available: use the skill, MCP server, CLI, or other access method configured by
the user in `.agents/daik-tracker.md`.

## Procedure

1. Confirm that `.agents/daik-config.yaml` selects
   `daik.tracker.github-issues`.
2. Read `.daik/github-issues-spec.md`. This explicit user request authorizes
   reading that otherwise-internal file; do not inspect unrelated `.daik/`
   content.
3. Read `.agents/daik-workflow.yaml` for its states and portable actions, and
   `.agents/daik-tracker.md` for the target repository and access method.
4. Determine the GitHub product and API version exposed by that access method.
   If unavailable, record it as `UNKNOWN`; do not substitute a local `gh`
   executable unless the tracker instructions select it.
5. Verify each required data field, repository feature, and permission from the
   compatibility spec. Prefer capability, repository configuration, label,
   dependency, and existing-issue reads.
6. Do not create or modify a probe issue. If behavior cannot be established
   without mutation, mark it `UNKNOWN` and describe the smallest optional probe
   a user could authorize separately.
7. Report the observed API/product version, reference API version, and one
   `PASS`, `FAIL`, or `UNKNOWN` result for each requirement group: issue fields,
   labels, workflow status, assignees/claim serialization, native dependencies,
   comments, artifact links, close state reason, daik close-reason label, ready
   selection, and required read/write permissions.
8. Finish with an overall result: `FAIL` if any group fails, `UNKNOWN` if none
   fail but any are unknown, otherwise `PASS`.

Include concise evidence for every failure or unknown. Make no repository or
tracker changes during the audit.
