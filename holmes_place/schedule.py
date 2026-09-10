"""Scheduling — generate launchd / systemd timers for booking at registration open.

Each lesson's registration opens at registration_day + registration_start_time
(in Asia/Jerusalem). We schedule a job to run `lead_seconds` before that
(default 2s) which invokes `holmes-place book --execute --yes` for the
upcoming lesson date. Timers are one-shot for the *next* occurrence; re-run
`holmes-place schedule` weekly or after booking to re-arm.

Why not poll 1 req/s via timer? The timer fires *once* at open; the `book`
command itself polls 1 req/s for ~180s inside the opening window (booking.py).
So timer frequency is low (one wake per lesson) and booking rate-limit stays.

Safeguards carried into timers:
- kill-switch env respected (HOLMES_KILL_SWITCH=1 aborts before request)
- per-member lock via member_id (phone) in book()
- logs redacted (via client), written to per-job log file
- Asia/Jerusalem throughout; schedule lists next run in local time + UTC
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from zoneinfo import ZoneInfo

from holmes_place.catalog import LessonConfig, next_registration_time
from holmes_place.config import JERUSALEM_TZ


@dataclass(frozen=True)
class ScheduledJob:
    lesson: LessonConfig
    run_at: datetime  # registration open - lead_seconds, tz=Jerusalem
    registration_open: datetime
    lesson_date: str  # YYYY/MM/DD for the upcoming lesson
    lesson_time: str  # HH:MM
    command: str
    log_path: Path
    job_name: str


def _lesson_date_for_registration(lesson: LessonConfig, registration_open: datetime) -> str:
    """Lesson date is the next occurrence of lesson.day on/after registration_open."""
    # mapping from catalog
    from holmes_place.catalog import WEEKDAY_MAP, _parse_hhmm

    target_wd = WEEKDAY_MAP.get(lesson.day.lower())
    if target_wd is None:
        return registration_open.strftime("%Y/%m/%d")
    # lesson's next occurrence at or after registration_open's date
    # registration_open is on registration_day; lesson is typically 1-2 days later
    # Find next lesson.day at lesson.start_time that is >= registration_open date
    days_ahead = (target_wd - registration_open.weekday()) % 7
    # if registration is same day as lesson but we are before lesson time, lesson is today
    # else lesson is days_ahead away
    # special: if lesson is 2 days after registration, days_ahead will be 2
    cand = registration_open + timedelta(days=days_ahead)
    return cand.strftime("%Y/%m/%d")


def _normalize_time(s: str) -> str:
    from holmes_place.catalog import _parse_hhmm

    try:
        h, m = _parse_hhmm(s)
        return f"{h:02d}:{m:02d}"
    except Exception:
        return s


def plan_schedule(
    lessons: list[LessonConfig],
    branch_filter: str | None = None,
    now: datetime | None = None,
    lead_seconds: int = 2,
    seat_args: str | None = None,
    log_dir: Path | str = "logs",
) -> list[ScheduledJob]:
    """Plan one-shot jobs for the next registration occurrence of each lesson."""
    if now is None:
        now = datetime.now(tz=JERUSALEM_TZ)
    log_dir_p = Path(log_dir)
    jobs: list[ScheduledJob] = []
    for lesson in lessons:
        if branch_filter and lesson.branch_id != branch_filter:
            continue
        if not lesson.registration_day or not lesson.registration_start_time:
            continue
        try:
            reg_open = next_registration_time(lesson.registration_day, lesson.registration_start_time, now=now)
        except Exception:
            continue
        run_at = reg_open - timedelta(seconds=lead_seconds)
        # if run_at already in past (shouldn't with next_registration_time), skip
        if run_at <= now:
            continue
        lesson_date = _lesson_date_for_registration(lesson, reg_open)
        lesson_time = _normalize_time(lesson.start_time)
        # build booking command — explicit date/time so book polls at open
        seat_opt = f" --seats {shlex.quote(seat_args)}" if seat_args else ""
        # --seats or fallback to random; if seat_args is "12,10" we pass --seats
        if seat_args and "," not in seat_args and seat_args.isdigit():
            # single seat numeric -> use --seat for backward compat, but prefer --seats
            seat_opt = f" --seat {seat_args}"
        cmd_parts = [
            "holmes-place",
            "book",
            f"--branch {shlex.quote(lesson.branch_id)}",
            f"--lesson {shlex.quote(lesson.lesson_id)}",
            f"--date {shlex.quote(lesson_date)}",
            f"--time {shlex.quote(lesson_time)}",
            f"--instructor {shlex.quote(lesson.instructor_id)}",
            seat_opt.strip(),
            "--execute",
            "--yes",
        ]
        cmd = " ".join(p for p in cmd_parts if p)
        safe_type = "".join(c if c.isalnum() else "_" for c in lesson.type)
        job_name = f"holmes-{lesson.branch_id}-{lesson.lesson_id}-{safe_type}"
        log_path = log_dir_p / f"{job_name}.log"
        jobs.append(
            ScheduledJob(
                lesson=lesson,
                run_at=run_at,
                registration_open=reg_open,
                lesson_date=lesson_date,
                lesson_time=lesson_time,
                command=cmd,
                log_path=log_path,
                job_name=job_name,
            )
        )
    # sort by run_at
    jobs.sort(key=lambda j: j.run_at)
    return jobs


def render_launchd(job: ScheduledJob) -> str:
    """launchd plist for macOS — one-shot, StartCalendarInterval at run_at."""
    dt = job.run_at
    # launchd frequent: run once; for weekly repeat user re-runs schedule
    # Use StartCalendarInterval for precision to the second is not supported (minute granularity)
    # So we use StartCalendarInterval for minute and add sleep in wrapper if needed.
    # Simpler: generate a wrapper script that sleeps to second.
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.holmes-place.{job.job_name}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/sh</string>
        <string>-c</string>
        <string>{shlex.quote(job.command)} &gt;&gt; {shlex.quote(str(job.log_path))} 2&gt;&amp;1</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Month</key><integer>{dt.month}</integer>
        <key>Day</key><integer>{dt.day}</integer>
        <key>Hour</key><integer>{dt.hour}</integer>
        <key>Minute</key><integer>{dt.minute}</integer>
    </dict>
    <key>StandardOutPath</key><string>{job.log_path}</string>
    <key>StandardErrorPath</key><string>{job.log_path}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>TZ</key><string>Asia/Jerusalem</string>
    </dict>
</dict>
</plist>
"""


