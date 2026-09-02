import asyncio
import json
import os
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from strands import ToolContext, tool


API_URL_ENV_VAR = "LARAVEL_AGENT_TOOLS_URL"
REGISTRATION_PATH = "/air-conditioners"
MAX_RESPONSE_BYTES = 1024 * 1024
ALLOWED_AIR_CONDITIONER_FIELDS = (
    "id",
    "manufacturer",
    "model_number",
    "serial_number",
    "manufactured_year",
    "notes",
    "created_at",
    "updated_at",
)


def _validate_registration_parameters(
    manufacturer: str,
    model_number: str,
    serial_number: str,
    manufactured_year: int,
    notes: str,
):
    if not isinstance(manufacturer, str) or not 1 <= len(manufacturer.strip()) <= 100:
        raise ValueError("manufacturer must be a non-empty string of 100 characters or fewer")
    if not isinstance(model_number, str) or not 1 <= len(model_number.strip()) <= 100:
        raise ValueError("model_number must be a non-empty string of 100 characters or fewer")
    if not isinstance(serial_number, str) or len(serial_number) > 100:
        raise ValueError("serial_number must be a string of 100 characters or fewer")
    if (
        not isinstance(manufactured_year, int)
        or isinstance(manufactured_year, bool)
        or (manufactured_year != 0 and not 1900 <= manufactured_year <= datetime.now().year)
    ):
        raise ValueError("manufactured_year must be 0 or a valid year")
    if not isinstance(notes, str) or len(notes) > 2000:
        raise ValueError("notes must be a string of 2000 characters or fewer")


def _request_air_conditioner_registration(
    api_base_url: str,
    access_token: str,
    manufacturer: str,
    model_number: str,
    serial_number: str,
    manufactured_year: int,
    notes: str,
) -> dict:
    """Register one air conditioner in Laravel and return allowed fields only."""
    _validate_registration_parameters(
        manufacturer,
        model_number,
        serial_number,
        manufactured_year,
        notes,
    )

    if not api_base_url.startswith(("http://", "https://")):
        raise RuntimeError(f"{API_URL_ENV_VAR} must be an HTTP or HTTPS URL")

    api_url = f"{api_base_url.rstrip('/')}{REGISTRATION_PATH}"
    payload = {
        "manufacturer": manufacturer.strip(),
        "model_number": model_number.strip(),
    }
    if serial_number:
        payload["serial_number"] = serial_number
    if manufactured_year:
        payload["manufactured_year"] = manufactured_year
    if notes:
        payload["notes"] = notes

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
        raise RuntimeError(f"Laravel air-conditioner registration API returned HTTP {error.code}") from error
    except URLError as error:
        raise RuntimeError("Laravel air-conditioner registration API could not be reached") from error

    if len(raw_response) > MAX_RESPONSE_BYTES:
        raise RuntimeError("Laravel air-conditioner registration API response was too large")

    try:
        decoded = json.loads(raw_response.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("Laravel air-conditioner registration API returned invalid JSON") from error

    air_conditioner = decoded.get("data")
    if not isinstance(air_conditioner, dict):
        raise RuntimeError("Laravel air-conditioner registration API response has an invalid data field")

    return {
        "data": {
            field: air_conditioner.get(field)
            for field in ALLOWED_AIR_CONDITIONER_FIELDS
        }
    }


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
async def register_airconditioner(
    manufacturer: str,
    model_number: str,
    serial_number: str = "",
    manufactured_year: int = 0,
    notes: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """Register one air conditioner in Laravel when the user explicitly requests registration."""
    if tool_context is None:
        raise RuntimeError("Tool context is unavailable")

    _user_id, access_token = _authenticated_request(tool_context)

    api_base_url = os.getenv(API_URL_ENV_VAR, "")
    if not api_base_url:
        raise RuntimeError(f"{API_URL_ENV_VAR} is not configured")

    return await asyncio.to_thread(
        _request_air_conditioner_registration,
        api_base_url,
        access_token,
        manufacturer,
        model_number,
        serial_number,
        manufactured_year,
        notes,
    )
