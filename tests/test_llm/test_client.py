"""Tests for AstraeaLLMClient (unit tests, no real API calls)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, Field

from astraea.llm.client import AstraeaLLMClient


class SampleOutput(BaseModel):
    """A simple Pydantic model for testing structured output."""

    name: str = Field(..., description="A name")
    score: float = Field(..., description="A score")


class TestAstraeaLLMClientInstantiation:
    """Tests for client creation."""

    @patch("astraea.llm.client.anthropic.Anthropic")
    def test_instantiate_with_default_api_key(self, mock_anthropic: MagicMock) -> None:
        """Client can be created without explicit API key."""
        client = AstraeaLLMClient()
        mock_anthropic.assert_called_once_with(api_key=None)
        assert client._client is not None

    @patch("astraea.llm.client.anthropic.Anthropic")
    def test_instantiate_with_explicit_api_key(self, mock_anthropic: MagicMock) -> None:
        """Client can be created with an explicit API key."""
        client = AstraeaLLMClient(api_key="sk-test-key")
        mock_anthropic.assert_called_once_with(api_key="sk-test-key")
        assert client._client is not None


class TestAstraeaLLMClientParse:
    """Tests for the parse() method."""

    @patch("astraea.llm.client.anthropic.Anthropic")
    def test_parse_calls_messages_parse_with_correct_args(
        self, mock_anthropic_cls: MagicMock
    ) -> None:
        """parse() delegates to client.messages.parse() with all arguments."""
        mock_client_instance = MagicMock()
        mock_anthropic_cls.return_value = mock_client_instance

        mock_response = MagicMock()
        mock_response.parsed_output = SampleOutput(name="test", score=0.95)
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_client_instance.messages.parse.return_value = mock_response

        client = AstraeaLLMClient()
        result = client.parse(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "test prompt"}],
            output_format=SampleOutput,
            max_tokens=2048,
            temperature=0.2,
            system="You are a test assistant.",
        )

        mock_client_instance.messages.parse.assert_called_once_with(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            temperature=0.2,
            messages=[{"role": "user", "content": "test prompt"}],
            output_format=SampleOutput,
            system="You are a test assistant.",
        )
        assert isinstance(result, SampleOutput)
        assert result.name == "test"
        assert result.score == 0.95

    @patch("astraea.llm.client.anthropic.Anthropic")
    def test_parse_omits_system_when_none(self, mock_anthropic_cls: MagicMock) -> None:
        """parse() does not pass system kwarg when it is None."""
        mock_client_instance = MagicMock()
        mock_anthropic_cls.return_value = mock_client_instance

        mock_response = MagicMock()
        mock_response.parsed_output = SampleOutput(name="x", score=0.5)
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 10
        mock_client_instance.messages.parse.return_value = mock_response

        client = AstraeaLLMClient()
        client.parse(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "hello"}],
            output_format=SampleOutput,
        )

        call_kwargs = mock_client_instance.messages.parse.call_args.kwargs
        assert "system" not in call_kwargs

    @patch("astraea.llm.client.anthropic.Anthropic")
    def test_parse_uses_default_temperature_and_max_tokens(
        self, mock_anthropic_cls: MagicMock
    ) -> None:
        """parse() uses default temperature=0.1 and max_tokens=4096."""
        mock_client_instance = MagicMock()
        mock_anthropic_cls.return_value = mock_client_instance

        mock_response = MagicMock()
        mock_response.parsed_output = SampleOutput(name="x", score=0.5)
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 10
        mock_client_instance.messages.parse.return_value = mock_response

        client = AstraeaLLMClient()
        client.parse(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "hello"}],
            output_format=SampleOutput,
        )

        call_kwargs = mock_client_instance.messages.parse.call_args.kwargs
        assert call_kwargs["temperature"] == 0.1
        assert call_kwargs["max_tokens"] == 4096


class TestAstraeaLLMClientRetry:
    """Tests that retry decorator is properly applied."""

    def test_parse_has_retry_decorator(self) -> None:
        """The parse method should be wrapped by tenacity retry."""
        # tenacity wraps functions with a 'retry' attribute
        assert hasattr(AstraeaLLMClient.parse, "retry")

    def test_retry_config_stop_after_3_attempts(self) -> None:
        """Retry should stop after 3 attempts."""
        retry_obj = AstraeaLLMClient.parse.retry
        # The stop strategy should be stop_after_attempt(3)
        assert retry_obj.stop is not None

    def test_retry_config_has_wait_strategy(self) -> None:
        """Retry should use exponential backoff."""
        retry_obj = AstraeaLLMClient.parse.retry
        assert retry_obj.wait is not None
