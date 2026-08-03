## GitHub Issues操作

このプロジェクトではIssue trackerとしてGitHub Issuesを使用する。

- `issue.read`: Issue本文、comment、label、関連するPull Requestを取得する。
- `issue.create`: titleと受け入れ条件を含む本文でIssueを作成する。
- `issue.claim`: `daik:ready`を外し、`daik:running`を付ける。
- `issue.set_phase(<phase>)`: 既存の`daik:phase:*` labelを外し、
  `daik:phase:<phase>`を付ける。
- `issue.comment`: 進捗、判断、検証結果をcommentとして追加する。
- `issue.link`: 成果物の種類とURLをcommentとして追加する。
- `issue.block`: `daik:running`を外し、`daik:blocked`を付け、理由と再開に
  必要な入力をcommentする。
- `issue.complete`: 変更と検証結果をcommentし、作業用labelを外してIssueを
  closeする。

## Tracker tool

GitHub Issuesの読み書きには、次のskill、MCP、またはCLIを使用すること。

<<DAIK:TRACKER_TOOL>>
