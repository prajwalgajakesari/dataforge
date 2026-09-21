"""
LLM Client for DataForge.

Provides a unified interface for interacting with Large Language Models (primarily Anthropic Claude).
Handles retries, token tracking, structured outputs, and streaming.
"""

import asyncio
import json
from typing import Any, AsyncIterator, Dict, List, Optional, Type, Union

from anthropic import AsyncAnthropic
from anthropic.types import Message, MessageStreamEvent
from pydantic import BaseModel

from core.utils.config import settings
from core.utils.logger import get_logger

logger = get_logger(__name__)


class LLMUsage(BaseModel):
    """Token usage statistics for an LLM call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


class LLMResponse(BaseModel):
    """Response from an LLM call."""

    content: str
    model: str
    usage: LLMUsage
    stop_reason: Optional[str] = None
    metadata: Dict[str, Any] = {}


class LLMClient:
    """
    Universal client for interacting with Large Language Models.

    Currently supports:
    - Anthropic Claude (Sonnet, Opus, Haiku)
    - OpenAI (future)

    Features:
    - Automatic retries with exponential backoff
    - Token usage tracking and cost estimation
    - Structured output via Pydantic models
    - Streaming support
    - Prompt template management
    - Context window management
    """

    # Pricing per 1M tokens (as of Jan 2025)
    PRICING = {
        "claude-opus-5": {"input": 5.0, "output": 25.0},
        "claude-sonnet-5": {"input": 2.0, "output": 10.0},
        "claude-haiku-4-5": {"input": 1.0, "output": 5.0},
        "claude-fable-5-1": {"input": 10.0, "output": 50.0},
        # Legacy ids kept for cost reporting on old sessions
        "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
        "claude-3-5-haiku-20241022": {"input": 0.8, "output": 4.0},
        "claude-3-opus-20240229": {"input": 15.0, "output": 75.0},
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_retries: int = 3,
    ):
        """
        Initialize the LLM client.

        Args:
            api_key: Anthropic API key (uses settings if not provided)
            model: Model name (uses settings if not provided)
            temperature: Sampling temperature (uses settings if not provided)
            max_tokens: Maximum tokens to generate (uses settings if not provided)
            max_retries: Maximum number of retry attempts
        """
        self.api_key = api_key or settings.anthropic_api_key
        self.model = model or settings.default_model
        self.temperature = temperature if temperature is not None else settings.model_temperature
        self.max_tokens = max_tokens or settings.model_max_tokens
        self.max_retries = max_retries

        if not self.api_key:
            raise ValueError("Anthropic API key is required")

        self.client = AsyncAnthropic(api_key=self.api_key)
        self.total_usage = LLMUsage()

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None,
    ) -> LLMResponse:
        """
        Generate a completion from the LLM.

        Args:
            prompt: User prompt/message
            system: Optional system prompt
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            stop_sequences: Optional stop sequences

        Returns:
            LLMResponse with generated content and metadata

        Raises:
            Exception: If all retry attempts fail
        """
        messages = [{"role": "user", "content": prompt}]

        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
        }

        if system:
            kwargs["system"] = system

        if stop_sequences:
            kwargs["stop_sequences"] = stop_sequences

        # Retry logic
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response: Message = await self.client.messages.create(**kwargs)

                # Extract content
                content = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        content += block.text

                # Calculate usage
                usage = LLMUsage(
                    prompt_tokens=response.usage.input_tokens,
                    completion_tokens=response.usage.output_tokens,
                    total_tokens=response.usage.input_tokens + response.usage.output_tokens,
                    cost_usd=self._calculate_cost(
                        response.usage.input_tokens,
                        response.usage.output_tokens,
                        self.model,
                    ),
                )

                # Track total usage
                self.total_usage.prompt_tokens += usage.prompt_tokens
                self.total_usage.completion_tokens += usage.completion_tokens
                self.total_usage.total_tokens += usage.total_tokens
                self.total_usage.cost_usd += usage.cost_usd

                logger.info(
                    f"LLM call completed: {usage.total_tokens} tokens, "
                    f"${usage.cost_usd:.4f}"
                )

                return LLMResponse(
                    content=content,
                    model=response.model,
                    usage=usage,
                    stop_reason=response.stop_reason,
                )

            except Exception as e:
                last_error = e
                logger.warning(f"LLM call failed (attempt {attempt + 1}/{self.max_retries}): {e}")

                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    await asyncio.sleep(2**attempt)
                    continue
                else:
                    logger.error(f"All retry attempts exhausted: {e}")
                    raise

        raise Exception(f"LLM generation failed after {self.max_retries} attempts: {last_error}")

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[BaseModel],
        system: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> tuple[BaseModel, LLMResponse]:
        """
        Generate a structured response conforming to a Pydantic model.

        Args:
            prompt: User prompt
            response_model: Pydantic model class for the response
            system: Optional system prompt
            temperature: Override default temperature

        Returns:
            Tuple of (parsed model instance, LLMResponse)

        Raises:
            Exception: If parsing fails or generation fails
        """
        # Build enhanced prompt with JSON schema
        schema = response_model.model_json_schema()
        enhanced_prompt = f"""{prompt}

