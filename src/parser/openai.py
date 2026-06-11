"""
OpenAI API usage parser.

Handles:
- Chat Completions API (v1/chat/completions)
- Responses API (v1/responses)
- OpenAI-compatible APIs (vLLM, Ollama, local models, etc.)

Usage format:
{
  "usage": {
    "prompt_tokens": 123,
    "completion_tokens": 456,
    "total_tokens": 579
  }
}

Streaming: usage is in the final chunk when stream_options={"include_usage": true}
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.parser.base import ProviderParser, UsageData

logger = logging.getLogger("token_monitor.parser.openai")


class OpenAIParser(ProviderParser):
    """Parser for OpenAI and OpenAI-compatible APIs."""

    provider_name = "openai"

    # URL patterns that indicate an OpenAI or compatible API
    _url_patterns = [
        "api.openai.com",
        "/v1/chat/completions",
        "/v1/responses",
        "/v1/completions",
        # Compatible APIs
        "openrouter.ai",
        "api.deepseek.com",
        "api.mistral.ai",
        "api.groq.com",
        "api.together.xyz",
        "api.perplexity.ai",
        "api.fireworks.ai",
        "api.x.ai",
    ]

    def can_parse(self, url: str, headers: dict[str, str], request_body: bytes) -> bool:
        """Check if the URL matches OpenAI or any compatible API pattern."""
        url_lower = url.lower()
        for pattern in self._url_patterns:
            if pattern in url_lower:
                return True

        # Check if headers indicate OpenAI API
        auth = headers.get("authorization", headers.get("Authorization", ""))
        if "openai" in auth.lower():
            return True

        # Check request body for OpenAI-specific fields
        if request_body:
            try:
                body = json.loads(request_body)
                if "model" in body and (
                    "messages" in body
                    or "prompt" in body
                    or "input" in body
                ):
                    return True
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        return False

    def parse_response(
        self,
        response_body: bytes,
        request_body: bytes | None = None,
        status_code: int = 200,
    ) -> UsageData | None:
        """Parse OpenAI response for usage data."""
        data = self._safe_json(response_body)
        if data is None:
            return None

        usage = data.get("usage")
        if usage is None:
            # Try Responses API format: { "output": [{...}], "usage": {...} }
            return None

        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", input_tokens + output_tokens)

        # Extract model
        model = self.extract_model(request_body, data)

        # Handle prompt_tokens_details for cached tokens (if present)
        cache_read = 0
        details = usage.get("prompt_tokens_details", {})
        if details:
            cache_read = details.get("cached_tokens", 0)

        return UsageData(
            provider=self.provider_name,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cache_read_tokens=cache_read,
            status_code=status_code,
        )

    def parse_stream_chunk(self, chunk: dict[str, Any]) -> UsageData | None:
        """Parse a stream chunk for usage data.

        OpenAI sends usage in the final chunk with [DONE] or in the last
        chunk that has usage populated (when stream_options is enabled).
        """
        usage = chunk.get("usage")
        if usage is None:
            return None

        model = chunk.get("model", "unknown")
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", input_tokens + output_tokens)

        if total_tokens == 0:
            return None

        return UsageData(
            provider=self.provider_name,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
