import asyncio
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from strands import ToolContext, tool


# === Laravel customer search tool implementation: START ===
# This block is intentionally kept in one file so the Laravel integration is easy to find.
API_URL_ENV_VAR = "LARAVEL_AGENT_TOOLS_URL"
SEARCH_PATH = "/customers/search"
MAX_RESPONSE_BYTES = 1024 * 1024
ALLOWED_CUSTOMER_FIELDS = (
    "id",
    "customer_code",
    "name",
    "company_name",
    "status",
    "registered_at",
)


def _validate_search_parameters(query: str, status: str, limit: int):
    if not isinstance(query, str) or len(query) > 100:
        raise ValueError("query must be a string of 100 characters or fewer")
    if status not in {"", "active", "inactive"}:
        raise ValueError("status must be active, inactive, or empty")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 20:
        raise ValueError("limit must be an integer between 1 and 20")


def _request_customer_search(api_base_url: str, access_token: str, query: str, status: str, limit: int) -> dict:
    """Call Laravel and return only explicitly allowed customer fields."""
    _validate_search_parameters(query, status, limit)

    if not api_base_url.startswith(("http://", "https://")):
        raise RuntimeError(f"{API_URL_ENV_VAR} must be an HTTP or HTTPS URL")

    api_url = f"{api_base_url.rstrip('/')}{SEARCH_PATH}"

    payload = {"query": query, "limit": limit}
    if status:
        payload["status"] = status

    request = Request(
        api_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            raw_response = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        raise RuntimeError(f"Laravel customer API returned HTTP {error.code}") from error
    except URLError as error:
        raise RuntimeError("Laravel customer API could not be reached") from error

    if len(raw_response) > MAX_RESPONSE_BYTES:
        raise RuntimeError("Laravel customer API response was too large")

    try:
        decoded = json.loads(raw_response.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("Laravel customer API returned invalid JSON") from error

    customers = decoded.get("data")
    if not isinstance(customers, list):
        raise RuntimeError("Laravel customer API response has an invalid data field")

    safe_customers = []
    for customer in customers[:limit]:
        if isinstance(customer, dict):
            safe_customers.append({
                field: customer.get(field)
                for field in ALLOWED_CUSTOMER_FIELDS
            })

    return {"data": safe_customers, "count": len(safe_customers)}


def _authenticated_request(tool_context: ToolContext) -> tuple[str, str]:
    """Read authentication supplied by Laravel, never by the model."""
    user_id = tool_context.invocation_state.get("authenticated_user_id")
    access_token = tool_context.invocation_state.get("user_access_token")

    if not isinstance(user_id, str) or not user_id.isdigit():
        raise RuntimeError("Laravel authenticated user is unavailable")
    if not isinstance(access_token, str) or access_token == "":
        raise RuntimeError("Laravel access token is unavailable")

    return user_id, access_token


@tool(context=True)
async def search_customers(
    query: str = "",
    status: str = "",
    limit: int = 10,
    tool_context: ToolContext = None,
) -> dict:
    """Search Laravel customers by name/code/company and optional active status. Returns at most 20 customers."""
    if tool_context is None:
        raise RuntimeError("Tool context is unavailable")

    # user_id is intentionally resolved here even though Laravel ultimately authorizes the token.
    # This rejects tool calls that did not originate from an authenticated Laravel request.
    _user_id, access_token = _authenticated_request(tool_context)

    api_base_url = os.getenv(API_URL_ENV_VAR, "")
    if not api_base_url:
        raise RuntimeError(f"{API_URL_ENV_VAR} is not configured")

    return await asyncio.to_thread(
        _request_customer_search,
        api_base_url,
        access_token,
        query,
        status,
        limit,
    )
# === Laravel customer search tool implementation: END ===
