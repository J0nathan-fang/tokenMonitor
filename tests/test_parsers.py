"""
Tests for usage parsers across all providers.

Verifies that each parser correctly extracts usage data from
realistic API response JSON.
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parser.openai import OpenAIParser
from src.parser.anthropic import AnthropicParser
from src.parser.gemini import GeminiParser
from src.parser.deepseek import DeepSeekParser
from src.parser.openrouter import OpenRouterParser
from src.parser.ccswitch import CCSwitchParser
from src.parser.registry import ParserRegistry


class TestOpenAIParser(unittest.TestCase):
    """Test OpenAI API response parsing."""

    def setUp(self) -> None:
        self.parser = OpenAIParser()

    def test_chat_completion_response(self) -> None:
        """Parse a standard chat completion response."""
        response = json.dumps({
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "model": "gpt-4o-2024-08-06",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello!"}}],
            "usage": {
                "prompt_tokens": 123,
                "completion_tokens": 456,
                "total_tokens": 579,
            },
        }).encode()
        usage = self.parser.parse_response(response)
        self.assertIsNotNone(usage)
        self.assertEqual(usage.provider, "openai")
        self.assertEqual(usage.model, "gpt-4o-2024-08-06")
        self.assertEqual(usage.input_tokens, 123)
        self.assertEqual(usage.output_tokens, 456)
        self.assertEqual(usage.total_tokens, 579)

    def test_no_usage_field(self) -> None:
        """Response without usage field returns None."""
        response = json.dumps({
            "id": "chatcmpl-123",
            "choices": [{"message": {"content": "Hi"}}],
        }).encode()
        usage = self.parser.parse_response(response)
        self.assertIsNone(usage, "Should return None when no usage field")

    def test_url_detection(self) -> None:
        """Test URL-based detection."""
        self.assertTrue(self.parser.can_parse(
            "https://api.openai.com/v1/chat/completions", {}, b"{}"
        ))
        self.assertTrue(self.parser.can_parse(
            "https://api.openai.com/v1/responses", {}, b"{}"
        ))

    def test_stream_chunk_with_usage(self) -> None:
        """Parse a stream chunk that includes usage (final chunk)."""
        chunk = {
            "id": "chatcmpl-123",
            "model": "gpt-4o",
            "choices": [{"delta": {}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 100,
                "total_tokens": 150,
            },
        }
        usage = self.parser.parse_stream_chunk(chunk)
        self.assertIsNotNone(usage)
        self.assertEqual(usage.total_tokens, 150)


class TestAnthropicParser(unittest.TestCase):
    """Test Anthropic API response parsing."""

    def setUp(self) -> None:
        self.parser = AnthropicParser()

    def test_message_response(self) -> None:
        """Parse a standard Messages API response."""
        response = json.dumps({
            "id": "msg_123",
            "model": "claude-sonnet-4-20250514",
            "type": "message",
            "content": [{"type": "text", "text": "Hello!"}],
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_input_tokens": 20,
                "cache_creation_input_tokens": 10,
            },
        }).encode()
        usage = self.parser.parse_response(response)
        self.assertIsNotNone(usage)
        self.assertEqual(usage.provider, "anthropic")
        self.assertEqual(usage.model, "claude-sonnet-4-20250514")
        self.assertEqual(usage.input_tokens, 100)
        self.assertEqual(usage.output_tokens, 50)
        self.assertEqual(usage.total_tokens, 150)
        self.assertEqual(usage.cache_read_tokens, 20)
        self.assertEqual(usage.cache_write_tokens, 10)

    def test_stream_message_stop(self) -> None:
        """Parse a message_stop stream event."""
        chunk = {
            "type": "message_stop",
            "usage": {
                "input_tokens": 200,
                "output_tokens": 100,
            },
            "message": {"model": "claude-sonnet-4-20250514"},
        }
        usage = self.parser.parse_stream_chunk(chunk)
        self.assertIsNotNone(usage)
        self.assertEqual(usage.input_tokens, 200)
        self.assertEqual(usage.output_tokens, 100)

    def test_url_detection(self) -> None:
        """Test Anthropic URL detection."""
        self.assertTrue(self.parser.can_parse(
            "https://api.anthropic.com/v1/messages", {}, b"{}"
        ))


class TestGeminiParser(unittest.TestCase):
    """Test Gemini API response parsing."""

    def setUp(self) -> None:
        self.parser = GeminiParser()

    def test_generate_content_response(self) -> None:
        """Parse a generateContent response with usageMetadata."""
        response = json.dumps({
            "candidates": [{"content": {"parts": [{"text": "Hello"}]}}],
            "usageMetadata": {
                "promptTokenCount": 50,
                "candidatesTokenCount": 30,
                "totalTokenCount": 80,
            },
            "modelVersion": "gemini-2.5-pro",
        }).encode()
        usage = self.parser.parse_response(response)
        self.assertIsNotNone(usage)
        self.assertEqual(usage.provider, "gemini")
        self.assertEqual(usage.model, "gemini-2.5-pro")
        self.assertEqual(usage.input_tokens, 50)
        self.assertEqual(usage.output_tokens, 30)
        self.assertEqual(usage.total_tokens, 80)

    def test_url_detection(self) -> None:
        """Test Gemini URL detection."""
        self.assertTrue(self.parser.can_parse(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent",
            {}, b"{}"
        ))

    def test_stream_chunk(self) -> None:
        """Parse stream chunk with usageMetadata."""
        chunk = {
            "candidates": [{"content": {"parts": [{"text": "..."}]}}],
            "usageMetadata": {
                "promptTokenCount": 25,
                "candidatesTokenCount": 15,
                "totalTokenCount": 40,
            },
        }
        usage = self.parser.parse_stream_chunk(chunk)
        self.assertIsNotNone(usage)
        self.assertEqual(usage.total_tokens, 40)


class TestDeepSeekParser(unittest.TestCase):
    """Test DeepSeek parser (OpenAI-compatible format)."""

    def setUp(self) -> None:
        self.parser = DeepSeekParser()

    def test_deepseek_response(self) -> None:
        """Parse a DeepSeek response."""
        response = json.dumps({
            "id": "ds-123",
            "model": "deepseek-chat",
            "choices": [{"message": {"content": "Hello"}}],
            "usage": {
                "prompt_tokens": 200,
                "completion_tokens": 100,
                "total_tokens": 300,
            },
        }).encode()
        usage = self.parser.parse_response(response)
        self.assertIsNotNone(usage)
        self.assertEqual(usage.provider, "deepseek")
        self.assertEqual(usage.model, "deepseek-chat")

    def test_url_detection(self) -> None:
        """Test DeepSeek URL detection."""
        self.assertTrue(self.parser.can_parse(
            "https://api.deepseek.com/v1/chat/completions", {}, b"{}"
        ))
        self.assertTrue(self.parser.can_parse(
            "https://api.openai.com/v1/chat/completions", {},
            json.dumps({"model": "deepseek-reasoner"}).encode()
        ))


class TestOpenRouterParser(unittest.TestCase):
    """Test OpenRouter parser."""

    def setUp(self) -> None:
        self.parser = OpenRouterParser()

    def test_openrouter_response(self) -> None:
        """Parse an OpenRouter response."""
        response = json.dumps({
            "id": "or-123",
            "model": "openai/gpt-4o",
            "choices": [{"message": {"content": "Hi"}}],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
            },
        }).encode()
        usage = self.parser.parse_response(response)
        self.assertIsNotNone(usage)
        self.assertEqual(usage.provider, "openrouter")
        self.assertEqual(usage.model, "openai/gpt-4o")

    def test_url_detection(self) -> None:
        """Test OpenRouter URL detection."""
        self.assertTrue(self.parser.can_parse(
            "https://openrouter.ai/api/v1/chat/completions", {}, b"{}"
        ))
        self.assertTrue(self.parser.can_parse(
            "https://api.openai.com/v1/chat/completions", {},
            json.dumps({"model": "openai/gpt-4o"}).encode()
        ))


class TestParserRegistry(unittest.TestCase):
    """Test parser auto-detection."""

    def setUp(self) -> None:
        self.registry = ParserRegistry()

    def test_openai_url_returns_openai_parser(self) -> None:
        """Verify OpenAI URL is detected as OpenAI."""
        parser = self.registry.detect(
            "https://api.openai.com/v1/chat/completions", {}, b"{}"
        )
        self.assertIsNotNone(parser)
        self.assertEqual(parser.provider_name, "openai")

    def test_anthropic_url_returns_anthropic_parser(self) -> None:
        """Verify Anthropic URL is detected."""
        parser = self.registry.detect(
            "https://api.anthropic.com/v1/messages", {}, b"{}"
        )
        self.assertIsNotNone(parser)
        self.assertEqual(parser.provider_name, "anthropic")

    def test_deepseek_takes_priority_over_openai(self) -> None:
        """DeepSeek URL should use DeepSeek parser, not generic OpenAI."""
        parser = self.registry.detect(
            "https://api.deepseek.com/v1/chat/completions", {}, b"{}"
        )
        self.assertIsNotNone(parser)
        self.assertEqual(parser.provider_name, "deepseek")

    def test_unknown_url_returns_none(self) -> None:
        """Unknown URL should gracefully return None."""
        parser = self.registry.detect(
            "https://example.com/api", {}, b"{}"
        )
        self.assertIsNone(parser)


if __name__ == "__main__":
    unittest.main()
