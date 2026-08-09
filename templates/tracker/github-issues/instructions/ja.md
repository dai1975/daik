## GitHub Issues tracker mapping

このプロジェクトではIssue trackerとしてGitHub Issuesを使用する。ここではGitHubに
必要なdata変更を定義し、操作手段は規定しない。次にユーザーが指定したskill、
MCP server、CLI、その他のaccess方法を使用する。

<<DAIK:TRACKER_TOOL>>

### daik操作とGitHub表現の対応

- `issue.list_ready`: openで、設定された必須labelを全て持ち、daik statusが
  blockedでなく、未解決のblocked-by dependencyを持たないIssueを選ぶ。
- `issue.read`: repositoryとIssueのidentity、title、body、open/closed state、
  state reason、assignees、labels、dependencies、comments、linkされた開発成果物を読む。
- `issue.create`: 設定されたrepositoryへtitleとbodyを指定してIssueを作る。指定が
  あればlabel、assignee、dependencyも設定する。
- `issue.set_status(<status>)`: 既存の`daik:status:*` labelを全て外し、
  `daik:status:<status>`を一つだけ付ける。`issue.close`以外ではIssueをopenに保つ。
- `issue.assign(<actor>)`: GitHub assigneeを設定する。GitHubのassignment自体には
  compare-and-setがないため、claimではschedulerが直列化・再確認し、別workerを
  暗黙に上書きしない。
- `issue.add_dependency(<blocker>)`: 現在のIssueから`<blocker>`へのnativeな
  blocked-by dependencyを追加する。
- `issue.remove_dependency(<blocker>)`: そのnative dependencyを削除する。
- `issue.comment(<message>)`: Issue commentを追記する。
- `issue.link(<kind>, <url>)`: 利用可能ならnative development linkを使い、
  それ以外はtyped commentとしてartifact kindとURLを保存する。
- `issue.close(<reason>, <summary>)`: summaryをcommentし、Issueをcloseし、daik
  reasonを`daik:close-reason:<reason>` label一つで保存する。`completed`はGitHub
  state reasonの`completed`、`duplicate`、`superseded`、`cancelled`は
  `not_planned`へmappingする。

daik close reasonは`completed`、`duplicate`、`superseded`、`cancelled`とする。

標準workflowの上位actionは次の合成操作である。

- `issue.claim`: workerを割り当て、daik statusを`in_progress`にし、
  `daik:ready`を外して`daik:running`を付ける。claimはscheduler側で直列化する。
- `issue.set_phase(<phase>)`: `issue.set_status(<phase>)`を実行する。表示目的で
  `daik:phase:<phase>` labelにもmirrorしてよい。
- `issue.block`: daik statusを`blocked`にし、判明しているnative dependencyを
  追加し、`daik:running`を`daik:blocked`へ置き換えて理由をcommentする。
- `issue.complete`: `issue.close(completed, <summary>)`を実行し、一時的なdaik作業
  labelを削除する。
