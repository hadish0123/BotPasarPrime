from __future__ import annotations


def central_bot_enabled(value: object = True) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
