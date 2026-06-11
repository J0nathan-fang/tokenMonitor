"""
Google Gemini API usage parser.

Handles:
- Generate Content API (v1beta/models/*:generateContent)
- Stream Generate Content

Usage format:
{
  "usageMetadata": {
    "promptTokenCount": 123,
    "candidatesTokenCount": 456,
    "totalTokenCount": 579
  }
}
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.parser.base import ProviderParser, UsageData

logger = logging.getLogger("token_monitor.parser.gemini")


class GeminiParser(ProviderParser):
    """Parser for Google Gemini API."""

    provider_name = "gemini"

    _url_patterns = [
        "generativelanguage.googleapis.com",
        "googleapis.com",
        "/v1beta/models/",
        "gemini",
        ":generateContent",
        ":streamGenerateContent",
    ]

    def can_parse(self, url: str, headers: dict[str, str], request_body: bytes) -> bool:
        """Check if URL indicates Gemini API."""
        url_lower = url.lower()
        for pattern in self._url_patterns:
            if pattern in url_lower:
                return True

        # Check for Gemini-specific model names
        if request_body:
            try:
                body = json.loads(request_body)
                model = body.get("model", "")
                if "gemini" in model.lower():
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
        """Parse Gemini response for usage metadata."""
        data = self._safe_json(response_body)
        if data is None:
            return None

        usage = data.get("usageMetadata")
        if usage is None:
            return None

        input_tokens = usage.get("promptTokenCount", 0)
        output_tokens = usage.get("candidatesTokenCount", 0)
        total_tokens = usage.get("totalTokenCount", input_tokens + output_tokens)

        model = data.get("modelVersion", "unknown")
        if model == "unknown" and request_body:
            try:
                req = json.loads(request_body)
                model = req.get("model", "gemini")
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        return UsageData(
            provider=self.provider_name,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            status_code=status_code,
        )

    def parse_stream_chunk(self, chunk: dict[str, Any]) -> UsageData | None:
        """Gemini includes usageMetadata in the final stream chunk."""
        usage = chunk.get("usageMetadata")
        if usage is None:
            return None

        input_tokens = usage.get("promptTokenCount", 0)
        output_tokens = usage.get("candidatesTokenCount", 0)
        total_tokens = usage.get("totalTokenCount", input_tokens + output_tokens)

        if total_tokens == 0:
            return None

        return UsageData(
            provider=self.provider_name,
            model=chunk.get("modelVersion", "gemini"),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
