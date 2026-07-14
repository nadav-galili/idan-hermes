# PRD — Hermes Personal Assistant for My Brother

**Type:** Setup PRD + runbook (for me, the human operator)
**Status:** Design complete · no open unknowns · build not yet started
**Platform:** Nous Research **Hermes Agent** (open-source, self-hosted)
**Host:** Existing Hostinger VPS (`srv1762531`, KVM 2 — 2 vCPU / 8 GB / 100 GB, Ubuntu 24.04, Frankfurt)
**Companion artifact:** `.lavish/hermes-brother-assistant.html` (visual plan)

---

## Problem Statement

My brother is not technical, but he wants a personal assistant that helps him run his work and personal life. He will only interact with it through **WhatsApp** — he won't log into dashboards, install apps, or manage settings. He wants help reading and sending emails, handling calendar scheduling, searching things in his WhatsApp, and managing tasks — including recurring life-admin like remembering to reorder his dog's food. I already run a Hermes agent on my VPS for my own two profiles, and I want to give him the same kind of assistant without entangling his private life with mine.

Separately, I want the assistant to build up a durable, queryable memory of my brother's world — a "second brain" I can inspect llm-wiki style — rather than losing everything in chat scrollback.

## Solution

Stand up a **second, fully isolated Hermes Agent instance** on the same VPS, dedicated to my brother and running a single profile. He talks to it entirely over WhatsApp on a **dedicated phone number** (never his personal number). It reads/sends email, manages his calendar via invites, manages a tagged task list, and sends proactive reminders that learn his habits. In the background it distills durable facts and decisions into a **private GitHub "second brain" repo** that both the assistant (for recall) and I (for querying) can read — with my brother's knowledge and consent.

The instance is isolated from my existing agent at the data, session, and identity level; the two share only CPU/RAM on the box.

---

## User Stories

### Setup & operation (me, the operator)

1. As the operator, I want the new assistant to run as a **separate Hermes instance** (own container/service, own data dir, own port), so that my brother's private data never mixes with my two profiles.
2. As the operator, I want to confirm the VPS has headroom before launch, so that a second WhatsApp session doesn't degrade my existing agent.
3. As the operator, I want **daily backups enabled** before any of my brother's data lands, so that I can recover his email/WhatsApp/memory data after a failure.
4. As the operator, I want the assistant on a **dedicated physical SIM number**, so that WhatsApp ban risk never touches my brother's personal line.
5. As the operator, I want to link the assistant's WhatsApp via QR once, so that it can send and receive as its own account.
6. As the operator, I want the assistant to run under `restart=always`, so that a crash self-heals without my intervention.
7. As the operator, I want an **external dead-man's-switch (healthchecks.io)** that alerts me if the instance goes quiet, so that I find out about outages before my brother does.
8. As the operator, I want to be alerted when the WhatsApp session drops, so that I can re-scan the QR quickly.
9. As the operator, I want LLM calls routed through **OpenRouter**, so that I control cost and model choice from one place.
10. As the operator, I want a soft monthly spend ceiling (~$10–20), so that a runaway loop can't quietly run up a bill.
11. As the operator, I want the memory-worthiness judgment to run on a **cheap model behind a heuristic pre-filter**, so that I don't burn premium tokens deciding whether "ok thanks" is worth saving.
12. As the operator, I want the assistant to keep my two existing profiles **completely untouched** during setup, so that my own agent keeps working.

### WhatsApp channel (my brother)

13. As my brother, I want to chat with the assistant like a contact in WhatsApp, so that I don't have to learn any new app.
14. As my brother, I want the assistant to reply in **Hebrew, warmly but briefly**, so that messages are easy to read on my phone.
15. As my brother, I want the assistant to understand voice/typo-laden messages, so that I can talk to it naturally.
16. As my brother, I want to add the assistant to **1–2 group chats**, so that it can search and reference messages in those groups.
17. As my brother, I want to ask the assistant to find something said in a chat it belongs to, so that I don't have to scroll back manually.

### Email (my brother)

