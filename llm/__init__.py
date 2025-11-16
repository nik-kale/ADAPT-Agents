"""
LLM Integration Package
Provides abstraction for different LLM providers
"""

from .base_llm import BaseLLM, LLMMessage, LLMResponse

try:
    from .openai_llm import OpenAILLM
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

__all__ = ['BaseLLM', 'LLMMessage', 'LLMResponse']

if OPENAI_AVAILABLE:
    __all__.append('OpenAILLM')
