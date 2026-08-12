# ADR 0002: CLI wrapperとInvocation log

- Status: Proposed
- Date: 2026-08-12

## Context

daikはcoding agent softwareを外部processとして起動する。製品ごとにCLI option、
instruction、structured output、sandbox、session保存方式が異なるため、daikの共通
Invocation規約と各agent CLIの間に変換componentが必要である。また、agentの実行後に
問題を追跡できるlocal logが必要である。

`adapter`は一般的すぎ、tracker、agent CLI、将来の外部tool連携のどれを指すか
分かりにくい。このためdaik固有の用語を次のように区別する。

- **CLI wrapper**: daik Invocationとagent CLIのprocess規約を機械的に変換する
- **joint**: daikの意味的な中間operationとtrackerなど外部toolのmodelをmappingする

CLI wrapperはworkflowやIssue operationの意味を判断しない。jointは一般的な
adapter patternにおけるdaik固有のcomponent名である。

agent softwareは通常、native session transcriptを自身のstate directoryへ保存する。
daikが同じtranscriptを複製すると、容量、機密情報、retentionの管理が重複する。
一方、site内へlogを置くと、agentの探索、Gitへの誤commit、site共有時の漏洩を
招きやすい。

## Decision

### 1. Linuxのuser state directoryへInvocation logを置く

初期実装はLinuxのみを対象とし、daik state rootを次の優先順位で決定する。

1. `DAIK_STATE_HOME`
2. `$XDG_STATE_HOME/daik`
3. `$HOME/.local/state/daik`

`DAIK_STATE_HOME`はdaik rootそのものとし、末尾へさらに`daik`を追加しない。
siteに含まれる`.agents/daik-config.yaml`からstate rootを変更できないものとする。
他OSの標準directoryへのmappingはdaik command内へ将来追加する。

### 2. Site、Issue、Invocationごとにdirectoryを分ける

directory layoutは次とする。

```text
<state-root>/
└── sites/
    └── <site-slug>-<site-path-hash>/
        └── logs/
            └── <issue-slug>-<issue-hash>/
                └── <UTC-timestamp>-<invocation-id>/
```

site keyはcanonical site path、Issue keyはprovider-native Issue IDから生成する。
表示可能なslugだけで識別せず、hashを付けて衝突を避ける。Invocation IDは並行起動で
衝突しない一意な値とする。siteを移動した場合は新しいsite keyになり、以前のlogは
元のnamespaceに残る。

daik runnerはCLI wrapper起動前にInvocation directoryをowner-only permissionで
作成する。symlink、path traversal、既存Invocation directoryの再利用を拒否する。

### 3. Invocationへlocal log directoryを渡す

共通Invocationに次を含める。

```json
{
  "invocation_id": "0198f2a1-...",
  "log_directory": "/home/user/.local/state/daik/sites/.../logs/.../..."
}
```

`log_directory`はlocal CLI wrapper向けのabsolute pathであり、worker promptへ含める
必要はない。補助的に`DAIK_INVOCATION_ID`と`DAIK_LOG_DIRECTORY`もCLI wrapperの
environmentへ渡せる。

absolute path、native session path、Invocation log pathはIssue event、handoff、
workerの最終報告へ含めない。

### 4. Agent softwareのnative sessionをtranscriptの保存元とする

agent softwareが提供するsession保存機能を使用し、daikはnative transcriptを通常は
copyしない。CLI wrapperは実行後にnative sessionを特定し、共通resultのlocal-onlyな
参照としてdaikへ返す。

```json
{
  "native_artifacts": [
    {
      "type": "session",
      "id": "product-native-session-id",
      "path": "/home/user/.agent/sessions/..."
    }
  ]
}
```

native sessionの保存形式とpath解決は各CLI wrapperの責務であり、daik coreはCodex、
Claude Codeなどのdirectory layoutを知らない。

### 5. daikがnative sessionへのlinkを作る

daik runnerはCLI wrapperが返したsession参照を検証し、Invocation directory内へ
`native-session`、`native-session-2`のような固定名でsymbolic linkを作る。CLI wrapperに
link名を指定させない。

link作成前に少なくとも次を確認する。

- targetがabsolute pathで存在する
- targetがregular fileまたはdirectoryである
- targetのownerがdaik実行userと一致する
- Invocation directory内のlinkが未使用である

daikはtargetを再帰探索せず、内容をIssue trackerへ送らない。agent software側の
cleanupによってlinkが切れる場合に備え、session ID、元path、link名、CLI wrapper名、
link作成時刻を`native-session.json`にも記録する。

### 6. daik固有の記録だけを補助保存する

Invocation directoryにはnative transcriptとは別に、daikの呼び出しと結果を対応付ける
最小限の記録を置く。

```text
<invocation-directory>/
├── invocation.json
├── result.json
├── metadata.json
├── events.ndjson
├── wrapper.stderr.log
├── native-session -> <agent-software state directory>
└── native-session.json
```

`metadata.json`にはprotocol version、開始・終了時刻、exit status、CLI wrapper識別子を
記録する。environment全体やsecretを含み得るcommand optionは無加工で保存しない。
CLI wrapperのstdoutはprotocolとして検証し、正規化したrecordを`events.ndjson`へ
保存する。診断用stderrは長さの上限を設けて保存する。

これらはdebugとaudit用のartifactであり、workflow再開の正本ではない。brokerは
local logだけからcurrent state、visit count、claimを復元せず、Issue trackerのcontrol
eventを使用する。

### 7. Workerへlog directoryの権限を要求しない

native logはagent softwareのlauncher/session機能が保存し、daik固有logとsymlinkは
daik runnerが保存する。worker agent自身はInvocation log directoryを知らず、そこへの
書き込み権限を必要としない。siteとworktreeだけを書き込み可能にするsandboxと
両立させる。

## Consequences

- siteをGit管理、共有、archiveしてもInvocation logが混入しにくい。
- daik Invocationから製品固有session transcriptへ追跡できる。
- native transcriptの重複保存を避けられる。
- agent softwareのsession layout変更は対応するCLI wrapperだけに閉じ込められる。
- native sessionのretention次第でsymbolic linkが切れる可能性がある。
- logにはsource、Issue情報、tool出力が含まれ得るため、state rootのpermissionと
  retention管理が必要になる。

## Deferred decisions

- log一覧、検索、明示的archive、cleanup command
- retention policyと容量上限
- native sessionをcopyまたはarchiveする条件
- stderrとeventの具体的なsize limitとredaction方式
- Linux以外のstate directory mapping
