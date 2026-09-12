import unittest

import main


class RuntimeInputTests(unittest.TestCase):
    def test_extracts_token_only_into_invocation_state(self):
        payload = {"prompt": "hello", "user_access_token": "delegated-token"}
        self.assertEqual(main._extract_prompt(payload), "hello")
        self.assertEqual(
            main._extract_invocation_state(payload),
            {"user_access_token": "delegated-token"},
        )

    def test_token_is_optional(self):
        self.assertEqual(main._extract_invocation_state({"prompt": "hello"}), {})

    def test_rejects_invalid_tokens_before_agent_use(self):
        for token in ("", "   ", 123, None, []):
            with self.subTest(token=token), self.assertRaises(ValueError):
                main._extract_invocation_state({"prompt": "hello", "user_access_token": token})

    def test_existing_tools_and_aircon_tools_are_registered(self):
        names = {getattr(value, "tool_name", None) for value in main.tools}
        self.assertTrue({
            "read_web_page",
            "add_numbers",
            "search_aircon_companies",
            "search_aircon_properties",
            "search_aircon_systems",
            "search_aircon_units",
            "search_aircon_models",
        }.issubset(names))
        self.assertTrue(any(type(value).__name__ == "MCPClient" for value in main.tools))

    def test_image_contract_is_unchanged(self):
        png = b"\x89PNG\r\n\x1a\ncontent"
        import base64

        result = main._extract_prompt({
            "prompt": "describe",
            "media": {
                "type": "image",
                "format": "png",
                "data": base64.b64encode(png).decode("ascii"),
            },
        })
        self.assertEqual(result[0], {"text": "describe"})
        self.assertEqual(result[1]["image"]["source"]["bytes"], png)


class RuntimeStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_invocation_state_is_replaced_for_each_cached_agent_call(self):
        class FakeAgent:
            def __init__(self):
                self.calls = []

            async def stream_async(self, prompt, *, invocation_state):
                self.calls.append((prompt, dict(invocation_state)))
                yield {"event": {"messageStop": {"stopReason": "end_turn"}}}

        agent = FakeAgent()
        first = [event async for event in main._stream_filtered_events(
            agent, "first", {"user_access_token": "first-token"}
        )]
        second = [event async for event in main._stream_filtered_events(
            agent, "second", {}
        )]

        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertEqual(agent.calls, [
            ("first", {"user_access_token": "first-token"}),
            ("second", {}),
        ])

    async def test_existing_stream_filtering_is_preserved(self):
        class FakeAgent:
            async def stream_async(self, prompt, *, invocation_state):
                yield {"metadata": "ignored"}
                yield {"event": {"contentBlockStart": {}}}
                yield {"event": {"contentBlockStart": {"start": {"toolUse": {"name": "x"}}}}}

        events = [event async for event in main._stream_filtered_events(
            FakeAgent(), "prompt", {}
        )]
        self.assertEqual(events, [
            {"event": {"contentBlockStart": {"start": {"toolUse": {"name": "x"}}}}}
        ])


if __name__ == "__main__":
    unittest.main()
