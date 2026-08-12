# First milestone

`daik` の最初のマイルストーンでは、Issue tracker と coding agent を接続する
ための最小構成を実装する。

## Scope

- [x] `daik site init`
- [x] テンプレート一式
- [x] manifest によるファイル所有権管理
- [x] 日英、workflow、tracker packの選択と合成
- [x] capabilityによるworkflow/tracker互換性検査
- [x] workflow/config validator (`daik site validate`)
- [x] `daik site doctor`
- [x] GitHub Issues tracker mappingと互換性確認skill
- [x] Beads tracker mappingと互換性確認skill
- [x] Issue ごとの workspace と Git worktree の管理
- [x] Issue eventによるagent間handoff
- [x] coding agent runner
- [x] 共通agent contextとagent CLI wrapperの設計・生成
  ([ADR 0001](adr/0001-agent-context-orchestration-and-program-states.md),
  [ADR 0002](adr/0002-cli-wrapper-invocation-logs.md))
- [x] program orchestratorによるIssue stateとcontrol eventの管理
  ([ADR 0001](adr/0001-agent-context-orchestration-and-program-states.md))
- [ ] LLMを使用しないworkflow `program` state
  ([ADR 0001](adr/0001-agent-context-orchestration-and-program-states.md))
- [ ] polling、並行実行、再試行
- [ ] structured logging と status 表示
  ([ADR 0002](adr/0002-cli-wrapper-invocation-logs.md))

## Completion criteria

- 開発 workspace のルートで `daik site init` を実行できる
- `AGENTS.md` を作成、変更、上書きしない
- `.agents/`にagent向け文書、`.daik/`にoperator向け導入記録を展開できる
- 既存のユーザー所有ファイルを上書きしない
- GitHub Issues から実行可能な Issue を取得できる
- Issue ごとに `workspaces/` 以下へ隔離された作業場所を作成できる
- coding agent を起動し、workflow に従って Issue を処理できる
- 同時実行数の制限、再試行、停止を扱える
- 実行状況と失敗理由をログまたは status コマンドで確認できる
