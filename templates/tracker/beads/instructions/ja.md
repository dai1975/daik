## Beads tracker mapping

このプロジェクトではIssue trackerとしてBeadsを使用する。ここではBeadsに必要な
data変更を定義し、操作手段は規定しない。次にユーザーが指定したskill、MCP server、
その他のaccess方法を使用する。

<<DAIK:TRACKER_TOOL>>

### daik操作とBeads表現の対応

- `issue.list_ready`: closeされておらず、blockされておらず、設定された必須labelを
  全て持ち、dependencyが解決済みのbeadを選ぶ。
- `issue.read`: ID、title、description、status、assignee、labels、dependencies、
  notes、external references、close情報を読む。
- `issue.create`: 指定されたtitleとdescriptionでbeadを作る。指定があればlabel、
  assignee、dependencyも設定する。
- `issue.set_status(<status>)`: workflow定義の値をそのままBeadsの`status`へ保存する。
  built-inでない値はBeads projectのcustom statusとして宣言されている必要がある。
- `issue.assign(<actor>)`: Beadsの`assignee`を設定する。claimとしての割り当てでは、
  現在の別assigneeを上書きせず失敗しなければならない。
- `issue.add_dependency(<blocker>)`: 現在のbeadが`<blocker>`へ依存するblocking
  dependencyを追加する。
- `issue.remove_dependency(<blocker>)`: そのblocking dependencyを削除する。
- `issue.comment(<message>)`: Beadsのnotesまたは設定されたappend-only discussion
  fieldへ追記し、以前の内容を上書きしない。
- `issue.link(<kind>, <url>)`: artifact kindとURLをexternal referencesまたは
  append-only notesへ保存し、無関係な既存linkを上書きしない。
- `issue.close(<reason>, <summary>)`: statusを`closed`にし、summaryを人間向けの
  close reasonとして保持し、daik reasonをmetadataの`daik.close_reason`へ保存する。
  reasonは`completed`、`duplicate`、`superseded`、`cancelled`のいずれかとする。

標準workflowの上位actionは次の合成操作である。

- `issue.claim`: workerをatomicに割り当て、statusを`in_progress`にし、
  `daik:ready`を外して`daik:running`を付ける。
- `issue.set_phase(<phase>)`: statusをphase値そのものにする。siteによっては
  `daik:phase:<phase>` labelにも同じ値をmirrorしてよい。
- `issue.block`: statusを`blocked`にし、判明しているblocking dependencyを記録し、
  `daik:running`を`daik:blocked`へ置き換えて理由を追記する。
- `issue.complete`: `issue.close(completed, <summary>)`を実行し、一時的なdaik作業
  labelを削除する。

### daik issue event

daikが生成した`daik.issue-event.v1` objectは全てbeadのappend-only notesまたは
event historyへ追記する。完全なJSON objectを保存し、以前のeventを置換しない。
検索用にBeads status、labels、assignee、dependenciesへ現在状態をmirrorするが、
handoffとworkspace記録の正本はevent historyとする。作業開始前に最新のworkspace
eventと最新の`handoff` eventを読む。
