# daik

`daik` は、Issue tracker と coding agent をつなぐ、個人開発向けの協調ハーネスです。

Issue を仕事の単位として取得し、Issue ごとに隔離された workspace を用意して
coding agent を実行します。開発プロセスや agent のスキルはプロジェクト側へ
展開され、ユーザーが自分の開発環境に合わせて自由に変更できます。

名前は日本語の「大工」に由来します。また、作者の名前である `dai` を含む、
個人的な道具という意味も込めています。

> [!NOTE]
> 現在は設計・開発の初期段階です。以下には実装予定のインターフェースが
> 含まれます。

## Goals

- Issue tracker を coding agent の作業キューとして利用する
- Issue ごとに独立した workspace を作り、複数の agent を安全に並行実行する
- 開発プロセスと agent の指示を、プロジェクト内でバージョン管理する
- 単一リポジトリだけでなく、複数リポジトリや外部資料を含む開発に対応する
- 生成された設定をユーザーが所有し、プロジェクトごとに変更できるようにする
- 特定の coding agent や Issue tracker への依存を小さくする

`daik` は汎用ワークフローエンジンや、リポジトリ配置を規定するプロジェクト
管理ツールを目指しません。各リポジトリ、設計資料、その他のリソースをどこに
置くかはユーザーが決めます。

## Inspiration

`daik` は [OpenAI Symphony](https://github.com/openai/symphony) の、
Issue tracker を監視して Issue ごとの workspace で coding agent を動かす
設計を参考にしています。

Symphony が定義する scheduler、tracker adapter、workspace manager、agent
runner の責務分離を参考にしつつ、`daik` では個人の開発 workspace に展開して
直接編集できる設定、workflow、skills を重視します。

## Planned usage

まず、`daik` と作業対象のリポジトリを同じ開発ディレクトリに配置します。

```sh
mkdir my-project
cd my-project

git clone git@github.com:dai1975/daik
git clone git@github.com:user/userproj

daik/daik init userproj
```

`daik` の実行場所は `userproj/` の中ではなく、その親の `my-project/` です。
これにより、agent は複数のリポジトリやリポジトリ外の資料を同じ workspace
から参照できます。

リソースの配置に決められた形はありません。

```text
my-project/
├── AGENTS.md
├── .agents/
├── workspaces/
├── userproj/
├── another-repository/
├── specifications/
└── research-notes/
```

それぞれのディレクトリの目的、ビルドやテストの方法、agent が編集してよい
範囲などは、ユーザーが `AGENTS.md` またはそこから参照する文書に記述します。

## Workspace contract

`daik` が名前と役割を規定するのは、次の要素だけです。

```text
my-project/
├── AGENTS.md
├── .agents/
│   ├── AGENTS.md.template
│   ├── WORKFLOW.md
│   ├── daik-config.yaml
│   ├── daik-manifest.json
│   ├── daik-workflow-spec.md
│   └── skills/
│       └── daik-issue-worker/
│           └── SKILL.md
└── workspaces/
```

### `AGENTS.md`

開発 workspace 全体の説明と恒久的な開発ルールを記述します。

`AGENTS.md` は常にユーザー所有です。`daik` は作成、変更、上書きを行いません。
代わりに、追加を推奨する内容を `.agents/AGENTS.md.template` として用意します。
ユーザーは必要な部分だけを既存の `AGENTS.md` へコピーできます。

### `.agents/WORKFLOW.md`

Issue を受け取ってから作業を完了または人間へ引き渡すまでの開発プロセスを
定義します。例えば、次のような手順が含まれます。

1. Issue と関連資料を理解する
2. 実装計画を作る
3. 対象のコードを変更する
4. テストと静的検査を実行する
5. 変更内容をレビューする
6. 結果と検証の証拠を Issue tracker へ報告する
7. 次の状態へ引き渡す

初回の `init` ではテンプレートが作成されますが、その後はユーザーが所有し、
プロジェクトに合うように変更します。ファイル形式の契約は
`.agents/daik-workflow-spec.md` に定義します。

### `.agents/skills/`

workflow を実行するための再利用可能な手順を配置します。スキル名には他の
ツールやユーザー定義スキルとの衝突を避けるため、`daik-` prefix を付けます。

### `workspaces/`

Issue ごとの隔離された作業場所です。

```text
workspaces/
├── GH-123/
└── GH-124/
```

各 Issue workspace の内部構造は `daik` が固定しません。単一の Git worktree
だけを作ることも、複数リポジトリの worktree を並べることもできます。
workspace hook とプロジェクトの workflow が、そのプロジェクトに必要な構造を
決定します。

agent の current working directory は開発 workspace のルートです。実際の
変更は、割り当てられた `workspaces/<issue>/` 内の checkout に対して行います。
これにより、ルートの `AGENTS.md`、`.agents/skills/`、外部資料を参照しながら、
Issue ごとの変更を分離できます。

## File ownership

初期化や将来の更新でユーザーの変更を失わないように、ファイルの所有権を
区別します。

| File | Ownership | Update policy |
| --- | --- | --- |
| `AGENTS.md` | User | `daik` は変更しない |
| `.agents/AGENTS.md.template` | daik | 新しい推奨内容を提供できる |
| `.agents/WORKFLOW.md` | User | 初回のみ作成し、上書きしない |
| `.agents/skills/daik-*` | User | 初回展開後はユーザーの変更を保持する |
| `.agents/daik-workflow-spec.md` | daik | 互換性を確認したうえで更新できる |
| `.agents/daik-manifest.json` | daik | 展開バージョンとファイル状態を記録する |

## Planned architecture

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

オーケストレーターは、Issue の選択、同時実行数、再試行、停止、workspace の
ライフサイクルを管理します。Issue の具体的な処理方法は
`.agents/WORKFLOW.md` と skills に置き、プロジェクト固有の知識を
オーケストレーター本体へ組み込みません。

## Planned commands

```sh
daik init <primary-repository>
daik validate
daik doctor
daik run
daik watch
daik status
```

- `init`: 現在の開発 workspace にテンプレートと設定を展開する
- `validate`: workflow と設定ファイルを検証する
- `doctor`: Git、coding agent、tracker認証などの実行環境を診断する
- `run`: 実行可能な Issue を取得して処理する
- `watch`: Issue tracker を継続的に監視する
- `status`: 実行中、再試行待ち、完了した作業を表示する

