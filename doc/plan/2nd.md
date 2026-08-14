# Second milestone: real-application validation

第2マイルストーンでは、実際に開発中のMakepad GUI applicationへdaikを適用し、
要件分析、実装、機械的検証、人間によるUI評価までをIssue tracker上で運用する。
新しい抽象機能を先に一般化しすぎず、実作業で生じた摩擦を記録しながらworkflow、
broker、tracker joint、agent contextを洗練する。

関連する設計判断:

- [ADR 0003: Agent Work BrokerとLLM orchestratorの分離](../adr/0003-agent-work-broker-and-llm-orchestrator.md)
- [ADR 0004: Human participationとactivationのyield/resume](../adr/0004-human-participation-and-yield-resume.md)

## Goals

- 人間がagent-shell、Codex applicationなど任意のUIからdaik workへ参加できる
- 要件を人間とAIで議論し、合意内容から実装可能なIssueを作成できる
- broker-managed agentがhumanまたはtimer待ちでyieldし、別activationで再開できる
- GUIの起動、操作、目視確認を人間が行い、agentが記録とdaik操作を代行できる
- Makepad applicationの実開発を通じて、標準workflowと設定の不足を特定できる
- trackerをworkflow controlとhandoffの正本に保ち、local logだけへ依存しない

## Milestones

### 1. Activationとyield/resume contract

- [ ] agent resultに`disposition: completed | yielded | failed`を導入する
- [ ] yield固有情報を`yield.reason`、`yield.checkpoint`、`yield.resume`へまとめる
- [ ] `resume.kind: human`と`resume.kind: timer`を定義・検証する
- [ ] `agent.yielded`とactivation identityをIssue event仕様へ追加する
- [ ] workflow state、runtime status、activation count、yield countを分離する
- [ ] yield時にtransition countとvisit countを消費しないようbrokerを変更する
- [ ] trackerからwaiting stateとresume conditionを復元する
- [ ] activation loopを防ぐ独立した上限と診断を追加する
- [ ] broker logと`work status`へ`runnable | running | waiting`を表示する

### 2. Resume scheduling

- [ ] human responseを記録・検出するportable tracker operationを設計する
- [ ] human resume可能なIssueを`work.list_ready`で再取得できるようにする
- [ ] timerの`not_before`をbrokerが判定し、時刻到達後に再activationする
- [ ] broker再起動後もyielded workをtrackerから復旧できることを確認する
- [ ] 同一Issueを複数brokerがresumeしないようcontrol versionで排他する
- [ ] timer待ちで管理外のbackground processを残さないpolicyを文書化する

### 3. Human-attached invocation

- [ ] broker-managed invocationとhuman-attached invocationの共通contractを設計する
- [ ] 任意UIで起動済みのagentがIssueへattachするcommandを追加する
- [ ] attached agentへIssue、state、task、checkpoint、transition候補を渡す
- [ ] attached agentがstructured resultを提出するcommandを追加する
- [ ] attach、complete、abandonとbroker自動実行のclaim競合を防ぐ
- [ ] attached invocationもsite外の`invocations/`へ記録する
- [ ] attached agent向けのdaik skillとAGENTS.md指示をpackへ追加する
- [ ] 人間がGitHub UIやdaik CLIを直接操作せず、chatだけで作業を完了できることを確認する

### 4. Human work validation

- [ ] `type: human`のruntime contractとtracker表示を明確化する
- [ ] human workをtrackerのassignmentとnative notificationへmappingする
- [ ] 任意のattached agentがhuman workの対話、記録、完了操作を補助できるようにする
- [ ] Makepad applicationのUI review用human stateを作成する
- [ ] 画面確認、操作確認、screenshot、finding、承認・差し戻しを実Issueで試す
- [ ] 長時間回答がないhuman workのstatusとbroker behaviorを確認する

### 5. Work typeと複数workflow routing

- [ ] provider-independentな`work_type`を定義する
- [ ] tracker packへwork type mappingを追加する
- [ ] 複数workflowのfile layoutを決める
- [ ] `work_type`からworkflowとagent profileへのroutingを実装する
- [ ] unknown work type、workflow不在、routing変更時の安全なfailureを定義する
- [ ] management、requirements、implementation、UI reviewを通常のworkとして配送できるようにする

### 6. Requirements analysis workflow

- [ ] 人間とAIが対話して要件を深掘りするrequirements workflow packを作成する
- [ ] 目的、対象ユーザー、制約、非目標、acceptance criteria、未決事項を記録する
- [ ] requirements workから子Issueを作るportable operationと権限制約を確認する
- [ ] 子Issueへwork type、依存関係、親Issue referenceを設定する
- [ ] planner agentはworkerを直接起動せず、trackerへworkを登録するだけにする
- [ ] 元Issueへtask breakdownと判断理由を残す

### 7. Makepad pilot

- [ ] Makepad application用siteを作成し、repositoryと参考資料をAGENTS.mdへ記述する
- [ ] Makepad固有のbuild、run、hot reload、test入口を設定する
- [ ] requirements analysisから一つの中規模機能をIssueへ分解する
- [ ] implementation、program validation、review、human UI reviewを一巡させる
- [ ] agent-shellとCodex applicationの両方からattached invocationを試す
- [ ] brokerのpolling、並行実行、retry、yield/resume、crash recoveryを実作業で確認する
- [ ] 各Issueについて、手動で必要だったtracker操作とdaik操作を記録する
- [ ] pilotで得たfindingをdaik Issueへ戻し、優先度を付ける

### 8. Refinement and stabilization

- [ ] pilotで不要だった設定、event、用語を削減する
- [ ] 頻出した手動操作をcommand、skill、joint operationのどこへ置くか整理する
- [ ] standard workflowを実運用結果に基づいて更新する
- [ ] GitHub Issues jointのreference implementationまたは実用例を用意する
- [ ] operator向けstatusとlog表示でwaiting、attached、retryingを追跡できるようにする
- [ ] security boundary、secret redaction、permission設定を実環境で再確認する
- [ ] READMEには安定した利用方法だけを反映し、内部計画は本書へ残す

## Pilot workflow outline

```text
requirements (human + attached agent)
      │ Issues and dependencies
      ▼
implementation (broker-managed or attached agent)
      │
      ├── yielded / human ──▶ same state in a new activation
      ├── yielded / timer ──▶ same state after not_before
      ▼
program validation
      ▼
agent review
      ▼
UI review (human + optional attached agent)
      ▼
final
```

## Completion criteria

- 一つ以上のMakepad機能がrequirements discussionからUI reviewまでdaikで完了している
- 人間は任意のchat UIを利用でき、chat以外のtracker操作を日常的に要求されない
- broker-managed agentがhumanとtimerの両方でyieldし、新activationで安全に再開できる
- broker停止後もtracker上のcheckpointとresume conditionからworkを復旧できる
- requirements workが実装可能な子Issueと依存関係を作成できる
- UI reviewの結果、finding、判断者、証拠がIssue trackerへ残る
- `work status`とbroker logからrunning、waiting、retrying、attached workを追跡できる
- pilotで判明した重大なworkflowまたはsecurity上の問題が未整理のまま残っていない

## Out of scope

- daik独自chat UIの実装
- agent-shell、Codex applicationなどのnative session lifecycle管理
- 任意のresume条件式言語
- agentが直接ほかのworker processを起動する方式
- Makepad固有機能をdaik coreへ組み込むこと
