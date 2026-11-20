"""Apply safe, repeatable input normalization."""


def normalize_line(value: str) -> str:
    """Remove UTF-8 BOM and surrounding whitespace. Preserve URI semantics."""
    return value.lstrip("\ufeff").strip()
