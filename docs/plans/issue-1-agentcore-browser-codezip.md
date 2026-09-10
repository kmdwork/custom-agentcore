# Issue #1: AgentCore BrowserをCodeZip Runtimeへ最小構成で導入する計画

## Goal

CodeZip / Python 3.14の現行Runtimeを維持したまま、Amazon Bedrock AgentCore Browserを利用する高レベルStrands Tool `read_web_page(url)` を追加する。

BrowserセッションはTool呼び出しごとに生成・使用・終了し、モデルへ低レベルBrowser APIを公開しない。既存のAgentキャッシュ、Memory、MCP、画像入力、ストリーミング処理は維持する。

Related to #1

## Requirement Model

### Current behavior

- `agentcore/agentcore.json` の `MyAgent` はCodeZip / Python 3.14 / HTTP / PUBLIC構成で、Browser connectionはない。
- `app/MyAgent/main.py` は `session_id/user_id` 単位でAgentをプロセス内キャッシュし、Memory、MCP、画像入力、`stream_async` を扱う。
- `app/MyAgent/pyproject.toml` にBrowser/Playwright依存はない。
- 現在のロックファイルは `bedrock-agentcore 1.22.0` と `strands-agents 1.54.0` を解決している。
- 過去の `v0` には、Playwright付属Node.jsを `/tmp` へコピーするCodeZip workaroundと、`domcontentloaded` / 20秒timeout / 本文20,000文字制限の実装実績がある。
- 現行 `main` のWorking Treeはcleanで、Issueに関連する既存PR・計画ブランチはない。

### Required behavior

- 標準Browser resource `aws.browser.v1` を利用する。
- モデルへ公開するBrowser Toolは `read_web_page(url)` のみとする。
- 1回のTool呼び出し内でBrowserセッションを開始し、navigationと本文取得を行い、成功・失敗にかかわらず終了する。
- navigationは `networkidle` を待たず、`domcontentloaded` と20秒timeoutを使用する。
- モデルへ返す本文を20,000文字に制限する。
- Browserオブジェクトや停止済みPlaywright instanceをAgentキャッシュへ保持しない。
- CodeZip / Python 3.14、既存Agent factory/cache、Memory、MCP、画像、stream処理を維持する。

### Constraints and non-goals

- 生成済み `agentcore/cdk/` は直接編集しない。
- Container化、custom Browser、Browser profile、recording、VPC Browser、login、form submit、Cookie操作は対象外。
- Browserセッションを複数ターンで維持しない。
- `initSession`、`navigate`、`getText`、`close` などの低レベルAPIをモデルへ直接公開しない。
- Agent factory/cacheの大規模な再構成を行わない。
- 実AWS識別子、Browser ARN、セッションID、認証情報をリポジトリへ保存しない。

### Assumptions

- `strands-agents-tools[agent-core-browser]==0.8.8` を第一候補とする。Python 3.14を宣言上サポートし、`bedrock-agentcore>=1.1.0,<1.23.0` のため現行1.22.0と整合する。
- Git commit固定や `override-dependencies` は通常のlock更新で解決できない場合に限って再検討する。
- standard Browser connectionには実ARNを設定せず、宣言的な `type: browser` を使用する。
- `read_web_page` は公開Webページのテキスト取得に限定し、HTML、Cookie、認証ヘッダーを返さない。

### Questions resolved for this plan

- `strands-agents-tools v0.8.8` の `AgentCoreBrowser` は開始したBrowserClientを停止用辞書へ登録していないため、標準 `close` だけにcleanup保証を依存しない。
- adapter内で開始したBrowserClientを明示的に保持し、`finally` から `stop()` を必ず試行する。Playwright接続の終了と管理Browserセッションの停止を別々に検証する。
- URLは `http` / `https` のみ許可し、userinfo付きURL、localhost、private/link-local宛てを拒否する。redirect後の最終URLにも同じ境界を適用する。

## Plan

- [ ] Phase 1: Browser接続とPython 3.14互換の依存関係を追加する
- [ ] Phase 2: cleanup保証を持つ1回完結型Browser adapterを実装する
- [ ] Phase 3: 現行Agentへ最小限に接続し、既存入出力の回帰を防ぐ
- [ ] Phase 4: CodeZip Runtimeで統合検証し、公開差分を監査する

