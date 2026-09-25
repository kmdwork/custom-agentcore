from strands import ToolContext, tool


@tool(context=True)
def test_write_action(
    value: str,
    tool_context: ToolContext = None,
) -> dict:
    if tool_context is None:
        raise RuntimeError("Tool context is unavailable")

    approval = tool_context.interrupt(
        "poc-test-write-approval",
        reason={
            "tool_name": "test_write_action",
            "input": {
                "value": value,
            },
        },
    )

    if approval != "approve":
        return {
            "executed": False,
            "value": value,
        }

    token = tool_context.invocation_state.get("user_access_token")

    if token == "poc-write-token":
        token_marker = "resume-write-token"
    elif token == "poc-read-token":
        token_marker = "initial-read-token"
    else:
        token_marker = "other"

    return {
        "executed": True,
        "value": value,
        "token_marker": token_marker,
    }