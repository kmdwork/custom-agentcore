"""Explicit list of tools available to MyAgent."""

from laravel_tools.airconditioner_search import search_airconditioner
from laravel_tools.airconditioner_registration import register_airconditioner
from laravel_tools.customer_search import search_customers
from mcp_client.client import get_streamable_http_mcp_client


def create_tools() -> list:
    """Create the non-browser tools for one Agent invocation."""
    tools = [search_customers, search_airconditioner, register_airconditioner]

    # Gatewayを経由するツール
    gateway_client = get_streamable_http_mcp_client()
    if gateway_client is not None:
        tools.append(gateway_client)

    return tools
