---
name: daik-check-beads-compatibility
description: Check whether the Beads instance selected by a daik site satisfies daik's recorded Beads data-model contract. Use only when the user explicitly asks to check, verify, audit, or diagnose Beads compatibility for the site.
---

# Check daik Beads compatibility

Perform a read-only, evidence-based compatibility audit. Do not assume `bd` is
available: use the skill, MCP server, CLI, or other access method configured by
the user in `.agents/daik-tracker.md`.

## Procedure

1. Confirm that `.agents/daik-config.yaml` selects `daik.tracker.beads`.
2. Read `.daik/beads-spec.md`. This explicit user request authorizes reading
   that otherwise-internal file; do not inspect unrelated `.daik/` content.
3. Read `.agents/daik-workflow.md` for its phases and
   `.agents/daik-tracker.md` for the configured Beads access method.
4. Obtain the Beads implementation version through that access method. If the
   method exposes no version, record it as `UNKNOWN`; do not substitute a local
   `bd` executable unless the tracker instructions select it.
5. Verify each required data field and behavior from the compatibility spec.
   Prefer schema, configuration, capability, and existing-issue reads.
6. Do not create or modify a probe issue. If a behavior cannot be established
   without mutation, mark it `UNKNOWN` and describe the smallest optional probe
   a user could authorize separately.
7. Report the installed version, reference version, and one `PASS`, `FAIL`, or
   `UNKNOWN` result for each requirement group: statuses, custom workflow
   phases, assignment/claim, labels, dependencies, append-only discussion,
   artifact links, close reason metadata, ready selection, and close behavior.
8. Finish with an overall result: `FAIL` if any group fails, `UNKNOWN` if none
   fail but any are unknown, otherwise `PASS`.

Include concise evidence for every failure or unknown. Make no configuration or
tracker changes during the audit.
