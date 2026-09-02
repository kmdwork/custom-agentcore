"""Filter Strands streaming events for the Laravel client."""


async def stream_agent(agent, prompt, authenticated_request: dict):
    """Yield only complete AgentCore event dictionaries."""
    async for event in agent.stream_async(
        prompt,
        invocation_state=authenticated_request,
    ):
        if not isinstance(event, dict) or "event" not in event:
            continue

        content_block_start = event["event"].get("contentBlockStart")
        if content_block_start is not None and not content_block_start.get("start"):
            continue

        yield event
