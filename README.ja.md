# daik

[English](README.md)

`daik`は、Issue trackerとcoding agentをつなぐ、個人開発向けの協調ハーネスです。

Issueを仕事の単位として取得し、Issueごとに隔離されたworkspaceを用意して
coding agentを実行します。開発プロセスとtracker操作の指示はユーザーの
開発環境へ展開され、その環境に合わせて自由に変更できます。

名前は日本語の「大工」に由来します。

> [!NOTE]
> 現在は開発の初期段階です。siteを展開・診断する`init`、`validate`、`doctor`
> コマンドを利用できます。GitHub IssuesとBeadsのmappingを利用でき、
> orchestrationとagent実行機能は今後実装します。

## Goals

- Issue trackerをcoding agentの作業キューとして利用する
- Issueごとに独立したworkspaceを作り、複数のagentを安全に並行実行する
- 開発プロセスとagentの指示を、開発環境内でversion管理する
- 単一リポジトリだけでなく、複数リポジトリや外部資料を含む開発に対応する
- 生成された設定をユーザーが所有し、開発環境ごとに変更できるようにする
- 特定のcoding agentやIssue trackerへの依存を小さくする

daikは汎用ワークフローエンジンや、リポジトリ配置を規定するプロジェクト管理
ツールを目指しません。各リポジトリ、設計資料、その他のリソースをどこに置くかは
ユーザーが決めます。

## Usage

ここでは、coding agentのrootであり、リポジトリ、資料、その他の開発リソースを
まとめるディレクトリを**site**と呼びます。

まずsiteを作り、daik、作業対象のリポジトリ、リポジトリ外のリソースをその中に
配置します。以下はbackendとfrontendが別リポジトリになっている例です。

```sh
mkdir my-site
cd my-site

git clone git@github.com:dai1975/daik
git clone git@github.com:user/backend
git clone git@github.com:user/frontend

mkdir -p resources ref/rfc
```

workflowとtrackerは**pack**という単位でまとめられています。利用可能なpackの
一覧は次のコマンドで確認できます。

```sh
./daik/daik site packs
```

使用する自然言語、workflow pack、tracker packを選択してsiteを初期化します。

```sh
./daik/daik site init \
  --lang ja \
  --workflow standard \
  --tracker github-issues \
  --wet-run
```

`--wet-run`を付けない場合はpreviewのみとなり、ファイルを変更しません。

```sh
./daik/daik site init
```

`site init`は既存ファイルを上書きしないため、同じpack選択で安全に再実行できます。
初期化済みsiteで言語またはpack選択を変更しようとすると、ユーザー所有ファイルと
manifestの不一致を避けるため中止します。

daikの実行場所は`backend/`や`frontend/`の中ではなく、siteルートの`my-site/`です。
リソースの配置に決められた形はありません。

```text
my-site/
├── AGENTS.md
├── .agents/
├── .daik/
├── workspaces/
├── backend/                  # Git repository
├── frontend/                 # Git repository
├── resources/                # GitHubには置かない画像など
└── ref/
    └── rfc/                  # 参考文書、標準仕様など
```

それぞれのディレクトリの目的、buildやtestの方法、agentが編集してよい範囲は、
ユーザーが`AGENTS.md`またはそこから参照する文書に記述します。

### Commands

現在利用できるコマンド:

```sh
daik site packs
daik site init
daik site validate
daik site doctor
```

- `site packs`: 利用可能なpackを一覧表示する
- `site init`: 展開内容をpreviewする。`--wet-run`指定時だけ実際に書き込む
- `site validate`: 外部サービスへ接続せず、site内の契約を検証する
- `site doctor`: 契約を検証し、local toolと実行環境を診断する

`AGENTS.md`のblockをcopyして変更し、生成ファイルを確認した後、次のコマンドで
siteを検証します。

```sh
./daik/daik site validate
```

文書metadataと構文、workflow/tracker capability、設定値、未置換placeholder、
manifestとの整合性、daik所有ファイルの完全性を検査します。errorがある場合は
終了status 1、warningと情報メッセージだけの場合は0を返します。