18. As my brother, I want to **forward an email** to the assistant, so that it can read and summarize it for me.
19. As my brother, I want to ask the assistant to draft a reply to a forwarded email, so that I don't have to write it myself.
20. As my brother, I want the assistant to show me the draft and only send after I reply "YES", so that nothing goes out in my name without my say-so.
21. As my brother, I want the assistant to send email from its own address, so that I keep control of my own inbox.
22. As my brother, I do **not** want the assistant reading my whole inbox, so that my private email stays private unless I choose to forward it.

### Calendar (my brother)

23. As my brother, I want to ask the assistant to schedule something ("lunch with Dana Thursday 1pm"), so that it gets onto my calendar.
24. As my brother, I want the assistant to create the event and **invite me** (and my team when relevant), so that it appears on my calendar without me granting it access to my account.
25. As my brother, I want the assistant to confirm event details before creating, so that I can catch mistakes.
26. As my brother, I want to accept the invite on my own phone, so that the event lands natively with normal reminders.

### Reminders & tasks (my brother)

27. As my brother, I want the assistant to remind me to reorder my dog's food, so that I never run out.
28. As my brother, I want to reply "done"/"הזמנתי" when I've ordered, so that the assistant resets the reminder clock.
29. As my brother, I want the assistant to **learn my ~40-day reorder cadence** from my first few orders, so that I don't have to configure an interval.
30. As my brother, I want to snooze a reminder, so that I can defer it a couple of days.
31. As my brother, I want to add tasks in plain language, so that I can offload things I need to do.
32. As my brother, I want to tag tasks as **work or personal**, so that I can ask for just one kind.
33. As my brother, I want to list and complete tasks over WhatsApp, so that I manage everything from one place.
34. As my brother, I want proactive reminders to arrive as WhatsApp messages, so that they reach me where I already am.

### Second brain / memory

35. As my brother, I want the assistant to remember durable facts, decisions, and preferences, so that I don't have to repeat myself.
36. As my brother, I want to explicitly tell it "תזכור ש…" (remember that…), so that I can pin something important.
37. As my brother, I want to correct or delete a memory in plain language ("לא נכון" / "תשכח את זה"), so that wrong or stale memories get fixed.
38. As my brother, I want to ask the assistant "מה החלטנו לגבי X?", so that it answers from its own memory.
39. As my brother, I want the assistant to use its memory during normal conversation, so that it feels like it knows me.
40. As my brother, I want to be told plainly that a private memory is kept and that my brother (the operator) can read it, so that I've consented to it.
41. As the operator, I want each memory committed as its own file to a **private GitHub repo**, so that the git log is a timestamped record of what the assistant learned.
42. As the operator, I want the wiki as **atomic markdown notes with frontmatter and `[[wikilinks]]` plus a `MEMORY.md` index**, so that it reads the same as my existing memory system.
43. As the operator, I want to query the repo with **any LLM I already use** (Claude Code, Obsidian, grep), so that "llm-wiki style" querying needs no custom tooling.
44. As the operator, I want the instance to push using a **per-repo SSH deploy key**, so that a box compromise exposes only this one repo — not my GitHub account.

---

## Implementation Decisions

**Deployment / isolation**
- Second Hermes instance on the same VPS, run as its own container **or** its own systemd service under a dedicated OS user, with its own data directory, port, and Google identity. Existing instance #1 is not modified.
- The two instances share only hardware. Verified headroom at design time: memory 26% used (~6 GB free), disk 17/100 GB. CPU averages ~51% with instance #1 — monitor after launch; upgrade the KVM tier only if it's steady (not spiky).

**Messaging channel**
- WhatsApp via Hermes' unofficial QR-linked session (whatsapp-web.js / Baileys class), consistent with instance #1.
- Assistant runs on a **dedicated physical SIM** number, not my brother's personal number, not a VoIP number.
- WhatsApp "search" is scoped to chats the assistant is actually a member of: its DM with my brother plus 1–2 groups it's added to. No access to my brother's personal WhatsApp account.

**Email**
- MVP: my brother **manually forwards** selected emails to the assistant's own Gmail address. No auto-forward rule, no inbox OAuth, no triage.
- Sending: **draft-and-confirm** — the assistant drafts, my brother replies "YES", then it sends from the assistant's own address. Replies come from the assistant's address (a "send-as him" alias is explicitly deferred).

