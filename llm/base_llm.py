"""
Base LLM Interface
Provides abstraction for different LLM providers with streaming support
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, AsyncIterator
from pydantic import BaseModel


class LLMMessage(BaseModel):
    """LLM message format"""
    role: str  # system, user, assistant
    content: str


class LLMResponse(BaseModel):
    """LLM response format"""
    content: str
    finish_reason: str
    usage: Dict[str, int]
    model: str


class BaseLLM(ABC):
    """Abstract base class for LLM providers"""

    def __init__(
        self,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 4000,
        timeout: int = 60
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Generate text response from LLM.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional provider-specific parameters

        Returns:
            Generated text response
        """
        pass

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate structured JSON response from LLM.

        Args:
            prompt: User prompt
            schema: JSON schema for response validation
            system_prompt: Optional system prompt
            **kwargs: Additional provider-specific parameters

        Returns:
            Parsed JSON response matching schema
        """
        pass

    @abstractmethod
    async def generate_with_messages(
        self,
        messages: List[LLMMessage],
        **kwargs
    ) -> LLMResponse:
        """
        Generate response from message history.

        Args:
            messages: List of conversation messages
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse with generated content and metadata
        """
        pass

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream text response from LLM chunk by chunk.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional provider-specific parameters

        Yields:
            Text chunks as they are generated

        Note:
            Default implementation calls generate() and yields full response.
            Override in provider implementations for true streaming.
        """
        # Default non-streaming implementation
        response = await self.generate(prompt, system_prompt, **kwargs)
        yield response

    async def stream_with_messages(
        self,
        messages: List[LLMMessage],
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream response from message history chunk by chunk.

        Args:
            messages: List of conversation messages
            **kwargs: Additional provider-specific parameters

        Yields:
            Text chunks as they are generated

        Note:
            Default implementation calls generate_with_messages() and yields full response.
            Override in provider implementations for true streaming.
        """
        # Default non-streaming implementation
        response = await self.generate_with_messages(messages, **kwargs)
        yield response.content

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        Default implementation - override for accurate provider-specific counting.

        Args:
            text: Text to count tokens for

        Returns:
            Estimated token count
        """
        # Rough estimation: ~4 characters per token
        return len(text) // 4


# Global LLM instance
_llm_instance: Optional[BaseLLM] = None


def get_llm() -> BaseLLM:
    """
    Get configured LLM instance.

    Returns:
        Configured LLM provider instance

    Raises:
        ValueError: If LLM provider not configured or API key missing
    """
    global _llm_instance

    if _llm_instance is not None:
        return _llm_instance

    from config.settings import get_settings
    settings = get_settings()

    if not settings.llm_api_key:
        raise ValueError(
            "LLM API key not configured. Set ADAPT_LLM_API_KEY environment variable."
        )

    if settings.llm_provider == "openai":
        from llm.openai_llm import OpenAILLM
        _llm_instance = OpenAILLM(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            timeout=settings.llm_timeout_seconds
        )
    elif settings.llm_provider == "anthropic":
        from llm.anthropic_llm import AnthropicLLM
        _llm_instance = AnthropicLLM(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            timeout=settings.llm_timeout_seconds
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")

    return _llm_instance
