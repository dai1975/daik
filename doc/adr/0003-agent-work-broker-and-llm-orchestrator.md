# ADR 0003: Agent Work BrokerとLLM orchestratorの分離

- Status: Accepted
- Date: 2026-08-13

## Context

一般にorchestratorという語は、workerの選択、計画、監督、task分解などを行うLLMを
指すことがある。一方、daikが現在実装している単一Issueの実行主体はプログラムであり、
polling、claim、state遷移、排他、制限、復旧などの決定的な処理を担当する。

両者をorchestratorと呼ぶと、実行制御をLLMが判断しているのか、検証可能なプログラムが
適用しているのかが分かりにくい。また将来は、設計、実装、reviewに加えて、Issue分解や
依存関係調整を行う知的なmanagement処理が必要になる可能性がある。

実行分担には次の形が考えられる。

1. プログラムがworkを取得し、LLM orchestratorがworkerを直接起動する。
2. LLM orchestratorがworkを取得し、プログラムへworker起動を依頼する。
3. プログラムがworkを取得して種類に対応するworkerを起動し、management workでは
   LLM orchestratorをworkerの一種として起動する。

## Decision

### 決定的な実行主体をAgent Work Brokerと呼ぶ

daikのプログラム側の実行主体を`broker`、正式にはAgent Work Brokerと呼ぶ。brokerは
Issue trackerとworkerの間でworkを配送し、次を担当する。

- ready workの取得とclaim
- work typeとworkflowに基づく実行主体の選択
- workspace準備
- agent、program、human、final stateの進行
- 許可されたtransitionの検証と適用
- 並行数、timeout、retry、停止の管理
- tracker上のcontrol eventとstateの更新
- 競合検出とcrash recovery

brokerは、実装内容、設計の妥当性、Issue分解などの意味的判断を行わない。CLIでは
既存の`daik work run ISSUE`を単一workのbroker実行として維持し、pollingは将来の
`daik work watch`に追加する。

### 知的な管理主体を暫定的にLLM orchestratorと呼ぶ

Issue分解、依存関係設定、優先度や停滞の分析などを行う知的な主体は、設計が固まるまで
`LLM orchestrator`と呼ぶ。LLM orchestratorはbrokerを置き換えず、brokerが起動する
agent workerの一種とする。

基本的な発展方向には上記の第3案を採用する。将来`management` work typeとworkflowを
追加し、その担当workerとしてLLM orchestratorを割り当てる。LLM orchestratorは別の
workerを直接起動せず、新しいwork、依存関係、判断結果をIssue trackerへ記録する。
brokerがそれを通常のqueueから取得し、claimして実行する。

```text
Issue tracker
      │
      ▼
Agent Work Broker
      ├── implementation work ── implementation agent
      ├── design work ────────── design agent
      ├── review work ────────── review agent
      ├── program state ──────── external command
      └── management work ────── LLM orchestrator
                                      │
                                      └── new workをtrackerへ登録
```

すべてのworkを最初にmanagement workflowへroutingすれば第1案に近い運用も可能である。
ただし、work typeやrouting schemaはpolling実装に必要になるまで確定しない。

### 起動権限をbrokerに集中させる

workerはIssue trackerへ新しいworkを作成できるが、他のworkerプロセスを直接起動しない。
実行開始、claim、同時実行制限、再試行をbrokerだけが担う。trackerをworker間通信と
durable queueの正本にする既存方針を維持する。

## Consequences

- 決定的なcontrol planeとLLMによるdecision planeを区別できる。
- LLM orchestratorなしでも単純なIssue workflowを実行できる。
- management、designなどを通常のwork typeとして追加できる。
- workerが停止しても、trackerへ登録済みのworkから再開できる。
- LLM orchestratorの判断にもbrokerの排他、制限、監査を適用できる。
- 将来、work type、workflow routing、親子workのportable contractが必要になる。

## Deferred decisions

- `work_type`のportable schemaとtracker mapping
- `work_type`からworkflowおよびagent profileへのrouting書式
- management workの作成条件とloop防止
- 親子work、依存関係、完了集約の規則
- LLM orchestratorの権限、context、result protocol
