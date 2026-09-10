"""Tests for config-driven discovery (catalog)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from holmes_place.catalog import (
    LessonConfig,
    load_lessons_config,
    next_registration_time,
    validate_catalog,
    discovery_summary,
)
from holmes_place.config import JERUSALEM_TZ
from holmes_place.errors import LessonTimeNotFoundError


def test_next_registration_time():
    # Mon 2026-09-07 10:00 Jerusalem, registration is Monday 08:30
    # next Monday 08:30 is 2026-09-14 08:30 (since today 10:00 already past)
    now = datetime(2026, 9, 7, 10, 0, tzinfo=JERUSALEM_TZ)  # Monday
    nxt = next_registration_time("monday", "08:30", now=now)
    assert nxt.weekday() == 0
    assert nxt.day == 14
    assert nxt.hour == 8 and nxt.minute == 30

    # If now is Friday 07:00 and registration is Friday 07:30, next is today 07:30
    now2 = datetime(2026, 9, 11, 7, 0, tzinfo=JERUSALEM_TZ)  # Friday
    nxt2 = next_registration_time("friday", "07:30", now=now2)
    assert nxt2.day == 11 and nxt2.hour == 7 and nxt2.minute == 30

    # Same day but time passed -> next week
    now3 = datetime(2026, 9, 11, 8, 0, tzinfo=JERUSALEM_TZ)
    nxt3 = next_registration_time("friday", "07:30", now=now3)
    assert nxt3.day == 18


def test_load_lessons_config(tmp_path: Path):
    yaml_text = """
clubs:
  205:
    pilates:
      - day: monday
        type: pilates
        start_time: '8:30'
        registration_day: sunday
        registration_start_time: '8:30'
        lesson_id: '10440'
        instructor_id: '27'
    yoga:
      - day: tuesday
        type: yoga
        start_time: '9:30'
        registration_day: monday
        registration_start_time: '9:30'
        lesson_id: '10051'
        instructor_id: '50'
"""
    p = tmp_path / "holmes_lessons.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    lessons = load_lessons_config(p)
    assert len(lessons) == 2
    assert lessons[0].branch_id == "205"
    assert lessons[0].lesson_id == "10440"
    assert lessons[0].type == "pilates"
    assert lessons[1].lesson_id == "10051"


def test_validate_catalog_success_and_error():
    from holmes_place.client import HolmesPlaceClient
    from holmes_place.config import Settings

    c = HolmesPlaceClient(Settings(base_url="https://example.com"))
    lessons = [
        LessonConfig(
            branch_id="205",
            lesson_id="10440",
            instructor_id="27",
            type="pilates",
            day="monday",
            start_time="8:30",
            registration_day="sunday",
            registration_start_time="08:30",
        ),
        LessonConfig(
            branch_id="205",
            lesson_id="99999",
            instructor_id="1",
            type="spinning",
            day="tuesday",
            start_time="19:00",
            registration_day="tuesday",
            registration_start_time="17:00",
        ),
    ]

    def fake_get(branch_id, lesson_id, date, time):
        if lesson_id == "10440":
            return [1, 5, 10]
        raise LessonTimeNotFoundError("(30) not found")

    c.get_available_seats = MagicMock(side_effect=fake_get)  # type: ignore[method-assign]
    now = datetime(2026, 9, 7, 6, 0, tzinfo=JERUSALEM_TZ)
    results = validate_catalog(c, lessons, now=now, sleep_s=0)
    assert len(results) == 2
    assert results[0].available_seats == [1, 5, 10]
    assert results[0].seat_behavior == "seats"
    assert results[0].next_registration is not None
    assert results[1].error is not None
    assert "LessonTimeNotFound" in results[1].error
    assert results[1].available_seats is None


def test_validate_catalog_branch_filter():
    from holmes_place.client import HolmesPlaceClient
    from holmes_place.config import Settings

    c = HolmesPlaceClient(Settings(base_url="https://example.com"))
    lessons = [
        LessonConfig("205", "1", "7", "pilates", "monday", "8:30", "sunday", "08:30"),
        LessonConfig("999", "2", "7", "pilates", "monday", "8:30", "sunday", "08:30"),
    ]
    c.get_available_seats = MagicMock(return_value=[1])  # type: ignore[method-assign]
    now = datetime(2026, 9, 7, 6, 0, tzinfo=JERUSALEM_TZ)
    results = validate_catalog(c, lessons, branch_filter="205", now=now, sleep_s=0)
    assert len(results) == 1
    assert results[0].lesson.branch_id == "205"


def test_discovery_summary():
    now = datetime(2026, 9, 7, 6, 0, tzinfo=JERUSALEM_TZ)
    lessons = [
        LessonConfig("205", "1", "7", "pilates", "monday", "8:30", "sunday", "08:30"),
        LessonConfig("205", "2", "7", "yoga", "tuesday", "8:30", "monday", "08:30"),
    ]
    from holmes_place.client import HolmesPlaceClient
    from holmes_place.config import Settings

    c = HolmesPlaceClient(Settings(base_url="https://example.com"))
    c.get_available_seats = MagicMock(return_value=[])  # type: ignore[method-assign]
    results = validate_catalog(c, lessons, now=now, sleep_s=0)
    summ = discovery_summary(results)
    assert summ["total"] == 2
    assert "205" in summ["branches"]  # type: ignore[operator]
    assert "note" in summ


def test_cli_discover_with_config(tmp_path: Path, capsys, monkeypatch):
    yaml_text = """
clubs:
  205:
    pilates:
      - day: monday
        type: pilates
        start_time: '8:30'
        registration_day: sunday
        registration_start_time: '8:30'
        lesson_id: '10440'
        instructor_id: '27'
"""
    p = tmp_path / "holmes_lessons.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    monkeypatch.setenv("HOLMES_PHONE", "054")
    monkeypatch.setenv("HOLMES_PASSWORD", "pw")
    import json
    from holmes_place.cli import main

    with patch("holmes_place.cli.HolmesPlaceClient") as MockClient:
        inst = MockClient.return_value
        inst.get_available_seats.return_value = [1, 2]
        inst.login.return_value = MagicMock()
        inst.logout.return_value = MagicMock()
        rc = main(["discover", "--config", str(p)])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert "summary" in out
        assert "lessons" in out
        assert out["lessons"][0]["lesson_id"] == "10440"