def render_systemd_service(job: ScheduledJob) -> str:
    return f"""[Unit]
Description=Holmes Place booking {job.job_name} (lesson {job.lesson.lesson_id} branch {job.lesson.branch_id})
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
Environment=TZ=Asia/Jerusalem
ExecStart=/bin/sh -c '{job.command} >> {shlex.quote(str(job.log_path))} 2>&1'
"""


def render_systemd_timer(job: ScheduledJob) -> str:
    dt = job.run_at
    # one-shot timer
    on_calendar = f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d} {dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}"
    return f"""[Unit]
Description=Timer for Holmes Place {job.job_name}

[Timer]
OnCalendar={on_calendar}
Unit={job.job_name}.service

[Install]
WantedBy=timers.target
"""


def generate_schedule(
    output_dir: Path | str,
    lessons: list[LessonConfig],
    branch_filter: str | None = None,
    now: datetime | None = None,
    lead_seconds: int = 2,
    seat_args: str | None = None,
    log_dir: Path | str = "logs",
) -> dict[str, Any]:
    """Write launchd + systemd files for each job to output_dir."""
    out = Path(output_dir)
    launchd_dir = out / "launchd"
    systemd_dir = out / "systemd"
    launchd_dir.mkdir(parents=True, exist_ok=True)
    systemd_dir.mkdir(parents=True, exist_ok=True)
    jobs = plan_schedule(
        lessons, branch_filter=branch_filter, now=now, lead_seconds=lead_seconds, seat_args=seat_args, log_dir=log_dir
    )
    written: list[str] = []
    for job in jobs:
        lp = launchd_dir / f"com.holmes-place.{job.job_name}.plist"
        lp.write_text(render_launchd(job), encoding="utf-8")
        written.append(str(lp))
        sp = systemd_dir / f"{job.job_name}.service"
        sp.write_text(render_systemd_service(job), encoding="utf-8")
        written.append(str(sp))
        tp = systemd_dir / f"{job.job_name}.timer"
        tp.write_text(render_systemd_timer(job), encoding="utf-8")
        written.append(str(tp))
    # summary manifest
    return {
        "jobs": len(jobs),
        "written": written,
        "next_runs": [
            {
                "job": j.job_name,
                "branch": j.lesson.branch_id,
                "lesson": j.lesson.lesson_id,
                "run_at": j.run_at.isoformat(),
                "run_at_utc": j.run_at.astimezone(ZoneInfo("UTC")).isoformat() if j.run_at.tzinfo else None,
                "registration_open": j.registration_open.isoformat(),
                "lesson_date": j.lesson_date,
                "lesson_time": j.lesson_time,
                "command": j.command,
                "log": str(j.log_path),
            }
            for j in jobs
        ],
    }



