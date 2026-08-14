# ADR 0004: Human participationとactivationのyield/resume

- Status: Accepted
- Date: 2026-08-15

## Context

daikをGUI applicationの開発へ適用すると、要件分析、UI評価、承認など、人間が作業の
中心になるstateが必要になる。一方、通常のagent stateでも、小さな仕様確認、command
実行許可、外部testやCIの完了待ちなど、一時的に実行を継続できない場合がある。

これらをすべてworkflowの`human` stateへのtransitionとして表現すると、あらゆるagent
stateへ同じ例外edgeが必要になり、仕事の論理的な段階と実行上の待機が混ざる。また、
人間がagent-shell、Codex application、terminalなどのどのchat UIを使うかは、その時の
環境で変わる。daikが特定UIの起動やnative chat sessionの維持を担当するのは適切でない。

長時間待機中にagent processを維持する方式は、cost、process ownership、crash recovery、
並行数管理の点でも望ましくない。実行権をbrokerへ戻し、条件成立後に新しいagentを
起動して作業を継続できるmodelが必要である。

## Decision

### 1. Human stateでは人間が実行方法を選ぶ

`type: human`は、仕事そのものの責任主体が人間であるworkflow stateを表す。要件議論、
UI目視評価、承認、外部操作などが該当する。

daik workflowは、人間がAI agentを補助に使うか、どのchat UIを使うかを規定しない。
人間はsite rootで任意のagent UIを起動し、対象Issueのdaik workへ参加するよう指示
できる。attached agentはIssue、workflow、handoffを読み、人間との対話を支援し、
tracker更新とdaik操作を代行する。

daik coreはchat UIを起動、proxy、保存、resumeしない。agent software固有のsessionは
そのsoftwareとUIが所有する。

### 2. Agentの起動方法をworkflowから分離する

同じagent workは、brokerがCLI wrapperから起動する場合と、人間が任意UIで起動済みの
agentをattachする場合がある。

- **broker-managed invocation**: brokerが非対話的にagentを起動する
- **human-attached invocation**: 人間が起動したagentがdaik workへattachする

これはwork typeやworkflow state typeではなくruntime上の起動方法である。workflowへ
chat UIや`interactive` flagを定義しない。attached agentも同じtask、権限制約、transition
contractに従う。

人間が現在のattached invocationへ参加している場合、agentはstateを変えずに短い確認を
行ってよい。重要な回答はIssueへ記録する。broker-managed invocationに人間とのchannelが
ない場合、または長時間の回答待ちになる場合は、後述のyieldを使用する。

agent software自身のsandboxやcommand approval UIは、そのsoftwareのsecurity boundaryと
して扱い、daikが代替しない。非対話実行ではapproval待ちで無期限停止しないpolicyを
CLI wrapperへ設定する。

### 3. Workflow stateとactivation lifecycleを分離する

workflow stateは`implementation`や`review`など仕事の論理的段階を表す。stateを進める
ためにagentまたはprogramを一度起動することを**activation**と呼ぶ。同じworkflow state
に留まったまま、複数activationを実行できる。

activationの終了理由を**disposition**として次のように正規化する。

- `completed`: 宣言済みtransitionを選び、workflow stateを完了した
- `yielded`: stateを完了せず、継続情報と復帰条件を残して実行権をbrokerへ返した
- `failed`: invocationまたはresult protocolが異常終了した

`yield`は、協調的schedulerでtaskが実行権を自発的に譲る意味で使用する。満期や金融上の
利回りを意味しない。yield時にagent processは終了する。brokerは条件成立後、原則として
新しいactivationを起動する。

workflow stateとは別にruntime statusを持つ。

- `runnable`: activationを開始できる
- `running`: activationを実行中
- `waiting`: yieldedし、resume conditionを待っている

例えば`workflow state = implementation`かつ`runtime status = waiting`かつ
`resume.kind = human`を表現できる。これはworkflowのsubstateではなく、activationを
scheduleするための直交したruntime情報である。

