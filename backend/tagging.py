"""Tag normalization and filtering helpers."""

from __future__ import annotations


RESERVED_ROLE_TAGS = {"manager", "coder", "analyzer"}


def sanitize_tags(tags: list[str] | None) -> list[str]:
    """Normalize tags and remove reserved orchestration role tags."""
    if not tags:
        return []

    cleaned: list[str] = []
    seen: set[str] = set()

    for tag in tags:
        normalized = (tag or "").strip().lstrip("#")
        if not normalized:
            continue

        normalized_lower = normalized.lower()
        if normalized_lower in RESERVED_ROLE_TAGS:
            continue

        if normalized_lower in seen:
            continue

        seen.add(normalized_lower)
        cleaned.append(normalized)

    return cleaned
