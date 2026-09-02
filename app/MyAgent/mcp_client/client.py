import os
import logging
from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

logger = logging.getLogger(__name__)

GATEWAY_URL_ENV = "AGENTCORE_GATEWAY_STRANDS_APP_TOOLS_URL"

def get_streamable_http_mcp_client() -> MCPClient | None:
    """Return an MCP client connected to strands-app-tools."""

    gateway_url = os.environ.get(GATEWAY_URL_ENV)

    if not gateway_url:
        logger.warning(
            "%s is not set; Gateway tools are unavailable",
            GATEWAY_URL_ENV,
        )
        return None

    region = os.environ.get(
        "AWS_REGION",
        os.environ.get("AWS_DEFAULT_REGION", "ap-northeast-1"),
    )

    return MCPClient(
        lambda: aws_iam_streamablehttp_client(
            gateway_url,
            aws_service="bedrock-agentcore",
            aws_region=region,
        ),
        prefix="gw",
    )