## Phase Details and Acceptance Criteria

### Phase 1: Browser接続と依存関係

#### Scope

- `agentcore/agentcore.json` の `MyAgent` Runtimeへ `managedBrowser` connectionを追加する。
- `app/MyAgent/pyproject.toml` へ `strands-agents-tools[agent-core-browser]==0.8.8` を追加する。
- `uv lock` を更新し、既存のAgentCore/Strands依存とPython 3.14で解決できることを確認する。
- Git URL sourceやdependency overrideは、通常解決に失敗しない限り追加しない。

#### Acceptance criteria

- [ ] Runtimeの `build` は `CodeZip`、`runtimeVersion` は `PYTHON_3_14` のままである。
- [ ] connectionは `{"id":"managedBrowser","to":{"type":"browser"}}` と等価で、実Browser ARNを含まない。
- [ ] `agentcore validate` が成功する。
- [ ] `uv lock --check` が成功する。
- [ ] Python 3.14環境で `AgentCoreBrowser`、Playwright、AgentCore BrowserClientをimportできる。
- [ ] `bedrock-agentcore 1.22.x` とBrowser extraの依存範囲が衝突しない。

### Phase 2: 1回完結型Browser adapter

#### Scope

- `app/MyAgent/agentcore_browser.py` を新設する。
- `prepare_playwright(log)` を実装し、Playwright付属Node.jsを実行可能な `/tmp/playwright-driver-node` へ配置する。
- 初期化は同一プロセス内で安全に再実行でき、packaged nodeが存在しない場合は明確に失敗させる。
- 最小化した `ReliableAgentCoreBrowser` でBrowserClientの追跡、`domcontentloaded`、20秒timeout、本文20,000文字制限を扱う。
- `read_web_page(url)` を唯一のモデル向けBrowser Toolとして実装する。
- 36文字以下のランダムな内部セッション名を使う。
- `initSession → navigate → getText` を実行し、`finally` でPlaywright接続と管理Browserセッションを終了する。
- URLのscheme、userinfo、ホスト、解決先IPを検証し、localhost、private、loopback、link-localを拒否する。redirect後も再検証する。
- URL query/fragment、Cookie、認証ヘッダー、ページHTMLをログやTool結果へ露出しない。

#### Acceptance criteria

- [ ] 正常時に `body` の本文だけを返す。
- [ ] 20,000文字を超える本文は明示的なtruncation表示付きで切り詰められる。
- [ ] navigationは `wait_until="domcontentloaded"`、`timeout=20_000` を使用する。
- [ ] 不正scheme、userinfo付きURL、内部ネットワーク宛てURLをBrowser開始前に拒否する。
- [ ] redirect後に禁止された宛先へ到達した場合も本文を返さない。
- [ ] init、navigate、本文取得、Playwright close、BrowserClient stopの各失敗経路を単体テストする。
- [ ] 成功・失敗のどちらでもBrowserClientの `stop()` が少なくとも1回試行される。
- [ ] cleanup失敗は元の例外を隠さず、安全にログへ残される。
- [ ] BrowserオブジェクトはモジュールグローバルまたはAgentキャッシュへ保存されない。

### Phase 3: 現行Agentへの統合と回帰防止

#### Scope

- `app/MyAgent/main.py` で `prepare_playwright` と `read_web_page` をimportする。
- Runtime起動時にPlaywrightのCodeZip準備を行う。
- 既存 `tools` 配列へ `read_web_page` を追加する。
- Agent factory/cache key、Memory session manager、MCP client、画像検証、payload解析、`stream_async` は変更しない。
- `app/MyAgent/tests/test_agentcore_browser.py` と必要最小限の回帰テストを追加する。

#### Acceptance criteria

- [ ] モデルへ公開されるBrowser Toolは `read_web_page` だけで、低レベル `browser.browser` は公開されない。
- [ ] 同一キャッシュ済みAgentから複数回呼び出しても、各Tool呼び出しが新しいBrowserセッションを使用する。
- [ ] 終了済みPlaywright instanceを次回呼び出しが再利用しない。
- [ ] `add_numbers` と既存MCP Toolの登録が維持される。
- [ ] plain prompt、messages、tool results、画像入力の既存payload処理が維持される。
- [ ] 既存のstream event filteringが維持される。
- [ ] `python -m unittest discover -s tests` が成功する。

