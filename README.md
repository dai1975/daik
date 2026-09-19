# daik

[日本語](README.ja.md)

`daik` is a collaboration harness for personal development that connects issue
trackers with coding agents.

It takes issues as units of work, prepares an isolated workspace for each issue,
and runs coding agents. Development processes and tracker-operation instructions
are deployed into the user's development environment, where they can be freely
customized.

The name comes from 大工, the Japanese word for carpenter.

> [!NOTE]
> daik is currently in an early stage of development. The `init`, `validate`,
> and `doctor` commands can deploy and diagnose a site. GitHub Issues and Beads
> mappings, agent execution, and single-Issue broker execution are available.
> Polling, concurrent execution, and retry are available through `work watch`.

## Goals

- Use an issue tracker as a work queue for coding agents
- Create an independent workspace for each issue and run multiple agents safely
  in parallel
- Version development processes and agent instructions in the development
  environment
- Support development involving multiple repositories and external reference
  material, not only a single repository
- Let users own generated configuration and customize it for each environment
- Minimize dependencies on any particular coding agent or issue tracker

daik is not intended to be a general-purpose workflow engine or a project
management tool that dictates repository layout. Users decide where to place
repositories, design documents, and other resources.

## Usage

A directory that serves as the coding agent's root and collects repositories,
documents, and other development resources is called a **site**.

First, create a site and place daik, the repositories being developed, and
resources outside those repositories inside it. The following example uses
separate backend and frontend repositories.

```sh
mkdir my-site
cd my-site

git clone git@github.com:dai1975/daik
git clone git@github.com:user/backend
git clone git@github.com:user/frontend

mkdir -p resources ref/rfc
```

Workflows and trackers are distributed in units called **packs**. List the
available packs with:

```sh
./daik/daik site packs
```

Initialize the site by selecting a natural language, workflow pack, and tracker
pack.

```sh
./daik/daik site init \
  --lang en \
  --workflow standard \
  --tracker github-issues \
  --wet-run
```

Without `--wet-run`, the command only previews its changes and does not write
any files.

```sh
./daik/daik site init
```

When `--root` names a missing directory, `--wet-run` creates that directory and
its parents before deploying the site. Preview mode reports the directory but does
not create it.

```sh
./daik/daik site init --root ../new-site --wet-run
```

`site init` never overwrites existing files, so it is safe to run again with
the same pack selection. If a different language or pack selection is requested
for an initialized site, daik stops to avoid making the manifest inconsistent
with user-owned files.

Run daik from the `my-site/` root, not from `backend/` or `frontend/`. Resource
layout is otherwise unrestricted.

```text
my-site/
├── AGENTS.md
├── .agents/
├── .daik/
├── workspaces/
├── backend/                  # Git repository
├── frontend/                 # Git repository
├── resources/                # Images and other files not stored on GitHub
└── ref/
    └── rfc/                  # Reference documents and standards
```

Describe the purpose of each directory, build and test commands, and areas that
agents may edit in `AGENTS.md` or in documents linked from it.

### Commands

Commands currently available:

```sh
daik site packs
daik site init
daik site validate
daik site doctor
daik work workspace create
daik work workspace show
daik work workspace list
daik work workspace reconcile
daik work workspace remove
daik work handoff create
daik work agent run
daik work run
daik work watch
daik work status
```

- `site packs`: list available packs
- `site init`: preview deployment; write files only when `--wet-run` is supplied
- `site validate`: validate the local site contract without accessing external services
- `site doctor`: validate the contract and diagnose local tools and runtime readiness
- `work workspace`: create, inspect, reconcile, and remove per-issue Git worktrees
- `work handoff create`: emit a structured event for the next agent role
- `work agent run`: invoke one agent state and emit transition and handoff events
- `work run`: run the broker for one claimed Issue until it stops or reaches a final state
- `work watch`: poll ready Issues and run up to the configured concurrency limit
- `work status`: show the latest local broker run without contacting the tracker

After copying and customizing the `AGENTS.md` block and reviewing the generated
files, validate the site with:

For an existing site, rerun `site init --wet-run` to regenerate the daik-owned
template, then copy and customize its tagged block again. The command does not
overwrite the user-owned root `AGENTS.md`.

```sh
./daik/daik site validate
```

The command checks document metadata and syntax, workflow/tracker capabilities,
configuration values, unresolved placeholders, manifest consistency, and the
integrity of daik-owned files. Errors produce exit status 1; warnings and
informational messages do not.

