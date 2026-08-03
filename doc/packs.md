# daik pack format

[日本語](packs.ja.md)

A daik pack is a unit of static instructions and configuration selected and
composed by `daik site init`. Packs do not install or execute skills, MCP
servers, or execution hooks.

## Discovery

daik recursively searches the built-in `templates/` directory and directories
added with `--template-dir`. Hidden directories, including `.git`, are not
searched.

Every pack has a `pack.yaml` at its root. Packs are identified as base,
workflow, or tracker packs by the manifest's `kind` field, not by their
filesystem location.

## Manifest

```yaml
schema_version: 1
id: example.workflow.standard
key: standard
kind: workflow
version: 1
name:
  ja: 標準ワークフロー
  en: Standard workflow
languages:
  - ja
  - en
daik_config: daik-config/workflow.yaml
phases:
  - implementation
  - testing
  - review
requires:
  - issue.read
  - issue.set_phase
  - issue.complete
provides:
  - example.optional-capability
contributions:
  workflow:
    ja: workflow/ja.md
    en: workflow/en.md
files_user:
  config/example.yaml: .agents/example.yaml
files_daik:
  spec/example.md: .agents/example-spec.md
```

### Fields

- `schema_version`: currently `1`
- `id`: an ID unique across all packs
- `key`: a short name accepted by the CLI; defaults to the final component of
  the ID
- `kind`: one of `base`, `workflow`, or `tracker`
- `version`: an integer version of the pack format
- `name`: display names by language
- `languages`: natural languages provided by the pack
- `daik_config`: optional pack-relative YAML fragment appended to the generated
  `.agents/daik-config.yaml`
- `phases`: workflow phases; required for workflow packs
- `requires`: capabilities required by a workflow from its tracker
- `provides`: capabilities implemented by a tracker
- `contributions`: localized Markdown fragments
- `files_user`: user-owned files placed only on first initialization
- `files_daik`: static files recorded as daik-owned

Config fragments are composed in base, workflow, and tracker order. A pack
should contribute only the top-level configuration that belongs to its own
responsibility. For example, the base pack owns `workspace`, `agent`, and
`polling`, while a tracker pack owns `tracker`.

Because daik uses a built-in dependency-free parser, manifests are restricted
to a simple YAML subset containing mappings, lists of scalars, strings,
integers, and booleans.

## Contributions

The currently supported contribution slots are:

- `agents`: appended to `.daik/daik-AGENTS.md.template`
- `internal`: appended to `.daik/AGENTS.md`
- `workflow`: appended to the workflow portion of
  `.agents/daik-workflow.md`
- `tracker`: appended to `.agents/daik-tracker.md`

Each value maps a language to a path relative to the pack. If the requested
language is unavailable but English is present, daik falls back to English. If
neither is available, initialization stops.

An `agents` document must clearly separate the explanation of the template,
the copyable section enclosed by `DAIK:COPY:BEGIN` and `DAIK:COPY:END`, and
user-replaceable placeholders in the form `<<DAIK:...>>`.

## Capabilities

Portable tracker operations use the `issue.*` namespace:

- `issue.read`
- `issue.create`
- `issue.claim`
- `issue.set_phase`
- `issue.comment`
- `issue.link`
- `issue.block`
- `issue.complete`

A workflow may freely define values passed to `issue.set_phase`.
Provider-specific operations use a provider namespace, such as
`github.request_review`.

## Safety

- Source and target paths cannot escape the pack or site, including through
  symlinks
- Initialization fails if selected packs provide different content for the same
  target
- Existing project files are never overwritten
- Programs and hooks contained in packs are never executed
- Users select and install skills, MCP servers, and CLIs separately
