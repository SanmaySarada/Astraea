"""Shared LLM client wrapper for the Astraea pipeline.

Wraps the Anthropic SDK with structured output via Pydantic models,
automatic retry on transient errors, and loguru-based call logging.
All LLM calls in the pipeline should go through this client.
"""

from __future__ import annotations

import time
from typing import TypeVar

import anthropic
from loguru import logger
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

T = TypeVar("T", bound=BaseModel)


class AstraeaLLMClient:
    """Anthropic API client with structured output, retry, and logging.

    Usage::

        client = AstraeaLLMClient()
        result = client.parse(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Extract fields from ..."}],
            output_format=ECRFFormExtraction,
            temperature=0.2,
        )
        # result is a validated ECRFFormExtraction instance
    """

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize the Anthropic client.

        Args:
            api_key: Optional API key. If None, reads from ANTHROPIC_API_KEY env var.
        """
        self._client = anthropic.Anthropic(api_key=api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=30),
        retry=retry_if_exception_type(
            (
                anthropic.APITimeoutError,
                anthropic.APIConnectionError,
                anthropic.RateLimitError,
            )
        ),
        reraise=True,
    )
    def parse(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        output_format: type[T],
        max_tokens: int = 4096,
        temperature: float = 0.1,
        system: str | None = None,
    ) -> T:
        """Make a structured output LLM call returning a validated Pydantic model.

        Uses ``client.messages.parse()`` for guaranteed schema-compliant output.

        Args:
            model: Claude model ID (e.g., "claude-sonnet-4-20250514").
            messages: List of message dicts with "role" and "content" keys.
            output_format: Pydantic model class to parse the response into.
            max_tokens: Maximum tokens in the response.
            temperature: Sampling temperature (0.0-1.0).
            system: Optional system prompt.

        Returns:
            Validated instance of the output_format Pydantic model.

        Raises:
            anthropic.BadRequestError: On invalid request (not retried).
            anthropic.APITimeoutError: After 3 retry attempts.
            anthropic.APIConnectionError: After 3 retry attempts.
            anthropic.RateLimitError: After 3 retry attempts.
        """
        start = time.monotonic()

        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
            "output_format": output_format,
        }
        if system is not None:
            kwargs["system"] = system

        response = self._client.messages.parse(**kwargs)
        elapsed = time.monotonic() - start

        logger.info(
            "LLM call | model={model} temp={temp} "
            "input_tokens={inp} output_tokens={out} latency={lat:.2f}s",
            model=model,
            temp=temperature,
            inp=response.usage.input_tokens,
            out=response.usage.output_tokens,
            lat=elapsed,
        )

        return response.parsed_output
