"""Endpoints, timezone, and runtime config."""

from __future__ import annotations

import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo

DEFAULT_BASE_URL = "https://www.holmesplace.co.il"
JERUSALEM_TZ = ZoneInfo("Asia/Jerusalem")

ENDPOINTS: dict[str, str] = {
    "login": "{base_url}/api.php?action=login",
    "logout": "{base_url}/api.php?action=logout",
    "available_seats": "{base_url}/api.php?action=getAvailableSeats",
    "register": "{base_url}/api.php?action=register",
    "register_to_lesson": "{base_url}/api.php?action=registerToLesson",
    "register_to_lesson_with_seat": "{base_url}/api.php?action=registerToLessonWithSeat",
    "unregister": "{base_url}/api.php?action=unRegisterToLesson",
}


@dataclass(frozen=True)
class Settings:
    base_url: str = DEFAULT_BASE_URL
    kill_switch: bool = False

    @staticmethod
    def from_env() -> Settings:
        base_url = os.getenv("HOLMES_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
        kill = os.getenv("HOLMES_KILL_SWITCH", "0").lower() in ("1", "true", "yes")
        return Settings(base_url=base_url, kill_switch=kill)

    def endpoint(self, name: str) -> str:
        tmpl = ENDPOINTS[name]
        return tmpl.format(base_url=self.base_url)
