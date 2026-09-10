from __future__ import annotations


def normalize_database_url(url: str) -> str:
    value = (url or "").strip()
    if not value:
        return value

    replacements = (
        ("postgres://", "postgresql+asyncpg://"),
        ("postgresql://", "postgresql+asyncpg://"),
        ("postgresql+psycopg2://", "postgresql+asyncpg://"),
        ("postgresql+psycopg://", "postgresql+asyncpg://"),
        ("postgresql+asyncpg://", "postgresql+asyncpg://"),
    )
    for source, target in replacements:
        if value.startswith(source):
            return target + value[len(source):]
    return value
