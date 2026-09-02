from typing import Any
from urllib.parse import urlparse

from strands_tools.browser import AgentCoreBrowser


MAX_EXTRACTED_TEXT_CHARS = 20_000


# AgentCoreBrowserを継承している
class ReliableAgentCoreBrowser(AgentCoreBrowser):
    """AgentCore Browser with a bounded, DOM-ready navigation wait."""

    async def _async_navigate(self, action) -> dict[str, Any]:
        parsed_url = urlparse(action.url)
        hostname = (parsed_url.hostname or "").lower()
        is_google_domain = (
            hostname == "google.com"
            or hostname.endswith(".google.com")
            or hostname.startswith("google.")
            or hostname.startswith("www.google.")
        )

        if is_google_domain and parsed_url.path.rstrip("/") == "/search":
            return {
                "status": "error",
                "content": [{
                    "text": (
                        "Google Search is not available for automated browsing. "
                        "Use an official source directly, or use another search provider."
                    ),
                }],
            }

        error_response = self.validate_session(action.session_name)
        if error_response:
            return error_response

        page = self.get_session_page(action.session_name)
        if page is None:
            return {
                "status": "error",
                "content": [{"text": "Error: No active page for session"}],
            }

        try:
            # The upstream implementation waits for networkidle.
            # Search pages can keep background requests open, so stop waiting once the DOM is ready.
            await page.goto(
                action.url,
                wait_until="domcontentloaded",
                # DOMの準備が20秒以内に終わらなければ、ページ移動を失敗として扱う
                timeout=20_000,
            )
            return {
                "status": "success",
                "content": [{"text": f"Navigated to {action.url}"}],
            }
        except Exception as error:
            return {
                "status": "error",
                "content": [{"text": f"Navigation failed: {error}"}],
            }

    async def _async_get_text(self, action) -> dict[str, Any]:
        """Return page text without sending an unbounded page to the model."""
        error_response = self.validate_session(action.session_name)
        if error_response:
            return error_response

        page = self.get_session_page(action.session_name)
        if page is None:
            return {
                "status": "error",
                "content": [{"text": "Error: No active page for session"}],
            }

        try:
            text = await page.text_content(action.selector) or ""

            if len(text) > MAX_EXTRACTED_TEXT_CHARS:
                text = (
                    text[:MAX_EXTRACTED_TEXT_CHARS]
                    + "\n\n[Page text was truncated at 20,000 characters.]"
                )

            return {
                "status": "success",
                "content": [{"text": f"Text content: {text}"}],
            }
        except Exception as error:
            return {
                "status": "error",
                "content": [{"text": f"Text extraction failed: {error}"}],
            }
