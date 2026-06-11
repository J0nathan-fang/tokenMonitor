"""
Anthropic Claude API usage parser.

Handles:
- Messages API (v1/messages)
- Streaming with SSE

Usage format:
{
  "usage": {
    "input_tokens": 123,
    "output_tokens": 456,
    "cache_read_input_tokens": 0,
    "cache_creation_input_tokens": 0
  }
}

Streaming: usage is in message_stop / message_delta events.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.parser.base import ProviderParser, UsageData

logger = logging.getLogger("token_monitor.parser.anthropic")


class AnthropicParser(ProviderParser):
    """Parser for Anthropic Claude Messages API."""

    provider_name = "anthropic"

    _url_patterns = [
        "api.anthropic.com",
        "/v1/messages",
    ]

    def can_parse(self, url: str, headers: dict[str, str], request_body: bytes) -> bool:
        """Check if the URL or headers indicate Anthropic API."""
        url_lower = url.lower()
        for pattern in self._url_patterns:
            if pattern in url_lower:
                return True

        # Check headers
        for key in ("x-api-key", "anthropic-version"):
            if key in headers or key.lower() in headers:
                return True

        # Check request body for Anthropic-specific fields
        if request_body:
            try:
                body = json.loads(request_body)
                if "model" in body and ("messages" in body or "system" in body):
                    model = body.get("model", "")
                    if any(m in model.lower() for m in ("claude", "anthropic")):
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
        """Parse Anthropic response for usage data."""
        data = self._safe_json(response_body)
        if data is None:
            return None

        usage = data.get("usage")
        if usage is None:
            return None

        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        total_tokens = input_tokens + output_tokens
        cache_read = usage.get("cache_read_input_tokens", 0)
        cache_write = usage.get("cache_creation_input_tokens", 0)

        model = self.extract_model(request_body, data)

        return UsageData(
            provider=self.provider_name,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
            status_code=status_code,
        )

    def parse_stream_chunk(self, chunk: dict[str, Any]) -> UsageData | None:
        """Parse SSE stream event for usage.

        Anthropic sends usage in:
        - message_stop event: { "type": "message_stop", "usage": {...} }
        - message_delta event: { "type": "message_delta", "usage": { "output_tokens": N } }
        """
        event_type = chunk.get("type", "")

        if event_type == "message_stop":
            usage = chunk.get("usage", {})
            message = chunk.get("message", {})
            model = message.get("model", chunk.get("model", "unknown"))
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)

            return UsageData(
                provider=self.provider_name,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                cache_read_tokens=usage.get("cache_read_input_tokens", 0),
                cache_write_tokens=usage.get("cache_creation_input_tokens", 0),
            )

        elif event_type == "message_delta":
            usage = chunk.get("usage", {})
            delta_out = usage.get("output_tokens", 0)
            delta = chunk.get("delta", {})
            # message_delta only has output_tokens increment
            return UsageData(
                provider=self.provider_name,
                model=chunk.get("model", "unknown"),
                output_tokens=delta_out,
                total_tokens=delta_out,
            )

        return None
