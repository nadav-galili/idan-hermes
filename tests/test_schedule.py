"""Tests for scheduling — timers at registration open."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from holmes_place.catalog import LessonConfig
from holmes_place.config import JERUSALEM_TZ
from holmes_place.schedule import plan_schedule, render_launchd, render_systemd_timer, generate_schedule


def _lessons():
    return [
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
            lesson_id="10051",
            instructor_id="50",
            type="yoga",
            day="tuesday",
            start_time="8:30",
            registration_day="monday",
            registration_start_time="08:30",
        ),
    ]


def test_plan_schedule_next_run():
    now = datetime(2026, 9, 6, 12, 0, tzinfo=JERUSALEM_TZ)  # Sunday 12:00 — registration for next Monday is Monday 08:30? Wait pilates reg is Sunday 08:30 already passed, so next is next Sunday
    # Actually monday pilates reg is sunday 08:30 — on Sunday 12:00, next is next Sunday 08:30
    jobs = plan_schedule(_lessons(), now=now, lead_seconds=2, seat_args="12,10")
    # yoga registration is Monday 08:30 — next is Mon 2026-09-07 08:30, run at 08:29:58
    assert len(jobs) == 2
    # sorted by run_at
    assert jobs[0].lesson.lesson_id == "10051"  # Monday reg earlier than Sunday next week
    assert jobs[0].run_at.hour == 8 and jobs[0].run_at.minute == 29 and jobs[0].run_at.second == 58
    assert "holmes-place book" in jobs[0].command
    assert "--seats 12,10" in jobs[0].command or "--seats" in jobs[0].command
    assert jobs[0].lesson_date  # computed
    # log path
    assert jobs[0].log_path.name.startswith("holmes-205-")


def test_plan_schedule_branch_filter():
    now = datetime(2026, 9, 6, 12, 0, tzinfo=JERUSALEM_TZ)
    lessons = _lessons() + [
        LessonConfig("999", "999", "1", "spinning", "monday", "8:30", "sunday", "08:30")
    ]
    jobs = plan_schedule(lessons, branch_filter="205", now=now)
    assert all(j.lesson.branch_id == "205" for j in jobs)
    assert len(jobs) == 2


def test_render_launchd_and_systemd():
    now = datetime(2026, 9, 7, 6, 0, tzinfo=JERUSALEM_TZ)
    jobs = plan_schedule(_lessons(), now=now)
    assert jobs
    pl = render_launchd(jobs[0])
    assert "com.holmes-place" in pl
    assert "<key>StartCalendarInterval</key>" in pl
    assert "Asia/Jerusalem" in pl
    svc = render_systemd_timer(jobs[0])
    assert "OnCalendar=" in svc
    assert ".service" in svc


def test_generate_schedule_writes_files(tmp_path: Path):
    now = datetime(2026, 9, 6, 12, 0, tzinfo=JERUSALEM_TZ)
    out = tmp_path / "schedule"
    res = generate_schedule(out, _lessons(), now=now, seat_args="5")
    assert res["jobs"] == 2
    assert len(res["written"]) == 6  # 2 jobs * 3 files
    assert (out / "launchd").exists()
    assert (out / "systemd").exists()
    # dry-run via plan preserves kill-switch? not needed


def test_cli_schedule_dry_run(tmp_path: Path, capsys, monkeypatch):
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
    import json
    from holmes_place.cli import main

    rc = main(["schedule", "--config", str(p), "--dry-run"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["jobs"] == 1
    assert "run_at" in out["next_runs"][0]


def test_cli_schedule_writes(tmp_path: Path, capsys):
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
    out = tmp_path / "sched"
    import json
    from holmes_place.cli import main

    rc = main(["schedule", "--config", str(p), "--output", str(out), "--i-have-permission"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["jobs"] == 1
    assert (out / "launchd").exists()
    assert (out / "systemd").exists()
