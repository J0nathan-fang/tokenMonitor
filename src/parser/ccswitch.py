"""
CC-Switch API usage parser.

cc-switch is a proxy/middleware that routes requests to various AI providers.
It typically uses an OpenAI-compatible format and may include
usage in the response or in custom headers.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.parser.openai import OpenAIParser
from src.parser.base import UsageData

logger = logging.getLogger("token_monitor.parser.ccswitch")


class CCSwitchParser(OpenAIParser):
    """Parser for cc-switch proxy API."""

    provider_name = "cc-switch"

    def can_parse(self, url: str, headers: dict[str, str], request_body: bytes) -> bool:
        """Detect cc-switch requests by URL or custom headers."""
        url_lower = url.lower()

        if "cc-switch" in url_lower or "ccswitch" in url_lower:
            return True

        # Custom cc-switch headers
        for key in ("x-cc-switch", "x-ccswitch", "cc-switch-route"):
            if key.lower() in (k.lower() for k in headers):
                return True

        return False

    def parse_response(
        self,
        response_body: bytes,
        request_body: bytes | None = None,
        status_code: int = 200,
    ) -> UsageData | None:
        """Parse cc-switch response — OpenAI format with possible custom fields."""
        data = self._safe_json(response_body)
        if data is None:
            return None

        usage = data.get("usage")
        if usage is None:
            return None

        model = data.get("model", "unknown")

        # cc-switch may use either OpenAI or custom field names
        input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens", 0)
        output_tokens = usage.get("completion_tokens") or usage.get("output_tokens", 0)
        total_tokens = usage.get("total_tokens", input_tokens + output_tokens)

        return UsageData(
            provider=self.provider_name,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            status_code=status_code,
        )
