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

### Harnessの制約と注意点

このリポジトリで使用している宣言的Harnessには、次の制約があります。

- **画像入力には未対応**: 現在の`InvokeHarness`のメッセージ入力には画像用のContent Blockがなく、この構成でも画像受信を確認できませんでした。画像を扱う場合は、画像入力に対応する独自のAgentCore Runtimeなど、別の構成を検討する必要があります。
- **任意のアプリケーション処理は追加できない**: `harness.json`ではモデル、Tool、Skill、Memoryなどを宣言できますが、ログイン状態の検証、独自の認可、リクエストの加工、外部DBの参照、レスポンス整形といった任意のコードは実装できません。必要な場合は、コードベースのAgentCore Runtimeへ移行します。
- **クライアント認証は呼び出し側で行う**: Harness自体はWebクライアントのユーザー登録やログイン状態を管理しません。メールアドレスとパスワード、Cookie、セッショントークンなどの認証情報をHarnessやモデルへ送信してはいけません。信頼できるバックエンドで認証し、必要な場合は秘密情報ではない内部ユーザーIDだけを`runtimeUserId`およびMemory用の`actorId`として渡します。
- **会話とMemoryの分離はIDの管理に依存する**: 会話の継続には同じ`session_id`を使用し、ユーザーごとに安定した`actorId`を割り当てます。異なるユーザー間でこれらのIDを使い回すと、会話やMemoryが意図せず共有されるおそれがあります。
- **機密情報を入力しない**: 入力、モデル出力、Toolの実行結果がログやMemoryへ保存される可能性を考慮し、パスワード、認証トークン、Cookie、秘密鍵などを含めません。
- **回答やTool実行は確定的ではない**: モデルの回答、Knowledge Baseの検索結果、BrowserやGatewayの実行は、モデル、権限、接続先、データの状態に依存します。重要な判断に利用する場合は、呼び出し側で検証やエラー処理を行います。

そのため、ブラウザからHarnessを直接呼び出すのではなく、認証、認可、入力検証、IDの割り当てを行うバックエンドを経由させます。

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
