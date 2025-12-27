"""
Base LLM Interface
Provides abstraction for different LLM providers with streaming support
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, AsyncIterator
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


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


class CircuitBreakerLLM(BaseLLM):
    """
    LLM wrapper with circuit breaker protection
    
    Wraps any BaseLLM implementation to provide:
    - Automatic failure detection
    - Fast failure when service is down
    - Automatic recovery when service returns
    - Fallback to rule-based analysis
    """
    
    def __init__(self, wrapped_llm: BaseLLM, circuit_breaker_name: Optional[str] = None):
        """
        Initialize circuit breaker wrapper
        
        Args:
            wrapped_llm: The actual LLM implementation to wrap
            circuit_breaker_name: Optional custom circuit breaker name
        """
        # Copy settings from wrapped LLM
        super().__init__(
            model=wrapped_llm.model,
            temperature=wrapped_llm.temperature,
            max_tokens=wrapped_llm.max_tokens,
            timeout=wrapped_llm.timeout
        )
        
        self.wrapped_llm = wrapped_llm
        
        # Initialize circuit breaker
        from utils.circuit_breaker import circuit_breaker_registry
        
        if circuit_breaker_name is None:
            circuit_breaker_name = f"llm_{wrapped_llm.model}"
        
        self.circuit_breaker = circuit_breaker_registry.get_or_create(
            name=circuit_breaker_name,
            failure_threshold=3,  # Open after 3 failures
            recovery_timeout=30,  # Try recovery after 30 seconds
            half_open_requests=2,  # Need 2 successes to close
            expected_exception=Exception,  # Catch all exceptions
            fallback=self._fallback_response
        )
        
        logger.info(f"LLM circuit breaker initialized: {circuit_breaker_name}")
    
    async def _fallback_response(self, *args, **kwargs) -> str:
        """Fallback response when circuit is open"""
        logger.warning("LLM circuit breaker: Using fallback (rule-based) response")
        return "LLM service unavailable. Analysis will use rule-based methods only."
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate with circuit breaker protection"""
        return await self.circuit_breaker.execute(
            self.wrapped_llm.generate,
            prompt,
            system_prompt,
            **kwargs
        )
    
    async def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate structured response with circuit breaker protection"""
        return await self.circuit_breaker.execute(
            self.wrapped_llm.generate_structured,
            prompt,
            schema,
            system_prompt,
            **kwargs
        )
    
    async def generate_with_messages(
        self,
        messages: List[LLMMessage],
        **kwargs
    ) -> LLMResponse:
        """Generate from messages with circuit breaker protection"""
        return await self.circuit_breaker.execute(
            self.wrapped_llm.generate_with_messages,
            messages,
            **kwargs
        )
    
    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream with circuit breaker protection"""
        # For streaming, we check circuit state but don't wrap each chunk
        if self.circuit_breaker.state.value == "open":
            logger.warning("LLM circuit breaker: Stream blocked, circuit is open")
            yield "LLM service unavailable."
            return
        
        try:
            async for chunk in self.wrapped_llm.stream(prompt, system_prompt, **kwargs):
                yield chunk
        except Exception as e:
            self.circuit_breaker._on_failure(e)
            raise
    
    def get_circuit_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state"""
        return self.circuit_breaker.get_state()


# Global LLM instance
_llm_instance: Optional[BaseLLM] = None


def get_llm(enable_circuit_breaker: bool = True) -> BaseLLM:
    """
    Get configured LLM instance with optional circuit breaker protection.

    Args:
        enable_circuit_breaker: Whether to wrap LLM with circuit breaker (default: True)

    Returns:
        Configured LLM provider instance (optionally wrapped)

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

    # Create base LLM instance
    base_llm: BaseLLM
    
    if settings.llm_provider == "openai":
        from llm.openai_llm import OpenAILLM
        base_llm = OpenAILLM(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            timeout=settings.llm_timeout_seconds
        )
    elif settings.llm_provider == "anthropic":
        from llm.anthropic_llm import AnthropicLLM
        base_llm = AnthropicLLM(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            timeout=settings.llm_timeout_seconds
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")

    # Wrap with circuit breaker for production resilience
    if enable_circuit_breaker:
        logger.info(f"Wrapping {settings.llm_provider} LLM with circuit breaker")
        _llm_instance = CircuitBreakerLLM(base_llm)
    else:
        _llm_instance = base_llm

    return _llm_instance
