"""Approval-gated Aircon write tool backed by the common Aircon API."""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from strands import ToolContext, tool

from aircon_tools import (
    AirconToolError,
    REQUEST_TIMEOUT_SECONDS,
    _access_token,
    _api_url,
    _read_limited,
)


MAX_OPERATIONS = 20
MAX_FIELD_CHARS = 500
MAX_WRITE_REQUEST_BYTES = 64 * 1024


@dataclass(frozen=True)
class OperationSchema:
    required: frozenset[str]
    optional: frozenset[str] = frozenset()
    nullable: frozenset[str] = frozenset()
    reference_pairs: tuple[tuple[str, str, str], ...] = ()


OPERATION_SCHEMAS = {
    "create_company": OperationSchema(frozenset({"name"})),
    "create_property": OperationSchema(
        frozenset({"name"}),
        frozenset({"company_id", "company_ref", "address"}),
        frozenset({"address"}),
        (("company_id", "company_ref", "create_company"),),
    ),
    "create_system": OperationSchema(
        frozenset({"name"}),
        frozenset({"property_id", "property_ref"}),
        reference_pairs=(("property_id", "property_ref", "create_property"),),
    ),
    "create_model": OperationSchema(frozenset({"manufacturer", "model_number"})),
    "create_unit": OperationSchema(
        frozenset({"name", "unit_type"}),
        frozenset({"system_id", "system_ref", "model_id", "model_ref"}),
        frozenset({"model_id"}),
        (
            ("system_id", "system_ref", "create_system"),
            ("model_id", "model_ref", "create_model"),
        ),
    ),
    "update_company": OperationSchema(frozenset({"id"}), frozenset({"name"})),
    "update_property": OperationSchema(
        frozenset({"id"}),
        frozenset({"company_id", "name", "address"}),
        frozenset({"address"}),
    ),
    "update_system": OperationSchema(
        frozenset({"id"}), frozenset({"property_id", "name"})
    ),
    "update_model": OperationSchema(
        frozenset({"id"}), frozenset({"manufacturer", "model_number"})
    ),
    "update_unit": OperationSchema(
        frozenset({"id"}),
        frozenset({"system_id", "model_id", "name", "unit_type"}),
        frozenset({"model_id"}),
    ),
}


