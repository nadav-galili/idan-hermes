"""Config-driven discovery — validates holmes_lessons.yaml entries against live api.php.

No server-side catalog endpoint was found (probed api.php?action=getClubs etc.
on 2026-09-10 — only login/getAvailableSeats/register* return JSON; others
429/302). So discovery is **allow-list validation**: given the member's YAML,
probe each lesson via getAvailableSeats and report seat behavior + opening time.

Opening timestamp is derived from the YAML's registration_day/registration_start_time
fields (same as reference impl) and computed to the next occurrence in Asia/Jerusalem.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from holmes_place.client import HolmesPlaceClient
from holmes_place.config import JERUSALEM_TZ
from holmes_place.errors import HolmesPlaceError

logger = logging.getLogger(__name__)

# holmes_lessons.yaml mapping: day string -> weekday number (Mon=0)
WEEKDAY_MAP: dict[str, int] = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


@dataclass(frozen=True)
class LessonConfig:
    branch_id: str
    lesson_id: str
    instructor_id: str
    type: str
    day: str
    start_time: str  # "7:30" or "18:00"
    registration_day: str
    registration_start_time: str


def _parse_hhmm(s: str) -> tuple[int, int]:
    parts = s.strip().split(":")
    return int(parts[0]), int(parts[1]) if len(parts) > 1 else 0


def next_registration_time(
    registration_day: str,
    registration_start_time: str,
    now: datetime | None = None,
) -> datetime:
    """Compute next registration datetime from registration_day/time in Asia/Jerusalem."""
    if now is None:
        now = datetime.now(tz=JERUSALEM_TZ)
    target_wd = WEEKDAY_MAP[registration_day.lower()]
    h, m = _parse_hhmm(registration_start_time)
    # candidate = next occurrence of registration_day at h:m
    days_ahead = (target_wd - now.weekday()) % 7
    cand = now.replace(hour=h, minute=m, second=0, microsecond=0) + timedelta(days=days_ahead)
    # if same day but time already passed, go +7 days
    if cand <= now:
        cand = cand + timedelta(days=7)
    return cand


def load_lessons_config(path: str | Path) -> list[LessonConfig]:
    """Load holmes_lessons.yaml (reference format: clubs: {branch: {type: [lesson...]}})."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"config not found: {p}")
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as e:
        raise ImportError("PyYAML required: pip install pyyaml") from e
    data: Any = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "clubs" not in data:
        raise ValueError(f"bad config shape: top-level 'clubs' missing in {p}")
    out: list[LessonConfig] = []
    clubs = data["clubs"] or {}
    for branch_id, types in clubs.items():
        if not isinstance(types, dict):
            continue
        for lesson_type, lessons in types.items():
            if not isinstance(lessons, list):
                continue
            for entry in lessons:
                if not isinstance(entry, dict):
                    continue
                out.append(
                    LessonConfig(
                        branch_id=str(branch_id),
                        lesson_id=str(entry.get("lesson_id", "")),
                        instructor_id=str(entry.get("instructor_id", "")),
                        type=str(entry.get("type", lesson_type)),
                        day=str(entry.get("day", "")),
                        start_time=str(entry.get("start_time", "")),
                        registration_day=str(entry.get("registration_day", "")),
                        registration_start_time=str(entry.get("registration_start_time", "")),
                    )
                )
    return out


@dataclass
class LessonValidation:
    lesson: LessonConfig
    target_date: str  # YYYY/MM/DD derived from lesson day
    target_time: str
    available_seats: list[int] | None
    error: str | None
    seat_behavior: str  # "seats" | "no_seats" | "unknown" | "error"
    next_registration: datetime | None
    raw_response: str | None = None


