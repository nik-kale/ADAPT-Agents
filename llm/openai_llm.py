"""
OpenAI LLM Implementation
"""

import json
from typing import Dict, Any, Optional, List
from llm.base_llm import BaseLLM, LLMMessage, LLMResponse


class OpenAILLM(BaseLLM):
    """OpenAI LLM implementation"""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4",
        temperature: float = 0.0,
        max_tokens: int = 4000,
        timeout: int = 60
    ):
        super().__init__(model, temperature, max_tokens, timeout)
        self.api_key = api_key

        # Lazy import to avoid dependency if not using OpenAI
        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=api_key, timeout=timeout)
        except ImportError:
            raise ImportError(
                "openai package not installed. "
                "Install with: pip install openai"
            )

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate text response"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            **kwargs
        )

        return response.choices[0].message.content

    async def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate structured JSON response"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Enhance prompt with schema instruction
        enhanced_prompt = f"{prompt}\n\nRespond with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}"
        messages.append({"role": "user", "content": enhanced_prompt})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
            **kwargs
        )

        content = response.choices[0].message.content
        return json.loads(content)

    async def generate_with_messages(
        self,
        messages: List[LLMMessage],
        **kwargs
    ) -> LLMResponse:
        """Generate from message history"""
        formatted_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=formatted_messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            **kwargs
        )

        choice = response.choices[0]
        usage = response.usage

        return LLMResponse(
            content=choice.message.content,
            finish_reason=choice.finish_reason,
            usage={
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens
            },
            model=response.model
        )

    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken"""
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model(self.model)
            return len(encoding.encode(text))
        except ImportError:
            # Fallback to estimation
            return super().count_tokens(text)