より広い実行環境の診断には次のコマンドを使います。

```sh
./daik/daik site doctor
```

validateに加えて、Git、Issue用workspace外のcheckout、設定されたworkspace
directoryへの書き込みを確認します。tracker accessにはskill、MCP server、CLI、
その他の方法を使えるため、tracker互換性については選択packのread-onlyな
互換性確認skillを案内します。

helpは次のように表示できます。

```sh
./daik/daik --help
./daik/daik site init --help
```

以下のコマンドは今後実装する予定です。

```sh
daik work run
daik work watch
daik work status
```

- `work run`: 実行可能なIssueを取得して処理する
- `work watch`: Issue trackerを継続的に監視する
- `work status`: 実行中、再試行待ち、完了した作業を表示する

## Site

daikでは、coding agentが作業するルートディレクトリを**site**と呼びます。
siteは単一のGitリポジトリではなく、一つの開発対象に関係する複数のリポジトリ、
リポジトリ外の資料やリソース、daikの設定、Issueごとのworkspaceをまとめる
入れ物です。coding agentのcurrent working directoryもsiteのルートになります。

site内のリポジトリや資料の配置はdaikが規定しません。その構成と編集可能な
範囲は、siteルートの`AGENTS.md`またはそこから参照する文書でagentに説明します。

siteディレクトリ自体をGitリポジトリとして管理しても構いません。その場合、
site共通の`AGENTS.md`、daik設定、共有資料などをversion管理し、site内の個別
リポジトリはsubmoduleにするか、site側の`.gitignore`で除外できます。

### Site contract

daikが名前と役割を規定するのは、次の要素だけです。

```text
my-site/
├── AGENTS.md
├── .agents/
│   ├── daik-workflow.md
│   ├── daik-tracker.md
│   ├── daik-config.yaml
│   └── daik-workflow-spec.md
├── .daik/
│   ├── .ignore
│   ├── AGENTS.md
│   ├── daik-AGENTS.md.template
│   └── manifest.json
└── workspaces/
```

#### `AGENTS.md`

site全体の説明と恒久的な開発ルールを記述します。

`AGENTS.md`は常にユーザー所有です。daikは作成、変更、上書きを行いません。
代わりに、追加を推奨する内容を`.daik/daik-AGENTS.md.template`として用意します。
template内の`DAIK:COPY:BEGIN`と`DAIK:COPY:END`で囲まれた部分だけを既存の
`AGENTS.md`へコピーし、`<<DAIK:WORKSPACE_GUIDE>>`をsite固有の説明に
置き換えます。template自身の説明とユーザーへの記述ガイドはコピー範囲の外に
置かれます。

#### `.agents/daik-workflow.md`

Issueを受け取ってから作業を完了または人間へ引き渡すまでの、provider非依存の
開発プロセスを定義します。front matterには選択したpack、使用するphase、必要な
issue actionを機械可読な形で記録します。

初回の`init`で作成された後はユーザーが所有し、siteに合うように変更します。
ファイル形式の契約は`.agents/daik-workflow-spec.md`に定義します。tracker上で
各actionをどう実行するかは`.agents/daik-tracker.md`を参照します。

#### `.agents/daik-tracker.md`

workflowが指示するissue actionを、選択したtracker上でどう実現するかを定義します。
front matterにはtracker packと提供するaction、本文にはlabelやstateなどの具体的な
対応関係を記録します。

daikのpackはskillやMCPそのものを配置しません。trackerの操作に使用するskill、
MCP、CLIはユーザーが選び、生成された`<<DAIK:TRACKER_TOOL>>`を具体的な利用方法で
置き換えます。

#### `workspaces/`

Issueごとの隔離された作業場所です。

```text
workspaces/
├── GH-123/
└── GH-124/
```

各Issue workspaceの内部構造はdaikが固定しません。単一のGit worktreeだけを
作ることも、複数リポジトリのworktreeを並べることもできます。agentのcurrent
working directoryはsiteのルートですが、実際の変更は割り当てられた
`workspaces/<issue>/`内のcheckoutに対して行います。

