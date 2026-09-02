"""AgentCore Runtime entrypoint for MyAgent."""

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from agent.factory import create_agent
from browser_tools.playwright_setup import prepare_playwright
from invocation.request_parser import (
    extract_authenticated_request,
    extract_memory_identity,
    extract_prompt,
    validate_actor_identity,
)
from invocation.streaming import stream_agent
from memory.session import create_memory_session_manager

# ここで最初の実行 BedrockAgentCore　を起動する
app = BedrockAgentCoreApp()
log = app.logger

# ここも起動時の処理、playwrightの初期処理
prepare_playwright(log)


# runtimeの開始(AgentCore SDK)
@app.entrypoint
async def invoke(payload, context):
    # 「"""」で始まるものはdocstringで関数・ファイル・クラスの先頭におく説明文のようなもの
    """Validate one request, create its Agent, and stream the response."""
    log.info("Invoking Agent.....")

    # リクエストの受け取り
    prompt = extract_prompt(payload)
    # 認証情報受け取り
    authenticated_request = extract_authenticated_request(payload)
    memory_identity = extract_memory_identity(payload, context)

    # authenticated_user_idとactor_idが同じであることを確認する
    validate_actor_identity(memory_identity, authenticated_request)

    # テストで使った履歴なし会話(なくても良い)
    if memory_identity is None:
        agent = create_agent()
        async for event in stream_agent(agent, prompt, authenticated_request):
            yield event

        return

    actor_id, session_id = memory_identity

    # The context manager flushes buffered Memory events before the request ends.
    # 「with as 」は try finallyのようなもの create_memory_session_manager() が作成したオブジェクトを、ブロック内で session_manager という変数名で使用
    with create_memory_session_manager(actor_id, session_id) as session_manager:
        agent = create_agent(session_manager=session_manager)

        async for event in stream_agent(agent, prompt, authenticated_request):
            yield event


# サーバー起動
if __name__ == "__main__":
    app.run()
