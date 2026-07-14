# PROTOTYPE — Curation job (issue #4). Throwaway. Delete once the decision is recorded.

**Question this answers:** design the separate scheduled curation job that reads `raw/`,
derives/updates `notes/`, and commits+pushes. This is a *cheap concrete artifact to react
to* — a proposal + prompt + one worked before/after — **not** a runnable pipeline. Nothing
here calls an LLM or writes to the real repo.

## The four decisions (charting's recommendation = the starting point to react to, NOT a verdict)

| # | Decision | Charting's lean | What the artifact shows |
|---|----------|-----------------|-------------------------|
| 1 | **Where it runs** | Standalone job, *not* inside Hermes | `host-stub.sh` — clone → derive → commit → push loop, runnable on VPS cron **or** a `/schedule` cloud agent. Same script either way. |
| 2 | **Trigger / cadence** | Batched **daily** | `host-stub.sh` header shows the cron line + the "yesterday's day-file(s)" window it reads. |
| 3 | **Model** | One we trust for graphify-style curation | `derivation-prompt.md` is model-agnostic; the open sub-question (which model) is called out below. |
| 4 | **Algorithm** | No inline heuristic pre-filter — the model decides durability | `derivation-prompt.md` + the `sample-input → sample-output` worked example demonstrate durability, merge, dedup, wikilinks, `MEMORY.md`. |

## Layout

```
derivation-prompt.md        # the actual LLM prompt — the meat of "algorithm"
host-stub.sh                # decisions 1 & 2: where it runs + cadence, as a runnable-shaped stub
sample-input/
  raw/2026-07-13.jsonl      # one synthetic day-file (Hebrew, realistic) — the day being curated
  notes-before/             # notes that ALREADY exist — so merge & dedup are visible, not described
    MEMORY.md
    people/idan.md
sample-output/
  notes-after/              # the exact notes/ + MEMORY.md the prompt should produce
    MEMORY.md               # ← diff vs notes-before/MEMORY.md is the "what changed" signal
    people/idan.md          # ← MERGED: gym+wfh+roey+rex links folded in, old source id kept
    people/roey.md          # ← new (best friend from army)
    routines/gym.md         # ← new
    facts/dog-rex.md        # ← new (Royal-Canin-only)
    decisions/wfh-fridays.md # ← new
  DERIVATION-LOG.md         # what the job would report each run (for observability / the raw dir:out echo)
```

## Open sub-questions for the human (the react-to list)

- **Decision 3 — which model?** Candidates: Claude (Opus/Sonnet) via API, or the same OpenRouter
  key Hermes already uses (map mentions an OpenRouter prepaid ceiling). Graphify-style curation
  wants strong Hebrew + careful merge judgment → leans a frontier model, not a cheap one. **Undecided.**
- **Decision 1 — VPS cron vs `/schedule` cloud agent?** The stub runs identically on both. VPS cron =
  one more thing on the box, uses the box's deploy key. `/schedule` = runs off-box against a clone,
  no box load, but needs its own repo write auth (overlaps issue #6). **Which host?**
- **Decision 2 — is daily right?** Daily batches keeps notes ~24h stale. Per-session would be fresher
  but re-derives constantly. On-demand ("hey, remember this") is a *third* trigger that could coexist
  with daily. **Daily only, or daily + on-demand?**
- **Idempotency / re-runs:** if the job runs twice on the same day-file, does it double-write? The
  prompt is given the *current* notes each run, so it should converge — but is "regenerate the whole
  note from all its sources" safer than "append the delta"? (See prompt §Merge.)
