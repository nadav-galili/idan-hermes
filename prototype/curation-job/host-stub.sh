#!/usr/bin/env bash
# PROTOTYPE — curation job host stub (issue #4, decisions 1 "where" & 2 "cadence").
# Throwaway shape, NOT wired: the `derive` step is a placeholder, not a real LLM call.
#
# Decision 1 (WHERE): this same script runs identically as either
#   (a) a VPS cron job on the Hostinger box, using the box's per-repo SSH deploy key, or
#   (b) a Claude Code `/schedule` cloud agent against a fresh clone (needs its own write auth — see #6).
# The clone → derive → commit → push loop below is host-agnostic; only the auth + trigger differ.
#
# Decision 2 (CADENCE) — RESOLVED: PER-SESSION, not daily. Hermes fires this script after a
# conversation goes idle (a debounced "session-idle" hook — see the graduated ticket). A daily
# cron stays only as a cheap safety-net sweep in case a session-idle fire is missed:
#   30 3 * * *  /opt/idan-brain/prototype/curation-job/host-stub.sh >> /var/log/idan-curation.log 2>&1
# Window = "raw day-files newer than the last successful run" (works for both entry points).

set -euo pipefail

REPO_URL="git@github.com:nadav-galili/idan-brain.git"   # the private BRAIN repo (not this planning repo)
WORK="$(mktemp -d /tmp/idan-curation.XXXX)"             # scratch clone, wiped each run — no persistence
LAST_RUN_FILE=".curation/last-run"                      # committed marker: ISO date of last successful run

cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT

# 1. Fresh clone (source of truth is the repo, always; no local state carried between runs)
git clone --depth 50 "$REPO_URL" "$WORK"
cd "$WORK"

# 2. Determine the window: raw/ day-files strictly newer than last-run marker (default yesterday)
LAST_RUN="$(cat "$LAST_RUN_FILE" 2>/dev/null || date -v-1d +%F)"
WINDOW_FILES=$(find raw -name '*.jsonl' -newermt "$LAST_RUN" | sort)
if [ -z "$WINDOW_FILES" ]; then echo "nothing new since $LAST_RUN"; exit 0; fi

# 3. DERIVE  <-- the meat. Assembles derivation-prompt.md with:
#       RAW_WINDOW    = concatenated $WINDOW_FILES
#       CURRENT_NOTES = full contents of notes/**
#    Sends to the trusted model (Decision 3 — model TBD), applies the returned JSON edit plan:
#      - writes/rewrites each notes/ file
#      - overwrites MEMORY.md
#      - appends the returned `log` to raw/ as a dir:out record (observability + the reminder-caveat echo)
#    NO inline heuristic pre-filter — the model judges durability (charting decision).
echo "[stub] derive: prompt = derivation-prompt.md; window = $WINDOW_FILES  (real LLM call goes here)"

# 4. Commit + push (the job IS the single writer; commit is the backup — map defers Hostinger backups)
date +%F > "$LAST_RUN_FILE"
git add -A
git commit -m "curate: derive notes from raw window >$LAST_RUN" || { echo "no changes"; exit 0; }
git push origin main
