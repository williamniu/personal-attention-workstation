from __future__ import annotations

import json
import logging

REDACTED_KEYS = {"password", "cookie", "authorization", "api_token", "body"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extras = getattr(record, "structured", {})
        payload["structured"] = {
            key: "[REDACTED]" if key.lower() in REDACTED_KEYS else value
            for key, value in extras.items()
        }
        return json.dumps(payload, default=str)
