# daik pack format

[English](packs.md)

daik packは`daik site init`が選択・合成する、静的な指示と設定の単位である。
packはskill、MCP server、実行hookをインストールまたは実行しない。

## Discovery

daikは組み込みの`templates/`と、`--template-dir`で追加されたディレクトリを
再帰的に探索する。`.git`を含む隠しディレクトリ内は探索しない。

各packはルートに`pack.yaml`を持つ。配置場所ではなくmanifestの`kind`によって
base、workflow、trackerを区別する。

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

- `schema_version`: 現在は`1`
- `id`: 全packで一意なID
- `key`: CLIで使える短い名前。省略時はIDの最後の要素
- `kind`: `base`、`workflow`、`tracker`のいずれか
- `version`: pack形式の整数バージョン
- `name`: 言語別の表示名
- `languages`: 提供する自然言語
- `daik_config`: 生成される`.agents/daik-config.yaml`へ追加する、pack内相対pathの
  YAML fragment。省略可能
- `phases`: workflowが使用する進行phase。workflow packでは必須
- `requires`: workflowがtrackerへ要求するcapability
- `provides`: trackerが実現するcapability
- `contributions`: 言語別Markdown断片
- `files_user`: 初回だけ配置するユーザー所有ファイル
- `files_daik`: daik所有として記録する静的ファイル

config fragmentはbase、workflow、trackerの順に合成する。各packは自身の責務に
属するtop-level設定だけを提供する。例えばbase packは`workspace`、`agent`、
`polling`を、tracker packは`tracker`を所有する。

組み込みのdependency-free parserを使用するため、manifestはmapping、scalarの
list、文字列、整数、booleanからなる単純なYAMLに限定する。

## Contributions

現在のcontribution slotは次の通り。

- `agents`: `.daik/daik-AGENTS.md.template`へ追加する
- `internal`: `.daik/AGENTS.md`へ追加する
- `workflow`: `.agents/daik-workflow.md`のworkflow部分へ追加する
- `tracker`: `.agents/daik-tracker.md`へ追加する

値は言語とpack内相対パスのmappingである。指定言語がなく英語があれば英語へ
fallbackし、英語もなければ初期化を中止する。

`agents`文書は、template全体の説明、`DAIK:COPY:BEGIN`と`DAIK:COPY:END`で
囲まれたコピー範囲、`<<DAIK:...>>`形式のユーザー置換箇所を明確に分離する。

## Capabilities

portableなtracker操作には`issue.*`を使用する。

- `issue.list_ready`
- `issue.read`
- `issue.create`
- `issue.set_status`
- `issue.assign`
- `issue.add_dependency`
- `issue.remove_dependency`
- `issue.close`

workflow packは次の合成actionも使用できる。

- `issue.claim`
- `issue.set_phase`
- `issue.comment`
- `issue.link`
- `issue.block`
- `issue.complete`

`issue.set_status`と`issue.set_phase`の値はworkflowが自由に定義する。
`issue.close`のreasonは`completed`、`duplicate`、`superseded`、`cancelled`の
いずれかとする。provider固有操作は
`github.request_review`のようにproviderのnamespaceを使用する。

## Safety

- sourceとtargetはpackまたはworkspaceの外へ出られず、symlink経由の書き込みも拒否する
- 複数packが異なる内容を同じtargetへ配置しようとした場合は失敗する
- 既存のプロジェクトファイルを上書きしない
- pack内のプログラムやhookを実行しない
- skill/MCP/CLIはユーザーが別途選択して導入する
