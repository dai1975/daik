---
daik:
  schema_version: 1
  artifact: worker-policy
  ownership: user
  user_action: review-and-customize
---

# daik worker policy

- Read the assigned issue and its latest handoff events before acting.
- Record investigation, implementation details, questions, validation evidence,
  review findings, commits, and artifact links directly on the issue.
- Do not change the issue claim, workflow state, visit count, retry state, or other
  orchestrator-owned control data.
- Work only on the current workflow state's task. Do not skip ahead to the next state.
- Modify only the assigned checkouts under `workspaces/` and follow the site's
  `AGENTS.md` instructions.
- Return one declared transition with concise evidence through the daik result protocol.
