import os
import socket
import unittest
from unittest.mock import patch

from agentcore_browser import MAX_PAGE_TEXT_CHARS, _read_web_page, _validate_public_url


PUBLIC_ADDRESS = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


class FakePage:
    def __init__(self, text="page text", goto_error=None):
        self.url = "https://example.com/final"
        self.text = text
        self.goto_error = goto_error
        self.goto_args = None

    def route(self, pattern, handler):
        self.route_pattern = pattern
        self.route_handler = handler

    def goto(self, url, **kwargs):
        self.goto_args = (url, kwargs)
        if self.goto_error:
            raise self.goto_error

    def locator(self, selector):
        self.selector = selector
        return self

    def inner_text(self, **kwargs):
        self.inner_text_args = kwargs
        return self.text


class FakeContext:
    def __init__(self, page):
        self.pages = [page]


class FakeBrowser:
    def __init__(self, page):
        self.contexts = [FakeContext(page)]
        self.closed = False

    def close(self):
        self.closed = True


class FakePlaywright:
    def __init__(self, browser):
        self.chromium = self
        self.browser = browser

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def connect_over_cdp(self, ws_url, headers):
        self.connection = (ws_url, headers)
        return self.browser


class FakeBrowserClient:
    def generate_ws_headers(self):
        return "wss://browser.example/ws", {"x-test": "value"}


class FakeSession:
    def __init__(self):
        self.exited = False

    def __enter__(self):
        return FakeBrowserClient()

    def __exit__(self, *args):
        self.exited = True


class AgentCoreBrowserTests(unittest.TestCase):
    @patch("agentcore_browser.socket.getaddrinfo", return_value=PUBLIC_ADDRESS)
    def test_reads_page_and_closes_resources(self, _getaddrinfo):
        page = FakePage()
        browser = FakeBrowser(page)
        session = FakeSession()

        with patch.dict(os.environ, {"AWS_REGION": "ap-northeast-1"}, clear=True):
            result = _read_web_page(
                "https://example.com",
                session_factory=lambda *args, **kwargs: session,
                playwright_factory=lambda: FakePlaywright(browser),
            )

        self.assertEqual(result, "page text")
        self.assertTrue(browser.closed)
        self.assertTrue(session.exited)
        self.assertEqual(page.goto_args[1]["wait_until"], "domcontentloaded")
        self.assertEqual(page.goto_args[1]["timeout"], 20_000)

    @patch("agentcore_browser.socket.getaddrinfo", return_value=PUBLIC_ADDRESS)
    def test_truncates_long_text(self, _getaddrinfo):
        browser = FakeBrowser(FakePage("x" * (MAX_PAGE_TEXT_CHARS + 1)))
        with patch.dict(os.environ, {"AWS_REGION": "ap-northeast-1"}, clear=True):
            result = _read_web_page(
                "https://example.com",
                session_factory=lambda *args, **kwargs: FakeSession(),
                playwright_factory=lambda: FakePlaywright(browser),
            )
        self.assertTrue(result.startswith("x" * MAX_PAGE_TEXT_CHARS))
        self.assertIn("省略", result)

    @patch("agentcore_browser.socket.getaddrinfo", return_value=PUBLIC_ADDRESS)
    def test_closes_resources_when_navigation_fails(self, _getaddrinfo):
        browser = FakeBrowser(FakePage(goto_error=RuntimeError("navigation failed")))
        session = FakeSession()
        with patch.dict(os.environ, {"AWS_REGION": "ap-northeast-1"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "navigation failed"):
                _read_web_page(
                    "https://example.com",
                    session_factory=lambda *args, **kwargs: session,
                    playwright_factory=lambda: FakePlaywright(browser),
                )
        self.assertTrue(browser.closed)
        self.assertTrue(session.exited)

    @patch("agentcore_browser.socket.getaddrinfo", return_value=[
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))
    ])
    def test_rejects_private_address(self, _getaddrinfo):
        with self.assertRaises(ValueError):
            _validate_public_url("http://example.com")

    def test_rejects_credentials_and_non_http_scheme(self):
        for url in ("file:///etc/passwd", "https://user:pass@example.com"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                _validate_public_url(url)


if __name__ == "__main__":
    unittest.main()
