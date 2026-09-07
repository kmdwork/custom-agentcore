import os
import logging
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

logger = logging.getLogger(__name__)


def get_strands_app_tools_mcp_client() -> MCPClient | None:
    """Returns an MCP Client connected to the strands-app-tools gateway."""
    url = os.environ.get("AGENTCORE_GATEWAY_STRANDS_APP_TOOLS_URL")
    if not url:
        logger.warning("AGENTCORE_GATEWAY_STRANDS_APP_TOOLS_URL not set — strands-app-tools gateway tools unavailable")
        return None
    return MCPClient(lambda: streamablehttp_client(url), prefix="strands_app_tools")
    
def get_all_gateway_mcp_clients() -> list[MCPClient]:
    """Returns MCP clients for all configured gateways."""
    clients = []
    client = get_strands_app_tools_mcp_client()
    if client:
        clients.append(client)
    return clients
