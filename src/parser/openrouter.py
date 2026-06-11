"""
OpenRouter API usage parser.

OpenRouter uses OpenAI-compatible format but routes to various models.
The response includes usage with the actual model used.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.parser.openai import OpenAIParser
from src.parser.base import UsageData

logger = logging.getLogger("token_monitor.parser.openrouter")


class OpenRouterParser(OpenAIParser):
    """Parser for OpenRouter API (OpenAI-compatible with routing metadata)."""

    provider_name = "openrouter"

    def can_parse(self, url: str, headers: dict[str, str], request_body: bytes) -> bool:
        """Check if this is an OpenRouter request."""
        url_lower = url.lower()

        if "openrouter.ai" in url_lower:
            return True

        # Check headers
        for key, value in headers.items():
            if "openrouter" in str(value).lower():
                return True

        if request_body:
            try:
                body = json.loads(request_body)
                model = body.get("model", "")
                if "/" in model and any(
                    prefix in model.lower()
                    for prefix in ("openai/", "anthropic/", "google/", "meta/", "mistral/")
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
        """Parse OpenRouter response. Model comes from response, not request."""
        data = self._safe_json(response_body)
        if data is None:
            return None

        usage = data.get("usage")
        if usage is None:
            return None

        # OpenRouter returns the actual model used
        model = data.get("model", "unknown")

        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", input_tokens + output_tokens)

        return UsageData(
            provider=self.provider_name,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            status_code=status_code,
        )
