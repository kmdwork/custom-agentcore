# C. Strands http_request

AgentCore RuntimeからBrowserを使わず、Strands Agents Toolsの `http_request` でWebページやHTTP APIへアクセスする最小構成です。

## 実装

`main.py`でToolをimportし、Agentへ登録するだけです。

```python
from strands_tools import http_request

tools = [http_request, get_current_datetime]
```

AgentCore Browser connection、Playwright、Chromium、Browserセッション管理は使用しません。

依存関係は通常版の `strands-agents-tools` です。

```toml
"strands-agents-tools == 0.8.8"
```

## 検証

プロジェクトルートで構成を検証します。

```bash
agentcore validate
```

ローカルRuntimeを起動する場合:

```bash
agentcore dev
```

別ターミナルから呼び出します。

```bash
agentcore invoke --dev "http_requestを使って https://example.com をGETし、内容を要約してください"
```

AWSへデプロイする場合:

```bash
agentcore deploy
agentcore invoke "http_requestを使って https://example.com をGETし、内容を要約してください"
```

HTMLをMarkdownへ変換するようモデルへ依頼することもできます。

```text
http_requestのconvert_to_markdownをtrueにして、
https://example.com をGETし、内容を要約してください
```

## Browser方式との違い

- JavaScriptを実行しません。
- クリック、フォーム入力、ログイン画面操作はできません。
- HTTPメソッド、ヘッダー、本文、クエリパラメーター、認証、リダイレクトなどを指定できます。
- HTMLやJSONを直接取得する用途ではBrowserより単純です。

認証トークンやパスワードをTool引数へ直接渡すと、トレースやログに残る可能性があります。本番用資格情報はAgentCore Identityなどから安全に渡す構成を検討してください。