You must respond with valid JSON matching this schema:

```json
{json.dumps(schema, indent=2)}
```

Respond with ONLY the JSON object, no additional text or markdown formatting.
"""

        enhanced_system = system or ""
        enhanced_system += (
            "\n\nYou are a precise data assistant. Always respond with valid JSON "
            "matching the requested schema. Never include markdown code blocks or additional text."
        )

        # Generate response
        response = await self.generate(
            prompt=enhanced_prompt,
            system=enhanced_system,
            temperature=temperature,
            stop_sequences=["```", "\n\n#"],
        )

        # Parse JSON
        try:
            # Clean up common issues
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            # Parse as JSON
            data = json.loads(content)

            # Validate with Pydantic model
            parsed = response_model(**data)

            logger.info(f"Successfully parsed structured response: {response_model.__name__}")
            return parsed, response

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}\nContent: {response.content}")
            raise ValueError(f"LLM did not return valid JSON: {e}")
        except Exception as e:
            logger.error(f"Failed to validate response against model: {e}")
            raise ValueError(f"Response does not match expected schema: {e}")

    async def stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """
        Stream a completion from the LLM.

        Args:
            prompt: User prompt
            system: Optional system prompt
            temperature: Override default temperature
            max_tokens: Override default max_tokens

        Yields:
            String chunks as they are generated

        Raises:
            Exception: If streaming fails
        """
        messages = [{"role": "user", "content": prompt}]

        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
        }

        if system:
            kwargs["system"] = system

        try:
            async with self.client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    if hasattr(event, "type"):
                        if event.type == "content_block_delta":
                            if hasattr(event, "delta") and hasattr(event.delta, "text"):
                                yield event.delta.text

                # Get final message for usage tracking
                final_message = await stream.get_final_message()
                usage = LLMUsage(
                    prompt_tokens=final_message.usage.input_tokens,
                    completion_tokens=final_message.usage.output_tokens,
                    total_tokens=final_message.usage.input_tokens
                    + final_message.usage.output_tokens,
                    cost_usd=self._calculate_cost(
                        final_message.usage.input_tokens,
                        final_message.usage.output_tokens,
                        self.model,
                    ),
                )

                # Track total usage
                self.total_usage.prompt_tokens += usage.prompt_tokens
                self.total_usage.completion_tokens += usage.completion_tokens
                self.total_usage.total_tokens += usage.total_tokens
                self.total_usage.cost_usd += usage.cost_usd

                logger.info(
                    f"LLM streaming completed: {usage.total_tokens} tokens, "
                    f"${usage.cost_usd:.4f}"
                )

        except Exception as e:
            logger.error(f"LLM streaming failed: {e}")
            raise

    def _calculate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Calculate cost in USD for token usage."""
        if model not in self.PRICING:
            logger.warning(f"Unknown model for pricing: {model}")
            return 0.0

        pricing = self.PRICING[model]
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def get_total_usage(self) -> LLMUsage:
        """Get total token usage and cost for this client instance."""
        return self.total_usage

    def reset_usage(self) -> None:
        """Reset usage tracking."""
        self.total_usage = LLMUsage()


# Convenience function for one-off calls
async def generate_text(
    prompt: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
) -> str:
    """
    Convenience function for simple text generation.

    Args:
        prompt: User prompt
        system: Optional system prompt
        model: Model to use
        temperature: Sampling temperature

    Returns:
        Generated text content
    """
    client = LLMClient(model=model, temperature=temperature)
    response = await client.generate(prompt=prompt, system=system)
    return response.content


async def generate_json(
    prompt: str,
    response_model: Type[BaseModel],
    system: Optional[str] = None,
    model: Optional[str] = None,
) -> BaseModel:
    """
    Convenience function for structured JSON generation.

    Args:
        prompt: User prompt
        response_model: Pydantic model for response
        system: Optional system prompt
        model: Model to use

    Returns:
        Parsed Pydantic model instance
    """
    client = LLMClient(model=model)
    parsed, _ = await client.generate_structured(
        prompt=prompt,
        response_model=response_model,
        system=system,
    )
    return parsed
