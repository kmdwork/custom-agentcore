"""Read-only Aircon tools backed by an AgentCore Gateway target."""

from __future__ import annotations

import json
import os
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from strands import ToolContext, tool


REQUEST_TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_FILTER_CHARS = 200


class AirconToolError(RuntimeError):
    """A safe error suitable for returning through a model tool boundary."""


def _access_token(tool_context: ToolContext) -> str:
    token = tool_context.invocation_state.get("user_access_token")
    if not isinstance(token, str) or not token:
        raise AirconToolError("Aircon authentication is required")
    return token


def _gateway_url(operation: str) -> str:
    base_url = os.getenv("AIRCON_GATEWAY_URL", "").rstrip("/")
    if not base_url or base_url == "<AIRCON_GATEWAY_URL>":
        raise AirconToolError("Aircon Gateway is not configured")

    parsed = urlsplit(base_url)
    local_dev = os.getenv("LOCAL_DEV") == "1"
    valid_local = local_dev and parsed.scheme == "http" and parsed.hostname in {
        "localhost",
        "127.0.0.1",
        "::1",
    }
    if (
        not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or (parsed.scheme != "https" and not valid_local)
    ):
        raise AirconToolError("Aircon Gateway configuration is invalid")
    return f"{base_url}/{operation}"


def _optional_filter(value: str, name: str) -> str | None:
    if not isinstance(value, str):
        raise AirconToolError(f"{name} must be a string")
    value = value.strip()
    if not value:
        return None
    if len(value) > MAX_FILTER_CHARS:
        raise AirconToolError(f"{name} must not exceed {MAX_FILTER_CHARS} characters")
    return value


def _safe_http_error(status: int) -> AirconToolError:
    messages = {
        400: "Aircon search input was rejected",
        401: "Aircon authentication is invalid or expired",
        403: "Aircon read permission is required",
        429: "Aircon service is temporarily rate limited",
    }
    if status in messages:
        return AirconToolError(messages[status])
    if status >= 500:
        return AirconToolError("Aircon service is temporarily unavailable")
    return AirconToolError("Aircon service returned an unexpected response")


def _read_limited(response: Any) -> bytes:
    content_length = response.headers.get("Content-Length")
    if content_length:
        try:
            if int(content_length) > MAX_RESPONSE_BYTES:
                raise AirconToolError("Aircon response exceeded the size limit")
        except ValueError as error:
            raise AirconToolError("Aircon response metadata is invalid") from error

    body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise AirconToolError("Aircon response exceeded the size limit")
    return body


def _post_aircon(
    operation: str,
    payload: dict[str, str],
    expected_key: str,
    tool_context: ToolContext,
) -> dict[str, list[Any]]:
    token = _access_token(tool_context)
    request = Request(
        _gateway_url(operation),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            status = response.status
            if status < 200 or status >= 300:
                raise _safe_http_error(status)
            content_type = response.headers.get_content_type()
            if content_type != "application/json":
                raise AirconToolError("Aircon service returned a non-JSON response")
            body = _read_limited(response)
    except HTTPError as error:
        raise _safe_http_error(error.code) from None
    except (URLError, TimeoutError, socket.timeout, OSError):
        raise AirconToolError("Aircon service could not be reached") from None

    try:
        result = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise AirconToolError("Aircon service returned invalid JSON") from None
    if not isinstance(result, dict) or set(result) != {expected_key}:
        raise AirconToolError("Aircon service returned an unexpected response shape")
    rows = result[expected_key]
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise AirconToolError("Aircon service returned an unexpected response shape")
    return {expected_key: rows}


def _filters(**values: str) -> dict[str, str]:
    payload: dict[str, str] = {}
    for name, value in values.items():
        normalized = _optional_filter(value, name)
        if normalized is not None:
            payload[name] = normalized
    return payload


@tool(context=True)
def search_aircon_companies(query: str = "", tool_context: ToolContext = None) -> dict:
    """Search aircon-management companies by name, or list companies when query is empty."""
    return _post_aircon("companies/search", _filters(query=query), "companies", tool_context)


@tool(context=True)
def search_aircon_properties(
    query: str = "", company_id: str = "", tool_context: ToolContext = None
) -> dict:
    """Search properties by name and optionally restrict them to a company ID."""
    return _post_aircon(
        "properties/search",
        _filters(query=query, company_id=company_id),
        "properties",
        tool_context,
    )


@tool(context=True)
def search_aircon_systems(
    query: str = "", property_id: str = "", tool_context: ToolContext = None
) -> dict:
    """Search aircon systems by name and optionally restrict them to a property ID."""
    return _post_aircon(
        "systems/search",
        _filters(query=query, property_id=property_id),
        "systems",
        tool_context,
    )


@tool(context=True)
def search_aircon_units(
    query: str = "", system_id: str = "", tool_context: ToolContext = None
) -> dict:
    """Search aircon units by name and optionally restrict them to a system ID."""
    return _post_aircon(
        "units/search",
        _filters(query=query, system_id=system_id),
        "units",
        tool_context,
    )


@tool(context=True)
def search_aircon_models(query: str = "", tool_context: ToolContext = None) -> dict:
    """Search aircon models by manufacturer or model number, or list all models."""
    return _post_aircon("models/search", _filters(query=query), "models", tool_context)


AIRCON_TOOLS = [
    search_aircon_companies,
    search_aircon_properties,
    search_aircon_systems,
    search_aircon_units,
    search_aircon_models,
]
