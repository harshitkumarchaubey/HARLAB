"""Optional three-provider AI assistant module with automatic failover."""

from .ai_assistant import ResearchAssistant
from .providers import (
    AIProviderAdapter,
    AIRequest,
    AIResponse,
    FailureKind,
    GeminiAdapter,
    GroqAdapter,
    OpenRouterAdapter,
    ProviderError,
)
from .router import AIProviderRouter, RouterResult

__all__ = [
    "AIProviderAdapter",
    "AIProviderRouter",
    "AIRequest",
    "AIResponse",
    "FailureKind",
    "GeminiAdapter",
    "GroqAdapter",
    "OpenRouterAdapter",
    "ProviderError",
    "ResearchAssistant",
    "RouterResult",
]
