# MyAgentCore

Amazon Bedrock AgentCore Runtimeを利用する、Strands Pythonエージェントのサンプルプロジェクトです。

v2.0では、以前のHarness構成やHarnessからのエクスポート結果を引き継がず、AgentCore CLIでRuntimeを一から新規作成しました。`app/MyAgent/`は、生成後にエージェントコードを変更していない初期状態です。

## v2.0の構成

- プロジェクト名: `myruntime`
- Runtime名: `MyAgent`
- エージェントフレームワーク: Strands Agents
- モデル: Amazon BedrockのClaude Sonnet 4.5
- ビルド方式: CodeZip
- Runtime: Python 3.14
- プロトコル: HTTP
- ネットワークモード: PUBLIC
- Memory: `MyAgentMemory`
- サンプルTool: `add_numbers`
- MCP: 認証不要のExa MCPサンプル
- Harness、Knowledge Base、AgentCore Gateway: 未設定

## ディレクトリ構成

```text
myagentcore-public/
├── agentcore/
│   ├── agentcore.json       # RuntimeとMemoryの宣言
│   ├── aws-targets.json     # デプロイ先AWS環境
│   └── cdk/                 # AgentCore CLIが生成したCDKコード
├── app/MyAgent/
│   ├── main.py              # AgentCore Runtimeのエントリーポイント
│   ├── model/               # Bedrockモデルの設定
│   ├── memory/              # AgentCore Memoryとの連携
│   ├── mcp_client/          # Streamable HTTP MCPクライアント
│   ├── skills/              # Skill取得用コード
│   ├── pyproject.toml       # Pythonプロジェクト設定
│   └── uv.lock              # 依存関係のロックファイル
└── VERSIONS.md              # バージョン履歴
```

## Runtime

`app/MyAgent/main.py`では、`BedrockAgentCoreApp`の`@app.entrypoint`を使用してStrands Agentを公開します。

入力は、文字列の`prompt`、Harness互換の`messages`、または`tool_results`を受け付け、結果をストリーミングで返します。初期Toolとして、2つの数値を加算する`add_numbers`が登録されています。

モデルは`app/MyAgent/model/load.py`でClaude Sonnet 4.5を指定しています。

## Memory

`MyAgentMemory`はイベントを30日間保持し、次の4種類のMemory Strategyを設定しています。

- Semantic Memory
- User Preference Memory
- Summarization Memory
- Episodic Memory

Runtimeでは、呼び出し時のセッションIDとユーザーIDをMemoryの`sessionId`と`actorId`として使用します。Memory IDが環境変数へ設定されていないローカル環境では、AgentCore Memoryを使用せずに動作します。

## MCP

初期テンプレートには、認証不要のExa MCPサーバーへ接続するStreamable HTTPクライアントが含まれています。エージェントがこのToolを使用すると、検索内容などが外部サービスへ送信されるため、利用条件と送信データを確認してください。

不要な場合は、本番利用前にMCPクライアントを無効化または削除します。

## 検証とローカル実行

プロジェクトのルートで実行します。

```bash
agentcore validate
agentcore dev
```

別のターミナルからローカルRuntimeを呼び出します。

```bash
agentcore invoke --dev "1と2を足してください"
```

## デプロイ

AWS Credentialとデプロイ先を設定したうえで実行します。

```bash
agentcore deploy --dry-run
agentcore deploy
agentcore status
```

## 初期テンプレートの注意点

- このリポジトリは生成直後の比較・検証用スナップショットであり、本番向けの認証、認可、入力制限、レート制限は追加していません。
- ユーザーIDが呼び出しコンテキストにない場合は`default-user`が使用されます。複数ユーザーで運用する場合は、認証済みの非秘密ユーザーIDを必ず割り当てます。
- セッションごとのAgentインスタンスはプロセス内キャッシュにも保持されます。プロセス再起動やスケールアウトを前提に、永続状態はAgentCore Memory側で管理します。
- MCPなどの外部Toolへ、パスワード、Cookie、トークン、個人情報を送信しません。
- モデル回答とTool実行は確定的ではありません。重要な用途では、呼び出し側で検証とエラー処理を行います。

## 公開用の設定値

この公開リポジトリでは、AWSアカウントIDを次のプレースホルダーへ置き換えています。

```text
AWSアカウントID: <AWS_ACCOUNT_ID>
```

このままでは実環境へデプロイできません。`agentcore/aws-targets.json`へ利用するAWSアカウントIDを設定してください。

## 公開時の注意

- `.env.local`、AWS Credential、APIキー、トークンはGitへ登録しません。
- `.cli`、`.cache`、`.venv`、`cdk.out`、`node_modules`などのローカル状態や生成物はGit管理外です。
- `agentcore/cdk/`はAgentCore CLIによる生成コードのため、原則として直接編集しません。

変更履歴は[VERSIONS.md](VERSIONS.md)に記録しています。
