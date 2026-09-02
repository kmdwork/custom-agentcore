# MyAgentCore

Amazon Bedrock AgentCore上でStrands Agentを動かすためのプロジェクトです。

現在のv1.0は、AgentCore CLIの`agentcore create`で作成した初期構成です。Laravel連携、Knowledge Base、永続Memoryなどはまだ実装していません。

## 現在の機能

- Amazon Bedrock AgentCore Runtimeの基本構成
- Strands Agentsによる応答生成
- Amazon Bedrock上のClaudeモデルの利用
- Server-Sent Events（SSE）による応答ストリーミング
- サンプルTool `add_numbers`
- Streamable HTTP MCPクライアント
- `session_id`ごとのプロセス内会話保持

会話履歴はプロセス内だけに保持されるため、再起動やコールドスタートで失われます。

## ディレクトリ構成

```text
myagentcore-public/
├── agentcore/
│   ├── agentcore.json       # RuntimeなどのAgentCore設定
│   ├── aws-targets.json     # デプロイ先AWS環境の設定
│   └── cdk/                 # AgentCore CLIが生成したCDKコード
├── app/MyAgent/
│   ├── main.py              # Runtimeのエントリーポイント
│   ├── model/               # Bedrockモデルの生成処理
│   ├── mcp_client/          # MCPクライアント設定
│   ├── pyproject.toml       # Pythonプロジェクト設定
│   └── uv.lock              # 依存関係のロックファイル
└── VERSIONS.md              # バージョンごとの概要
```

## ローカルでの実行

```bash
cd app/MyAgent
uv sync
cd ../..
agentcore dev
```

別のターミナルから呼び出します。

```bash
agentcore invoke --dev "こんにちは"
```

## デプロイ

AWS Credentialとデプロイ先を設定したうえで実行します。

```bash
agentcore validate
agentcore deploy --dry-run
agentcore deploy
```

現在の`aws-targets.json`にはデプロイ先が登録されていないため、実際にデプロイする前にAWS環境の設定が必要です。

## 公開時の注意

- `.env.local`、AWS Credential、トークンなどの秘密情報はGitへ登録しません。
- `.venv`、`node_modules`、CDK生成物、AgentCore CLIの状態ファイルはGit管理外です。
- `agentcore/cdk/`はCLIによる生成コードのため、原則として直接編集しません。
- 外部MCPエンドポイントを利用する場合は、送信する情報と提供元の利用条件を確認してください。

今後の変更内容は[VERSIONS.md](VERSIONS.md)へ記録します。
