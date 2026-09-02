import unittest
from types import SimpleNamespace
from unittest.mock import patch

import main
from invocation.streaming import stream_agent


class FakeAgent:
    def __init__(self):
        self.received_prompt = None
        self.received_invocation_state = None

    async def stream_async(self, prompt, invocation_state):
        self.received_prompt = prompt
        self.received_invocation_state = invocation_state

        yield {"internal": "not an AgentCore event"}
        yield {"event": {"contentBlockStart": {}}}
        yield {"event": {"contentBlockDelta": {"delta": {"text": "Hello"}}}}


class StreamAgentTest(unittest.IsolatedAsyncioTestCase):
    async def test_filters_internal_events_and_passes_authentication_state(self):
        agent = FakeAgent()
        authentication = {
            "authenticated_user_id": "123",
            "user_access_token": "token",
        }

        events = [
            event
            async for event in stream_agent(agent, "prompt", authentication)
        ]

        self.assertEqual(events, [
            {"event": {"contentBlockDelta": {"delta": {"text": "Hello"}}}},
        ])
        self.assertEqual(agent.received_prompt, "prompt")
        self.assertIs(agent.received_invocation_state, authentication)

    async def test_no_memory_entrypoint_streams_and_finishes(self):
        agent = FakeAgent()

        with patch.object(main, "create_agent", return_value=agent):
            events = [
                event
                async for event in main.invoke(
                    {"prompt": "Hello"},
                    SimpleNamespace(session_id="unused-without-memory"),
                )
            ]

        self.assertEqual(events, [
            {"event": {"contentBlockDelta": {"delta": {"text": "Hello"}}}},
        ])
        self.assertEqual(agent.received_prompt, "Hello")
        self.assertEqual(agent.received_invocation_state, {})


if __name__ == "__main__":
    unittest.main()
