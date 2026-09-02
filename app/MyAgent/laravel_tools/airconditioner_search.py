import asyncio
import json
import os
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from strands import ToolContext, tool


API_URL_ENV_VAR = "LARAVEL_AGENT_TOOLS_URL"
SEARCH_PATH = "/air-conditioners/search"
MAX_RESPONSE_BYTES = 1024 * 1024
ALLOWED_AIR_CONDITIONER_FIELDS = (
    "id",
    "manufacturer",
    "model_number",
    "serial_number",
    "manufactured_year",
    "notes",
)


def _validate_search_parameters(query: str, manufactured_year: int, limit: int):
    if not isinstance(query, str) or len(query) > 100:
        raise ValueError("query must be a string of 100 characters or fewer")
    if (
        not isinstance(manufactured_year, int)
        or isinstance(manufactured_year, bool)
        or (manufactured_year != 0 and not 1900 <= manufactured_year <= datetime.now().year)
    ):
        raise ValueError("manufactured_year must be 0 or a valid year")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 20:
        raise ValueError("limit must be an integer between 1 and 20")


def _request_air_conditioner_search(
    api_base_url: str,
    access_token: str,
    query: str,
    manufactured_year: int,
    limit: int,
) -> dict:
    """Call Laravel and return only explicitly allowed air-conditioner fields."""
    _validate_search_parameters(query, manufactured_year, limit)

    if not api_base_url.startswith(("http://", "https://")):
        raise RuntimeError(f"{API_URL_ENV_VAR} must be an HTTP or HTTPS URL")

    api_url = f"{api_base_url.rstrip('/')}{SEARCH_PATH}"
    payload = {"query": query, "limit": limit}
    if manufactured_year:
        payload["manufactured_year"] = manufactured_year

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
        raise RuntimeError(f"Laravel air-conditioner API returned HTTP {error.code}") from error
    except URLError as error:
        raise RuntimeError("Laravel air-conditioner API could not be reached") from error

    if len(raw_response) > MAX_RESPONSE_BYTES:
        raise RuntimeError("Laravel air-conditioner API response was too large")

    try:
        decoded = json.loads(raw_response.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("Laravel air-conditioner API returned invalid JSON") from error

    air_conditioners = decoded.get("data")
    if not isinstance(air_conditioners, list):
        raise RuntimeError("Laravel air-conditioner API response has an invalid data field")

    safe_air_conditioners = []
    for air_conditioner in air_conditioners[:limit]:
        if isinstance(air_conditioner, dict):
            safe_air_conditioners.append({
                field: air_conditioner.get(field)
                for field in ALLOWED_AIR_CONDITIONER_FIELDS
            })

    return {"data": safe_air_conditioners, "count": len(safe_air_conditioners)}


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
async def search_airconditioner(
    query: str = "",
    manufactured_year: int = 0,
    limit: int = 10,
    tool_context: ToolContext = None,
) -> dict:
    """Search Laravel air conditioners by manufacturer, model number, serial number, and optional year."""
    if tool_context is None:
        raise RuntimeError("Tool context is unavailable")

    _user_id, access_token = _authenticated_request(tool_context)

    api_base_url = os.getenv(API_URL_ENV_VAR, "")
    if not api_base_url:
        raise RuntimeError(f"{API_URL_ENV_VAR} is not configured")

    return await asyncio.to_thread(
        _request_air_conditioner_search,
        api_base_url,
        access_token,
        query,
        manufactured_year,
        limit,
    )
