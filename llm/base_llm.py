"""
Base LLM Interface
Provides abstraction for different LLM providers
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
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