**Calendar**
- Uses Hermes' native pattern: the assistant creates events on **its own** Google Calendar and **invites** my brother (and his team). No OAuth or delegated access on my brother's Google account. Event creation is confirmed before committing.

**Reminders & scheduling**
- **Resolved capability:** Hermes ships "Scheduled automations — built-in cron with delivery to any platform," and lists "scheduled reports" under WhatsApp. So proactive WhatsApp-on-a-timer is a **configuration of Hermes cron**, not a net-new scheduler build.
- Custom layer on top of cron: **ack-reset + interval learning**. The assistant logs each "done"/ordered event with a timestamp; after 2–3 orders it computes the median gap (~40 days) and auto-arms a recurring reminder scheduled from the last order. Every "done" resets the clock; the interval self-corrects. Snooze supported. Auto-capture is limited to durable items so it never fires on transient chatter.

**Tasks**
- One task list, each task tagged **work** or **personal**. Add / complete / list / filter, all via WhatsApp natural language.

**Persona**
- Hebrew, warm but brief. Short message bubbles, minimal emoji.

**Second brain (memory → GitHub wiki)**
- Scope: **my brother's agent only**, its own **private** repo.
- Content: **curated knowledge** (facts / decisions / preferences), not raw transcripts.
- Format: atomic markdown notes, YAML frontmatter (`type`, `date`, `tags`), `[[wikilinks]]`, foldered by kind (`people/`, `decisions/`, `preferences/`, `tasks/`, `facts/`), `MEMORY.md` index. Mirrors my existing Claude/graphify memory format.
- Capture: **hybrid** — auto-extract durable items + explicit "תזכור ש…" + plain-language correct/delete. Auto-captures write quietly and note it briefly ("שמרתי: …").
- Cadence: **commit + push per memory write/edit**; commit message = the memory summary. Curated volume is low, so no commit spam.
- Storage model: the on-box memory directory **is** the git working copy; the repo is its off-box mirror and audit log. Single writer (this instance) → no merge conflicts.
- Query: my brother via WhatsApp (assistant gains recall for free); I query the raw markdown repo with any LLM. No custom UI.
- Git auth: **per-repo SSH deploy key** (write), stored inside the instance's isolated data dir.
- Consent: I give my brother a plain-language heads-up that the assistant keeps a private memory he and I can read; he has agreed.

**LLM / cost**
- LLM routed via **OpenRouter** (Hermes is model-agnostic): capable model for conversation, cheap model for the memory-worthiness judgment behind a heuristic pre-filter. Prepaid credits act as the spend ceiling (~$10–20/mo target).

**Reliability**
- Instance under systemd/Docker `restart=always`. Dropped WhatsApp session is detected and prompts a re-scan.
- **healthchecks.io dead-man's-switch**: the instance pings an external monitor every few minutes; if pings stop, the monitor alerts **me** (email/Telegram) — external to the box, so it fires even if the whole instance is down. My brother is never expected to notice a failure.

---

## Setup Runbook (do this on the VPS, in order)

> I run these; I have direct access to the box. Ordered so each step de-risks the next.

0. **Scheduling — already resolved.** Hermes' built-in cron handles proactive WhatsApp; nothing to build. When configuring reminders, use Hermes cron + the ack-reset/interval-learning layer.
1. **Enable Hostinger daily backups** ($6/mo) *before* any of my brother's data lands.
2. **Acquire a dedicated physical SIM** for the assistant's WhatsApp number; keep it in a spare phone for the initial QR-link and occasional re-scans.
3. **Provision Hermes instance #2** — separate container / systemd service under its own user, own data dir + port, its own Google (Gmail + Calendar) identity. Do **not** touch instance #1.
4. **Configure the LLM provider** — point instance #2 at OpenRouter; set the conversation model and the cheap memory-judgment model; fund credits to the monthly ceiling.
5. **QR-link the assistant WhatsApp number**; set the Hebrew warm-but-brief persona; add the assistant to the 1–2 groups for search.
6. **Configure email + calendar** — confirm the assistant's own Gmail can send; wire the draft→YES send gate; confirm calendar event creation + invite flow.
7. **Configure reminders & tasks** — Hermes cron for delivery; implement the ack-reset + interval-learning layer; the one tagged task list.
8. **Create the private "second brain" GitHub repo**; generate a per-repo SSH deploy key (write); place it in the instance's data dir; point the on-box memory dir at the repo; enable commit+push per memory.
9. **Wire reliability** — set `restart=always`; register a healthchecks.io check; wire the heartbeat ping + WhatsApp-session-drop alert to me.
10. **Onboard my brother** — he saves the assistant contact; I tell him the assistant's email to forward to and the consent note about memory; he accepts a test calendar invite; run the dog-food reminder end-to-end.

