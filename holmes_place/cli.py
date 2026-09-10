"""CLI — discovery first, then booking. Dry-run default for safety."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime

from holmes_place.booking import LessonKey, book, check_clock_drift, discover
from holmes_place.client import HolmesPlaceClient
from holmes_place.config import JERUSALEM_TZ, Settings
from holmes_place.secrets import get_credentials

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="holmes-place")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--branch", required=True, help="branch/club ID (allow-list)")
        sp.add_argument("--lesson", required=True, help="lesson ID")
        sp.add_argument("--date", required=True, help="YYYY/MM/DD")
        sp.add_argument("--time", required=True, help="HH:MM (Asia/Jerusalem)")
        sp.add_argument("--base-url", default=None)
        sp.add_argument("--kill-switch", action="store_true", help="refuse to send")

    d = sub.add_parser("discover", help="read-only: list available seats / validate catalog")
    d.add_argument("--branch", required=False, default=None, help="branch/club ID (allow-list)")
    d.add_argument("--lesson", required=False, default=None, help="lesson ID")
    d.add_argument("--date", required=False, default=None, help="YYYY/MM/DD")
    d.add_argument("--time", required=False, default=None, help="HH:MM (Asia/Jerusalem)")
    d.add_argument("--config", required=False, default=None, help="path to holmes_lessons.yaml for catalog validation")
    d.add_argument("--base-url", default=None)
    d.add_argument("--kill-switch", action="store_true", help="refuse to send")

    b = sub.add_parser("book", help="book a lesson (dry-run by default unless --execute)")
    common(b)
    b.add_argument("--instructor", default="", help="instructor ID (required for booking)")
    b.add_argument("--seat", type=int, default=None, help="preferred seat")
    b.add_argument("--seats", default=None, help="comma-separated preferred seats, e.g. 12,10,8")
    b.add_argument("--dry-run", action="store_true", help="validate without registering")
    b.add_argument("--execute", action="store_true", help="actually register (required to book)")
    b.add_argument("--no-random-fallback", action="store_true")
    b.add_argument("--max-wait", type=int, default=180, help="seconds to poll opening window")
    b.add_argument("--yes", action="store_true", help="skip confirmation prompt")

    u = sub.add_parser("cancel", help="cancel registration")
    common(u)

    sub.add_parser("check-clock", help="compare server Date header to local Jerusalem time")

    return p.parse_args(argv)


def _validate_date_time(date: str, time_str: str) -> None:
    try:
        dt = datetime.strptime(f"{date} {time_str}", "%Y/%m/%d %H:%M")
        dt = dt.replace(tzinfo=JERUSALEM_TZ)
    except ValueError as e:
        raise SystemExit(f"bad date/time: {e} (expected YYYY/MM/DD and HH:MM)") from e
    # no further validation — server is source of truth for opening timestamp


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    settings = Settings.from_env()
    if getattr(args, "base_url", None):
        settings = Settings(base_url=args.base_url, kill_switch=settings.kill_switch)
    if getattr(args, "kill_switch", False):
        settings = Settings(base_url=settings.base_url, kill_switch=True)

    if settings.kill_switch:
        print("kill-switch active — refusing to run", file=sys.stderr)
        return 2

    if args.cmd == "check-clock":
        client = HolmesPlaceClient(settings)
        drift = check_clock_drift(client)
        print(json.dumps({"drift_seconds": drift.total_seconds() if drift else None}, indent=2))
        return 0

    # discover with --config is catalog mode (branch/lesson/date/time not required)
    is_catalog_discover = args.cmd == "discover" and getattr(args, "config", None)

    if not is_catalog_discover:
        _validate_date_time(args.date, args.time)

    client = HolmesPlaceClient(settings)

    # login for discover/book/cancel (read-only discovery still needs auth per live probe)
    try:
        creds = get_credentials()
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    try:
        client.login(creds.phone, creds.password)
    except Exception as e:
        print(f"login failed: {e}", file=sys.stderr)
        return 1

    try:
        if args.cmd == "discover":
            if getattr(args, "config", None):
                from holmes_place.catalog import discovery_summary, load_lessons_config, validate_catalog

                try:
                    lessons = load_lessons_config(args.config)
                except Exception as e:
                    print(f"config load failed: {e}", file=sys.stderr)
                    return 2
                # branch filter if provided
                branch_filter = getattr(args, "branch", None)
                results = validate_catalog(client, lessons, branch_filter=branch_filter)
                summary = discovery_summary(results)
                # JSON with per-lesson details + summary
                out = {
                    "summary": summary,
                    "lessons": [
                        {
                            "branch_id": r.lesson.branch_id,
                            "lesson_id": r.lesson.lesson_id,
                            "instructor_id": r.lesson.instructor_id,
                            "type": r.lesson.type,
                            "day": r.lesson.day,
                            "start_time": r.lesson.start_time,
                            "registration_day": r.lesson.registration_day,
                            "registration_start_time": r.lesson.registration_start_time,
                            "next_registration": r.next_registration.isoformat() if r.next_registration else None,
                            "target_date": r.target_date,
                            "target_time": r.target_time,
                            "available_seats": r.available_seats,
                            "seat_behavior": r.seat_behavior,
                            "error": r.error,
                        }
                        for r in results
                    ],
                }
                print(json.dumps(out, indent=2, ensure_ascii=False))
                return 0
            # single-lesson mode
            if not args.branch or not args.lesson or not args.date or not args.time:
                print("discover requires --branch --lesson --date --time (or --config)", file=sys.stderr)
                return 2
            disc = discover(client, branch_id=args.branch, lesson_id=args.lesson, date=args.date, time_str=args.time)
            print(json.dumps(disc, indent=2, ensure_ascii=False))
            return 0

        if args.cmd == "cancel":
            client.unregister(branch_id=args.branch, lesson_id=args.lesson, date=args.date, time=args.time)
            print("canceled (if registered)")
            return 0

        if args.cmd == "book":
            if not args.instructor:
                print("--instructor is required for book", file=sys.stderr)
                return 2
            # safety: dry-run unless --execute
            dry_run = not args.execute or args.dry_run
            if dry_run and args.execute and args.dry_run:
                dry_run = True

            seats: list[int] = []
            if args.seats:
                seats = [int(s.strip()) for s in args.seats.split(",") if s.strip()]
            elif args.seat is not None:
                seats = [args.seat]

            if not dry_run and not args.yes:
                print(f"book {args.lesson} {args.date} {args.time} branch {args.branch} seat {seats or 'any'} ? [y/N] ", end="")
                ans = input().strip().lower()
                if ans not in ("y", "yes"):
                    print("aborted")
                    return 0

            lesson = LessonKey(
                branch_id=args.branch,
                lesson_id=args.lesson,
                date=args.date,
                time=args.time,
                instructor_id=args.instructor,
            )
            res = book(
                client,
                lesson,
                seat_preferences=seats,
                dry_run=dry_run,
                max_wait_s=args.max_wait,
                allow_random_fallback=not args.no_random_fallback,
                on_status=lambda m: print(m),
                member_id=creds.phone,
            )
            print(json.dumps({"status": res.status, "seat": res.seat, "message": res.message}, indent=2, ensure_ascii=False))
            return 0 if res.status in ("booked", "already_registered", "dry_run") else 1
    finally:
        try:
            client.logout()
        except Exception:
            pass
    return 1
