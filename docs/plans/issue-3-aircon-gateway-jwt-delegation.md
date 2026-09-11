# Issue #3: Cloudflare Aircon APIをAgentCore Gateway経由でJWT委譲する計画

## Goal

Better Authで認証されたユーザー向けにCloudflare Workerが発行する短期JWTを、モデルへ公開せずAgentCore Runtimeの呼び出し単位の状態として扱い、AgentCore Gateway経由でCloudflare Aircon Agent APIへそのまま委譲する。Strands Agentは5つのread ToolからD1の会社・物件・系統・機器・型式を検索でき、既存のBrowser、MCP、Memory、画像入力、ストリーミング契約を維持する。

Related to #3

## Current Behavior

- `app/MyAgent/main.py` は `prompt`、Harness互換 `messages`、`tool_results`、画像 `media` を受け取り、セッション・ユーザー単位でキャッシュしたAgentを `stream_async()` で実行している。
- 現在の `stream_async()` 呼び出しには `invocation_state` がなく、`user_access_token` の入力検証もない。
- 現在のToolは `read_web_page`、`add_numbers`、既存MCPクライアントで、Aircon Toolはない。
- AgentCore Memoryは `session_id` と `user_id` を使うが、呼び出しpayload全体やJWTを保存する処理はない。
- `agentcore/agentcore.json` には既存Gatewayがあるが、Cloudflare Aircon API向けtargetおよびRuntime用 `AIRCON_GATEWAY_URL` はない。
- Python側の既存テストはBrowser adapterのみで、Runtime入力、invocation state、Aircon HTTP境界の回帰テストはない。
- 参照するCloudflare契約は5つのPOST endpoint、`Authorization: Bearer <JWT>`、JSON body、認証失敗401、scope不足403である。

## Required Behavior

- Runtime payloadの `user_access_token` は非空文字列としてのみ受理し、Agent cache、Memory、prompt、messages、ログへ保存せず、呼び出しごとの `invocation_state` にだけ格納する。
- Toolはモデル入力にJWTやGateway URLを公開せず、`ToolContext.invocation_state` とRuntime環境変数から取得する。
- GatewayはCloudflare向けHTTPS targetへ受け取ったBearer tokenを `JWT_PASSTHROUGH` で転送し、再署名・再発行しない。
- 5つのread ToolはCloudflare API契約に沿うJSONを送り、サイズ上限、JSON検証、HTTP status別の安全なエラー変換を行う。
- 既存Agent機能とSSE event streamを維持し、実環境で正常系・認証異常系・機密情報非露出を確認する。

## Constraints and Non-goals

- CodeZip、Python 3.14、PUBLIC network、HTTP Runtimeを維持する。
- `agentcore/*.json` を構成の正本とし、生成済み `agentcore/cdk/` は直接編集しない。
- JWT refresh、AgentCore側でのJWT署名、Better Auth Cookie転送、`AGENT_API_TOKEN_SECRET` のAgentCore配置は行わない。
- write API、create/update/delete Tool、Cloudflare DB schema変更、5 APIを束ねる独自横断検索は行わない。
- 実Gateway ID/ARN、実endpoint、JWT、Authorization header、SecretをGitへ保存しない。
- Cloudflare側で将来追加される横断検索endpointは本Issueの対象外とする。

## Assumptions and Dependencies

- Cloudflare側PR #4 Phase 1/2の契約が対象環境へデプロイされ、5つのread endpointと同一のJWT仕様（HS256、audience `aircon-agent-api`、TTL 180秒、`aircon:read`）を提供する。
- Cloudflareのbase URL、生成後のGateway URL/ARNはデプロイ環境で与え、公開リポジトリにはプレースホルダーまたはデプロイ時注入手順だけを置く。
- GatewayはCloudflare JWTを検証せず、`authorizerType: NONE` とtargetの `JWT_PASSTHROUGH` によりBearer tokenを変更せず転送する。最終的な真正性・audience・期限・scope検証はCloudflareが担う。
- AgentCore CLI 0.28.1では `JWT_PASSTHROUGH` がpassthrough target専用のため、Cloudflareの `/api/agent/aircon` をbase endpointとする `CUSTOM` passthrough targetを使用する。Gatewayのtarget prefix配下へ5つの相対パスだけをToolから送る。
- `AIRCON_GATEWAY_URL` はRuntime環境変数から取得する。実値の注入方式は既存のAgentCore CLI/CDK生成フローに従い、生成済みCDKへ手作業で埋め込まない。

## Plan

- [ ] Phase 1: Runtimeで短期JWTを呼び出し単位の状態へ安全に渡す
- [ ] Phase 2: Cloudflare Aircon API向けGateway targetとJWT passthrough経路を構成する
- [ ] Phase 3: 5つのAircon read Toolと安全なHTTP境界を実装する
- [ ] Phase 4: 現行Agentへ統合し、既存契約を回帰テストする
- [ ] Phase 5: 実環境E2Eと機密情報非露出を検証する

## Phase 1: Runtimeで短期JWTを呼び出し単位の状態へ安全に渡す

