import io
import json
import os
import socket
import unittest
from email.message import Message
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from aircon_tools import (
    AirconToolError,
    MAX_RESPONSE_BYTES,
    _post_aircon,
)


class FakeToolContext:
    def __init__(self, token=None):
        self.invocation_state = {} if token is None else {"user_access_token": token}


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


class AirconToolTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {"AIRCON_GATEWAY_URL": "https://gateway.example/aircon-target"},
            clear=True,
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()

    @patch("aircon_tools.urlopen")
    def test_success_uses_bearer_json_and_expected_path(self, opener):
        opener.return_value = FakeResponse(b'{"companies":[{"id":"company-1"}]}')
        result = _post_aircon(
            "companies/search",
            {"query": "Kamada"},
            "companies",
            FakeToolContext("delegated-token"),
        )

        self.assertEqual(result, {"companies": [{"id": "company-1"}]})
        request = opener.call_args.args[0]
        self.assertEqual(request.full_url, "https://gateway.example/aircon-target/companies/search")
        self.assertEqual(request.method, "POST")
        self.assertEqual(json.loads(request.data), {"query": "Kamada"})
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(request.get_header("Authorization"), "Bearer delegated-token")
        self.assertEqual(opener.call_args.kwargs["timeout"], 10)

    @patch("aircon_tools.urlopen")
    def test_empty_array_is_valid(self, opener):
        opener.return_value = FakeResponse(b'{"units":[]}')
        self.assertEqual(
            _post_aircon("units/search", {}, "units", FakeToolContext("token")),
            {"units": []},
        )

    @patch("aircon_tools.urlopen")
    def test_rejects_missing_token_without_network(self, opener):
        with self.assertRaisesRegex(AirconToolError, "authentication is required"):
            _post_aircon("companies/search", {}, "companies", FakeToolContext())
        opener.assert_not_called()

    @patch("aircon_tools.urlopen")
    def test_maps_http_statuses_without_exposing_token(self, opener):
        cases = {
            400: "input was rejected",
            401: "invalid or expired",
            403: "read permission",
            429: "rate limited",
            503: "temporarily unavailable",
        }
        for status, message in cases.items():
            with self.subTest(status=status):
                error = HTTPError(
                    "https://gateway.example", status, "upstream", {}, io.BytesIO()
                )
                opener.side_effect = error
                try:
                    with self.assertRaisesRegex(AirconToolError, message) as caught:
                        _post_aircon(
                            "companies/search", {}, "companies", FakeToolContext("secret-token")
                        )
                    self.assertNotIn("secret-token", str(caught.exception))
                finally:
                    error.close()

    @patch("aircon_tools.urlopen", side_effect=URLError("offline"))
    def test_maps_network_failure_safely(self, _opener):
        with self.assertRaisesRegex(AirconToolError, "could not be reached"):
            _post_aircon("models/search", {}, "models", FakeToolContext("token"))

    @patch("aircon_tools.urlopen")
    def test_rejects_timeout_oversize_non_json_and_bad_shape(self, opener):
        cases = [
            (socket.timeout(), "could not be reached"),
            (FakeResponse(b"{}", length=MAX_RESPONSE_BYTES + 1), "size limit"),
            (FakeResponse(b"not-json"), "invalid JSON"),
            (FakeResponse(b'{"wrong":[]}'), "unexpected response shape"),
            (FakeResponse(b'{"companies":{}}'), "unexpected response shape"),
            (FakeResponse(b'{"companies":[]}', content_type="text/plain"), "non-JSON"),
        ]
        for returned, message in cases:
            with self.subTest(message=message):
                opener.reset_mock()
                opener.side_effect = returned if isinstance(returned, BaseException) else None
                opener.return_value = None if isinstance(returned, BaseException) else returned
                with self.assertRaisesRegex(AirconToolError, message):
                    _post_aircon("companies/search", {}, "companies", FakeToolContext("token"))

    def test_rejects_unconfigured_or_insecure_gateway(self):
        for value in ("", "<AIRCON_GATEWAY_URL>", "http://public.example/api"):
            with self.subTest(value=value), patch.dict(
                os.environ, {"AIRCON_GATEWAY_URL": value}, clear=True
            ), self.assertRaises(AirconToolError):
                _post_aircon("companies/search", {}, "companies", FakeToolContext("token"))


if __name__ == "__main__":
    unittest.main()
