# MyAgentCore

Amazon Bedrock AgentCore Harnessを利用する、宣言的なAIエージェントプロジェクトです。

現在のv1.01では、PythonのAgentコードを配置せず、`harness.json`とシステムプロンプトからAgentの構成を定義しています。

## 現在の構成

- Harness名: `MyHarness`
- モデルプロバイダー: Amazon Bedrock
- モデル: Claude Haiku 4.5
- Tool: 未設定
- Skill: 未設定
- Memory: 無効
- システムプロンプト: 汎用アシスタント

## ディレクトリ構成

```text
myagentcore-public/
├── agentcore/
│   ├── agentcore.json       # Harnessを含むAgentCore全体の設定
│   ├── aws-targets.json     # デプロイ先AWS環境の設定
│   └── cdk/                 # AgentCore CLIが生成したCDKコード
├── app/MyHarness/
│   ├── harness.json         # モデル、Tool、Skill、Memoryの設定
│   └── system-prompt.md     # Harnessへ渡すシステムプロンプト
└── VERSIONS.md              # バージョンごとの概要
```

## 設定ファイル

`app/MyHarness/harness.json`がHarnessの基本設定です。

```json
{
  "name": "MyHarness",
  "model": {
    "provider": "bedrock",
    "modelId": "global.anthropic.claude-haiku-4-5-20251001-v1:0"
  },
  "tools": [],
  "skills": [],
  "memory": {
    "mode": "disabled"
  }
}
```

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

公開リポジトリの`aws-targets.json`ではAWSアカウントIDを`<AWS_ACCOUNT_ID>`に置き換えています。実際にデプロイするときは、ローカル環境で対象アカウントの値を設定してください。

## 公開時の注意

- `.env.local`、AWS Credential、APIキー、トークンはGitへ登録しません。
- `.cli`、`cdk.out`、`node_modules`などの生成物はGit管理外です。
- `agentcore/cdk/`はAgentCore CLIによる生成コードのため、原則として直接編集しません。
- Tool、Skill、Memoryを追加した場合は、外部サービスへ送信する情報と権限設定を確認します。

変更履歴は[VERSIONS.md](VERSIONS.md)に記録しています。