def _date_for_lesson_day(day: str, now: datetime | None = None) -> str:
    """Next occurrence of lesson `day` as YYYY/MM/DD in Asia/Jerusalem."""
    if now is None:
        now = datetime.now(tz=JERUSALEM_TZ)
    target_wd = WEEKDAY_MAP.get(day.lower())
    if target_wd is None:
        # unknown day — just use today
        return now.strftime("%Y/%m/%d")
    days_ahead = (target_wd - now.weekday()) % 7
    # if today is the lesson day, use today (so getAvailableSeats can be probed for upcoming instance)
    # caller can override by passing explicit date; this is just for catalog sweep
    cand = now + timedelta(days=days_ahead)
    return cand.strftime("%Y/%m/%d")


def validate_catalog(
    client: HolmesPlaceClient,
    lessons: list[LessonConfig],
    branch_filter: str | None = None,
    now: datetime | None = None,
    sleep_s: float = 1.0,
) -> list[LessonValidation]:
    """Probe each lesson via getAvailableSeats — read-only, no booking.

    sleep_s throttles to ~1 req/s to stay under Cloudflare 429 (seen after 3
    rapid unauth probes on 2026-09-10).
    """
    if now is None:
        now = datetime.now(tz=JERUSALEM_TZ)
    filtered = [l for l in lessons if not branch_filter or l.branch_id == branch_filter]
    results: list[LessonValidation] = []
    for idx, lesson in enumerate(filtered):
        target_date = _date_for_lesson_day(lesson.day, now=now)
        # normalize time to HH:MM with zero pad
        try:
            h, m = _parse_hhmm(lesson.start_time)
            target_time = f"{h:02d}:{m:02d}"
        except Exception:
            target_time = lesson.start_time
        next_reg: datetime | None = None
        if lesson.registration_day and lesson.registration_start_time:
            try:
                next_reg = next_registration_time(
                    lesson.registration_day, lesson.registration_start_time, now=now
                )
            except Exception:
                next_reg = None
        seats: list[int] | None = None
        err: str | None = None
        behavior = "unknown"
        raw: str | None = None
        try:
            seats = client.get_available_seats(
                branch_id=lesson.branch_id,
                lesson_id=lesson.lesson_id,
                date=target_date,
                time=target_time,
            )
            if seats:
                behavior = "seats"
            else:
                behavior = "no_seats"
        except HolmesPlaceError as e:
            err = f"{type(e).__name__}: {e}"
            raw = str(e)
            behavior = "error"
            # map known error semantics
            name = type(e).__name__
            if "LessonTimeNotFound" in name or "LessonNotFound" in name:
                behavior = "error: lesson/time not found — check branch/lesson/instructor"
            elif "NoAvailableSeats" in name:
                behavior = "no_seats"
            elif "LessonNotOpen" in name:
                behavior = "seats: not open yet (retry near registration time)"
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            behavior = "error"
        results.append(
            LessonValidation(
                lesson=lesson,
                target_date=target_date,
                target_time=target_time,
                available_seats=seats,
                error=err,
                seat_behavior=behavior,
                next_registration=next_reg,
                raw_response=raw,
            )
        )
        # throttle between probes (skip after last)
        if sleep_s > 0 and idx < len(filtered) - 1:
            import time as _time

            _time.sleep(sleep_s)
    return results


def discovery_summary(results: list[LessonValidation]) -> dict[str, object]:
    """Summarize catalog validation for CLI output."""
    total = len(results)
    by_behavior: dict[str, int] = {}
    for r in results:
        by_behavior[r.seat_behavior] = by_behavior.get(r.seat_behavior, 0) + 1
    branches = sorted({r.lesson.branch_id for r in results})
    lesson_ids = sorted({r.lesson.lesson_id for r in results})
    return {
        "total": total,
        "branches": branches,
        "lesson_ids": lesson_ids,
        "by_behavior": by_behavior,
        # note that no server catalog endpoint exists — this is config validation
        "note": "no server-side catalog endpoint found; this is allow-list validation via getAvailableSeats (probed 2026-09-10)",
    }
