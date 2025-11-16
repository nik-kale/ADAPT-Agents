"""
Anthropic (Claude) LLM Implementation
"""

import json
from typing import Dict, Any, Optional, List
from llm.base_llm import BaseLLM, LLMMessage, LLMResponse


class AnthropicLLM(BaseLLM):
    """Anthropic Claude LLM implementation"""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        temperature: float = 0.0,
        max_tokens: int = 4000,
        timeout: int = 60
    ):
        super().__init__(model, temperature, max_tokens, timeout)
        self.api_key = api_key

        # Lazy import to avoid dependency if not using Anthropic
        try:
            from anthropic import AsyncAnthropic
            self.client = AsyncAnthropic(api_key=api_key, timeout=timeout)
        except ImportError:
            raise ImportError(
                "anthropic package not installed. "
                "Install with: pip install anthropic"
            )

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate text response"""
        messages = [{"role": "user", "content": prompt}]

        create_kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            **kwargs
        }

        if system_prompt:
            create_kwargs["system"] = system_prompt

        response = await self.client.messages.create(**create_kwargs)

        return response.content[0].text

    async def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate structured JSON response"""
        # Enhance prompt with schema instruction
        enhanced_prompt = f"{prompt}\n\nRespond with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}"

        system_instruction = "You are a precise data extraction assistant. Always respond with valid JSON."
        if system_prompt:
            system_instruction = f"{system_prompt}\n\n{system_instruction}"

        messages = [{"role": "user", "content": enhanced_prompt}]

        response = await self.client.messages.create(
            model=self.model,
            messages=messages,
            system=system_instruction,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            **kwargs
        )

        content = response.content[0].text

        # Extract JSON from response (Claude sometimes wraps in markdown)
        if "```json" in content:
            # Extract from code block
            json_start = content.find("```json") + 7
            json_end = content.find("```", json_start)
            content = content[json_start:json_end].strip()
        elif "```" in content:
            # Generic code block
            json_start = content.find("```") + 3
            json_end = content.find("```", json_start)
            content = content[json_start:json_end].strip()

        return json.loads(content)

    async def generate_with_messages(
        self,
        messages: List[LLMMessage],
        **kwargs
    ) -> LLMResponse:
        """Generate from message history"""
        # Convert to Anthropic format
        formatted_messages = []
        system_prompt = None

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
            else:
                formatted_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

        create_kwargs = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            **kwargs
        }

        if system_prompt:
            create_kwargs["system"] = system_prompt

        response = await self.client.messages.create(**create_kwargs)

        return LLMResponse(
            content=response.content[0].text,
            finish_reason=response.stop_reason,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            },
            model=response.model
        )

    def count_tokens(self, text: str) -> int:
        """Count tokens using Anthropic's tokenizer"""
        try:
            # Anthropic uses their own tokenizer
            # For now, use estimation (will be more accurate with anthropic SDK)
            # Claude typically has ~3.5 chars per token
            return len(text) // 3.5
        except Exception:
            # Fallback to base estimation
            return super().count_tokens(text)
