"""Shared LLM provider configuration and utilities.

Centralizes provider URLs and provider-specific API parameters
so they don't need to be duplicated across websocket.py, scheduler.py,
task_executor.py, agent_tools.py, and feishu.py.
"""

# Default base URLs for each known provider.
# If a model has a custom base_url in DB, that takes precedence.
PROVIDER_URLS: dict[str, str | None] = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "openrouter": "https://openrouter.ai/api/v1",
    "custom": None,
}

# Providers that support OpenAI-compatible tool_choice and parallel_tool_calls
_TOOL_CHOICE_PROVIDERS = {"openai", "qwen", "deepseek", "zhipu", "openrouter", "custom"}


def get_provider_base_url(provider: str, custom_base_url: str | None = None) -> str | None:
    """Return the API base URL for a provider.

    If the model has a custom base_url configured, that takes precedence.
    Otherwise falls back to the default URL for the provider.
    """
    if custom_base_url:
        return custom_base_url
    return PROVIDER_URLS.get(provider, "https://api.openai.com/v1")


def get_tool_params(provider: str) -> dict:
    """Return provider-specific tool calling parameters.

    Qwen and OpenAI support `tool_choice` and `parallel_tool_calls`.
    Anthropic uses a different tool calling format, so we skip these params.
    """
    if provider in _TOOL_CHOICE_PROVIDERS:
        return {
            "tool_choice": "auto",
            "parallel_tool_calls": True,
        }
    return {}
