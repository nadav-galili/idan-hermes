"""Booking & discovery tests — mocked client, no real HTTP."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, call, patch

import requests

from holmes_place.booking import LessonKey, book, discover
from holmes_place.config import Settings
from holmes_place.client import HolmesPlaceClient
from holmes_place.errors import AlreadyRegisteredError, BikeOccupiedError, LessonNotOpenError


def _client_with_mocks():
    c = HolmesPlaceClient(Settings(base_url="https://example.com"))
    return c


def test_discover_returns_seats():
    c = _client_with_mocks()
    c.get_available_seats = MagicMock(return_value=[1, 5, 9])  # type: ignore[method-assign]
    res = discover(c, branch_id="205", lesson_id="123", date="2026/09/10", time_str="18:00")
    assert res["available_seats"] == [1, 5, 9]
    assert res["count"] == 3


def test_book_dry_run_does_not_register():
    c = _client_with_mocks()
    c.get_available_seats = MagicMock(return_value=[1, 2])  # type: ignore[method-assign]
    c.register_with_seat = MagicMock()  # type: ignore[method-assign]
    res = book(
        c,
        LessonKey(branch_id="205", lesson_id="123", date="2026/09/10", time="18:00", instructor_id="7"),
        dry_run=True,
    )
    assert res.status == "dry_run"
    c.register_with_seat.assert_not_called()


def test_book_idempotent_already_registered():
    c = _client_with_mocks()
    c.get_available_seats = MagicMock(return_value=[12, 13])  # type: ignore[method-assign]
    c.register_with_seat = MagicMock(side_effect=AlreadyRegisteredError("already (32)"))  # type: ignore[method-assign]
    res = book(
        c,
        LessonKey(branch_id="205", lesson_id="123", date="2026/09/10", time="18:00", instructor_id="7"),
        seat_preferences=[12],
        max_wait_s=2,
    )
    assert res.status == "already_registered"


def test_book_prefers_preferred_seat_then_fallback():
    c = _client_with_mocks()
    # available seats include 12 (preferred) and 5
    c.get_available_seats = MagicMock(return_value=[5, 12])  # type: ignore[method-assign]

    def reg(**kwargs):
        if kwargs.get("seat_id") == 12:
            raise BikeOccupiedError("bike (33)")
        return MagicMock()

    c.register_with_seat = MagicMock(side_effect=reg)  # type: ignore[method-assign]

    # patch sleep to avoid real delay
    with patch("holmes_place.booking.time.sleep"):
        with patch("holmes_place.booking.single_stream_lock"):
            # need to bypass file lock for test; patch yields
            res = book(
                c,
                LessonKey(branch_id="205", lesson_id="123", date="2026/09/10", time="18:00", instructor_id="7"),
                seat_preferences=[12],
                max_wait_s=3,
                poll_interval_s=0,
                allow_random_fallback=True,
            )
    # should fallback to 5 and succeed
    assert res.status == "booked"
    assert res.seat == 5


def test_book_waits_on_not_open_then_books():
    c = _client_with_mocks()
    # first call raises LessonNotOpenError, second returns seats
    c.get_available_seats = MagicMock(side_effect=[LessonNotOpenError("not open (50)"), [8]])  # type: ignore[method-assign]
    c.register_with_seat = MagicMock(return_value=MagicMock())  # type: ignore[method-assign]
    with patch("holmes_place.booking.time.sleep"):
        with patch("holmes_place.booking.single_stream_lock"):
            res = book(
                c,
                LessonKey(branch_id="205", lesson_id="123", date="2026/09/10", time="18:00", instructor_id="7"),
                seat_preferences=[8],
                max_wait_s=3,
                poll_interval_s=0,
            )
    assert res.status == "booked"
    assert res.seat == 8


def test_book_single_stream_lock_blocks_second_stream():
    from holmes_place.booking import single_stream_lock
    import tempfile
    from pathlib import Path

    # use a temp lock file so we don't interfere with real /tmp lock
    with tempfile.TemporaryDirectory() as td:
        lock = Path(td) / "lock"
        # first lock held
        with single_stream_lock(lock):
            # second attempt should raise
            try:
                with single_stream_lock(lock):
                    assert False, "should have raised"
            except RuntimeError as e:
                assert "another booking" in str(e)


def test_member_lock_path_is_per_member():
    from holmes_place.booking import member_lock_path

    a = member_lock_path("0541234567")
    b = member_lock_path("0549999999")
    assert a != b
    assert "0541234567" in str(a)
    assert a.parent == b.parent


def test_book_uses_per_member_lock(monkeypatch):
    from holmes_place.booking import book, member_lock_path

    c = _client_with_mocks()
    c.get_available_seats = MagicMock(return_value=[1])  # type: ignore[method-assign]
    c.register_with_seat = MagicMock(return_value=MagicMock())  # type: ignore[method-assign]
    # patch drift + sleep + lock to capture lock path
    with patch("holmes_place.booking.check_clock_drift", return_value=None):
        with patch("holmes_place.booking.time.sleep"):
            with patch("holmes_place.booking.single_stream_lock") as mock_lock:
                mock_lock.return_value.__enter__ = MagicMock(return_value=None)
                mock_lock.return_value.__exit__ = MagicMock(return_value=False)
                res = book(
                    c,
                    LessonKey(branch_id="205", lesson_id="123", date="2026/09/10", time="18:00", instructor_id="7"),
                    seat_preferences=[1],
                    max_wait_s=2,
                    poll_interval_s=0,
                    member_id="0541234567",
                )
                assert res.status == "booked"
                # lock was called with per-member path
                called_path = mock_lock.call_args[0][0]
                assert called_path == member_lock_path("0541234567")
