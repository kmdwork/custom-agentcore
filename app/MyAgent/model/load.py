from strands.models.bedrock import BedrockModel


MODEL_ID = "jp.anthropic.claude-sonnet-4-6"


def load_model() -> BedrockModel:
    """Get Bedrock model client using IAM credentials."""
    return BedrockModel(model_id=MODEL_ID)


def load_low_reasoning_model() -> BedrockModel:
    """Get the Bedrock model configured for low reasoning effort."""
    return BedrockModel(
        model_id=MODEL_ID,
        additional_request_fields={
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": "low"},
        },
    )


def load_high_reasoning_model() -> BedrockModel:
    """Get the Bedrock model configured for high reasoning effort."""
    return BedrockModel(
        model_id=MODEL_ID,
        additional_request_fields={
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": "high"},
        },
    )
