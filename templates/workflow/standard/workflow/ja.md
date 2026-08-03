# 標準Issueワークフロー

## 目的

割り当てられたIssueを理解し、検証可能な変更とPull Requestを作成して、
人間または次の工程へ安全に引き渡す。

## Process

Issue actionの具体的な実行方法は`.agents/daik-tracker.md`に従う。

1. `AGENTS.md`、関連する指示、Issue、資料を読む。
2. Issueの受け入れ条件と編集可能な範囲を確認し、Issueをclaimする。
3. phaseを`implementation`にし、割り当てられた`workspaces/`以下のcheckoutで
   変更を実装する。
4. phaseを`testing`にし、関連するテスト、lint、型検査を実行する。
5. phaseを`review`にし、最終diffの正しさ、スコープ、機密情報を確認する。
6. phaseを`pull-request`にし、Pull Requestを作成してIssueへ関連付ける。
7. 変更内容と検証結果をIssueへ記録し、作業をcompleteにする。

## Handoff

- 続行にユーザーの判断や権限が必要な場合は、Issueをblockし、理由と必要な
  入力を記録する。
- 検証できなかった項目を成功したものとして報告しない。
