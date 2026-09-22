"""Rough token estimates. Prefer tiktoken if installed; else chars/4."""

from __future__ import annotations

_ENCODING = None
_METHOD = None


def token_method() -> str:
    global _METHOD
    if _METHOD is None:
        try:
            import tiktoken  # noqa: F401

            _METHOD = "tiktoken(cl100k_base)"
        except ImportError:
            _METHOD = "chars/4"
    return _METHOD


def count_tokens(text: str) -> int:
    global _ENCODING
    if not text:
        return 0
    try:
        import tiktoken

        if _ENCODING is None:
            _ENCODING = tiktoken.get_encoding("cl100k_base")
        return len(_ENCODING.encode(text))
    except Exception:
        return max(1, len(text) // 4) if text else 0
