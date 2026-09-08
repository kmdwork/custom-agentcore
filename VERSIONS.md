# バージョン履歴

## v2.0

以前のHarness構成を置き換え、AgentCore Runtimeを一から新規作成。生成後にコードを変更していない`MyAgent`を保存した初期スナップショット。

Strands Agents、Claude Sonnet 4.5、CodeZip、Python 3.14、HTTP Runtimeで構成。サンプルの`add_numbers` Tool、Exa MCPクライアント、4種類のStrategyを持つ`MyAgentMemory`を含む。

## v1.1

`agentcore export harness --name MyHarness`で生成された、未編集の`MyHarnessAgent`を比較・検証用のスナップショットとして保存。元の`MyHarness`も残しているため、Harness構成とRuntime構成を比較できる。

エクスポートされたRuntimeはCodeZip、Python 3.14、HTTPプロトコルの構成。CodeZipではAgentCore Browserが除外されること、managed Memoryが永続Memoryとして移行されないこと、Gateway URLの設定と生成Toolの安全性確認が必要なことを記録。

## v1.02

HarnessにAgentCore Browser、Gateway経由のKnowledge Base検索、managed Memoryを追加。公開用設定ではAWSアカウントID、S3 URI、Gateway ARNをサンプル値へ置換。

## v1.01

Pythonで作成したAgent構成から、`harness.json`とシステムプロンプトで定義するAgentCore Harness構成へ変更。Claude Haiku 4.5を使用し、Tool、Skill、Memoryは未設定の最小構成。

## v1.0

AgentCore CLIの`agentcore create`で初期プロジェクトを作成。Strands Agent、Bedrockモデル、SSE応答、サンプルの加算Tool、MCPクライアントを含む最小構成。
