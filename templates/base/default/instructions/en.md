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
`<<DAIK:SITE_GUIDE>>` with the actual guidance or a link to it.

## Section to copy into AGENTS.md

<!-- DAIK:COPY:BEGIN -->
## Issue-driven development with daik

For work assigned through an issue tracker, follow the process defined in
`.agents/daik-workflow.yaml`. Its format and portable operations are defined in
`.agents/daik-workflow-spec.md`. Runtime issue events are defined in
`.agents/daik-issue-event-spec.md`. Follow `.agents/daik-tracker.md` for concrete issue
tracker operations, and follow `.agents/daik-worker.md` for worker permissions and
responsibilities. The CLI wrapper protocol is defined in
`.agents/daik-agent-context-spec.md`. Writable checkouts for individual issues are
created under `workspaces/`.

`.daik/` is an internal management area for daik and human operators. Do not
read or modify it during normal issue investigation, implementation, testing,
or review. Access it only when explicitly asked to set up, configure, or update
daik itself.

### Site guide

<<DAIK:SITE_GUIDE>>
<!-- DAIK:COPY:END -->

## Guidance the user must provide

Replace `<<DAIK:SITE_GUIDE>>` with this information or links to documents
that provide it:

- source repositories in the site and their roles
- locations of reference material, generated files, and other resources
- distinction between source checkouts in the site and generated Issue
  checkouts under `workspaces/`
- writable and read-only areas for agents
- project-specific entry points for build, test, and review

ex:

```
### Workspace guide

Per-issue checkouts are created under `workspaces/` according to the
`repositories` configuration in `.agents/daik-config.yaml`.

- `daik`: The daik codebase. This is the target for implementation and testing.
- `.agents/`: Site configuration and workflow instructions. Treat this directory
  as read-only during normal Issue work.

Limit all edits to the assigned checkout within the Issue workspace.
```
