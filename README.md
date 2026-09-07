# MyAgentCore

Amazon Bedrock AgentCore Harnessを利用する、宣言的なAIエージェントプロジェクトです。

現在のv1.02では、PythonのAgentコードを配置せず、Harnessの設定ファイルからBrowser、Knowledge Base、Memoryを利用できる構成にしています。

## 現在の構成

- Harness名: `MyHarness`
- モデルプロバイダー: Amazon Bedrock
- モデル: Claude Haiku 4.5
- Browser: AgentCore BrowserをToolとして利用
- Knowledge Base: AgentCore Gateway経由で検索
- Memory: managed Memoryを利用
- Skill: 未設定
- システムプロンプト: 汎用アシスタント

## ディレクトリ構成

```text
myagentcore-public/
├── agentcore/
│   ├── agentcore.json       # Knowledge Base、Gateway、Harnessの登録
│   ├── aws-targets.json     # デプロイ先AWS環境の設定
│   └── cdk/                 # AgentCore CLIが生成したCDKコード
├── app/MyHarness/
│   ├── harness.json         # モデル、Tool、Skill、Memoryの設定
│   └── system-prompt.md     # Harnessへ渡すシステムプロンプト
└── VERSIONS.md              # バージョンごとの概要
```

## Harness

`app/MyHarness/harness.json`では、次のToolとMemoryを有効にしています。

- `browser`: Webサイトの閲覧に使用するAgentCore Browser
- `strands-app-tools`: Knowledge Baseへ接続するAgentCore Gateway
- `managed` Memory: Harness専用のAgentCore Memoryをデプロイ時に作成

同じ会話を継続するときは、呼び出し側で同じ`session_id`を使用します。

## Knowledge Base

`agentcore/agentcore.json`で次のリソースを定義しています。

- S3をデータソースとする`MyKnowledgeBase`
- Knowledge Baseへ接続するGateway `strands-app-tools`
- 複数段階で検索する`AgenticRetrieveStream`
- 通常検索を行う`Retrieve`

Harnessはデプロイ済みGatewayのARNを参照し、Gateway経由でKnowledge BaseをToolとして呼び出します。

## 検証とローカル実行

プロジェクトのルートで実行します。

```bash
agentcore validate
agentcore dev
```

別のターミナルからHarnessを呼び出します。

```bash
agentcore invoke --harness MyHarness \
  --session-id "$(uuidgen)" \
  "こんにちは"
```

## デプロイ

AWS Credentialとデプロイ先を設定したうえで実行します。

```bash
agentcore deploy --dry-run
agentcore deploy
agentcore status
```

managed Memoryの初回作成には時間がかかる場合があります。

## 公開用の設定値

この公開リポジトリでは、AWS環境を特定できる値を次のサンプル値へ置き換えています。

```text
AWSアカウントID: <AWS_ACCOUNT_ID>
S3 URI: s3://example-agentcore-knowledge-base
Gateway ARN: <AGENTCORE_GATEWAY_ARN>
```

このままでは実環境へデプロイできません。ローカルで実際のAWSアカウントID、S3 URI、デプロイ済みGateway ARNを設定してください。

## 公開時の注意

- `.env.local`、AWS Credential、APIキー、トークンはGitへ登録しません。
- `.cli`、`cdk.out`、`node_modules`などのローカル状態や生成物はGit管理外です。
- `agentcore/cdk/`はAgentCore CLIによる生成コードのため、原則として直接編集しません。
- BrowserやKnowledge Baseへ機密情報を送信しないよう、入力内容と権限設定を確認します。

変更履歴は[VERSIONS.md](VERSIONS.md)に記録しています。