### Scope

- Runtime payloadから `user_access_token` を独立して抽出・検証する。
- tokenをAgent生成前のキャッシュキーや永続化対象へ混ぜず、`agent.stream_async(..., invocation_state={...})` にだけ渡す。
- tokenなしでも通常会話は維持し、Aircon Tool使用時にだけ明確な認証エラーにできる状態を作る。
- payloadやinvocation state全体をログ出力しない回帰テストを追加する。

### Acceptance Criteria

- [ ] 非空のstring `user_access_token` が `invocation_state["user_access_token"]` として当該呼び出しへ渡る。
- [ ] 未指定は通常会話を拒否せず、invocation stateではtoken不在として扱われる。
- [ ] 空文字、空白のみ、非string tokenは入力エラーとなり、Agentを実行しない。
- [ ] tokenはAgent cacheのキー・値、Memory session manager、prompt、messagesへ追加されない。
- [ ] tokenまたはpayload全体をアプリケーションログへ出力する処理がないことをテストまたはログ捕捉で確認できる。
- [ ] `prompt`、`messages`、`tool_results`、画像入力、既存stream event filteringのテストが成功する。

## Phase 2: Cloudflare Aircon API向けGateway targetとJWT passthrough経路を構成する

### Scope

- Cloudflareの `/api/agent/aircon` をbase endpointとする `CUSTOM` passthrough targetを既存Gatewayへ追加する。
- Gatewayはinbound認証情報を変換せず、target outbound authに `JWT_PASSTHROUGH` を設定する。
- Runtimeから参照するGateway URLを `AIRCON_GATEWAY_URL` として外部設定可能にし、実値をソースへ固定しない。
- schema-first方針に従い `agentcore validate` とCDK synth差分で構成を検証する。

### Acceptance Criteria

- [ ] targetは `passthrough` / `CUSTOM` とし、endpointをCloudflareの `/api/agent/aircon` base pathへ限定する。
- [ ] targetのoutbound authは `JWT_PASSTHROUGH` で、OAuth/API key/AgentCore独自JWT発行を追加しない。
- [ ] Gatewayは `authorizerType: NONE` のままCloudflareを最終JWT検証者とし、Bearer tokenを変更せずdownstream `Authorization` へ渡せる。
- [ ] RuntimeコードはGateway URLを `AIRCON_GATEWAY_URL` から取得し、未設定時に機密情報を含まない構成エラーを返せる。
- [ ] 実Gateway ID/ARN/URL、Cloudflare Secret、JWTが新規Git差分に含まれない。
- [ ] `agentcore validate` と `cd agentcore/cdk && npm test -- --runInBand` が成功し、生成済みCDKを直接編集していない。

## Phase 3: 5つのAircon read Toolと安全なHTTP境界を実装する

### Scope

- `app/MyAgent/aircon_tools.py` にtoken取得、Gateway呼び出し、response制限、JSON検証、エラー変換の共通処理と5 Toolをまとめる。
- すべてのToolを `@tool(context=True)` とし、検索条件だけをモデル向けschemaへ公開する。
- request timeout、response byte上限、許容Content-Type、status別エラーを共通化する。
- 実ネットワークを使わない単体テストでrequestとresponse境界を検証する。

### Acceptance Criteria

- [ ] `search_aircon_companies(query="")`、`search_aircon_properties(query="", company_id="")`、`search_aircon_systems(query="", property_id="")`、`search_aircon_units(query="", system_id="")`、`search_aircon_models(query="")` が定義される。
- [ ] モデルへ公開される引数にJWT、Authorization、Gateway URL、Secretが含まれない。
- [ ] 各Toolは `ToolContext.invocation_state` のtokenを使い、token不在時はdownstreamへ接続せず認証エラーを返す。
- [ ] 5つの操作が対応するGateway操作へ `Content-Type: application/json` とBearer token付きで送信され、空の任意条件はCloudflare契約どおり省略または空bodyとして扱われる。
- [ ] timeoutとresponse body上限があり、上限超過、非JSON、想定外JSON shapeを安全なTool errorへ変換する。
- [ ] 400は入力エラー、401はtoken無効/期限切れ、403はscope不足、429は一時的な利用制限、5xx/通信失敗はupstream障害として区別できる。
- [ ] 例外、Tool result、ログ、mock assertion failureにtokenまたはAuthorization header全文を含めない。
- [ ] success、空配列、各status、timeout、過大response、不正JSON、tokenなしを単体テストが網羅する。

## Phase 4: 現行Agentへ統合し、既存契約を回帰テストする

### Scope

- 5 Toolを `main.py` の既存Tool collectionへ追加する。
- Agent cache、Memory、Browser、既存MCP、`add_numbers`、画像入力、streaming処理を維持する。
- Runtimeレベルのテストを追加し、同一キャッシュAgentへの連続呼び出しでもinvocation stateが呼び出し間で漏れないことを確認する。
- 必要な利用手順と環境変数をREADMEへ記録する。

### Acceptance Criteria

