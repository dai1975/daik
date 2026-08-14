---
daik:
  schema_version: 1
  artifact: agents-template
  ownership: daik
  user_action: copy-and-customize
---

# daik AGENTS.md導入ガイド

このファイル全体を`AGENTS.md`へコピーしないでください。下の
`DAIK:COPY:BEGIN`と`DAIK:COPY:END`で囲まれた部分だけをコピーし、
`<<DAIK:SITE_GUIDE>>`を実際の説明または説明文書へのリンクに置き換えます。

## AGENTS.mdへコピーする部分

<!-- DAIK:COPY:BEGIN -->
## daikによるIssue駆動開発

Issue trackerから割り当てられた作業では、`.agents/daik-workflow.yaml`に定義された
プロセスに従ってください。このworkflowの書式と共通操作は
`.agents/daik-workflow-spec.md`に定義されています。runtime issue eventは
`.agents/daik-issue-event-spec.md`に
定義されています。Issue trackerの具体的な操作は`.agents/daik-tracker.md`に
従い、workerの権限と責務は`.agents/daik-worker.md`に従ってください。
CLI wrapper protocolは`.agents/daik-agent-context-spec.md`に定義されています。
Issueごとの書き込み可能なcheckoutは
`workspaces/`以下に作成されます。

`.daik/`はdaikと人間のoperatorが使用する内部管理領域です。通常のIssue調査、
実装、テスト、レビューでは読み取り・変更しないでください。daik自体の導入、
設定、更新を明示的に依頼された場合に限り参照できます。

### Site guide

<<DAIK:SITE_GUIDE>>
<!-- DAIK:COPY:END -->

## ユーザーが記述する内容

`<<DAIK:SITE_GUIDE>>`には、次の情報を直接記述するか、それらを説明する
文書へのリンクを記述してください。

- siteに含まれるsource repositoryとそれぞれの役割
- 参考資料、生成物、その他のリソースの場所
- site直下などに置かれたsource checkoutと、`workspaces/`以下に生成される
  Issue用checkoutの違い
- agentが編集してよい範囲と読み取り専用の範囲
- プロジェクト固有のbuild、test、reviewの入口
