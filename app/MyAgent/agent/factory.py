"""Create a fully configured Strands Agent."""

import os
from uuid import uuid4

from strands import Agent
# from strands.agent.conversation_manager.null_conversation_manager import (
#     NullConversationManager,
# )
from strands.agent.conversation_manager import (
    SlidingWindowConversationManager,
)

from agent.prompts import create_system_prompt
from agent.tool_registry import create_tools
from browser_tools.reliable_agentcore_browser import ReliableAgentCoreBrowser
from model.load import load_model


def create_agent(session_manager=None) -> Agent:
    """Create a fresh agent, optionally backed by AgentCore Memory."""
    # A closed AgentCoreBrowser instance cannot initialize another session.
    # Use one new Browser instance for every Runtime invocation.
    browser = ReliableAgentCoreBrowser(
        region=os.getenv("AWS_REGION", "ap-northeast-1"),
        identifier="aws.browser.v1",
        session_timeout=300,
    )

    # Browser session names have a maximum length of 36 characters.
    browser_session_name = f"b-{uuid4().hex}"

    arguments = {
        "model": load_model(),
        "system_prompt": create_system_prompt(browser_session_name),
        # ブラウザツール以外のツールの呼び出し
        "tools": [browser.browser, *create_tools()],
        "conversation_manager": SlidingWindowConversationManager(
            window_size=40,
        ),
        "hooks": [],
    }

    if session_manager is not None:
        arguments["session_manager"] = session_manager

    return Agent(**arguments)
