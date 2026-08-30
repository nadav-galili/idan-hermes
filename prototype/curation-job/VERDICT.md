# VERDICT — issue #4 resolved (HITL, 2026-07-14)

The four decisions, settled with the human via the Lavish review:

| Decision | Answer |
|----------|--------|
| **1. Where it runs** | Standalone script **on the Hermes VPS box** (its own infra/deploy key) — *not* a `/schedule` cloud agent, *not* inside the Hermes process. |
| **2. Trigger / cadence** | **Per-session**, fired by a **session-idle hook** in Hermes (after a conversation goes quiet), **plus a daily cron as a cheap safety-net sweep**. (Resolved the cron-is-a-timer vs per-session-is-an-event tension.) |
| **3. Model** | The **existing OpenRouter key** Hermes already uses (reuses the prepaid ceiling). Specific OpenRouter model TBD at execution. |
| **4. Merge / idempotency** | **Regenerate the whole note** from (current note + new raw) each run — idempotent, no dupe drift. It's a materialized view over `raw/`. |

Everything else in `derivation-prompt.md` (no inline pre-filter; `source:` provenance; wikilinks; `MEMORY.md` index; five folders) stands as prototyped.

**Graduated fog:** per-session forces a real trigger-wiring question → new ticket *"Session-idle trigger: how Hermes fires the curation job after a conversation goes quiet"* (`wayfinder:research`), since #3 already found Hermes lacks some gateway hooks (FR #22603).

This prototype is throwaway — delete once the runbook absorbs the decision.