- [ ] 既存Toolに5つのAircon Toolが追加され、既存Toolが削除・改名されない。
- [ ] 同じsession/userで連続実行した場合も、ある呼び出しのtokenが次の呼び出しから参照できない。
- [ ] AgentCore Memoryへ保存される会話イベントにtokenが含まれず、既存namespaceとsession/actor mappingが維持される。
- [ ] BrowserのURL防御・timeout・truncate・cleanupテストが引き続き成功する。
- [ ] MCP/Knowledge Base接続、画像の形式・2 MiB制限、stream event filteringが維持される。
- [ ] READMEに `AIRCON_GATEWAY_URL`、Gateway/Cloudflare前提、180秒TTL、tokenをログ・Memoryへ保存しない運用を記載する。
- [ ] `cd app/MyAgent && uv lock --check && uv run python -m unittest discover -s tests -v` が成功する。

## Phase 5: 実環境E2Eと機密情報非露出を検証する

### Scope

- Gateway/targetとRuntimeを検証環境へデプロイし、CloudflareのサンプルD1データを使ってBrowserからの経路全体を確認する。
- 正常token、tokenなし、期限切れ/改ざんtoken、scope不足をそれぞれ確認する。
- CloudWatch/AgentCore trace、モデル出力、Tool error、公開差分を監査する。
- 検証後に孤立したGateway targetや不要な実値ファイルを残さない。

### Acceptance Criteria

- [ ] Better Auth loginから `POST /api/chat`、Runtime、Tool、Gateway、Cloudflare、D1、最終SSE回答までの正常経路でサンプルデータを取得できる。
- [ ] 5つのread Toolが実Gateway経由で対応データを返す。
- [ ] tokenなし、期限切れ/改ざんtokenは401相当、scope不足は403相当としてモデルへ機密情報なしで伝わる。
- [ ] Cloudflareで観測したdownstream AuthorizationのtokenがRuntimeへ渡したtokenと同一で、再署名・再発行されていないことを秘匿した検証手段で確認できる。
- [ ] JWT、Authorization header、Secretがモデル出力、Memory、Agent cache、CloudWatch/AgentCoreログ、trace属性に存在しない。
- [ ] 既存SSEのtext、tool、image、error、doneの扱いとBrowser/MCP/Memory機能に回帰がない。
- [ ] `agentcore validate`、`agentcore deploy --dry-run`、Python単体・回帰テスト、CDK test、公開前secret/identifier scanが成功する。

## Expected Change Boundary

- `agentcore/agentcore.json`
- `app/MyAgent/main.py`
- `app/MyAgent/aircon_tools.py`（new）
- `app/MyAgent/tests/test_main.py`（newまたは同等のRuntime回帰テスト）
- `app/MyAgent/tests/test_aircon_tools.py`（new）
- `app/MyAgent/README.md`
- `README.md`、`VERSIONS.md`（利用者向け変更記録が必要な場合）
- `app/MyAgent/pyproject.toml` と `uv.lock`（既存依存だけで安全なHTTP clientを実装できない場合のみ）

生成済み `agentcore/cdk/`、Memory schema、Cloudflare側コード/DBは変更対象外とする。

## Risks

- Cloudflare JWTはHS256でOIDC discovery endpointを持たないため、Gatewayの `CUSTOM_JWT` authorizerではなく `NONE + JWT_PASSTHROUGH` を前提とする。これによりGateway自体は公開経路となるため、公開操作を5つに限定し、Cloudflare側のJWT/scope検証とレート制限を最終防御とする。
- GatewayのCUSTOM passthrough targetが任意HS256 Bearer tokenを期待どおり転送し、base path外へ逸脱しないことはAWS実環境依存である。Phase 2で構成検証、Phase 5で同一tokenとpath routingを確認し、未対応なら認証境界を変更せず別方式を再設計する。
- token TTLは180秒でrefreshしないため、長時間の推論後はToolが401になる。自動再試行で期限切れtokenを繰り返さず、そのinvocationを認証失敗として終了する。
- Agentはsession/user単位でキャッシュされるため、tokenをAgent objectやTool closureへ保持するとユーザー間・呼び出し間漏えいになる。tokenは必ずinvocation stateから都度取得する。
- 既存 `mcp_client/client.py` には実Gateway URLに見える固定値がある。本Issueでは既存MCPの挙動を保つが、公開差分監査で新しい実値を増やさず、既存値の扱いは必要に応じて別Issueへ分離する。
- response上限とtimeoutの具体値はCloudflareの最大responseとAgentCore制限を確認して保守的に決め、テストとREADMEで契約化する。
- passthrough endpointと生成後Gateway URLの実値は公開用placeholderとデプロイ時注入を分離し、コミットしない。

## Questions

現時点で実装開始を止める未解決事項はない。実装時に、検証環境のCloudflare base URL、Gateway URL/ARNの注入値、E2Eで使うBetter Auth userをデプロイ担当者から受け取る必要があるが、これらは計画・コード構造を変更しない環境依存値として扱う。
