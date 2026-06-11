"""
Token counting fallback using tiktoken.

Used when API responses lack usage fields.
"""

import logging

logger = logging.getLogger("token_monitor.utils.token_counter")

# Lazy-loaded tiktoken encodings
_encodings: dict[str, object] = {}


def _get_encoding(model: str) -> object | None:
    """Get the appropriate tiktoken encoding for a model.

    Args:
        model: Model name (e.g., 'gpt-4', 'claude-sonnet-4-20250514').

    Returns:
        tiktoken.Encoding or None if model is unsupported.
    """
    try:
        import tiktoken
    except ImportError:
        logger.warning("tiktoken not installed, cannot count tokens")
        return None

    # OpenAI models use cl100k_base (GPT-4, GPT-3.5) or o200k_base (GPT-4o, o-series)
    model_lower = model.lower()

    if model_lower in _encodings:
        return _encodings[model_lower]

    encoding_name = "cl100k_base"  # default safe choice
    if any(x in model_lower for x in ("gpt-4o", "o1", "o3", "o4", "gpt-5")):
        encoding_name = "o200k_base"
    elif "gpt-3.5" in model_lower:
        encoding_name = "cl100k_base"

    try:
        enc = tiktoken.get_encoding(encoding_name)
    except Exception:
        try:
            enc = tiktoken.get_encoding("cl100k_base")
        except Exception:
            logger.warning("Cannot load tiktoken encoding for %s", model)
            return None

    _encodings[model_lower] = enc
    return enc


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count tokens in text using tiktoken.

    Args:
        text: The text to count tokens for.
        model: Model name to select the appropriate encoding.

    Returns:
        Token count, or 0 if counting fails.
    """
    if not text:
        return 0

    enc = _get_encoding(model)
    if enc is None:
        return 0

    try:
        return len(enc.encode(text))
    except Exception as e:
        logger.debug("Token count failed for model %s: %s", model, e)
        return 0


def estimate_tokens(text: str) -> int:
    """Quick token estimate: ~4 chars per token for English text.

    Used as a last-resort fallback when tiktoken is unavailable.

    Args:
        text: The text to estimate tokens for.

    Returns:
        Estimated token count.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)
