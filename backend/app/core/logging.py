from __future__ import annotations

import json
import logging
from datetime import UTC, datetime


class KeyValueFormatter(logging.Formatter):
    """Small structured formatter suited for academic backend logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        context = getattr(record, "context", None)
        if isinstance(context, dict):
            payload.update(context)
        return " ".join(
            f"{key}={json.dumps(value, ensure_ascii=False)}"
            for key, value in payload.items()
        )


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(KeyValueFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
