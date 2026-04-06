"""
Model name mapping utility.
Maps Claude/Anthropic model names to GLM model names for display.
"""

# Default GLM model names for each Anthropic model tier
_MODEL_MAP = {
    "opus": "GLM-4.7",
    "sonnet": "GLM-4.7",
    "haiku": "GLM-4.5-Air",
    "glm-4.7": "GLM-4.7",
    "glm-4.5": "GLM-4.5",
    "glm-4.5-air": "GLM-4.5-Air",
    "glm-5": "GLM-5",
    "glm-5-turbo": "GLM-5 Turbo",
}


def map_model_name(model_name: str) -> str:
    """Map Claude/Anthropic model display name to GLM model name."""
    if not model_name:
        return "Unknown"
    lower = model_name.lower()
    for key, value in _MODEL_MAP.items():
        if key in lower:
            return value
    return model_name