### Phase 4: CodeZip統合検証と公開差分監査

#### Scope

- CodeZip packageへPlaywright driver/nodeが含まれることを確認する。
- `agentcore dev` で公開テストページ、長文ページ、timeoutケースを確認する。
- 承認されたAWS環境で標準Browser connectionを用いたRuntime invocationを確認する。
- RuntimeログまたはBrowser session APIで、呼び出し後に孤立セッションが残らないことを確認する。
- 実装差分を公開前監査する。

#### Acceptance criteria

- [ ] `agentcore validate` が成功する。
- [ ] CodeZip環境でNode.jsを `/tmp` から実行できる。
- [ ] 公開ページの本文を取得できる。
- [ ] 継続的なバックグラウンド通信があるページでも `networkidle` 待ちで停止しない。
- [ ] 長文ページで20,000文字上限が機能する。
- [ ] navigation失敗後も管理Browserセッションが終了する。
- [ ] Memory、MCP、画像入力、ストリーミングへ回帰がない。
- [ ] `github-public-audit --mode diff` で新規CRITICAL/HIGH/MEDIUM実値が検出されない。
- [ ] 差分にAWSアカウントID、Browser ARN、Browser session ID、認証情報、ローカル絶対パスが含まれない。

## Expected Change Boundary

Implementation is expected to touch only:

- `agentcore/agentcore.json`
- `app/MyAgent/pyproject.toml`
- `app/MyAgent/uv.lock`
- `app/MyAgent/agentcore_browser.py`（new）
- `app/MyAgent/tests/test_agentcore_browser.py`（new）
- `app/MyAgent/main.py`

`agentcore/cdk/`、Memory、MCP、model、image parsing、streaming implementationは原則変更しない。

## Dependencies

- `strands-agents-tools[agent-core-browser]==0.8.8`
- `bedrock-agentcore 1.22.x`
- `playwright>=1.42.0,<2.0.0`（Browser extra経由）
- 標準Browser resource `aws.browser.v1`
- AgentCore Browserを開始・停止できるRuntime execution role
- CodeZip artifactへ同梱されたPlaywright Node driver

## Risks

- **Managed session leak:** `AgentCoreBrowser v0.8.8` の標準cleanupだけではBrowserClient停止を保証できない可能性がある。adapterがClientを明示追跡し、すべての経路で `stop()` を検証する。
- **Upstream private behavior:** `ReliableAgentCoreBrowser` がupstream内部実装へ依存する。Browser固有コードを1ファイルへ隔離し、SDK移行時の変更境界を限定する。
- **CodeZip execution:** 配布先の読み取り専用領域ではPlaywright Nodeを実行できない可能性がある。実行可能な `/tmp` へのコピーを起動時に検証する。
- **Event-loop interaction:** Strandsの非同期stream中にBrowser Tool独自のevent loopが動く。単体テストとRuntime integrationでdeadlockがないことを確認する。
- **SSRF and data exposure:** 任意URL Toolは内部ネットワークアクセスや大量本文返却の入口になる。scheme/host/IP/redirect制限と本文上限をadapter内で強制する。
- **DNS rebinding:** 事前解決だけではredirectや再解決を完全には制御できない。最終URLの再検証を必須とし、必要ならBrowserのrequest interceptionを後続hardeningとして検討する。
- **Dependency drift:** Git commit固定を避ける代わりに、0.8.8を固定しlockfileをレビューする。
- **Existing public history:** 過去コミットの既知MEDIUM識別子は本Issueの変更対象外。新規差分には実インフラ識別子を追加しない。
- **Documentation mismatch:** root READMEの「生成後未変更」という説明は現行コードと一致しないが、Issueの明示変更境界外のため、本PR計画では実装修正対象に含めない。必要なら別Issueで扱う。

## Current Phase

Planning complete. Implementation has not started. Next: Phase 1.
