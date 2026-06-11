"""
Cost calculator — computes cost based on model pricing and token counts.

Prices are per 1M tokens. Cache tokens have separate pricing where applicable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.database.repository import Repository

logger = logging.getLogger("token_monitor.statistics.calculator")


@dataclass
class CostResult:
    """Result of cost calculation."""

    input_cost: float
    output_cost: float
    cache_read_cost: float
    cache_write_cost: float
    total_cost: float
    currency: str = "USD"


class CostCalculator:
    """Calculates costs based on token usage and model pricing.

    Pricing is stored in model_configs table (input_price/output_price per 1M tokens).
    """

    def __init__(self, repository: Repository) -> None:
        """Initialize with a repository for model price lookup.

        Args:
            repository: Repository instance for database queries.
        """
        self._repository = repository
        self._price_cache: dict[str, dict[str, Any]] = {}
        self._refresh_cache()

    def _refresh_cache(self) -> None:
        """Refresh the in-memory price cache from the database."""
        models = self._repository.get_enabled_models()
        self._price_cache = {}
        for m in models:
            key = m["model_name"]
            self._price_cache[key] = m
        logger.debug("Price cache refreshed: %d models", len(self._price_cache))

    def _get_prices(self, model: str) -> dict[str, Any]:
        """Get pricing info for a model.

        Args:
            model: Model name.

        Returns:
            Dict with input_price, output_price, cache_read_price, cache_write_price, currency.
            Defaults to zeros if model not found.
        """
        # Exact match
        if model in self._price_cache:
            return self._price_cache[model]

        # Prefix match
        for cached_model, prices in self._price_cache.items():
            if model.startswith(cached_model):
                return prices

        # Try DB lookup (handles new models seen first time)
        db_model = self._repository.get_model_price(model)
        if db_model:
            self._price_cache[model] = db_model
            return db_model

        logger.debug("No pricing found for model: %s, using zero", model)
        return {
            "input_price": 0.0,
            "output_price": 0.0,
            "cache_read_price": 0.0,
            "cache_write_price": 0.0,
            "currency": "USD",
        }

    def calculate(
        self,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
    ) -> CostResult:
        """Calculate cost for a single request.

        Args:
            model: Model name.
            input_tokens: Number of input/prompt tokens.
            output_tokens: Number of output/completion tokens.
            cache_read_tokens: Number of cache read tokens (Anthropic).
            cache_write_tokens: Number of cache write tokens (Anthropic).

        Returns:
            CostResult with detailed cost breakdown.
        """
        prices = self._get_prices(model)
        currency = prices.get("currency", "USD")

        # Prices are per 1M tokens
        input_price_per_token = prices.get("input_price", 0.0) / 1_000_000
        output_price_per_token = prices.get("output_price", 0.0) / 1_000_000
        cache_read_price_per_token = prices.get("cache_read_price", 0.0) / 1_000_000
        cache_write_price_per_token = prices.get("cache_write_price", 0.0) / 1_000_000

        input_cost = input_tokens * input_price_per_token
        output_cost = output_tokens * output_price_per_token
        cache_read_cost = cache_read_tokens * cache_read_price_per_token
        cache_write_cost = cache_write_tokens * cache_write_price_per_token

        # For Anthropic: cache reads/writes replace (not add to) the base input price
        # The base input price applies to non-cached input tokens
        # We use the cache pricing for cached tokens instead of base pricing
        total_cost = input_cost + output_cost + cache_read_cost + cache_write_cost

        return CostResult(
            input_cost=input_cost,
            output_cost=output_cost,
            cache_read_cost=cache_read_cost,
            cache_write_cost=cache_write_cost,
            total_cost=round(total_cost, 8),
            currency=currency,
        )

    def refresh(self) -> None:
        """Force refresh of the price cache."""
        self._refresh_cache()

    @property
    def known_models(self) -> list[str]:
        """Get list of models with known pricing."""
        return list(self._price_cache.keys())