For broader environment diagnostics, run:

```sh
./daik/daik site doctor
```

In addition to validation, doctor checks Git, discovers checkouts outside the
per-issue workspace area, and verifies that the configured workspace directory
is writable. For the built-in GitHub wrapper it also requires GitHub CLI 2.94.0
or newer, which provides the Issue dependency fields used by ready selection.
For broader tracker compatibility it points to the selected pack's
read-only compatibility skill, because tracker access may use a skill, MCP
server, CLI, or another method.

### Process environments

`.daik/config.yaml` assigns the broker and every workflow role to exactly one
top-level `processes` entry. A process receives a small baseline environment
(`PATH`, `HOME`, locale, and temporary-directory variables) plus only its own
`env` mappings. Use `from_env` to alias a parent variable or `value` for a
non-secret literal; `required: true` fails immediately before that process is
started. Parent variable names and settings from other processes are not
implicitly inherited or merged. Existing sites must add one `type: broker`
entry and complete, non-overlapping `type: agent` role assignments.

Display help with:

```sh
./daik/daik --help
./daik/daik site init --help
./daik/daik work workspace --help
```

Configure source repositories in `.daik/config.yaml` before creating a
workspace:

```yaml
repositories:
  backend:
    path: backend
    base: main
  frontend:
    path: frontend
    base: main
```

Create or reuse one worktree per configured repository:

```sh
./daik/daik work workspace create github:backend#123
```

The command prints a `daik.issue-event.v1` JSON object. Post that complete event
to the issue using the access method configured in `.agents/daik-tracker.md`.
daik stores no runtime workspace metadata in `.daik/`; Git is the local source
of truth and append-only issue events are the shared source of truth.

At a role boundary, generate a handoff event for the next agent:

```sh
./daik/daik work handoff create github:backend#123 \
  --from implementation \
  --to review \
  --phase review \
  --summary "Implementation and tests completed" \
  --validation "All pytest tests passed" \
  --next-action "Review retry boundaries"
```

`workspace remove` previews by default and requires `--wet-run` to remove
worktrees. It never deletes issue branches.

Enable the built-in Codex CLI wrapper. It translates the common daik Invocation to
non-interactive `codex exec` without putting Codex-specific behavior in the runner:

```yaml
agent:
  cli_wrapper: codex
  wrapper_options:
    sandbox: workspace-write
  timeout_seconds: 3600
```

Run exactly one workflow agent state:

```sh
./daik/daik work agent run github:backend#123 --state implementation
```

The command runs from the site root and prints newline-delimited `agent.started`,
`agent.completed`, and `handoff` events. A tracker wrapper must append these complete
events to the issue. Agent or protocol failure instead emits `agent.failed`. See
`.agents/daik-agent-context-spec.md` for the Invocation and CLI wrapper contracts.
Invocation records are stored outside the site under `DAIK_STATE_HOME`,
`$XDG_STATE_HOME/daik`, or `$HOME/.local/state/daik`, in that order. When discoverable,
the record links to Codex's native session transcript.

Local state is separated by responsibility:

```text
sites/<site-id>/
├── invocations/<issue-id>/<invocation-id>/
└── broker-runs/<broker-run-id>/
    ├── metadata.json
    └── events.ndjson
```

The GitHub Issues pack enables the built-in `github-gh` tracker wrapper. It uses the
authenticated `gh` account and resolves the GitHub repository from each source
checkout configured under `repositories`:

```yaml
tracker:
  wrapper: github-gh
```

Run `gh auth status` before starting the broker. Custom tracker wrappers can instead
be configured as an argv list implementing `.daik/tracker-wrapper-spec.md`.

Then claim and process one Issue:

```sh
./daik/daik work run github:backend#123
```

The tracker retains the authoritative current state and control events. A human state
stops execution; after recording the human decision on the Issue, resume through one
declared edge with `--transition NAME`.

A workflow can run deterministic validation without an LLM by using a `program`
state. The command is an argv sequence and runs directly in the named repository's
Issue worktree:

```yaml
testing:
  type: program
  command: [make, test]
  repository: backend
  timeout_seconds: 900
  transitions:
    succeeded:
      to: review
    failed:
      to: implementation
    error:
      to: await_human
```

