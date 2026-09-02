import json
import os
import unittest
from unittest.mock import MagicMock, patch

from strands import ToolContext

from laravel_tools.airconditioner_registration import (
    _request_air_conditioner_registration,
    _validate_registration_parameters,
    register_airconditioner,
)


class AirConditionerRegistrationToolTest(unittest.TestCase):
    def test_rejects_invalid_parameters(self):
        with self.assertRaises(ValueError):
            _validate_registration_parameters("", "MODEL-1", "", 0, "")

        with self.assertRaises(ValueError):
            _validate_registration_parameters("メーカー", "", "", 0, "")

        with self.assertRaises(ValueError):
            _validate_registration_parameters("メーカー", "MODEL-1", "", 1800, "")

    @patch("laravel_tools.airconditioner_registration.urlopen")
    def test_posts_expected_registration_and_filters_fields(self, mocked_urlopen):
        response = MagicMock()
        response.read.return_value = json.dumps({
            "data": {
                "id": 10,
                "manufacturer": "ダイキン",
                "model_number": "AN40ZRP-W",
                "serial_number": "SERIAL-001",
                "manufactured_year": 2022,
                "notes": "登録テスト",
                "created_at": "2026-08-19T00:00:00.000000Z",
                "updated_at": "2026-08-19T00:00:00.000000Z",
                "unexpected": "must-not-be-returned",
            },
        }).encode("utf-8")
        mocked_urlopen.return_value.__enter__.return_value = response

        result = _request_air_conditioner_registration(
            "http://example.test/api/agent-tools/",
            "1|sanctum-test-token",
            " ダイキン ",
            " AN40ZRP-W ",
            "SERIAL-001",
            2022,
            "登録テスト",
        )

        request = mocked_urlopen.call_args.args[0]
        sent_payload = json.loads(request.data.decode("utf-8"))

        self.assertEqual(
            request.full_url,
            "http://example.test/api/agent-tools/air-conditioners",
        )
        self.assertEqual(request.method, "POST")
        self.assertEqual(sent_payload, {
            "manufacturer": "ダイキン",
            "model_number": "AN40ZRP-W",
            "serial_number": "SERIAL-001",
            "manufactured_year": 2022,
            "notes": "登録テスト",
        })
        self.assertEqual(request.get_header("Authorization"), "Bearer 1|sanctum-test-token")
        self.assertNotIn("unexpected", result["data"])
        self.assertEqual(result["data"]["id"], 10)

    def test_authentication_is_not_exposed_in_model_tool_schema(self):
        properties = register_airconditioner.tool_spec["inputSchema"]["json"]["properties"]

        self.assertNotIn("authenticated_user_id", properties)
        self.assertNotIn("user_access_token", properties)
        self.assertNotIn("tool_context", properties)


class AirConditionerRegistrationAsyncToolTest(unittest.IsolatedAsyncioTestCase):
    @patch.dict(os.environ, {"LARAVEL_AGENT_TOOLS_URL": "http://example.test/api/agent-tools"})
    @patch("laravel_tools.airconditioner_registration._request_air_conditioner_registration")
    async def test_tool_uses_base_url_and_sanctum_token(self, mocked_request):
        mocked_request.return_value = {"data": {"id": 10}}
        context = ToolContext(
            tool_use={"toolUseId": "test", "name": "register_airconditioner", "input": {}},
            agent=None,
            invocation_state={
                "authenticated_user_id": "123",
                "user_access_token": "1|sanctum-test-token",
            },
        )

        result = await register_airconditioner._tool_func(
            manufacturer="ダイキン",
            model_number="AN40ZRP-W",
            serial_number="SERIAL-001",
            manufactured_year=2022,
            notes="登録テスト",
            tool_context=context,
        )

        self.assertEqual(result, {"data": {"id": 10}})
        mocked_request.assert_called_once_with(
            "http://example.test/api/agent-tools",
            "1|sanctum-test-token",
            "ダイキン",
            "AN40ZRP-W",
            "SERIAL-001",
            2022,
            "登録テスト",
        )


if __name__ == "__main__":
    unittest.main()
