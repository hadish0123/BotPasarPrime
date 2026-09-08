from __future__ import annotations

import logging

from app.security.security_contract import sanitize_mapping


class SecurityLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        if isinstance(msg, dict):
            msg = sanitize_mapping(msg)
        return msg, kwargs


def get_security_logger() -> SecurityLoggerAdapter:
    logger = logging.getLogger("3xshop.security")
    return SecurityLoggerAdapter(logger, {})