def _validate_operations(operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(operations, list) or not operations:
        raise AirconToolError("operations must be a non-empty list")
    if len(operations) > MAX_OPERATIONS:
        raise AirconToolError(f"operations must not exceed {MAX_OPERATIONS} items")

    normalized: list[dict[str, Any]] = []
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            raise AirconToolError(f"operations[{index}] must be an object")

        operation_type = operation.get("type")
        if not isinstance(operation_type, str) or operation_type not in OPERATION_SCHEMAS:
            raise AirconToolError(f"operations[{index}].type is not supported")

        schema = OPERATION_SCHEMAS[operation_type]
        allowed = {"type"} | schema.required | schema.optional
        unknown = set(operation) - allowed
        if unknown:
            raise AirconToolError(f"operations[{index}] contains unsupported fields")

        missing = schema.required - set(operation)
        if missing:
            raise AirconToolError(f"operations[{index}] is missing required fields")

        item: dict[str, Any] = {"type": operation_type}
        for name in schema.required | schema.optional:
            if name not in operation:
                continue
            value = operation[name]
            if name.endswith("_ref"):
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise AirconToolError(f"operations[{index}].{name} must be an index")
                item[name] = value
                continue
            if value is None and name in schema.nullable:
                item[name] = None
                continue
            if not isinstance(value, str) or not value.strip():
                raise AirconToolError(
                    f"operations[{index}].{name} must be a non-empty string"
                )
            value = value.strip()
            if len(value) > MAX_FIELD_CHARS:
                raise AirconToolError(
                    f"operations[{index}].{name} must not exceed {MAX_FIELD_CHARS} characters"
                )
            if name == "unit_type" and value not in {"indoor", "outdoor"}:
                raise AirconToolError(
                    f"operations[{index}].unit_type must be indoor or outdoor"
                )
            item[name] = value

        for id_field, ref_field, expected_type in schema.reference_pairs:
            has_id = id_field in item
            has_ref = ref_field in item
            if id_field == "model_id" and not has_id and not has_ref:
                continue
            if has_id == has_ref:
                raise AirconToolError(
                    f"operations[{index}] must contain exactly one of {id_field} or {ref_field}"
                )
            if has_ref:
                reference = item[ref_field]
                if reference >= index or operations[reference].get("type") != expected_type:
                    raise AirconToolError(
                        f"operations[{index}].{ref_field} must reference an earlier {expected_type}"
                    )

        if operation_type.startswith("update_") and not (set(item) - {"type", "id"}):
            raise AirconToolError(f"operations[{index}] has no fields to update")

        normalized.append(item)

    encoded = json.dumps(
        {"operations": normalized}, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    if len(encoded) > MAX_WRITE_REQUEST_BYTES:
        raise AirconToolError("Aircon write request exceeded the size limit")
    return normalized


def _safe_write_http_error(status: int) -> AirconToolError:
    messages = {
        400: "Aircon changes were rejected",
        401: "Aircon authentication is invalid or expired",
        403: "Aircon write permission is required",
        409: "Aircon changes conflict with the current data",
        422: "Aircon changes failed validation",
        429: "Aircon service is temporarily rate limited",
    }
    if status in messages:
        return AirconToolError(messages[status])
    if status >= 500:
        return AirconToolError("Aircon service is temporarily unavailable")
    return AirconToolError("Aircon service returned an unexpected response")


def _post_aircon_changes(
    operations: list[dict[str, Any]], tool_context: ToolContext
) -> dict[str, Any]:
    token = _access_token(tool_context)
    request = Request(
        _api_url("changes/apply"),
        data=json.dumps(
            {"operations": operations}, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "myruntime-aircon-client/1.0",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            if response.status < 200 or response.status >= 300:
                raise _safe_write_http_error(response.status)
            if response.headers.get_content_type() != "application/json":
                raise AirconToolError("Aircon service returned a non-JSON response")
            body = _read_limited(response)
    except HTTPError as error:
        raise _safe_write_http_error(error.code) from None
    except (URLError, TimeoutError, socket.timeout, OSError):
        raise AirconToolError("Aircon service could not be reached") from None

    try:
        result = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise AirconToolError("Aircon service returned invalid JSON") from None
    if (
        not isinstance(result, dict)
        or set(result) != {"success", "results"}
        or result["success"] is not True
        or not isinstance(result["results"], list)
        or not all(isinstance(item, dict) for item in result["results"])
    ):
        raise AirconToolError("Aircon service returned an unexpected response shape")
    return result


def _apply_aircon_changes(
    operations: list[dict[str, Any]], tool_context: ToolContext
) -> dict[str, Any]:
    if tool_context is None:
        raise AirconToolError("Tool context is unavailable")

    normalized = _validate_operations(operations)
    approval = tool_context.interrupt(
        "aircon-write-approval",
        reason={"tool_name": "apply_aircon_changes", "operations": normalized},
    )
    if approval != "approve":
        return {"success": False, "executed": False, "reason": "rejected"}

    return _post_aircon_changes(normalized, tool_context)


@tool(context=True)
def apply_aircon_changes(
    operations: list[dict[str, Any]], tool_context: ToolContext = None
) -> dict:
    """Apply validated Aircon create/update operations after explicit user approval.

    Pass 1-20 operations using these fields:
    - create_company: name
    - create_property: name, company_id or company_ref, optional address
    - create_system: name, property_id or property_ref
    - create_model: manufacturer, model_number
    - create_unit: name, unit_type, system_id or system_ref, optional model_id/model_ref
    - update_company: id and name
    - update_property: id and one or more of company_id/name/address
    - update_system: id and one or more of property_id/name
    - update_model: id and one or more of manufacturer/model_number
    - update_unit: id and one or more of system_id/model_id/name/unit_type

    A *_ref is the zero-based index of a compatible earlier create operation.
    unit_type is indoor or outdoor. Delete operations are not supported.
    """
    return _apply_aircon_changes(operations, tool_context)


AIRCON_WRITE_TOOLS = [apply_aircon_changes]
