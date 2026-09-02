import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from browser_tools.reliable_agentcore_browser import ReliableAgentCoreBrowser
from browser_tools.reliable_agentcore_browser import MAX_EXTRACTED_TEXT_CHARS


class ReliableAgentCoreBrowserTest(unittest.IsolatedAsyncioTestCase):
    async def test_navigation_uses_bounded_dom_content_loaded_wait(self):
        browser = object.__new__(ReliableAgentCoreBrowser)
        page = MagicMock()
        page.goto = AsyncMock()
        browser.validate_session = MagicMock(return_value=None)
        browser.get_session_page = MagicMock(return_value=page)
        action = SimpleNamespace(
            session_name="b-12345678901234567890123456789012",
            url="https://example.test/search",
        )

        result = await browser._async_navigate(action)

        self.assertEqual(result["status"], "success")
        page.goto.assert_awaited_once_with(
            "https://example.test/search",
            wait_until="domcontentloaded",
            timeout=20_000,
        )

    async def test_google_search_navigation_is_rejected(self):
        browser = object.__new__(ReliableAgentCoreBrowser)
        page = MagicMock()
        page.goto = AsyncMock()
        browser.validate_session = MagicMock(return_value=None)
        browser.get_session_page = MagicMock(return_value=page)
        action = SimpleNamespace(
            session_name="b-12345678901234567890123456789012",
            url="https://www.google.co.jp/search?q=SpaceX",
        )

        result = await browser._async_navigate(action)

        self.assertEqual(result["status"], "error")
        self.assertIn("Google Search is not available", result["content"][0]["text"])
        page.goto.assert_not_awaited()

    async def test_page_text_is_truncated_at_twenty_thousand_characters(self):
        browser = object.__new__(ReliableAgentCoreBrowser)
        page = MagicMock()
        page.text_content = AsyncMock(
            return_value="x" * (MAX_EXTRACTED_TEXT_CHARS + 1),
        )
        browser.validate_session = MagicMock(return_value=None)
        browser.get_session_page = MagicMock(return_value=page)
        action = SimpleNamespace(
            session_name="b-12345678901234567890123456789012",
            selector="body",
        )

        result = await browser._async_get_text(action)

        self.assertEqual(result["status"], "success")
        returned_text = result["content"][0]["text"]
        self.assertIn("x" * MAX_EXTRACTED_TEXT_CHARS, returned_text)
        self.assertIn("truncated at 20,000 characters", returned_text)
        self.assertNotIn("x" * (MAX_EXTRACTED_TEXT_CHARS + 1), returned_text)


if __name__ == "__main__":
    unittest.main()
