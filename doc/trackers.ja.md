# Tracker共通仕様

[English](trackers.md)

brokerはprovider非依存のIssue操作を要求する。tracker packはその操作を
provider dataへmappingし、access方法はユーザーが選択する。

provider非依存のdata操作は`issue.list_ready`、`issue.read`、`issue.create`、
`issue.set_status`、`issue.assign`、`issue.add_dependency`、
`issue.remove_dependency`、`issue.comment`、`issue.link`、`issue.close`である。
close reasonは`completed`、`duplicate`、`superseded`、`cancelled`とする。

`issue.claim`、`issue.set_phase`、`issue.block`、`issue.complete`などのworkflow
actionはdata操作の合成である。tracker packは両layerをprovider dataへmappingし、
access tool自体は規定しなくてよい。

## GitHub Issues

GitHub Issues packはdata modelの変更を規定し、access方法は規定しない。ユーザーが
`.agents/daik-tracker.md`へskill、MCP server、CLI、その他の方法を設定する。

| daik操作 | GitHub上の表現 |
| --- | --- |
| Ready queue | 設定された必須labelを全て持つopen Issue |
| Status | `daik:status:<status>` labelを一つだけ設定する |
| Assignment | GitHub assignee。claimはbroker側で直列化する |
| Dependencies | native blocked-by relationship |
| Claim | assignment、`in_progress`、作業label遷移 |
| Phase | phase値をdaik status labelへ保存する |
| Comment/link | Issue comment |
| Block | status、native dependency、label、reason comment |
| Close | GitHub state reason、summary comment、daik close-reason label |

生成される`.daik/github-issues-spec.md`にREST API version `2026-03-10`と必要な
behaviorを記録する。ユーザーが明示的に依頼した場合、
`daik-check-github-issues-compatibility` skillがread-only監査を行う。

## Beads

Beads packはdata modelの変更を規定し、access方法は規定しない。ユーザーが
`.agents/daik-tracker.md`へskill、MCP server、CLI、その他の方法を設定し、
その方法を理解するagentが必要な変更を行う。

| daik操作 | Beads上の表現 |
| --- | --- |
| Ready queue | blockerがなく、設定された必須labelを全て持つbead |
| Status | daik workflowの値をそのままBeads `status`へ保存する |
| Assignment | Beads `assignee`。claimでは既存割り当てを奪わない |
| Dependencies | directed blocking dependency |
| Claim | atomicな割り当て、`in_progress`、作業label遷移 |
| Phase | phase値をstatusへ保存し、必要ならphase labelにもmirrorする |
| Comment/link | notesへ追記する |
| Block | status、dependency、label、notesでblockを表現する |
| Close | `closed`、人間向けsummary、`daik.close_reason` metadata |

生成される`.daik/beads-spec.md`に参照Beads versionと必要なbehaviorを記録する。
ユーザーが明示的に依頼した場合、`daik-check-beads-compatibility` skillがread-onlyの
互換性確認を行う。