### 4. Yield固有情報を一つのobjectへまとめる

`yielded` resultは、yield固有情報を`yield` objectに格納する。

```json
{
  "disposition": "yielded",
  "yield": {
    "reason": "A product decision is required",
    "checkpoint": {
      "summary": "Current behavior and two alternatives were documented",
      "artifacts": [],
      "decisions": [],
      "next_actions": [
        "Apply the selected compatibility policy"
      ]
    },
    "resume": {
      "kind": "human",
      "request": "Should the old configuration format remain supported?"
    }
  }
}
```

- `yield.reason`: 現activationを継続できない理由
- `yield.checkpoint`: 次activationが作業を継続するための永続情報
- `yield.resume`: brokerが再activationしてよい条件

`yield`と対になる語には`resume`を使う。ここでresumeするのはworkflow stateの実行であり、
同じOS process、agent process、native sessionを再開することを保証しない。

### 5. 初期resume conditionはhumanとtimerに限定する

初期仕様は次の二種類を扱う。

- `human`: 人間の応答またはattached agentによる明示的な再開を待つ
- `timer`: `not_before`で指定した時刻以後に再activationできる

```json
{
  "disposition": "yielded",
  "yield": {
    "reason": "The external test job is still running",
    "checkpoint": {
      "summary": "CI job build-1234 was submitted",
      "artifacts": ["https://ci.example/jobs/build-1234"],
      "next_actions": ["Inspect the completed test result"]
    },
    "resume": {
      "kind": "timer",
      "not_before": "2026-08-15T15:00:00Z"
    }
  }
}
```

timer yieldは、agent終了後も外部CIなどが独立して動作する場合に使用する。agentが管理外の
background processを残すことは認めない。将来必要になれば`external`、`signal`、
`dependency`などを追加するが、初期仕様で汎用条件式言語は作らない。

### 6. Yieldはworkflow transitionとvisitを消費しない

yieldではcurrent workflow stateを変更せず、transition countとstate visit countも
増やさない。代わりに次を別々に記録する。

- `visit_count`: 別stateからそのworkflow stateへ入った回数
- `activation_count`: stateを進めるためにexecutorを起動した回数
- `yield_count`: 同じvisit中にyieldした回数

無限yieldや再activation loopを防ぐため、activation数にはworkflow transition limitと
独立した上限が必要である。上限到達時の扱いはbrokerが記録し、人間の介入または明示的な
failure policyへ委ねる。

### 7. Trackerをyield/resumeの正本とする

`agent.yielded` eventはreason、checkpoint、resume condition、activation identityをIssue
trackerへ保存する。再activation時は新しい`agent.started` eventを記録し、必要なら
`resumed_from`で前activationを参照する。独立した`agent.resumed` eventは必須としない。

broker local logは運用診断用であり、waiting状態やresume conditionの復旧にはtrackerの
control eventを使う。brokerが停止しても、新しいbrokerはIssueからcurrent stateとyieldを
復元できる。

## Consequences

- あらゆるagent stateに`needs_human` transitionを追加する必要がなくなる。
- human待ち、timer待ち、将来の外部event待ちを同じactivation modelで扱える。
- workflow graphは仕事の論理構造に集中できる。
- 人間は任意のchat UIとagent softwareを実行時に選択できる。
- 待機中にagent processを維持するcostとfailure modeを避けられる。
- 新activationが前activationの暗黙contextを持たないため、checkpointとIssue記録の品質が
  重要になる。
- agent result、Issue event、tracker wrapper、broker scheduling、status表示へactivationと
  yield/resumeの概念を追加する必要がある。

## Deferred decisions

- attached invocationのCLI commandとresult受け渡し形式
- human responseをtracker上で表現するportable operation
- activationおよびyield回数の具体的な上限と上限到達policy
- `external`、`signal`、`dependency` resume condition
- native agent sessionをbest-effortで再利用する条件
- attached agent向けskillの具体的なpromptと配布方法
