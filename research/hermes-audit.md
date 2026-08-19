# Hermes correctness audit — runbook assumptions vs. current docs/source

Resolves [#11](https://github.com/nadav-galili/idan-hermes/issues/11). Audited against:

- Docs: https://hermes-agent.nousresearch.com/docs/ (live, 2026-08-19)
- Source: [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) @ `b2057c16` (HEAD on audit date)

Verdict key: **CONFIRMED** (runbook is right as written) · **CHANGED** (works, but the correct way differs) · **BROKEN** (assumption fails; workaround given).

---

## 1. Plugin hooks `pre_gateway_dispatch` / `post_llm_call` — CONFIRMED (one timing correction, see §2a)

Both hooks exist with the shapes the runbook uses.

**`pre_gateway_dispatch`** — invoked in [`gateway/run.py` ~L16354](https://github.com/NousResearch/hermes-agent/blob/b2057c16856fc01eeb17a40aa65853a68e61b981/gateway/run.py) with kwargs `event`, `gateway`, `session_store`. Fires **before auth/pairing** for user-originated messages only — the gateway itself skips internal events (`event.internal` synthetic events never reach the hook), so the runbook's "skip `event.internal`" guard is redundant-but-harmless. Return contract matches: `{"action":"skip"}` drops, `{"action":"rewrite","text":...}` replaces `event.text`, `{"action":"allow"}`/`None` continues. Docs: [Hooks → pre_gateway_dispatch](https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks#pre_gateway_dispatch).

`MessageEvent` ([`gateway/platforms/base.py` ~L2300](https://github.com/NousResearch/hermes-agent/blob/b2057c16856fc01eeb17a40aa65853a68e61b981/gateway/platforms/base.py)) carries every field the runbook's record schema reads: `message_id` (Optional — hash fallback still needed), `timestamp`, `text`, `message_type`, `media_urls` (**local file paths**, good for copying into `media/`), `media_types`, `reply_to_message_id`, `platform_update_id`, `metadata`. `event.source` is a `SessionSource` ([`gateway/session.py` L149](https://github.com/NousResearch/hermes-agent/blob/b2057c16856fc01eeb17a40aa65853a68e61b981/gateway/session.py)) with `chat_type` ("dm"/"group"/"channel"/"thread"), `chat_id`, `chat_name`, `user_id`, `user_name` — DM/group slugging is supported as assumed.

**`post_llm_call`** — fired in [`agent/turn_finalizer.py` ~L623](https://github.com/NousResearch/hermes-agent/blob/b2057c16856fc01eeb17a40aa65853a68e61b981/agent/turn_finalizer.py) once per successful, non-interrupted turn with `session_id`, `task_id`, `turn_id`, `user_message`, `assistant_response`, `conversation_history`, `model`, `platform`. Return ignored (observer). Matches the runbook's `dir:"out"` logging plan. Docs: [Hooks reference table](https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks).

**Two capture-correctness caveats the runbook must absorb:**

- **(a) Voice transcript timing — the runbook's "voice already Hebrew-transcribed" note on `event.text` is wrong.** Auto-STT runs in `_enrich_message_with_transcription` (gateway/run.py ~L24400+), *after* `pre_gateway_dispatch`. At hook time a voice note's `event.text` is the caption/placeholder, not the transcript. The transcript is folded into the user message later, so it **is** available in `pre_llm_call`/`post_llm_call` via `user_message` (quoted `"transcript"` line). Fix in §Runbook amendments.
- **(b) Pre-auth capture.** The hook deliberately fires before authorization, so a naive capture plugin will log stranger/spam DMs to the SIM into `raw/`. The capture hook should filter to authorized/allowlisted chats.

## 2. `HERMES_LOCAL_STT_COMMAND` with `{language}` templating — CHANGED (works, but use `stt.providers.<name>: type: command` for the off-box wrapper)

The env var exists and templates `{input_path}`, `{output_dir}`, `{language}`, `{model}` ([env-vars reference](https://hermes-agent.nousresearch.com/docs/reference/environment-variables); [`tools/transcription_tools.py` `_transcribe_local_command`](https://github.com/NousResearch/hermes-agent/blob/b2057c16856fc01eeb17a40aa65853a68e61b981/tools/transcription_tools.py)). But two properties make it the wrong vehicle for the remote (RunPod) wrapper:

1. **It does NOT read stdout.** The command must write a `*.txt` transcript into `{output_dir}`; "prints the transcript" fails with "did not produce a .txt transcript".
2. **Child env is scrubbed** (`hermes_subprocess_env(inherit_credentials=False)`) — API keys in the gateway's env may not reach the wrapper.

**The current, better surface** is a named **command provider** — `stt.providers.<name>: type: command`, selected via `stt.provider: <name>` — same file, `_transcribe_command_stt` / `_run_command_stt`:

- Placeholders: `{input_path}`, `{output_path}`, `{output_dir}`, `{format}`, `{language}`, `{model}`.
- **stdout fallback**: if no output file is written, non-empty stdout IS the transcript — curl-style one-liners work.
- **`env_passthrough`**: config list of env var names explicitly forwarded to the child — the clean way to hand the wrapper a `RUNPOD_API_KEY`.
- Configurable idle timeout (progress-based; a slow-but-emitting remote call survives).

So the off-box design from #10 is fully supported: a small script that POSTs the audio to ivrit-ai's RunPod serverless endpoint and prints (or writes) the transcript, wired as a command provider with `language: he`. Local `faster-whisper` remains available as `transcribe_audio_local_fallback` if ever wanted (it isn't, on 2 vCPU).

```yaml
# instance-2 config.yaml
stt:
  enabled: true
  provider: ivrit-runpod
  providers:
    ivrit-runpod:
      type: command
      command: "/opt/idan/bin/ivrit-stt.sh {input_path} {output_path} {language}"
      language: "he"
      format: txt
      timeout: 120
      env_passthrough: [RUNPOD_API_KEY, RUNPOD_ENDPOINT_ID]
```

## 3. Per-profile toolset allowlist: expose `brain_search`, exclude `terminal`/`write_file`/`patch` — CONFIRMED

- Toolsets are the per-platform/per-profile allowlist mechanism; each profile has its own `config.yaml` (`toolsets:` list). Docs: [Toolsets Reference](https://hermes-agent.nousresearch.com/docs/reference/toolsets-reference), [Profiles](https://hermes-agent.nousresearch.com/docs/user-guide/profiles).
- A plugin registers its tool into its own toolset: `ctx.register_tool(name="brain_search", toolset="brain", schema=..., handler=...)` ([Build a Hermes Plugin](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins)). Plugin toolsets are enabled/disabled exactly like built-ins.
- Exclusion works by **not listing** `terminal` and `file`: `terminal` toolset = `terminal`+`process`; `file` toolset = `patch`, `read_file`, `search_files`, `write_file`. Note dropping `file` also drops `read_file`/`search_files` — fine, `brain_search` does its own reading.
- **Do NOT use the `hermes-whatsapp` platform preset** — it equals `hermes-cli` (full toolset incl. terminal/file). List core toolsets explicitly, e.g. `toolsets: [brain, memory, todo, clarify, vision, web]` (or start from `safe` + `brain`). A `custom_toolsets:` bundle in config.yaml can name the combination.
- Plugins are **disabled by default**; add the plugin name to `plugins.enabled` in config.yaml or nothing loads ([Plugins](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins)).

## 4. Built-in cron → proactive WhatsApp sends; FR #22603 status — CONFIRMED (workaround still needed, but it can be simpler)

- Cron delivery to WhatsApp is first-class: `deliver:` targets include `origin`, `whatsapp` (home channel), and explicit `platform:chat_id`; the gateway ticks the scheduler every 60s and runs jobs in isolated agent sessions, delivering the final response itself ([Cron docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron)). **CONFIRMED.**
- **FR [#22603](https://github.com/NousResearch/hermes-agent/issues/22603) (outbound `pre_gateway_text_send` hook) is still OPEN** — two candidate PRs ([#23020](https://github.com/NousResearch/hermes-agent/pull/23020), [#35312](https://github.com/NousResearch/hermes-agent/pull/35312)) exist, neither merged. The hooks doc explicitly states an outbound-delivery hook is deliberately not shipped yet. So the self-logging workaround is **not obsolete**.
- **Correction to the runbook's caveat:** cron turns run `agent.run_conversation` with `platform="cron"` ([`cron/scheduler.py` ~L5582](https://github.com/NousResearch/hermes-agent/blob/b2057c16856fc01eeb17a40aa65853a68e61b981/cron/scheduler.py)), so the brain-capture `post_llm_call` hook **does fire on cron turns** — "proactive cron sends are not caught by the outbound hook" is overstated. Remaining gaps that keep a small workaround alive: the hook payload has no delivery target chat_id, the delivered text gets cron's header/footer wrapper (unless `cron.wrap_response: false`), delivery failures are invisible, and **no-agent (script-only) cron jobs bypass the LLM entirely** and fire no hook.

## 5. Model configuration via OpenRouter — CONFIRMED (single static conversation model per profile is trivially supported)

Per #12 this is informational. Each profile's `config.yaml` sets one main model: `model: {provider: openrouter, default: <model-id>, ...}`; OpenRouter is a first-class provider ([Configuring Models](https://hermes-agent.nousresearch.com/docs/user-guide/configuring-models)). Auxiliary slots (compression, vision, title-gen) can be pinned independently but can be left on defaults. The curation script is standalone and calls OpenRouter directly with the same key, outside Hermes — unaffected.

## 6. Two isolated instances on one box (systemd + separate OS users) — CONFIRMED (supported; RAM fits the CX23 with the browser toolset off)

- Multi-instance on one machine is a documented, supported pattern: [Running Many Gateways at Once](https://hermes-agent.nousresearch.com/docs/user-guide/multi-profile-gateways). The **documented default** is now `hermes profile create <name>` → per-profile systemd **user** services (`hermes-gateway-<name>.service`) under one OS user, isolated via `HERMES_HOME` (config, sessions, memory, state DB, gateway PID, logs, cron all scope to it).
- Separate OS users (the runbook's stronger isolation) still works — `HERMES_HOME` "also scopes the gateway PID file and systemd service name, so multiple installations can run concurrently" ([env-vars reference](https://hermes-agent.nousresearch.com/docs/reference/environment-variables)). Keep it: instance #1 untouched, instance #2 under its own user. If ever consolidating under one user, note host profiles share `$HOME` CLI credentials by default (`terminal.home_mode: profile` opts out).
- **RAM on Hetzner CX23 (2 vCPU / 4 GB):** documented minimums are 1 GB per instance without browser tools, **≥2 GB per instance with the browser toolset active** ([Docker → Resource limits](https://hermes-agent.nousresearch.com/docs/user-guide/docker#resource-limits)). Each WhatsApp instance also runs a persistent Baileys Node bridge ([WhatsApp docs](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/whatsapp)) — Node.js v18+, no Chromium needed. Two instances fit in 4 GB **only with the browser toolset excluded on instance #2** (it is — see §3) and no local whisper. The #10 decision to move STT off-box removed the real RAM risk: `ivrit-ai/whisper-large-v3-turbo-ct2` on CPU would have needed ~2–3 GB peak. Verdict: sized OK; add ~2 GB swap as insurance and keep browser toolsets off.

---

## Runbook amendments (concrete changes to `hermes-brother-runbook.md`)

1. **Phase 0 step 6 — replace the local STT design (off-box, per #10).** Drop `HERMES_LOCAL_STT_COMMAND` + on-box faster-whisper. New text: configure a named command STT provider (`stt.provider: ivrit-runpod`, `stt.providers.ivrit-runpod: {type: command, command: "/opt/idan/bin/ivrit-stt.sh {input_path} {output_path} {language}", language: he, format: txt, timeout: 120, env_passthrough: [RUNPOD_API_KEY, RUNPOD_ENDPOINT_ID]}`). The wrapper POSTs the audio file to ivrit-ai's RunPod serverless endpoint and writes the transcript to `{output_path}` (stdout also accepted). Do not rely on inherited env — the child env is scrubbed; use `env_passthrough`. Gate stays the same: Hebrew voice note → Hebrew transcript, original audio retained.
2. **Phase 1 step 7 — fix the voice-transcript capture path.** `event.text` at `pre_gateway_dispatch` time does **not** contain the transcript (STT runs later in the pipeline). Amend: at `pre_gateway_dispatch`, log the inbound record with the media pointer and raw caption; capture the transcript from `pre_llm_call`/`post_llm_call`'s `user_message` (the transcript appears there as a quoted line) and either update the inbound record or store it on the `dir:"out"` record's meta. Simplest robust shape: key the pending inbound record by `session/turn`, backfill `text` in the `post_llm_call` handler.
3. **Phase 1 step 7 — add an authorization filter.** `pre_gateway_dispatch` fires before auth, so the capture hook must drop events from non-allowlisted senders/chats, or `raw/` will accumulate stranger DMs to the SIM.
4. **Phase 1 step 7 — note the internal-event guard is already done by the gateway** (hook only fires for non-internal events); keeping the plugin-side check is harmless defense.
5. **Phase 3 step 12 — spell out the toolset list.** Don't use the `hermes-whatsapp` preset (it's the full `hermes-cli` set). Explicitly: `plugins.enabled: [brain-capture, brain-search]`, `toolsets: [brain, memory, todo, clarify, web]` (tune), never `terminal`/`file`/`code_execution`/`delegation`/`browser`. Excluding `file` also removes `read_file`/`search_files` — intended.
6. **Phase 5 reminders caveat — soften and correct.** FR #22603 is still open (verified 2026-08-19; PRs #23020/#35312 unmerged), so there is still no outbound send-hook. But `post_llm_call` DOES fire on cron turns (`platform="cron"`), so the existing brain-capture hook already logs agent-mode reminder sends; the extra self-logging is only needed for (a) delivery target/failure metadata and (b) any no-agent (script-only) cron jobs. Consider `cron.wrap_response: false` so the logged response equals the delivered text.
7. **Phase 0 step 3 — keep separate OS users (still supported), and add a RAM note.** Two instances fit the CX23's 4 GB only with browser toolsets off (docs: 1 GB/instance without browser, ≥2 GB with) and STT off-box; add swap as insurance. Each instance runs its own Baileys Node bridge (Node 18+; session under `<HERMES_HOME>/platforms/whatsapp/session` — never commit it).
8. **Open items — one is now answered:** `event.source` cleanly distinguishes DM vs group (`SessionSource.chat_type` ∈ dm/group/channel/thread, plus `chat_id`/`chat_name`), so `wa:group:<slug>` slugging is safe. `message_id` remains Optional on the event — keep the content-hash fallback.
