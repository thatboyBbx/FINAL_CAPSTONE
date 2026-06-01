from __future__ import annotations

DEFAULT_LIMIT = 100
MAX_LIMIT = 500


def normalize_pagination(
    skip: int = 0,
    limit: int = DEFAULT_LIMIT,
    *,
    max_limit: int = MAX_LIMIT,
) -> tuple[int, int]:
    """Clamp offset pagination values to predictable, non-negative bounds."""
    safe_skip = max(skip or 0, 0)
    safe_limit = min(max(limit or DEFAULT_LIMIT, 1), max_limit)
    return safe_skip, safe_limit

