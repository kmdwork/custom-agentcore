"""A small, one-shot AgentCore Browser tool for public web pages."""

from __future__ import annotations

import ipaddress
import logging
import os
from pathlib import Path
import shutil
import socket
import stat
from typing import Callable
from urllib.parse import urlsplit
from uuid import uuid4

from bedrock_agentcore.tools.browser_client import browser_session
from playwright.sync_api import sync_playwright
from strands import tool


MAX_PAGE_TEXT_CHARS = 20_000
NAVIGATION_TIMEOUT_MS = 20_000
_PLAYWRIGHT_NODE_PATH = Path("/tmp/playwright-driver-node")


def prepare_playwright(log: logging.Logger) -> None:
    """Copy Playwright's packaged Node binary to writable storage for CodeZip."""
    import playwright

    packaged_node = Path(playwright.__file__).resolve().parent / "driver" / "node"
    if not packaged_node.is_file():
        raise RuntimeError("Playwright's packaged Node executable was not found")

    if not _PLAYWRIGHT_NODE_PATH.is_file() or (
        _PLAYWRIGHT_NODE_PATH.stat().st_size != packaged_node.stat().st_size
    ):
        shutil.copyfile(packaged_node, _PLAYWRIGHT_NODE_PATH)

    mode = _PLAYWRIGHT_NODE_PATH.stat().st_mode
    _PLAYWRIGHT_NODE_PATH.chmod(mode | stat.S_IXUSR)
    os.environ["PLAYWRIGHT_NODEJS_PATH"] = str(_PLAYWRIGHT_NODE_PATH)
    log.info("Playwright driver is ready")


def _validate_public_url(url: str) -> str:
    """Allow only HTTP(S) URLs whose hostname resolves exclusively to public IPs."""
    if not isinstance(url, str) or not url or len(url) > 2_048:
        raise ValueError("url must be a non-empty string of at most 2048 characters")

    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("only http and https URLs are allowed")
    if not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise ValueError("URL credentials and missing hostnames are not allowed")
    if parsed.hostname.lower().rstrip(".") == "localhost":
        raise ValueError("local and private network URLs are not allowed")

    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(
                parsed.hostname,
                parsed.port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        }
    except (OSError, ValueError) as error:
        raise ValueError("URL hostname could not be resolved") from error

    if not addresses:
        raise ValueError("URL hostname could not be resolved")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ValueError("local and private network URLs are not allowed")

    return url


def _read_web_page(
    url: str,
    *,
    session_factory: Callable = browser_session,
    playwright_factory: Callable = sync_playwright,
) -> str:
    """Navigate once, extract visible body text, and close every resource."""
    target_url = _validate_public_url(url)
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    if not region:
        raise RuntimeError("AWS region is not configured")

    session_name = f"read-web-{uuid4().hex[:24]}"
    with session_factory(region, name=session_name) as browser_client:
        ws_url, headers = browser_client.generate_ws_headers()
        with playwright_factory() as playwright:
            browser = playwright.chromium.connect_over_cdp(ws_url, headers=headers)
            try:
                context = browser.contexts[0] if browser.contexts else browser.new_context()
                page = context.pages[0] if context.pages else context.new_page()

                def guard_request(route) -> None:
                    try:
                        _validate_public_url(route.request.url)
                    except ValueError:
                        route.abort("blockedbyclient")
                        return
                    route.continue_()

                page.route("**/*", guard_request)
                page.goto(
                    target_url,
                    wait_until="domcontentloaded",
                    timeout=NAVIGATION_TIMEOUT_MS,
                )
                _validate_public_url(page.url)
                text = page.locator("body").inner_text(timeout=NAVIGATION_TIMEOUT_MS)
            finally:
                browser.close()

    if len(text) <= MAX_PAGE_TEXT_CHARS:
        return text
    return text[:MAX_PAGE_TEXT_CHARS] + "\n\n[本文は20,000文字で省略されました]"


@tool
def read_web_page(url: str) -> str:
    """Read visible text from a public HTTP(S) web page. Use only for public pages."""
    return _read_web_page(url)
