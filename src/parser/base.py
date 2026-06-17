"""
Base classes for provider usage parsers.

All parsers inherit from ProviderParser and follow the same interface.
New providers must not modify existing parsers — add a new class instead.
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("token_monitor.parser.base")


@dataclass
class UsageData:
    """Standardized usage data extracted from an API response.

    All parsers return this dataclass regardless of the original API format.

    Provider Identity Separation:
    - client_type: SDK/Protocol used (e.g. "openai", "anthropic")
    - actual_provider: Real backend API provider (e.g. "deepseek", "openai")
    - usage_source: "api" (from response) or "token_counter_fallback" (estimated)
    - pricing_version: Pricing snapshot identifier (e.g. "2026-06-deepseek")
    """

    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    latency_ms: float = 0.0
    endpoint: str = ""
    status_code: int = 200
    timestamp: float = field(default_factory=time.time)
    # Provider Identity
    client_type: str = ""
    actual_provider: str = ""
    # Usage source tracking
    usage_source: str = "api"  # "api" | "token_counter_fallback"
    # Pricing version for audit trail
    pricing_version: str = ""

    @property
    def is_valid(self) -> bool:
        """Check if this usage data contains meaningful information."""
        return self.total_tokens > 0 or self.input_tokens > 0 or self.output_tokens > 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for database insertion."""
        return {
            "timestamp": self.timestamp,
            "provider": self.provider,
            "client_type": self.client_type or self.provider,
            "actual_provider": self.actual_provider or self.provider,
            "model": self.model,
            "endpoint": self.endpoint,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "latency_ms": self.latency_ms,
            "status_code": self.status_code,
            "cost": 0.0,  # Filled by CostCalculator
            "currency": "USD",
            "pricing_version": self.pricing_version,
            "usage_source": self.usage_source,
        }


class ProviderParser(ABC):
    """Abstract base class for all provider-specific parsers.

    Subclasses must implement can_parse and parse_response.
    """

    provider_name: str = "unknown"

    @abstractmethod
    def can_parse(self, url: str, headers: dict[str, str], request_body: bytes) -> bool:
        """Check if this parser can handle the given request.

        Args:
            url: The full request URL.
            headers: Request headers dict.
            request_body: Raw request body bytes.

        Returns:
            True if this parser should handle the request.
        """
        ...

    @abstractmethod
    def parse_response(
        self,
        response_body: bytes,
        request_body: bytes | None = None,
        status_code: int = 200,
    ) -> UsageData | None:
        """Parse a complete (non-streaming) JSON response body.

        Args:
            response_body: Raw response body bytes.
            request_body: Raw request body bytes (to extract model).
            status_code: HTTP status code.

        Returns:
            UsageData if usage was found, None otherwise.
        """
        ...

    def parse_stream_chunk(self, chunk: dict[str, Any]) -> UsageData | None:
        """Parse a single SSE stream chunk.

        Override this for providers that include usage in stream chunks
        (e.g., OpenAI includes usage in the final chunk with stream_options).

        Args:
            chunk: Parsed JSON dict from an SSE data line.

        Returns:
            UsageData if this chunk contains usage info, None otherwise.
        """
        return None

    def extract_model(
        self,
        request_body: bytes | None,
        response_body: dict[str, Any] | None,
    ) -> str:
        """Extract the model name from request or response.

        Args:
            request_body: Raw request body bytes.
            response_body: Parsed response JSON.

        Returns:
            Model name string, or "unknown" if not found.
        """
        # Try response first (it has the actual model used)
        if response_body:
            model = response_body.get("model") or response_body.get("model_id")
            if model:
                return model

        # Try request body
        if request_body:
            try:
                req = json.loads(request_body)
                model = req.get("model") or req.get("model_id")
                if model:
                    return model
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        return "unknown"

    @staticmethod
    def _safe_json(body: bytes) -> dict[str, Any] | None:
        """Safely parse JSON bytes to dict.

        Args:
            body: Raw bytes to parse.

        Returns:
            Parsed dict or None if parsing fails.
        """
        try:
            return json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
            return None

    def _log_parse_result(self, usage: UsageData | None) -> None:
        """Log the result of parsing.

        Args:
            usage: The parsed UsageData or None.
        """
        if usage and usage.is_valid:
            logger.info(
                "Parsed usage [%s/%s]: input=%d output=%d total=%d",
                usage.provider,
                usage.model,
                usage.input_tokens,
                usage.output_tokens,
                usage.total_tokens,
            )
        else:
            logger.debug("No usage data found for request")
