"""Notification on booking outcome — console + optional webhook/log.

Spec safeguard: \"notification on success/failure\". Minimal implementation:
- always logs structured JSON to stderr (visible in timer logs)
- if HOLMES_NOTIFY_URL is set (or --notify-url), POSTs JSON payload
- if HOLMES_NOTIFY_LOG is set, appends JSON line to that file
All failures in notify are swallowed — booking result is never lost due to notify.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)


def _payload(
    status: str,
    lesson: dict[str, Any] | None = None,
    seat: int | None = None,
    message: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "seat": seat,
        "message": message,
        "lesson": lesson or {},
        **(extra or {}),
    }


def notify(
    status: str,
    lesson: dict[str, Any] | None = None,
    seat: int | None = None,
    message: str = "",
    notify_url: str | None = None,
    notify_log: str | Path | None = None,
) -> None:
    """Send notification via webhook and/or log file; always safe to call."""
    url = notify_url or os.getenv("HOLMES_NOTIFY_URL", "").strip()
    log_path = notify_log or os.getenv("HOLMES_NOTIFY_LOG", "").strip()
    payload = _payload(status, lesson, seat, message)
    # webhook
    if url:
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            logger.warning("notify webhook failed (%s): %s", url, e)
    # log file
    if log_path:
        try:
            p = Path(log_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("notify log failed (%s): %s", log_path, e)
