import io
import json
import os
import socket
import unittest
from email.message import Message
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from aircon_tools import AirconToolError, MAX_RESPONSE_BYTES
from aircon_write_tools import (
    MAX_FIELD_CHARS,
    MAX_OPERATIONS,
    _apply_aircon_changes,
    _post_aircon_changes,
    _validate_operations,
)


class FakeToolContext:
    def __init__(self, approval="approve", token=None):
        self.approval = approval
        self.invocation_state = {} if token is None else {"user_access_token": token}
        self.interrupt_calls = []

    def interrupt(self, name, reason):
        self.interrupt_calls.append((name, reason))
        return self.approval


class FakeResponse:
    def __init__(self, body, status=200, content_type="application/json", length=None):
        self.status = status
        self.body = body
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        if length is not None:
            self.headers["Content-Length"] = str(length)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, limit):
        return self.body[:limit]


class AirconWriteToolTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {"AIRCON_API_URL": "https://api.example/agent/aircon"},
            clear=True,
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_validates_and_normalizes_create_chain(self):
        operations = _validate_operations([
            {"type": "create_company", "name": " Company "},
            {
                "type": "create_property",
                "company_ref": 0,
                "name": " HQ ",
                "address": None,
            },
            {"type": "create_system", "property_ref": 1, "name": " 3F "},
            {
                "type": "create_model",
                "manufacturer": " Maker ",
                "model_number": " MODEL-1 ",
            },
            {
                "type": "create_unit",
                "system_ref": 2,
                "model_ref": 3,
                "name": " Unit ",
                "unit_type": "indoor",
            },
        ])

        self.assertEqual(operations[0]["name"], "Company")
        self.assertEqual(operations[1]["address"], None)
        self.assertEqual(operations[4]["system_ref"], 2)
        self.assertEqual(operations[4]["model_ref"], 3)

    def test_accepts_supported_updates_and_direct_create_ids(self):
        operations = _validate_operations([
            {"type": "create_property", "company_id": "company-1", "name": "HQ"},
            {"type": "create_system", "property_id": "property-1", "name": "3F"},
            {
                "type": "create_unit",
                "system_id": "system-1",
                "model_id": None,
                "name": "Unit",
                "unit_type": "outdoor",
            },
            {"type": "update_company", "id": "company-1", "name": "New company"},
            {"type": "update_property", "id": "property-1", "address": None},
            {"type": "update_system", "id": "system-1", "name": "New system"},
            {"type": "update_model", "id": "model-1", "manufacturer": "Maker"},
            {"type": "update_unit", "id": "unit-1", "model_id": None},
        ])

        self.assertEqual(len(operations), 8)
        self.assertIsNone(operations[2]["model_id"])
        self.assertIsNone(operations[7]["model_id"])

    def test_rejects_unknown_missing_oversize_and_delete_operations(self):
        cases = [
            ([], "non-empty"),
            ([{"type": "delete_unit", "id": "1"}], "not supported"),
            ([{"type": "create_company"}], "missing required"),
            ([{"type": "create_company", "name": "x", "sql": "DROP"}], "unsupported fields"),
            ([{"type": "create_company", "name": "x" * (MAX_FIELD_CHARS + 1)}], "must not exceed"),
            ([{"type": "update_company", "id": "company-1"}], "no fields to update"),
            ([{"type": "create_unit", "name": "U", "unit_type": "invalid", "system_id": "s"}], "indoor or outdoor"),
        ]
        for operations, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(AirconToolError, message):
                _validate_operations(operations)

        with self.assertRaisesRegex(AirconToolError, "must not exceed"):
            _validate_operations(
                [{"type": "create_company", "name": str(i)} for i in range(MAX_OPERATIONS + 1)]
            )

    def test_rejects_invalid_references(self):
        cases = [
            [{"type": "create_property", "name": "HQ", "company_ref": 0}],
            [
                {"type": "create_model", "manufacturer": "M", "model_number": "1"},
                {"type": "create_property", "name": "HQ", "company_ref": 0},
            ],
            [{"type": "create_property", "name": "HQ", "company_id": "c", "company_ref": 0}],
        ]
        for operations in cases:
            with self.subTest(operations=operations), self.assertRaises(AirconToolError):
                _validate_operations(operations)

    @patch("aircon_write_tools._post_aircon_changes")
    def test_interrupts_with_validated_input_before_write(self, post_changes):
        context = FakeToolContext(approval="reject", token="read-token")
        result = _apply_aircon_changes(
            [{"type": "create_company", "name": " Company "}], context
        )

        self.assertEqual(result, {"success": False, "executed": False, "reason": "rejected"})
        post_changes.assert_not_called()
        self.assertEqual(
            context.interrupt_calls,
            [("aircon-write-approval", {
                "tool_name": "apply_aircon_changes",
                "operations": [{"type": "create_company", "name": "Company"}],
            })],
        )
        self.assertNotIn("read-token", repr(context.interrupt_calls))

    @patch("aircon_write_tools._post_aircon_changes")
    def test_approve_executes_once(self, post_changes):
        post_changes.return_value = {"success": True, "results": [{"id": "company-1"}]}
        context = FakeToolContext(approval="approve", token="write-token")
        operations = [{"type": "create_company", "name": "Company"}]

        result = _apply_aircon_changes(operations, context)

        self.assertTrue(result["success"])
        post_changes.assert_called_once_with(operations, context)

    @patch("aircon_write_tools.urlopen")
    def test_success_uses_resume_token_and_expected_contract(self, opener):
        opener.return_value = FakeResponse(
            b'{"success":true,"results":[{"operation":"create_company","id":"company-1"}]}'
        )
        context = FakeToolContext(token="resume-write-token")
        operations = [{"type": "create_company", "name": "Company"}]

        result = _post_aircon_changes(operations, context)

        self.assertTrue(result["success"])
        request = opener.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.example/agent/aircon/changes/apply")
        self.assertEqual(request.method, "POST")
        self.assertEqual(json.loads(request.data), {"operations": operations})
        self.assertEqual(request.get_header("Authorization"), "Bearer resume-write-token")
        self.assertEqual(opener.call_args.kwargs["timeout"], 10)

    @patch("aircon_write_tools.urlopen")
    def test_maps_http_errors_without_exposing_token(self, opener):
        cases = {
            400: "changes were rejected",
            401: "invalid or expired",
            403: "write permission",
            409: "conflict",
            422: "failed validation",
            429: "rate limited",
            503: "temporarily unavailable",
        }
        for status, message in cases.items():
            with self.subTest(status=status):
                error = HTTPError("https://api.example", status, "upstream", {}, io.BytesIO())
                opener.side_effect = error
                try:
                    with self.assertRaisesRegex(AirconToolError, message) as caught:
                        _post_aircon_changes(
                            [{"type": "create_company", "name": "Company"}],
                            FakeToolContext(token="secret-write-token"),
                        )
                    self.assertNotIn("secret-write-token", str(caught.exception))
                finally:
                    error.close()

    @patch("aircon_write_tools.urlopen")
    def test_rejects_missing_token_and_invalid_responses(self, opener):
        with self.assertRaisesRegex(AirconToolError, "authentication is required"):
            _post_aircon_changes([], FakeToolContext())
        opener.assert_not_called()

        cases = [
            (socket.timeout(), "could not be reached"),
            (URLError("offline"), "could not be reached"),
            (FakeResponse(b"{}", length=MAX_RESPONSE_BYTES + 1), "size limit"),
            (FakeResponse(b"not-json"), "invalid JSON"),
            (FakeResponse(b'{"success":false,"results":[]}'), "unexpected response shape"),
            (FakeResponse(b'{"success":true,"results":{}}'), "unexpected response shape"),
            (FakeResponse(b'{"success":true,"results":[]}', content_type="text/plain"), "non-JSON"),
        ]
        for returned, message in cases:
            with self.subTest(message=message):
                opener.reset_mock()
                opener.side_effect = returned if isinstance(returned, BaseException) else None
                opener.return_value = None if isinstance(returned, BaseException) else returned
                with self.assertRaisesRegex(AirconToolError, message):
                    _post_aircon_changes(
                        [{"type": "create_company", "name": "Company"}],
                        FakeToolContext(token="token"),
                    )


if __name__ == "__main__":
    unittest.main()
