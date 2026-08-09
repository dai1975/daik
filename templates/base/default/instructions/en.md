---
daik:
  schema_version: 1
  artifact: agents-template
  ownership: daik
  user_action: copy-and-customize
---

# daik AGENTS.md integration guide

Do not copy this entire file into `AGENTS.md`. Copy only the section enclosed by
`DAIK:COPY:BEGIN` and `DAIK:COPY:END`, then replace
`<<DAIK:WORKSPACE_GUIDE>>` with the actual guidance or a link to it.

## Section to copy into AGENTS.md

<!-- DAIK:COPY:BEGIN -->
## Issue-driven development with daik

For work assigned through an issue tracker, follow the process defined in
`.agents/daik-workflow.yaml`. Its format and portable operations are defined in
`.agents/daik-workflow-spec.md`, and daik runtime settings are stored in
`.agents/daik-config.yaml`. Runtime issue events are defined in
`.agents/daik-issue-event-spec.md`. Follow `.agents/daik-tracker.md` for concrete issue
tracker operations. Writable checkouts for individual issues are created under
`workspaces/`.

`.daik/` is an internal management area for daik and human operators. Do not
read or modify it during normal issue investigation, implementation, testing,
or review. Access it only when explicitly asked to set up, configure, or update
daik itself.

### Workspace guide

<<DAIK:WORKSPACE_GUIDE>>
<!-- DAIK:COPY:END -->

## Guidance the user must provide

Replace `<<DAIK:WORKSPACE_GUIDE>>` with this information or links to documents
that provide it:

- repositories in the workspace and their roles
- locations of reference material, generated files, and other resources
- distinction between regular checkouts and checkouts under `workspaces/`
- writable and read-only areas for agents
- project-specific entry points for build, test, and review
