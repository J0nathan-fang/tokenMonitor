"""
Parser registry — auto-detects the correct parser for each request.

Parsers are tried in order of specificity (most specific first).
The first parser that can_parse() returns True wins.
"""

from __future__ import annotations

import logging
from typing import Any

from src.parser.base import ProviderParser, UsageData
from src.parser.anthropic import AnthropicParser
from src.parser.ccswitch import CCSwitchParser
from src.parser.deepseek import DeepSeekParser
from src.parser.gemini import GeminiParser
from src.parser.openai import OpenAIParser
from src.parser.openrouter import OpenRouterParser

logger = logging.getLogger("token_monitor.parser.registry")


class ParserRegistry:
    """Registry of all parser implementations with auto-detection.

    Parsers are ordered by specificity — most specific first.
    """

    def __init__(self) -> None:
        """Initialize with all built-in parsers in priority order."""
        self._parsers: list[ProviderParser] = [
            CCSwitchParser(),      # Most specific: cc-switch custom proxy
            DeepSeekParser(),      # Specific: deepseek.com
            OpenRouterParser(),    # Specific: openrouter.ai
            AnthropicParser(),     # Specific: anthropic.com
            GeminiParser(),        # Specific: googleapis.com
            OpenAIParser(),        # Catch-all: OpenAI-compatible (most generic)
        ]
        logger.info("ParserRegistry initialized with %d parsers", len(self._parsers))

    def register(self, parser: ProviderParser) -> None:
        """Register a new parser (highest priority).

        Args:
            parser: A ProviderParser instance.
        """
        self._parsers.insert(0, parser)
        logger.info("Registered parser: %s", parser.provider_name)

    def detect(
        self,
        url: str,
        headers: dict[str, str],
        request_body: bytes,
    ) -> ProviderParser | None:
        """Detect which parser should handle a request.

        Args:
            url: Full request URL.
            headers: Request headers.
            request_body: Raw request body bytes.

        Returns:
            The matching parser or None.
        """
        for parser in self._parsers:
            try:
                if parser.can_parse(url, headers, request_body):
                    logger.debug("Detected parser: %s for %s", parser.provider_name, url)
                    return parser
            except Exception as e:
                logger.warning("Parser %s.can_parse() raised: %s", parser.provider_name, e)

        logger.debug("No parser detected for URL: %s", url)
        return None

    def parse_response(
        self,
        response_body: bytes,
        url: str,
        headers: dict[str, str],
        request_body: bytes,
        status_code: int = 200,
    ) -> UsageData | None:
        """Auto-detect parser and parse the response.

        Args:
            response_body: Raw response body bytes.
            url: Request URL.
            headers: Request headers.
            request_body: Raw request body bytes.
            status_code: HTTP status code.

        Returns:
            UsageData if parsing succeeded, None otherwise.
        """
        parser = self.detect(url, headers, request_body)
        if parser is None:
            return None

        try:
            return parser.parse_response(response_body, request_body, status_code)
        except Exception as e:
            logger.error(
                "Parser %s failed on response: %s",
                parser.provider_name,
                e,
                exc_info=True,
            )
            return None

    def parse_stream_chunk(
        self,
        chunk: dict[str, Any],
        url: str,
        headers: dict[str, str],
        request_body: bytes,
    ) -> UsageData | None:
        """Parse a stream chunk using the detected parser.

        Args:
            chunk: Parsed JSON chunk from SSE stream.
            url: Request URL.
            headers: Request headers.
            request_body: Raw request body bytes.

        Returns:
            UsageData if this chunk contains usage, None otherwise.
        """
        parser = self.detect(url, headers, request_body)
        if parser is None:
            return None

        try:
            return parser.parse_stream_chunk(chunk)
        except Exception as e:
            logger.debug("Stream chunk parse failed for %s: %s", parser.provider_name, e)
            return None
