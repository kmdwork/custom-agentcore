# MyAgentCore

Amazon Bedrock AgentCore上で動作する、Strands Agentsベースのサンプルアプリケーションです。

LaravelアプリケーションからAgentCore Runtimeを呼び出し、会話、画像入力、Memory、Knowledge Base、Laravel内のデータ検索・登録を組み合わせる構成になっています。

## 主な機能

- Strands Agentsによる応答生成
- Server-Sent Events（SSE）によるストリーミング応答
- AgentCore Memoryを利用したユーザーごとの会話記憶
- Amazon Bedrock Knowledge Baseの検索
- AgentCore Browserを利用したWeb閲覧
- Laravelに登録された顧客情報の検索
- Laravelに登録されたエアコン情報の検索
- Laravelへのエアコン情報登録
- Laravel Sanctumトークンを利用したTool API認証

## 構成

```text
myagentcore-public/
├── agentcore/
│   ├── agentcore.json          # Runtime、Memory、Knowledge Base、Gateway設定
│   ├── aws-targets.json        # AWSアカウントとリージョン設定
│   ├── schemas/                # APIスキーマ
│   └── cdk/                    # AgentCore CLIが利用するCDKコード
└── app/MyAgent/
    ├── main.py                 # AgentCore Runtimeのエントリーポイント
    ├── agent/                  # Agent生成、プロンプト、Tool登録
    ├── browser_tools/          # AgentCore Browser関連処理
    ├── invocation/             # リクエスト検証とストリーミング処理
    ├── laravel_tools/          # Laravel APIを呼び出すTool
    ├── memory/                 # AgentCore Memory設定
    ├── mcp_client/             # Knowledge Base Gateway接続
    ├── model/                  # モデル設定
    └── tests/                  # ユニットテスト
```

## Laravel Tool

Agentから利用できるLaravel Toolは次の3つです。

| Tool | 処理 |
| --- | --- |
| `search_customers` | 顧客情報を検索する |
| `search_airconditioner` | エアコン情報を検索する |
| `register_airconditioner` | エアコン情報を登録する |

認証情報はモデルの引数には含めず、Laravelから渡された認証済み情報をStrandsの`ToolContext`から取得します。

## 公開用設定

このリポジトリの設定値は公開用のサンプルです。デプロイ前に次の値を実際の環境へ置き換えてください。

```text
https://laravel.example.com/api/agent-tools
s3://example-agentcore-knowledge-base
AWSアカウントID: <AWS_ACCOUNT_ID>
```

秘密情報は`.env.local`などのGit管理外ファイルで管理してください。Laravelとの通信にはHTTPSを使用し、SanctumトークンやAWS Credentialを`agentcore.json`へ直接記載しないでください。

## 開発準備

Python 3.10以上、`uv`、AgentCore CLI、AWS Credentialが必要です。Python依存関係は次のコマンドで用意します。

```bash
cd app/MyAgent
uv sync
cd ../..
```

## 動作確認

プロジェクトのルートで実行します。

```bash
app/MyAgent/.venv/bin/python -m unittest discover -s app/MyAgent/tests -v
agentcore validate
```

## デプロイ

設定差分を確認してからデプロイします。

```bash
agentcore deploy --dry-run
agentcore deploy --diff
agentcore deploy
```

デプロイ後はRuntimeの状態を確認できます。

```bash
agentcore status --runtime MyAgent
```

## 注意事項

- `agentcore/agentcore.json`を構成の正本として扱います。
- `agentcore/cdk/`の生成コードは直接編集しません。
- Resourceの`name`を変更すると、AWSリソースが再作成される場合があります。
- `.env.local`、CLI状態、ログ、トレース、仮想環境、生成物はGitへ登録しません。