### File ownership

初期化や将来の更新でユーザーの変更を失わないように、ファイルの役割と所有者を
区別します。

| File | Kind | Ownership | User action |
| --- | --- | --- | --- |
| `AGENTS.md` | Agent instructions | User | copy blockを取り込み、site情報を書く |
| `.daik/daik-AGENTS.md.template` | Integration guide | daik | copy blockだけを使用する |
| `.agents/daik-workflow.md` | Workflow | User | 作業手順を確認・編集する |
| `.agents/daik-tracker.md` | Tracker guide | User | 操作mappingとplaceholderを確認・編集する |
| `.agents/daik-config.yaml` | Runtime config | User | trackerと実行設定を確認・編集する |
| `.agents/daik-workflow-spec.md` | Reference | daik | 通常は参照のみ |
| `.daik/manifest.json` | Operation record | daik | 開発時には使用しない |

生成文書自身にも同じ区別を示します。Markdownはfront matterの`daik` mapping、
configは`daik_document` mapping、manifestは`document` objectに`artifact`、
`ownership`、`user_action`を記録します。

`.daik/`はdaikと人間のoperatorだけが使用する内部管理領域です。通常のcoding
agentによる探索から外すため`.daik/.ignore`を配置し、`.daik/AGENTS.md`と
ルート`AGENTS.md`用copy blockの両方で、daik自体の保守以外では参照しないよう
指示します。

## Architecture

daikは[OpenAI Symphony](https://github.com/openai/symphony)の、Issue trackerを
監視してIssueごとのworkspaceでcoding agentを動かす設計を参考にしています。

```text
Issue tracker
      │
      ▼
Tracker adapter
      │ normalized Issue
      ▼
Orchestrator
      │
      ├── Workspace manager
      │       └── workspaces/<issue>/
      │
      └── Agent runner
              └── coding agent
```

Symphonyが定義するscheduler、tracker adapter、workspace manager、agent runnerの
責務分離を参考にしつつ、daikでは個人のsiteに展開して直接編集できる設定と
workflowを重視します。

オーケストレーターはIssueの選択、同時実行数、再試行、停止、workspaceの
ライフサイクルを管理します。Issueの具体的な処理方法は
`.agents/daik-workflow.md`と`.agents/daik-tracker.md`に置き、site固有の知識を
オーケストレーター本体へ組み込みません。

### Packs

`site init`はbase、workflow、trackerの3種類のpackを合成します。

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

- base packは`AGENTS.md`への追記案など、site共通の指示を提供する
- workflow packは作業手順、phase、必要なtracker操作を定義する
- tracker packは抽象的な操作をGitHub Issuesなどでどう実現するか定義する

workflow packの`requires`とtracker packの`provides`は`issue.read`、
`issue.set_phase`、`issue.complete`などのcapabilityで照合されます。互換性のない
組み合わせはファイルを作成する前に拒否されます。

packは日本語と英語の指示を提供でき、`--lang ja`または`--lang en`で選択します。
詳細なpack形式は[doc/packs.ja.md](doc/packs.ja.md)を参照してください。

GitHub IssuesとBeadsのpackはprovider dataの変更を定義し、skill、MCP server、
CLIなどのaccess方法はユーザーが指定する。共通契約とprovider mappingは
[doc/trackers.ja.md](doc/trackers.ja.md)を参照してください。

#### Third-party packs

daikは指定されたtemplateディレクトリ以下の`pack.yaml`を再帰的に探索します。
第三者のリポジトリを`templates/`以下へcloneまたはsubmoduleとして配置すると、
組み込みpackと同様に選択できます。一つのリポジトリで複数packを提供できます。

別の場所に配置する場合は`--template-dir`を追加します。

```sh
./daik/daik site packs --template-dir ../community-packs

./daik/daik site init \
  --workflow example.workflow.custom \
  --tracker github-issues \
  --template-dir ../community-packs \
  --wet-run
```