Exit status zero selects `succeeded`, another normal exit selects `failed`, and an
execution failure or timeout selects `error`. Full output remains in the external
Invocation logs; bounded result data is recorded on the Issue.

Continuously poll and execute ready work with:

```sh
./daik/daik work watch
```

`agent.max_concurrent_agents` limits concurrent Issue runs. Polling uses
`polling.interval_ms`; transient polling and broker failures use capped exponential
backoff configured by `polling.max_retries`, `polling.retry_initial_ms`, and
`agent.max_retry_backoff_ms`. A claim conflict is skipped rather than retried. After
exhausting retries, an Issue is suppressed until the watch process restarts.

Use `--once` to perform one poll and wait for the submitted work, which is useful for
scheduled jobs and diagnostics.

Inspect the latest broker run, or select one by ID:

```sh
daik work status
daik work status --run BROKER_RUN_ID
daik work status --json
```

Status reads only local broker-run records. Issue workflow state and handoff data
remain authoritative in the tracker.

## Site

A **site** is the root directory in which coding agents work. It is not a single
Git repository. It is a container for multiple repositories related to one
development effort, material and resources outside those repositories, daik
configuration, and per-issue workspaces. A coding agent's current working
directory is also the site root.

daik does not prescribe where repositories and documents are placed within a
site. Explain the layout and writable areas to agents in the root `AGENTS.md` or
in documents linked from it.

The site directory itself may be managed as a Git repository. In that case,
site-wide `AGENTS.md` instructions, daik configuration, and shared documents can
be versioned there. Repositories inside the site may be submodules or excluded
by the site's `.gitignore`.

### Site contract

daik reserves names and roles only for the following elements:

```text
my-site/
├── AGENTS.md
├── .agents/
│   ├── daik-workflow.yaml
│   ├── daik-tracker.md
│   ├── daik-worker.md
│   ├── daik-workflow-spec.md
│   ├── daik-issue-event-spec.md
│   └── daik-agent-context-spec.md
├── .daik/
│   ├── .ignore
│   ├── AGENTS.md
│   ├── config.yaml
│   ├── daik-AGENTS.md.template
│   ├── tracker-wrapper-spec.md
│   └── manifest.json
└── workspaces/
```

#### `AGENTS.md`

This file describes the entire site and its permanent development rules.

`AGENTS.md` is always user-owned. daik never creates, changes, or overwrites it.
Instead, daik writes suggested additions to
`.daik/daik-AGENTS.md.template`. Copy only the section enclosed by
`DAIK:COPY:BEGIN` and `DAIK:COPY:END` into the existing `AGENTS.md`, then
replace `<<DAIK:SITE_GUIDE>>` with site-specific guidance. Explanations of
the template itself and instructions for the user remain outside the copy block.

#### `.agents/daik-workflow.yaml`

This file defines the provider-independent development process as a deterministic
state machine. The graph declares every possible transition; agents evaluate its
natural-language conditions but cannot invent or skip states. It also records the
selected packs and required issue actions in a machine-readable form.

After `init` creates it, the user owns it and may adapt it to the site. Its file
contract is defined in `.agents/daik-workflow-spec.md`. For the concrete
implementation of tracker actions, it refers to `.agents/daik-tracker.md`.

#### `.agents/daik-tracker.md`

This file defines how issue actions requested by the workflow are implemented
on the selected tracker. Its front matter records the tracker pack and actions
it provides; its Markdown body maps those actions to concrete labels, states,
and other provider operations.

daik packs do not install skills or MCP servers. The user selects the skill,
MCP server, or CLI used to operate the tracker and replaces
`<<DAIK:TRACKER_TOOL>>` with concrete usage instructions.

#### `.agents/daik-worker.md`

This user-owned file separates worker responsibilities from broker control.
Workers record substantive work on the issue but do not modify claim, workflow state,
visit count, or retry data. The daik-owned agent-context specification defines the
Invocation and CLI wrapper protocols.

#### `workspaces/`

This directory contains an isolated work area for each issue.

```text
workspaces/
├── GH-123/
└── GH-124/
```

daik does not fix the internal layout of an issue workspace. It may contain one
Git worktree or worktrees from multiple repositories. The agent's current
working directory remains the site root, while actual changes are made in the
assigned checkout under `workspaces/<issue>/`.

Workspace and agent state are not written to `.daik/`. Commands emit structured
events defined by `.agents/daik-issue-event-spec.md`; tracker packs describe how
to append them to each issue. A receiving agent reads the latest workspace and
handoff events before continuing the task.

