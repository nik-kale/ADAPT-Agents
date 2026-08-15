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
        
        # No breaker-level fallback: a single fallback cannot satisfy the three
        # different return types (str / Dict / LLMResponse). Each wrapper method
        # below catches CircuitOpenError and returns its own correctly-typed
        # degradation, while the breaker keeps one shared failure state.
        self.circuit_breaker = circuit_breaker_registry.get_or_create(
            name=circuit_breaker_name,
            failure_threshold=3,  # Open after 3 failures
            recovery_timeout=30,  # Try recovery after 30 seconds
            half_open_requests=2,  # Need 2 successes to close
            expected_exception=Exception,  # Catch all exceptions
            fallback=None
        )
        
        logger.info(f"LLM circuit breaker initialized: {circuit_breaker_name}")
    
    _FALLBACK_TEXT = "LLM service unavailable. Analysis will use rule-based methods only."

    async def _fallback_response(self, *args, **kwargs) -> str:
        """Fallback for generate() — callers expect a plain string."""
        logger.warning("LLM circuit breaker: Using fallback (rule-based) response")
        return self._FALLBACK_TEXT

    async def _fallback_structured(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Fallback for generate_structured() — callers expect a dict.

        Returning the plain string here would make callers such as
        LogAnalyzerAgent (`llm_response.get("findings", [])`) raise
        AttributeError, turning an open circuit into a type error instead of a
        clean degradation.
        """
        logger.warning("LLM circuit breaker: Using fallback structured response")
        return {"findings": [], "error": self._FALLBACK_TEXT, "degraded": True}

    async def _fallback_messages(self, *args, **kwargs) -> LLMResponse:
        """Fallback for generate_with_messages() — callers expect an LLMResponse."""
        logger.warning("LLM circuit breaker: Using fallback message response")
        return LLMResponse(
            content=self._FALLBACK_TEXT,
            model=self.model,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            finish_reason="circuit_open"
        )
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate with circuit breaker protection"""
        from utils.circuit_breaker import CircuitOpenError
        try:
            return await self.circuit_breaker.execute(
                self.wrapped_llm.generate,
                prompt,
                system_prompt,
                **kwargs
            )
        except CircuitOpenError:
            return await self._fallback_response()
    
    async def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate structured response with circuit breaker protection"""
        from utils.circuit_breaker import CircuitOpenError
        try:
            return await self.circuit_breaker.execute(
                self.wrapped_llm.generate_structured,
                prompt,
                schema,
                system_prompt,
                **kwargs
            )
        except CircuitOpenError:
            return await self._fallback_structured()
    
    async def generate_with_messages(
        self,
        messages: List[LLMMessage],
        **kwargs
    ) -> LLMResponse:
        """Generate from messages with circuit breaker protection"""
        from utils.circuit_breaker import CircuitOpenError
        try:
            return await self.circuit_breaker.execute(
                self.wrapped_llm.generate_with_messages,
                messages,
                **kwargs
            )
        except CircuitOpenError:
            return await self._fallback_messages()
    
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
# Cached per wrapping mode. A single slot would let the first caller decide the
# mode for the whole process — e.g. /health calling get_llm() would pin the
# circuit-breaker-wrapped instance for every later get_llm(enable_circuit_breaker=False).
_llm_instances: Dict[bool, BaseLLM] = {}


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
    cached = _llm_instances.get(enable_circuit_breaker)
    if cached is not None:
        return cached

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
        instance: BaseLLM = CircuitBreakerLLM(base_llm)
    else:
        instance = base_llm

    _llm_instances[enable_circuit_breaker] = instance
    return instance
