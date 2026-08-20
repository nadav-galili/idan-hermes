# Execution Runbook — Idan's Second Brain + WhatsApp Assistant

**Supersedes** the runbook section of `hermes-brother-assistant-PRD.md`.
**Derived from** the walked wayfinder map: [nadav-galili/idan-hermes#1](https://github.com/nadav-galili/idan-hermes/issues/1) (decisions #2–#6, #8).
**Stance:** the way is clear — this is execution, not planning. Build **brain-first**; assistant features come after the brain is proven.

Each phase de-risks the next. Ticket refs in `(#n)` point to the decision that governs the step.

---

## Guiding invariants (hold across every step)

- **`raw/` is the source of truth; `notes/` is a regenerable cache.** Never let a step treat notes as primary.
- **The brain lives in a SEPARATE PRIVATE repo.** `idan-hermes` (the map) is public — never point the brain at it. (#6)
- **Hermes is disposable plumbing.** Nothing brain-specific may depend on Hermes internals beyond the plugin seams. (#3, #5)
- **Single writer** (the box) → one `flock` serializes every git op (raw cron, curation, notes push). (#6, #8)
- **Instance #1 is untouched** throughout.

---

## Phase 0 — Provision (brain repo + isolated plumbing)

1. **Create the private brain repo** `idan-brain` (private). Commit the skeleton:
   ```
   raw/            # (empty; JSONL day-files land here)
   notes/{people,decisions,preferences,facts,routines}/
   media/
   MEMORY.md       # index seed
   README.md
   ```
   Schema of a `raw/` record and a `notes/` note per **#2** (see that ticket's resolution for the exact field table).

2. **Git write auth from the box** (#6):
   - `ssh-keygen -t ed25519 -N "" -f <DATADIR>/.ssh/idan_brain_deploy -C idan-brain-deploy`; `chmod 600`.
   - Add the public key as a **write-enabled Deploy Key** on `idan-brain`.
   - `<DATADIR>/.ssh/config` host alias `github-idan-brain` with `IdentitiesOnly yes`.
   - `git init` the on-box data dir, set **repo-local** `user.name`/`user.email`, `git remote add origin git@github-idan-brain:nadav-galili/idan-brain.git`, verify `git push`.

3. **Provision Hermes instance #2** (PRD step 3, kept): own systemd service under a dedicated OS user, own data dir + port, **own Google identity**. Data-level isolation. Do **not** touch instance #1.

4. **LLM provider** (#4): point instance #2 at **OpenRouter**; set the conversation model and the **curation model reuses the same key** (prepaid ceiling). Fund credits to the ~$10–20/mo ceiling.

5. **WhatsApp channel** (PRD step 5): dedicated physical SIM → QR-link the session; set the **Hebrew warm-but-brief** persona; add the assistant to the 1–2 groups for search.

6. **Hebrew STT** (#3): set `HERMES_LOCAL_STT_COMMAND` to an **ivrit-ai** faster-whisper CLI — `{language}=he`, model `ivrit-ai/whisper-large-v3-turbo-ct2` (fall back to `whisper-large-v3-ct2` if accuracy beats speed on the 2-vCPU box). Confirm a voice note yields a Hebrew transcript and the original audio is retained.

**Gate:** `git push` works from the box; a QR-linked WhatsApp session replies in Hebrew; a test voice note transcribes to Hebrew. Instance #1 unaffected.

---

## Phase 1 — Raw capture (truth in)

7. **Build the `brain-capture` plugin** (`~/.hermes/plugins/brain-capture/`, `plugin.yaml` + `tools.py`) (#3):
   - `pre_gateway_dispatch(event, …)` — skip `event.internal`; build a JSONL record: `id`=`event.message_id` (**content-hash fallback when None**), `ts`=`event.timestamp`, `dir`="in", `channel`/`sender` **derived from `event.source`** (`chat_type`/`chat_id`/`user_*`), `type`=`event.message_type`, `text`=`event.text` (voice already Hebrew-transcribed), `media`=copy each `event.media_urls[*]` into `media/<date>/` and store the pointer **list**, `meta`={reply_to, platform_update_id, media_types}. Append to `raw/<date>.jsonl`. Return `{"action":"allow"}` — **never blocks**.
   - `post_llm_call(…, assistant_response, …)` — append a `dir:"out"` record (`text`=assistant_response, synthesized `id`). Do not re-log the inbound.
   - **Also stamp** `last_activity[chat_id]=ts` on each inbound (state file) — the idle trigger reads this (#8).

8. **Hourly raw-commit cron** (#6): `flock <lock> -c 'git add raw/ media/ && git commit -m "raw: <date> <hh:00>" && git push'`. Raw is unregenerable → this tight cadence is the backup.

**Gate:** send text + Hebrew voice in the DM and post a message in a group the assistant is in → all three land in `raw/<date>.jsonl` with correct `channel`/`sender`, Hebrew transcript present, media file saved; the hourly cron pushes them.

---

## Phase 2 — Curation (notes derived)

9. **Standalone curation script on the VPS** (#4, prompt from #7):
   - Input: a chat's `raw/` records since its `last_curated`.
   - Run the derivation prompt via OpenRouter — **model judges durability** (no heuristic pre-filter).
   - **Regenerate the whole note** from (current note + new raw) — idempotent materialized view; no append-drift.
   - Maintain `[[wikilinks]]`, the `MEMORY.md` index, and each note's `source:` provenance back to raw (#2).
   - Commit **per note** (message = note summary) and push, all under the shared `flock` (#6). Update `last_curated`.

10. **Triggers** (#8 + #4):
    - **Debounce watcher** — systemd timer (~1–2 min) fires curation for any chat idle `> ~10–15 min` with `last_activity > last_curated`.
    - **Daily safety-net cron** — sweeps anything the idle path missed.

**Gate:** seed raw, let the watcher fire → `notes/` + `MEMORY.md` written with correct `source:` links; re-run over the same raw → **no duplicate notes** (idempotent).

---

## Phase 3 — Query (recall out)

11. **Build the `brain_search(query, deep=false)` plugin tool** (#5): notes-first (`MEMORY.md` + `notes/` with **Hebrew normalization** — strip niqqud, unify final/medial forms) → **raw fallback** on miss/`deep`; scoped to the repo dir; return structured hits (path + excerpt).

12. **Lock the toolset** (#5): per-profile allowlist exposes `brain_search` (read) and the messaging tools; **excludes `terminal`/`write_file`/`patch`** from the conversational agent. (Writes happen in hooks, not agent tools.)

13. **Persona nudge:** "for anything about Idan's life/history/decisions, call `brain_search` first."

**Gate:** ask `מה החלטנו לגבי X?` → answered from the brain; ask about something said **minutes ago** (before curation ran) → the **raw fallback** answers.

---

## Phase 4 — Reliability (keep-list only)

14. systemd **`restart=always`** (#hardening keep). Confirm the OpenRouter prepaid ceiling is the hard cost cap.
    **Deferred** (not now): Hostinger backups (git push *is* the backup), healthchecks.io dead-man's-switch, WhatsApp-drop alert, heavy container/OS-user isolation.

**Gate:** kill the instance → it self-heals.

---

## Phase 5 — Assistant features (only after the brain is proven)

Sequenced after Phases 0–4. Each feature's interactions **also append to `raw/`** (they flow through the same capture hooks), so they enrich the brain for free. PRD decisions mostly stand:
- **Email** — manual forward → summarize; draft → "YES" → send from the assistant's address.
- **Calendar** — create on the assistant's calendar, invite Idan.
- **Tasks** — one list, work/personal tags.
- **Reminders** — dog-food ack-reset + ~40-day interval-learning, delivered via Hermes cron. **Caveat (#3):** proactive cron sends are **not** caught by the outbound hook (turn-only, no gateway send-hook — Hermes FR #22603) → the reminder job must **self-log its own `dir:out` record**.

---

## Phase 6 — Onboard Idan

15. He saves the assistant contact; you give him the forward-to email and the **plain-language consent note** (a private memory he and you can read); he accepts a test calendar invite; run the dog-food reminder end-to-end.

---

## Acceptance checks (externally observable, over WhatsApp + in the repo)

- **Isolation** — nothing from your two profiles appears in Idan's assistant or its repo, and vice versa.
- **Capture** — every inbound/outbound (incl. group + Hebrew voice) appears in `raw/`.
- **Curation** — a durable fact produces a committed `notes/` file with a `source:` link and summary commit message; re-running is idempotent.
- **Recall** — `brain_search` answers from `notes/`, and from `raw/` for pre-curation freshness.
- **Group search** — ask it to find something said in a group → answers from that group's captured raw only.
- **Backup** — the on-box repo loss is recoverable from the GitHub mirror (git is the backup).
- **Reliability** — kill → `restart=always` recovers.

---

## Open items to settle at build time (not architecture — execution details)

- Confirm `event.source` distinguishes DM vs group cleanly enough to slug `wa:group:<slug>` on the WhatsApp adapter (verify against instance #1). (#3)
- Confirm the WhatsApp adapter populates `message_id` (the hash fallback covers gaps either way). (#3)
- Pick the exact OpenRouter conversation + curation models. (#4)
- Tune `idle_minutes` for WhatsApp after watching real burst patterns. (#8)
