"""Validate and convert payloads received from Laravel and AgentCore."""

import base64
import binascii
import re


_ACTOR_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_:/-]{0,254}")
_SESSION_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}")
_USER_ID_PATTERN = re.compile(r"[1-9][0-9]{0,19}")


def extract_authenticated_request(payload: dict) -> dict:
    """Return trusted Laravel authentication data for Strands ToolContext."""
    user_id = payload.get("authenticated_user_id")
    access_token = payload.get("user_access_token")

    if user_id is None and access_token is None:
        return {}

    if not isinstance(user_id, str) or not _USER_ID_PATTERN.fullmatch(user_id):
        raise ValueError("authenticated_user_id must be a positive integer string")

    if (
        not isinstance(access_token, str)
        or access_token == ""
        or len(access_token) > 512
        or any(character.isspace() for character in access_token)
    ):
        raise ValueError("user_access_token is invalid")

    return {
        "authenticated_user_id": user_id,
        "user_access_token": access_token,
    }


def extract_memory_identity(payload: dict, context):
    """Return (actor_id, session_id) when this request enables memory."""
    use_memory = payload.get("use_memory", False)

    if not isinstance(use_memory, bool):
        raise ValueError("use_memory must be true or false")

    if not use_memory:
        return None

    actor_id = payload.get("actor_id")

    if not isinstance(actor_id, str) or not _ACTOR_ID_PATTERN.fullmatch(actor_id):
        raise ValueError("actor_id is required when use_memory is true")

    session_id = getattr(context, "session_id", None)

    if not isinstance(session_id, str) or not _SESSION_ID_PATTERN.fullmatch(session_id):
        raise ValueError("a valid runtime session_id is required when use_memory is true")

    return actor_id, session_id


def validate_actor_identity(memory_identity, authenticated_request: dict) -> None:
    """Ensure Memory belongs to the user authenticated by Laravel."""
    if memory_identity is None or not authenticated_request:
        return

    actor_id, _session_id = memory_identity
    expected_actor_id = f"user-{authenticated_request['authenticated_user_id']}"

    if actor_id != expected_actor_id:
        raise ValueError("actor_id does not match authenticated_user_id")


def extract_prompt(payload: dict):
    """Accept messages, tool results, or a Laravel text/image payload."""
    if "messages" in payload:
        return payload["messages"]

    if "tool_results" in payload:
        return [{
            "role": "user",
            "content": [{
                "toolResult": {
                    "toolUseId": tool_result["toolUseId"],
                    "status": tool_result.get("status", "success"),
                    "content": tool_result.get("content", []),
                }
            } for tool_result in payload["tool_results"]],
        }]

    prompt = payload.get("prompt", "")
    media = payload.get("media")

    if media is None:
        return prompt

    if not isinstance(media, dict) or media.get("type") != "image":
        raise ValueError("media.type must be image")

    image_format = media.get("format")

    if image_format not in {"jpeg", "png", "webp"}:
        raise ValueError("media.format must be jpeg, png, or webp")

    encoded_image = media.get("data")

    if not isinstance(encoded_image, str) or encoded_image == "":
        raise ValueError("media.data must be a Base64 string")

    try:
        image_bytes = base64.b64decode(encoded_image, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("media.data is not valid Base64") from error

    if len(image_bytes) > 2 * 1024 * 1024:
        raise ValueError("image must be 2 MB or smaller")

    return [
        {"text": prompt},
        {
            "image": {
                "format": image_format,
                "source": {
                    "bytes": image_bytes,
                },
            },
        },
    ]
