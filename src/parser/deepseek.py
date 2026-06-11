"""
DeepSeek API usage parser.

DeepSeek uses an OpenAI-compatible API format.
This parser handles DeepSeek-specific endpoint detection
and delegates to OpenAI format parsing.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.parser.openai import OpenAIParser
from src.parser.base import UsageData

logger = logging.getLogger("token_monitor.parser.deepseek")


class DeepSeekParser(OpenAIParser):
    """Parser for DeepSeek API (OpenAI-compatible with DeepSeek-specific detection).

    Inherits from OpenAIParser since the API format is identical.
    Only overrides detection to correctly attribute to 'deepseek' provider.
    """

    provider_name = "deepseek"

    _deepseek_patterns = [
        "api.deepseek.com",
        "deepseek.com/v1",
        "/v1/chat/completions",  # Will be refined by can_parse
    ]

    def can_parse(self, url: str, headers: dict[str, str], request_body: bytes) -> bool:
        """Check if this request is specifically for DeepSeek."""
        url_lower = url.lower()

        # Explicit DeepSeek URL
        if "api.deepseek.com" in url_lower or "deepseek" in url_lower:
            return True

        # Check request body for DeepSeek model
        if request_body:
            try:
                body = json.loads(request_body)
                model = body.get("model", "")
                if "deepseek" in model.lower():
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
        """Parse DeepSeek response — same format as OpenAI but with correct provider."""
        usage = super().parse_response(response_body, request_body, status_code)
        if usage:
            usage.provider = self.provider_name
        return usage

    def parse_stream_chunk(self, chunk: dict[str, Any]) -> UsageData | None:
        """Parse stream chunk — same format as OpenAI with DeepSeek provider."""
        usage = super().parse_stream_chunk(chunk)
        if usage:
            usage.provider = self.provider_name
        return usage
