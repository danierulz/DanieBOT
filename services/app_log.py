"""Structured JSON logs for Cloud Logging / Log Explorer."""

from __future__ import annotations

import json
import logging
import os
from typing import Any


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    payload: dict[str, Any] = {
        "severity": "INFO",
        "event": event,
        "message": event,
        "logger": logger.name,
    }
    for key, value in fields.items():
        if value is not None:
            payload[key] = value
    line = json.dumps(payload, ensure_ascii=False, default=str)
    # Cloud Run parses a raw JSON stdout line into jsonPayload.event=...
    if os.environ.get("K_SERVICE"):
        print(line, flush=True)
    else:
        logger.info(line)
