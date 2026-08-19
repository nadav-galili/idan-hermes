# Hosting reset: cheapest box for two Hermes instances + Hebrew STT

Resolves [idan-hermes#10](https://github.com/nadav-galili/idan-hermes/issues/10). Researched 2026-08-19. Prices are current as of that date.

## Workload sizing

- **Two Hermes Agent instances** (instance #1 with two profiles + instance #2): Node/Python processes, each holding a persistent Baileys-class WhatsApp websocket. Steady-state ~400–800 MB RAM each, low CPU. Two instances comfortably fit in ~2 GB RAM + OS overhead.
- **Hebrew STT (ivrit-ai faster-whisper, CTranslate2, CPU)**: this dominates sizing *if run on-box*. The ivrit-ai `whisper-large-v3-turbo-ct2` model at int8 needs roughly **3 GB free RAM** while loaded and wants 2–4 dedicated vCPUs to transcribe near real-time. On-box STT therefore means an **8 GB / 4 vCPU** box; off-box STT lets a **4 GB / 2 vCPU** box carry everything.
- Volume assumption: **10–30 voice notes/day × ~30 s = 5–15 audio-min/day ≈ 2.5–7.5 audio-hours/month.** This is tiny — it matters a lot for the on-box vs API decision below.

## VPS comparison (August 2026 pricing)

Note: **Hetzner raised prices ~30–37% on 15 June 2026** (CX22→CX23 generation); older price references are stale. Hetzner prices below are **excl. VAT and excl. IPv4** (primary IPv4 is ~€0.60/mo extra; German VAT +19% if billed privately, net if you have a VAT ID).

| Provider | Plan | vCPU / RAM / disk | €/mo | Notes |
|---|---|---|---|---|
| Contabo | Cloud VPS 4 | 4 / 8 GB / 100 GB SSD | **€5.40** | Intro rate for first 24 months; EU (Nuremberg). Historically variable performance/support reputation; no setup fee currently shown |
| Hetzner | CX23 (x86) | 2 / 4 GB / 40 GB NVMe | **€5.49** + VAT + IPv4 (~€6.1 net, ~€7.2 incl. 19% VAT) | Post-June-2026 price; excellent reliability, hourly billing |
| netcup | VPS 500 G12 | 2 / 4 GB / 128 GB NVMe | **€5.91 incl. VAT** | No setup fee, no minimum term option, hourly billing possible; big disk |
| Hetzner | CAX11 (ARM) | 2 ARM / 4 GB / 40 GB | €5.99 + VAT/IPv4 | ARM64: Baileys/Node fine; CT2 has aarch64 wheels but CPU STT noticeably slower — ARM only makes sense with off-box STT |
| OVH | VPS-1 | 2 / 4 GB / 40 GB NVMe | ~€4.5–5.5 (listed $4.54) | EU regions; includes daily backup; promo-ish first-term pricing |
| OVH | VPS-2 | 4 / 8 GB / 75 GB NVMe | ~€8–9 (listed $8.50) | |
| Hetzner | CX33 (x86) | 4 / 8 GB / 80 GB NVMe | €8.49 + VAT/IPv4 (~€9.1 net) | The on-box-STT-capable Hetzner tier post price hike |
| netcup | VPS 1000 G12 | 4 / 8 GB / 256 GB NVMe | **€10.37 incl. VAT** | All-inclusive price, German DC |
| Hetzner | CAX21 (ARM) | 4 ARM / 8 GB / 80 GB | €10.49 + VAT/IPv4 | Post-hike; no longer a bargain |
| Hostinger | KVM 1 | 1 / 4 GB / 50 GB NVMe | $6.49 promo → **$11.99 renewal** | Renewal is what matters — the user already canceled KVM 2 over this |
| Hostinger | KVM 2 | 2 / 8 GB / 100 GB NVMe | $8.99 promo → **$14.99 renewal** (~€13.8) | Confirmed: not competitive at renewal; resubscribing not recommended |

## STT: on-box vs API

### Hosted API options (Hebrew-capable)

| Service | Model | Price | Cost at 2.5–7.5 h/mo |
|---|---|---|---|
| **ivrit-ai on RunPod serverless** | ivrit-ai Hebrew-fine-tuned whisper (official `ivrit-ai/runpod-serverless` image, one-click deploy from RunPod Hub) | ~**$0.03/audio-hour** (16 GB GPU worker, $0.00016/s, pay-per-use, scales to zero) | **~$0.08–0.23/mo** |
| Groq | whisper-large-v3-turbo | $0.04/audio-hour (10 s min billing per request) | ~$0.10–0.30/mo (30 s notes bill fine) |
| Groq | whisper-large-v3 | $0.111/audio-hour | ~$0.28–0.83/mo |
| OpenAI | gpt-4o-mini-transcribe | $0.003/min | ~$0.45–1.35/mo |
| OpenAI | whisper-1 / gpt-4o-transcribe | $0.006/min | ~$0.90–2.70/mo |

Hebrew quality: the **ivrit-ai fine-tune is the best available for Hebrew** (it exists precisely because vanilla Whisper underperforms on Hebrew); Groq/OpenAI large-v3 is decent, turbo somewhat worse on Hebrew. The killer fact: ivrit-ai's *own* recommended deployment is a RunPod serverless endpoint — so you can keep the exact same model you'd run on-box, hosted, for **well under $1/month** at this volume, including cold-start overhead. (Cold starts add a few seconds of latency per note; acceptable for voice-note transcription.)

### The math verdict

At 2.5–7.5 audio-hours/month, API STT costs **€0.1–2.5/mo** while on-box STT forces the jump from a 4 GB box (~€5.5–6) to an 8 GB box (~€5.4–10.4). Off-box STT is therefore **at worst cost-neutral and usually cheaper**, removes the CPU-sizing constraint entirely, keeps voice notes transcribing fast even while both Hermes instances are busy, and (via RunPod) sacrifices zero Hebrew quality. The only argument for on-box is "no external dependency / no audio leaves the box" — and Contabo's 8 GB at €5.40 makes that nearly free too, if you trust Contabo.

## Recommendations (ranked)

### 1. Hetzner CX23 + ivrit-ai on RunPod serverless — ~€6.5–7.5/mo total
- **Box:** Hetzner CX23 (2 vCPU, 4 GB, 40 GB NVMe, Falkenstein/Nuremberg) — €5.49 net + IPv4 ~€0.60 (+19% VAT unless VAT-registered).
- **STT:** official ivrit-ai RunPod serverless endpoint, ~$0.03/audio-hour ⇒ <$0.25/mo at expected volume.
- **Why #1:** Hetzner's reliability is exactly what two persistent WhatsApp sessions need (Baileys sessions hate flaky hosts/network); 4 GB is plenty for both instances without STT; best-in-class Hebrew STT quality at negligible cost. Total ≈ €6.5–7.5/mo, mid-target-range.

### 2. Contabo Cloud VPS 4, everything on-box — €5.40/mo total
- **Box:** 4 vCPU, 8 GB, 100 GB SSD, Nuremberg. Intro price locked for 24 months.
- **STT:** ivrit-ai faster-whisper CT2 (int8) on-box; 8 GB fits model + both Hermes instances; 4 vCPU transcribes a 30 s note in a few seconds.
- **Why #2:** cheapest absolute total, fully self-contained, no external API and no audio leaving the box. Trade-off: Contabo's historical reputation for oversold nodes and slow support — a real risk for always-on WhatsApp sessions. Mitigate with monitoring + session backup.

### 3. netcup VPS 1000 G12, everything on-box — €10.37/mo total (incl. VAT)
- **Box:** 4 vCPU, 8 GB, 256 GB NVMe, German DC, no setup fee, monthly cancelable option.
- **STT:** on-box ivrit-ai faster-whisper, same as #2.
- **Why #3:** the "German-quality, all-inclusive, self-contained" option. More trustworthy than Contabo, cheaper than Hetzner CX33 (+VAT/IPv4) for the same 8 GB class, huge disk. Pick this if you want on-box STT but won't gamble on Contabo. Still inside the €5–15 target.

### Explicitly not recommended
- **Resubscribing Hostinger:** KVM 2 renews at ~$14.99/mo (~€13.8) for 2 vCPU/8 GB — worse specs-per-euro than every option above; the cancellation was the right call.
- **Hetzner CAX (ARM) tiers:** after the June 2026 price hike they no longer undercut x86, and CPU CT2 inference is slower on ARM. Only viable paired with off-box STT, where CX23 is cheaper anyway.

## Sources
- Hetzner price adjustment (15 June 2026): https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/
- Hetzner CX23/CX33 specs: https://sparecores.com/server/hcloud/cx23, https://sparecores.com/server/hcloud/cx33
- Contabo VPS: https://contabo.com/en/vps/
- netcup VPS: https://www.netcup.com/en/server/vps
- OVH VPS: https://www.ovhcloud.com/en/vps/
- Hostinger KVM: https://www.hostinger.com/vps-hosting
- ivrit.ai API / RunPod serverless: https://www.ivrit.ai/en/api/, https://github.com/ivrit-ai/runpod-serverless
- Groq whisper pricing: https://openrouter.ai/openai/whisper-large-v3-turbo, https://www.cloudzero.com/blog/groq-pricing/
- OpenAI transcription pricing: https://costbench.com/software/ai-transcription-apis/openai-whisper/
