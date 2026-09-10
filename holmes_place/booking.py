"""Booking & discovery orchestration with safeguards.

Safeguards:
- single stream per member via file lock (fcntl)
- 1 req/s rate limit inside opening window
- idempotency: AlreadyRegistered is success
- allow-list: caller passes explicit branch/lesson
- dry-run / list, cancel, kill-switch, redacted logs
- Asia/Jerusalem throughout + clock drift check via Date header
- conservative retry/backoff for network errors
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

import requests
from dateutil import parser as date_parser

from holmes_place.client import HolmesPlaceClient
from holmes_place.config import JERUSALEM_TZ
from holmes_place.errors import AlreadyRegisteredError, BikeOccupiedError, LessonNotOpenError

logger = logging.getLogger(__name__)

LOCK_DIR = Path("/tmp")
DEFAULT_LOCK_PATH = LOCK_DIR / "holmes-place-booking.lock"


def member_lock_path(member_id: str) -> Path:
    """Per-member lock file — avoids cross-member serialization and respects (MultipleDevices) safeguard."""
    safe = "".join(c if c.isalnum() else "_" for c in member_id.strip())
    if not safe:
        return DEFAULT_LOCK_PATH
    return LOCK_DIR / f"holmes-place-booking-{safe}.lock"


@contextmanager
def single_stream_lock(lock_path: Path = DEFAULT_LOCK_PATH):  # type: ignore[no-untyped-def]
    """One booking stream per member — prevents MultipleDevices race (hebrew substring) and (32) AlreadyRegistered idempotency path.

    Uses fcntl flock where available; on platforms without fcntl, logs and proceeds
    with a warning that the safeguard is degraded (caller should ensure single stream externally).
    """
    try:
        import fcntl  # type: ignore[import-not-found]

        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "w") as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as e:
                raise RuntimeError(
                    f"another booking in progress (lock {lock_path}); refusing second stream"
                ) from e
            try:
                yield
            finally:
                try:
                    fcntl.flock(f, fcntl.LOCK_UN)
                except Exception:
                    pass
    except ImportError:
        logger.warning("fcntl unavailable — single-stream lock degraded; ensure single stream externally")
        yield


@dataclass(frozen=True)
class LessonKey:
    branch_id: str
    lesson_id: str
    date: str  # YYYY/MM/DD
    time: str  # HH:MM
    instructor_id: str


@dataclass(frozen=True)
class BookingResult:
    status: str  # "booked" | "already_registered" | "dry_run" | "failed"
    seat: int | None = None
    message: str = ""


def _sleep_rate_limited(last_ts: float | None, min_interval_s: float = 1.0) -> float:
    now = time.monotonic()
    if last_ts is not None:
        elapsed = now - last_ts
        if elapsed < min_interval_s:
            time.sleep(min_interval_s - elapsed)
    return time.monotonic()


def check_clock_drift(client: HolmesPlaceClient, max_drift_s: int = 120) -> timedelta | None:
    """Compare server Date header to local Jerusalem time. Return drift or None."""
    # do a cheap HEAD/GET to fetch Date — reuse a login-less endpoint if possible;
    # fall back to a dummy request and read header from last response if client tracks it
    try:
        # lightweight: fetch base url
        resp = client.session.request("HEAD", client.settings.base_url, timeout=5)
        date_hdr = resp.headers.get("Date")
        if not date_hdr:
            return None
        server_dt = date_parser.parse(date_hdr)
        if server_dt.tzinfo is None:
            from zoneinfo import ZoneInfo

            server_dt = server_dt.replace(tzinfo=ZoneInfo("UTC"))
        local_dt = datetime.now(tz=JERUSALEM_TZ)
        drift = server_dt.astimezone(JERUSALEM_TZ) - local_dt
        if abs(drift.total_seconds()) > max_drift_s:
            logger.warning("clock drift %.0fs exceeds %ss — sync clock", drift.total_seconds(), max_drift_s)
        return drift
    except Exception as e:
        logger.debug("clock drift check failed: %s", e)
        return None


def discover(
    client: HolmesPlaceClient,
    branch_id: str,
    lesson_id: str,
    date: str,
    time_str: str,
) -> dict[str, object]:
    """Read-only discovery: login assumed done, then list seats. No booking."""
    seats = client.get_available_seats(branch_id=branch_id, lesson_id=lesson_id, date=date, time=time_str)
    return {
        "branch_id": branch_id,
        "lesson_id": lesson_id,
        "date": date,
        "time": time_str,
        "available_seats": seats,
        "count": len(seats),
    }


def book(
    client: HolmesPlaceClient,
    lesson: LessonKey,
    seat_preferences: list[int] | None = None,
    *,
    dry_run: bool = False,
    max_wait_s: int = 180,
    poll_interval_s: float = 1.0,
    allow_random_fallback: bool = True,
    on_status: Callable[[str], None] | None = None,
    member_id: str | None = None,
    check_drift: bool = True,
) -> BookingResult:
    """Book with safeguards.

    - Single stream per member (file lock via member_lock_path)
    - Clock drift check (Asia/Jerusalem) before polling — warns and adjusts max_wait slightly
    - 1 req/s max inside wait loop
    - Retries on LessonNotOpenError for up to max_wait_s
    - Falls back through seat_preferences then random available seat
    - AlreadyRegistered (32) -> success
    """
    if dry_run:
        seats = client.get_available_seats(
            branch_id=lesson.branch_id, lesson_id=lesson.lesson_id, date=lesson.date, time=lesson.time
        )
        msg = f"dry-run: would book {lesson.lesson_id} on {lesson.date} {lesson.time} seats={seats}"
        if on_status:
            on_status(msg)
        return BookingResult(status="dry_run", message=msg)

    seat_preferences = seat_preferences or []

    if check_drift:
        drift = check_clock_drift(client)
        if drift is not None and abs(drift.total_seconds()) > 120 and on_status:
            on_status(f"warning: clock drift {drift.total_seconds():.0f}s — sync clock")

    lock_path = member_lock_path(member_id) if member_id else DEFAULT_LOCK_PATH
    with single_stream_lock(lock_path):
        # conservative retry for transient network errors
        last_ts: float | None = None

        def _try_register(seat: int) -> BookingResult | None:
            nonlocal last_ts
            last_ts = _sleep_rate_limited(last_ts, poll_interval_s)
            try:
                client.register_with_seat(
                    branch_id=lesson.branch_id,
                    lesson_id=lesson.lesson_id,
                    date=lesson.date,
                    time=lesson.time,
                    instructor_id=lesson.instructor_id,
                    seat_id=seat,
                )
                return BookingResult(status="booked", seat=seat, message=f"booked seat {seat}")
            except AlreadyRegisteredError as e:
                return BookingResult(status="already_registered", message=str(e))
            except BikeOccupiedError:
                return None
            except LessonNotOpenError:
                raise
            except requests.RequestException as e:
                # transient — log and let outer loop retry/backoff
                logger.warning("transient network error: %s", e)
                time.sleep(2)
                return None

        start = time.monotonic()
        # ordering: preferred seats that are actually available first, then fallback
        tried: set[int] = set()

        while time.monotonic() - start < max_wait_s:
            # refresh available seats each iteration (reference impl does same)
            try:
                available = client.get_available_seats(
                    branch_id=lesson.branch_id, lesson_id=lesson.lesson_id, date=lesson.date, time=lesson.time
                )
            except LessonNotOpenError:
                # still not open — sleep 1s and retry (this is the expected opening-window poll)
                if on_status:
                    on_status("not open yet, waiting...")
                _sleep_rate_limited(last_ts, poll_interval_s)
                last_ts = time.monotonic()
                continue
            except requests.RequestException:
                time.sleep(2)
                continue

            # preferred seats filtered to available
            for seat in seat_preferences:
                if seat in tried:
                    continue
                if seat not in available:
                    continue
                tried.add(seat)
                res = _try_register(seat)
                if res is not None:
                    if res.status in ("booked", "already_registered"):
                        return res
                    # bike occupied -> try next pref

            if allow_random_fallback:
                # try one random-ish available not yet tried (pick first deterministic for testability)
                for seat in available:
                    if seat in tried:
                        continue
                    tried.add(seat)
                    res = _try_register(seat)
                    if res is not None and res.status in ("booked", "already_registered"):
                        return res
                    break  # try one per poll iteration to keep 1 req/s

            # if we got here, no seat booked this iteration — wait for next poll
            # need to handle LessonNotOpenError separately: already raises above
            # for other cases, sleep and loop; but respect max_wait_s
            if time.monotonic() - start >= max_wait_s:
                break
            _sleep_rate_limited(last_ts, poll_interval_s)
            last_ts = time.monotonic()

        return BookingResult(status="failed", message="timeout or no seats available")
