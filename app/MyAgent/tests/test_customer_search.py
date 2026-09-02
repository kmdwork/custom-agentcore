import json
import os
import unittest
from unittest.mock import MagicMock, patch

from strands import ToolContext

from laravel_tools.customer_search import (
    _authenticated_request,
    _request_customer_search,
    _validate_search_parameters,
    search_customers,
)


class CustomerSearchToolTest(unittest.TestCase):
    def test_rejects_invalid_parameters(self):
        with self.assertRaises(ValueError):
            _validate_search_parameters("", "unknown", 10)

        with self.assertRaises(ValueError):
            _validate_search_parameters("", "active", 21)

    @patch("laravel_tools.customer_search.urlopen")
    def test_posts_expected_request_and_filters_fields(self, mocked_urlopen):
        response = MagicMock()
        response.read.return_value = json.dumps({
            "data": [{
                "id": 1,
                "customer_code": "C-001",
                "name": "山田太郎",
                "company_name": "山田商事",
                "status": "active",
                "registered_at": "2026-08-04",
                "email": "must-not-be-returned@example.com",
            }],
            "count": 1,
        }).encode("utf-8")
        mocked_urlopen.return_value.__enter__.return_value = response

        result = _request_customer_search(
            "http://example.test/api/agent-tools",
            "1|sanctum-test-token",
            "山田",
            "active",
            5,
        )

        request = mocked_urlopen.call_args.args[0]
        sent_payload = json.loads(request.data.decode("utf-8"))

        self.assertEqual(sent_payload, {"query": "山田", "status": "active", "limit": 5})
        self.assertEqual(request.full_url, "http://example.test/api/agent-tools/customers/search")
        self.assertEqual(request.get_header("Authorization"), "Bearer 1|sanctum-test-token")
        self.assertIsNone(request.get_header("X-agent-tool-key"))
        self.assertNotIn("email", result["data"][0])
        self.assertEqual(result["count"], 1)

    def test_authentication_comes_from_tool_context(self):
        context = ToolContext(
            tool_use={"toolUseId": "test", "name": "search_customers", "input": {}},
            agent=None,
            invocation_state={
                "authenticated_user_id": "123",
                "user_access_token": "1|sanctum-test-token",
            },
        )

        self.assertEqual(
            _authenticated_request(context),
            ("123", "1|sanctum-test-token"),
        )

    def test_authentication_is_not_exposed_in_model_tool_schema(self):
        properties = search_customers.tool_spec["inputSchema"]["json"]["properties"]

        self.assertNotIn("authenticated_user_id", properties)
        self.assertNotIn("user_access_token", properties)
        self.assertNotIn("tool_context", properties)


class CustomerSearchAsyncToolTest(unittest.IsolatedAsyncioTestCase):
    @patch.dict(os.environ, {"LARAVEL_AGENT_TOOLS_URL": "http://example.test/api/agent-tools"})
    @patch("laravel_tools.customer_search._request_customer_search")
    async def test_tool_uses_sanctum_token_from_context(self, mocked_request):
        mocked_request.return_value = {"data": [], "count": 0}
        context = ToolContext(
            tool_use={"toolUseId": "test", "name": "search_customers", "input": {}},
            agent=None,
            invocation_state={
                "authenticated_user_id": "123",
                "user_access_token": "1|sanctum-test-token",
            },
        )

        result = await search_customers._tool_func(
            query="山田",
            status="active",
            limit=5,
            tool_context=context,
        )

        self.assertEqual(result, {"data": [], "count": 0})
        mocked_request.assert_called_once_with(
            "http://example.test/api/agent-tools",
            "1|sanctum-test-token",
            "山田",
            "active",
            5,
        )


if __name__ == "__main__":
    unittest.main()