### File ownership

Files have explicit roles and owners so that initialization and future updates
do not destroy user changes.

| File | Kind | Ownership | User action |
| --- | --- | --- | --- |
| `AGENTS.md` | Agent instructions | User | Incorporate the copy block and document the site |
| `.daik/daik-AGENTS.md.template` | Integration guide | daik | Use only the copy block |
| `.agents/daik-workflow.yaml` | Workflow | User | Review and customize the process |
| `.agents/daik-tracker.md` | Tracker guide | User | Review the operation mapping and placeholder |
| `.agents/daik-worker.md` | Worker policy | User | Review worker permissions and responsibilities |
| `.daik/config.yaml` | Runtime config | User | Review tracker and execution settings |
| `.agents/daik-workflow-spec.md` | Reference | daik | Normally read-only |
| `.agents/daik-issue-event-spec.md` | Issue event contract | daik | Normally read-only |
| `.agents/daik-agent-context-spec.md` | Invocation and CLI wrapper contract | daik | Normally read-only |
| `.daik/tracker-wrapper-spec.md` | Tracker wrapper contract | daik | Normally read-only |
| `.daik/manifest.json` | Operation record | daik | Not used during development |

Generated documents also identify these roles themselves. Markdown files record
`artifact`, `ownership`, and `user_action` in the `daik` front-matter mapping;
the config uses `daik_document`, and the manifest uses its `document` object.

`.daik/` is an internal management area for daik and human operators. To keep
it out of normal coding-agent discovery, daik writes `.daik/.ignore` and
instructs agents in both `.daik/AGENTS.md` and the root `AGENTS.md` copy block
not to inspect it unless they are maintaining daik itself.

## Architecture

daik is inspired by [OpenAI Symphony](https://github.com/openai/symphony),
which monitors an issue tracker and runs coding agents in per-issue workspaces.

```text
Issue tracker
      │
      ▼
Tracker wrapper
      │ normalized Issue
      ▼
Agent Work Broker
      │
      ├── Workspace manager
      │       └── workspaces/<issue>/
      │
      └── Agent runner
              └── coding agent
```

It follows Symphony's separation of scheduler, tracker wrapper, workspace
manager, and agent runner responsibilities, while emphasizing configuration
and workflows that are deployed into and directly editable within a personal
site.

The broker manages issue selection, concurrency, retries, stopping, and
the workspace lifecycle. Concrete issue-processing policy lives in
`.agents/daik-workflow.yaml` and `.agents/daik-tracker.md`, keeping site-specific
knowledge out of the broker itself. A future LLM orchestrator may perform semantic
management work, but it will run as an agent worker selected and controlled by the
broker.

### Packs

`site init` composes three kinds of packs: base, workflow, and tracker.

```text
templates/
├── base/default/
│   └── pack.yaml
├── workflow/standard/
│   └── pack.yaml
└── tracker/
    ├── github-issues/
    │   └── pack.yaml
    └── beads/
        └── pack.yaml
```

- A base pack provides site-wide instructions such as suggested additions to
  `AGENTS.md`
- A workflow pack defines the state machine, agent profiles, and required tracker actions
- A tracker pack defines how abstract actions are implemented with a provider
  such as GitHub Issues

A workflow pack's `requires` capabilities are matched against a tracker pack's
`provides` capabilities, such as `issue.read`, `issue.set_phase`, and
`issue.complete`. Incompatible combinations are rejected before files are
created.

Packs may provide instructions in Japanese and English, selected with
`--lang ja` or `--lang en`. See [doc/packs.md](doc/packs.md) for the complete
pack format.

The GitHub Issues and Beads packs define provider data changes while leaving
access through a skill, MCP server, CLI, or another method to the user. See
[doc/trackers.md](doc/trackers.md) for the common contract and provider mappings.

#### Third-party packs

daik recursively searches for `pack.yaml` below configured template
directories. Clone or add a third-party repository as a submodule below
`templates/` to make its packs selectable like built-in packs. One repository
may provide multiple packs.

Use `--template-dir` when packs are stored elsewhere.

```sh
./daik/daik site packs --template-dir ../community-packs

./daik/daik site init \
  --workflow example.workflow.custom \
  --tracker github-issues \
  --template-dir ../community-packs \
  --wet-run
```
