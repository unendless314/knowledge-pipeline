"""
Knowledge Pipeline - LLM Provider 抽象層

提供統一的 LLM 介面，支援多種 Provider（Gemini CLI、OpenAI API 等）
"""

from src.llm.models import (
    ProviderType,
    TranscriptInput,
    Segment,
    AnalysisResult,
    GeminiCLIConfig,
    OpenAIConfig,
    LLMConfig,
)

from src.llm.exceptions import (
    LLMError,
    LLMCallError,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMParseError,
    PromptTemplateNotFoundError,
)

from src.llm.client import LLMClient

from src.llm.prompts import (
    PromptLoader,
    OutputParser,
)

__all__ = [
    # Models
    "ProviderType",
    "TranscriptInput",
    "Segment",
    "AnalysisResult",
    "GeminiCLIConfig",
    "OpenAIConfig",
    "LLMConfig",
    # Exceptions
    "LLMError",
    "LLMCallError",
    "LLMTimeoutError",
    "LLMRateLimitError",
    "LLMParseError",
    "PromptTemplateNotFoundError",
    # Client
    "LLMClient",
    # Prompts
    "PromptLoader",
    "OutputParser",
]