---

## Testing / Acceptance Decisions

Good checks here verify **externally observable behavior** over WhatsApp and in the wiki — not Hermes internals. The single highest-value seam is **the WhatsApp conversation**: nearly every capability is exercised by sending the assistant a message and observing the reply or the resulting side effect (calendar invite, sent email, committed memory file). Test there first.

Acceptance checks:

- **Isolation:** instance #2's data dir/session/Google identity are distinct from instance #1; nothing from my two profiles appears in my brother's assistant, and vice versa.
- **WhatsApp round-trip:** message the assistant → get a Hebrew reply. Add it to a group → ask it to find a message in that group → it answers from group content only.
- **Email:** forward an email → assistant summarizes; ask for a reply draft → it shows a draft and does **not** send until "YES"; after YES, the mail is sent from the assistant's address.
- **Calendar:** ask to schedule → it confirms details → creates the event and I receive an invite that lands on my calendar.
- **Reminder learning:** simulate 3 "ordered" events ~40 days apart → assistant auto-arms a ~40-day reminder; replying "done" resets the clock; snooze defers.
- **Tasks:** add work + personal tasks → "show my work tasks" returns only work ones → complete one → it drops off the list.
- **Second brain:** trigger a durable fact → a new markdown note is committed and pushed to the private repo with a summary commit message; "תזכור ש…" pins a fact; a correction deletes/edits it; asking "מה החלטנו לגבי X?" answers from memory.
- **Reliability:** kill the instance → `restart=always` brings it back; stop the heartbeat → healthchecks.io alerts me; drop the WhatsApp session → I get a re-scan alert.

Prior art: instance #1 (my existing two profiles) is the reference for a working Hermes WhatsApp + Gmail + Calendar + cron configuration; mirror its known-good setup where possible.

---

## Out of Scope

- **Official WhatsApp Business Cloud API** — staying on the unofficial QR-linked session.
- **Reading my brother's real inbox / auto-forward / proactive email triage** — MVP is manual forward only.
- **"Send-as my brother" email alias** — replies come from the assistant's address for now.
- **OAuth/delegated access on my brother's Google account** — calendar works by invite; none needed.
- **Second Hermes on a separate VPS** — same box, isolated instance.
- **Raw transcript archiving** in the second brain — curated knowledge only (raw log is a possible later add).
- **A dedicated web UI for querying the wiki** — query via WhatsApp or any LLM against the repo.
- **Multi-writer / merge handling on the wiki** — single writer by design.
- **Folding my own two profiles into the second brain** — brother's agent only.

---

## Further Notes

- **The one former unknown is closed:** Hermes has built-in cron with delivery to any platform (WhatsApp included), so no scheduler needs to be written. Sources: [Hermes Agent docs](https://hermes-agent.nousresearch.com/docs/), [integrations page](https://hermes-agent.ai/integrations).
- Two design bonuses fell out of confirming the platform: Hermes is **model-agnostic via OpenRouter** (matches the cost decision) and has **persistent memory + self-improving skills**, which is a natural foundation for the second-brain wiki.
- **Consent is a real prerequisite, not a formality:** the second brain turns my brother's distilled life into a repo I can read. He has agreed after a plain-language heads-up. If that ever stops being true, scope my read access down to backup-only.
- **Watch CPU after launch** — the box already averages ~51% on instance #1; a second idle WhatsApp session is mostly RAM, but confirm CPU stays sane before relying on it.
- No build has started — this PRD is the agreed design and the runbook to execute when I'm ready.
