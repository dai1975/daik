# ADR 0001: Agent context、orchestration、program stateの責務分離

- Status: Proposed
- Date: 2026-08-11

## Context

daikは、一つのIssueを複数のcoding agentへ引き継ぎながら、決定的なworkflowに
従って進行させる。現在のrunnerは、workflowの単一agent stateを外部agent
commandで実行し、結果を標準入出力で受け取る。polling、tracker更新、state遷移を
行うorchestratorは未実装である。

設計には次の課題がある。

- Codex、Claude Codeなどで、`AGENTS.md`探索、role、subagent、MCP、Skill、
  sandbox、structured output、sessionの機能が異なる。
- workerの完了報告をそのままstate遷移へ反映すると、未実行のtestや誤った報告を
  見逃す可能性がある。
- 全判断をLLM orchestratorへ任せると、workflow制御自体が非決定的になる。
- 全てのIssue更新をorchestratorへ集約すると、workerの作業contextが欠落し、
  伝達遅延や中央のbottleneckが生じる。
- test、lint、build、CI結果などはLLMを使わず機械的に判定できる。

## Decision

### 1. Program orchestratorをworkflow制御の正本とする

orchestratorは決定的なプログラムとして実装し、次を担当する。

- Issueのclaimとcurrent stateの更新
- 許可されたtransitionかの検証
- visit回数、global transition limit、retry、timeoutの管理
- 複数worker間の競合防止
- agentとprogramの起動・終了監視
- workflow制御eventのIssue trackerへの追記

orchestratorはworkerの代わりに実装内容を判断・作文しない。意味的な判断が必要な
場合は、明示されたagent stateまたはhuman stateを使用する。

### 2. Workerは作業情報をIssueへ直接記録する

workerは、設定されたSkill、MCP、CLIなどを使ってIssueと過去のhandoffを直接読み、
次の情報をIssueへ直接追記する。

- 調査結果と実装内容
- 人間への質問と判断材料
- test結果、review finding、commit、artifact URL
- 次の担当者向けhandoffの内容

一方、claim、current state、visit count、retryなどのworkflow制御情報は変更しない。
workerはtransition候補とevidenceをorchestratorへ返し、最終的なstate更新は
orchestratorが行う。

workerがtimeoutまたはcrashした場合も記録を残せるよう、`agent.started`、
`agent.failed`など外側から観測できるeventはorchestratorが追記する。

### 3. 共通agent contextと製品別CLI wrapperを分離する

daikは、製品に依存しない論理的なagent contextを定義する。

- siteの恒久的な指示
- worker共通policyと権限制約
- workflowのagent profile
- 現在stateのtaskとtransition候補
- Issueと最新handoff
- result protocol

製品別CLI wrapperは、このcontextを各agent softwareのprompt、native role、subagent、
MCP、Skill、sandbox、structured outputへmappingする。共通contextを特定製品の
機能へ直接依存させない。

### 4. 検証工程は明示的なworkflow stateにする

通常の意味的検証は、裏側で常に別のevaluation agentを起動するのではなく、
`testing`や`review`などの明示的なstateとして表現する。これにより、実行costと
workflow上の責任を可視化する。

重要な公開・security・承認について将来独立評価が必要になった場合も、原則として
agent stateまたはhuman stateを追加して表現する。

### 5. LLMを使用しない`program` stateを追加する

workflow state typeに`program`を追加する。ここでいうprogramは、softwareとしての
programと、あらかじめ定めた進行に沿って行うprogramの両方を意図する。`agent`、
`human`と同じく実行主体を表し、LLMまたは人間による意味的判断を行わない。

初期仕様の`program` stateは、orchestratorが単一の外部commandをshellを介さず
実行し、その終了結果を機械的にtransitionへ対応させる。実行方式を分類する
sub-kindは設けない。将来command以外の実行方式が必要になった時点で、互換性を
考慮して一般化する。

初期仕様では結果を次の三種類にする。

- `succeeded`: commandが正常終了した
- `failed`: test failure、lint違反、build failureなどcommandが通常の失敗を返した
- `error`: command起動不能、timeout、working directory不正など検査自体を
  正常に完了できない

将来、非同期CIを扱う際に`pending`を追加できるものとする。

概念上の例:

```yaml
states:
  testing:
    type: program
    command:
      - make
      - test
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

`program`のtransitionは自然言語条件ではなく、規定されたresult名に対応させる。
repository指定はIssue workspace内のworktreeへ解決し、working directoryがsiteまたは
worktreeの外へ出ないよう検証する。

program実行結果はIssue eventへ記録する。eventにはresult、exit code、duration、長さを
制限したsummaryを含める。完全なlogはIssueへ無制限に埋め込まず、CI artifactなどを
linkできる形にする。

## Consequences

- workflowの進行は決定的に保たれ、意味的判断だけをagentまたは人間へ委譲できる。
- workerが持つ詳細な作業contextをIssueへ直接残せる。
- trackerへの同時更新と異常終了はorchestratorが一貫して処理できる。
- 単純なtestやCI確認で追加LLM costが発生しない。
- agent CLI wrapperとtracker jointという二種類の境界設計が必要になる。
- worker用tracker権限とorchestrator用制御権限を分離する必要がある。
- `program` commandの安全なpath解決、timeout、出力制限、機密情報対策が必要になる。

## Deferred decisions

- 共通agent contextの具体的なfile layoutとschema
- 各agent CLI wrapperのinterface
- workerがIssueへ書き込むための最小権限モデル
- 一つの`program` stateで複数commandを扱う必要があるか
- 非同期CIの`pending`、polling、cancelの扱い
- control event更新で利用するtracker側の排他・冪等性方式
