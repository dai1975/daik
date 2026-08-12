---
daik:
  schema_version: 1
  artifact: worker-policy
  ownership: user
  user_action: review-and-customize
---

# daik worker policy

- 作業前に、割り当てられたIssueと最新のhandoff eventを読む。
- 調査、実装内容、質問、validation evidence、review finding、commit、artifact linkは
  Issueへ直接記録する。
- Issueのclaim、workflow state、visit count、retry stateなど、brokerが所有する
  control dataを変更しない。
- 現在のworkflow stateに定義されたtaskだけを行い、次のstateを先取りしない。
- siteの`AGENTS.md`に従い、`workspaces/`以下の割り当てられたcheckoutだけを変更する。
- daik result protocolを通じて、宣言済みのtransitionを一つ、簡潔なevidenceと共に返す。
