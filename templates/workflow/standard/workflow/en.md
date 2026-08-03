# Standard issue workflow

## Objective

Understand the assigned issue, produce a verifiable change and pull request,
and hand the work safely to a human or the next stage.

## Process

Follow `.agents/daik-tracker.md` for the concrete execution of issue actions.

1. Read `AGENTS.md`, applicable instructions, the issue, and reference material.
2. Confirm the acceptance criteria and editable scope, then claim the issue.
3. Set phase to `implementation` and implement the change in the assigned
   checkout under `workspaces/`.
4. Set phase to `testing` and run relevant tests, lint, and type checks.
5. Set phase to `review` and inspect the final diff for correctness, scope, and
   sensitive information.
6. Set phase to `pull-request`, create a pull request, and link it to the issue.
7. Record the change and validation results on the issue, then complete it.

## Handoff

- If progress requires a user decision or additional authority, block the issue
  and record the reason and required input.
- Never report an unverified check as successful.
