# Holmes Place Israel — Booking Client

Validated 2026-09-10 against live `https://www.holmesplace.co.il/api.php` endpoints (see `docs/holmes-place-booking-research.md`).

Builds a small, tested client around the still-live `api.php` flow. Uses `raviv-steinberg/holmesplace_register` only as protocol reference — not as a runtime dependency.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# secrets — never committed (see .gitignore)
cp .env.example .env   # HOLMES_PHONE, HOLMES_PASSWORD
# or: export HOLMES_PHONE=... HOLMES_PASSWORD=...

# read-only discovery (single lesson)
holmes-place discover --branch 205 --lesson 123 --date 2026/09/10 --time 18:00

# catalog validation — validates your holmes_lessons.yaml allow-list
# No server-side catalog endpoint was found (probed 2026-09-10); this validates
# the YAML via getAvailableSeats and reports seat behavior + next registration time.
holmes-place discover --config holmes_lessons.yaml
holmes-place discover --config holmes_lessons.yaml --branch 205

# dry-run booking (validates, does not send register)
holmes-place book --branch 205 --lesson 123 --date 2026/09/10 --time 18:00 --seat 12 --dry-run

# real booking with safeguards (single stream, rate-limited, idempotent)
holmes-place book --branch 205 --lesson 123 --date 2026/09/10 --time 18:00 --seat 12 --execute --yes

# schedule timers for next registration opens (one-shot per lesson, re-run weekly)
holmes-place schedule --config holmes_lessons.yaml --dry-run
holmes-place schedule --config holmes_lessons.yaml --branch 205 --seats 12,10 -o schedule
# macOS: launchctl load schedule/launchd/*.plist
# Linux: systemctl --user enable --now schedule/systemd/*.timer
# logs: schedule/launchd uses logs/ per job, respects HOLMES_KILL_SWITCH=1
```

## Safeguards

- Secrets from env / `.env` file only — never committed; cookies redacted in logs.
- `Asia/Jerusalem` timezone everywhere; server clock compared via `Date` header.
- Single attempt stream per member (file lock); 1 req/s only inside a short opening window.
- Idempotency: `already registered` is success, not error.
- Allow-list: branch/lesson must be explicitly passed.
- Dry-run / list mode, cancel path, kill switch (`--kill-switch` or `HOLMES_KILL_SWITCH=1`).
- Low frequency + conservative retry/backoff for network errors.

## Terms

Verify Holmes Place / Fizikal terms and obtain permission before unattended automation.

Unattended paths (`book --execute`, `schedule` without `--dry-run`) require an explicit gate:
`--i-have-permission` or `HOLMES_I_HAVE_PERMISSION=1`. Read-only paths (`discover`, `check-clock`, `book --dry-run`, `schedule --dry-run`) do not require it.

## Notifications

`book` always prints structured JSON to stdout. If configured, it also notifies on success/failure:
- `HOLMES_NOTIFY_URL` / `--notify-url` — POSTs JSON `{status, seat, message, lesson}` to webhook (Slack/Telegram adapter)
- `HOLMES_NOTIFY_LOG` / `--notify-log` — appends JSON line to file (default `logs/notifications.jsonl` if set)
- Timer logs (`schedule` → `logs/holmes-*.log`) already capture stdout with `TZ=Asia/Jerusalem`.

## Development

```bash
pytest
mypy holmes_place
```
