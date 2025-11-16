"""
LLM Integration Package
Provides abstraction for different LLM providers
"""

from .base_llm import BaseLLM, LLMMessage, LLMResponse, get_llm

try:
    from .openai_llm import OpenAILLM
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from .anthropic_llm import AnthropicLLM
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

__all__ = ['BaseLLM', 'LLMMessage', 'LLMResponse', 'get_llm']

if OPENAI_AVAILABLE:
    __all__.append('OpenAILLM')

if ANTHROPIC_AVAILABLE:
    __all__.append('AnthropicLLM')
