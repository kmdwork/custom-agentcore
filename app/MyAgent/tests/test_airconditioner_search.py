import json
import os
import unittest
from unittest.mock import MagicMock, patch

from strands import ToolContext

from laravel_tools.airconditioner_search import (
    _request_air_conditioner_search,
    _validate_search_parameters,
    search_airconditioner,
)


class AirConditionerSearchToolTest(unittest.TestCase):
    def test_rejects_invalid_parameters(self):
        with self.assertRaises(ValueError):
            _validate_search_parameters("", 1800, 10)

        with self.assertRaises(ValueError):
            _validate_search_parameters("", 0, 21)

    @patch("laravel_tools.airconditioner_search.urlopen")
    def test_posts_expected_request_and_filters_fields(self, mocked_urlopen):
        response = MagicMock()
        response.read.return_value = json.dumps({
            "data": [{
                "id": 1,
                "manufacturer": "ダイキン",
                "model_number": "AN40ZRP-W",
                "serial_number": "SERIAL-001",
                "manufactured_year": 2022,
                "notes": "テスト機器",
                "unexpected": "must-not-be-returned",
            }],
            "count": 1,
        }).encode("utf-8")
        mocked_urlopen.return_value.__enter__.return_value = response

        result = _request_air_conditioner_search(
            "http://example.test/api/agent-tools/",
            "1|sanctum-test-token",
            "ダイキン",
            2022,
            5,
        )

        request = mocked_urlopen.call_args.args[0]
        sent_payload = json.loads(request.data.decode("utf-8"))

        self.assertEqual(
            request.full_url,
            "http://example.test/api/agent-tools/air-conditioners/search",
        )
        self.assertEqual(
            sent_payload,
            {"query": "ダイキン", "manufactured_year": 2022, "limit": 5},
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer 1|sanctum-test-token")
        self.assertNotIn("unexpected", result["data"][0])
        self.assertEqual(result["count"], 1)

    def test_authentication_is_not_exposed_in_model_tool_schema(self):
        properties = search_airconditioner.tool_spec["inputSchema"]["json"]["properties"]

        self.assertNotIn("authenticated_user_id", properties)
        self.assertNotIn("user_access_token", properties)
        self.assertNotIn("tool_context", properties)


class AirConditionerSearchAsyncToolTest(unittest.IsolatedAsyncioTestCase):
    @patch.dict(os.environ, {"LARAVEL_AGENT_TOOLS_URL": "http://example.test/api/agent-tools"})
    @patch("laravel_tools.airconditioner_search._request_air_conditioner_search")
    async def test_tool_uses_base_url_and_sanctum_token(self, mocked_request):
        mocked_request.return_value = {"data": [], "count": 0}
        context = ToolContext(
            tool_use={"toolUseId": "test", "name": "search_airconditioner", "input": {}},
            agent=None,
            invocation_state={
                "authenticated_user_id": "123",
                "user_access_token": "1|sanctum-test-token",
            },
        )

        result = await search_airconditioner._tool_func(
            query="ダイキン",
            manufactured_year=2022,
            limit=5,
            tool_context=context,
        )

        self.assertEqual(result, {"data": [], "count": 0})
        mocked_request.assert_called_once_with(
            "http://example.test/api/agent-tools",
            "1|sanctum-test-token",
            "ダイキン",
            2022,
            5,
        )


if __name__ == "__main__":
    unittest.main()
