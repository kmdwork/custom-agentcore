import os
# これらはAgentCore SDKが提供しているクラス (https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/strands-sdk-memory.html)
from bedrock_agentcore.memory.integrations.strands.config import (
    AgentCoreMemoryConfig,
    RetrievalConfig,
)
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)


MEMORY_ID_ENV_VAR = "MEMORY_MYAGENTMEMORY_ID"


def create_memory_session_manager(
    actor_id: str,
    session_id: str,
) -> AgentCoreMemorySessionManager:
    """Create a Memory session for one authenticated user conversation."""
    memory_id = os.getenv(MEMORY_ID_ENV_VAR)

    if not memory_id:
        raise RuntimeError(
            f"{MEMORY_ID_ENV_VAR} is not set. Deploy MyAgentMemory before using memory."
        )

    region = os.getenv("AWS_REGION", "ap-northeast-1")

    config = AgentCoreMemoryConfig(
        memory_id=memory_id,
        actor_id=actor_id,
        session_id=session_id,
        batch_size=1,
        filter_restored_tool_context=True,
        retrieval_config={
            # 長期記憶の検索方法を指定する設定クラス (関連度0.5以上の記憶を最大3件取得)
            "/users/{actorId}/facts": RetrievalConfig(
                top_k=3,
                relevance_score=0.5,
            ),
        },
    )

    # AgentCore MemoryとStrands Agentを接続するSession Managerクラス
    return AgentCoreMemorySessionManager(
        agentcore_memory_config=config,
        region_name=region,
    )
