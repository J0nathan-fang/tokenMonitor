"""
SSE (Server-Sent Events) handler.

Parses SSE streams, extracts usage from final chunks,
and relays data to the client without modification.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from src.parser.base import UsageData
from src.parser.registry import ParserRegistry

logger = logging.getLogger("token_monitor.proxy.sse_handler")


class SSEHandler:
    """Parses and relays SSE (Server-Sent Events) streams.

    While forwarding bytes to the client, this handler:
    1. Buffers and parses SSE data lines
    2. Detects usage data in stream chunks
    3. Returns the final accumulated usage after stream ends
    """

    def __init__(self, parser_registry: ParserRegistry) -> None:
        """Initialize the SSE handler.

        Args:
            parser_registry: Parser registry for provider detection.
        """
        self._registry = parser_registry

    async def process_stream(
        self,
        source: AsyncIterator[bytes],
        url: str,
        request_headers: dict[str, str],
        request_body: bytes,
    ) -> tuple[AsyncIterator[bytes], UsageData | None]:
        """Process an SSE stream, yielding relayed bytes and accumulating usage.

        Args:
            source: Async iterator of raw bytes from the API provider.
            url: The request URL (for parser detection).
            request_headers: Original request headers.
            request_body: Original request body bytes.

        Returns:
            Tuple of (async iterator yielding bytes to relay to client, accumulated UsageData or None).
        """
        # We use a queue-like pattern: generator yields bytes, final usage is collected
        return _SSERelayGenerator(
            source=source,
            registry=self._registry,
            url=url,
            request_headers=request_headers,
            request_body=request_body,
        ), None  # Usage extracted after iteration via .usage property


class _SSERelayGenerator:
    """Internal async generator that relays SSE bytes and captures usage."""

    def __init__(
        self,
        source: AsyncIterator[bytes],
        registry: ParserRegistry,
        url: str,
        request_headers: dict[str, str],
        request_body: bytes,
    ) -> None:
        self._source = source
        self._registry = registry
        self._url = url
        self._request_headers = request_headers
        self._request_body = request_body
        self._buffer = b""
        self._usage: UsageData | None = None
        self._done = False

    @property
    def usage(self) -> UsageData | None:
        """Get the accumulated usage after stream completes."""
        return self._usage

    def __aiter__(self):
        return self

    async def __anext__(self) -> bytes:
        if self._done:
            raise StopAsyncIteration

        try:
            chunk = await self._source.__anext__()
        except StopAsyncIteration:
            self._done = True
            # Process any remaining buffer
            self._process_buffer(final=True)
            raise StopAsyncIteration

        self._buffer += chunk
        self._process_buffer(final=False)
        return chunk

    def _process_buffer(self, final: bool = False) -> None:
        """Parse buffered SSE data looking for usage information.

        Args:
            final: True if this is the last processing call.
        """
        # SSE format: "data: <json>\n\n"
        # We look for complete events (ending with \n\n)
        while True:
            idx = self._buffer.find(b"\n\n")
            if idx == -1:
                if final and self._buffer.strip():
                    self._try_parse_line(self._buffer)
                    self._buffer = b""
                break

            event_data = self._buffer[:idx]
            self._buffer = self._buffer[idx + 2:]

            self._try_parse_event(event_data)

    def _try_parse_event(self, event_data: bytes) -> None:
        """Try to extract usage from an SSE event.

        Args:
            event_data: Raw bytes of one SSE event (without the trailing \n\n).
        """
        for line in event_data.split(b"\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith(b"data: "):
                data_str = line[6:]
                self._try_parse_line(data_str)
            elif line.startswith(b"data:"):
                data_str = line[5:]
                self._try_parse_line(data_str)

    def _try_parse_line(self, data: bytes) -> None:
        """Try to parse a data line as JSON and extract usage.

        Args:
            data: Raw bytes of a data line.
        """
        # Skip [DONE] marker
        if data.strip() == b"[DONE]":
            return

        try:
            chunk = json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

        if not isinstance(chunk, dict):
            return

        try:
            result = self._registry.parse_stream_chunk(
                chunk,
                self._url,
                self._request_headers,
                self._request_body,
            )
            if result and result.is_valid:
                self._usage = result
                logger.debug("SSE usage extracted: %s/%s tokens=%d",
                            result.provider, result.model, result.total_tokens)
        except Exception as e:
            logger.debug("Error parsing SSE chunk: %s", e)
