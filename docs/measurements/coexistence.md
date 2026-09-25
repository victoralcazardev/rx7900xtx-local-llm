# Running alongside other GPU applications, and suspend

## Current conclusion

- **Nobody crashes when VRAM runs out.** When a second GPU process starts and there's no VRAM left,
  amdgpu/TTM places the newcomer's allocations in **GTT (system RAM)** instead of failing. The
  `llama-server` process keeps its VRAM and keeps working, just somewhat slower because it now
  shares the GPU. **Whichever process arrives late is the one that degrades** — with a browser, the
  expected symptom is a choppy video, not a crashed inference server.
- **Never suspend the machine with a model loaded**: with ~22 GB in use by a ROCm process, a
  suspend attempt hung the entire machine (incident below). `launch.py` now wraps the server in
  `systemd-inhibit --what=sleep:idle --mode=block` (works without sudo) specifically to prevent this.
  If you start the server by hand, do the same.

## Coexistence test

Method: main server (IQ3_S-mtp) with a full context, generating 3,000 tokens. 25 s in, a **second
Vulkan process** starts (Qwen3.5-2B Q8_0, 16K context, ~2-3 GB — the same graphics path a browser
uses) and answers one request. VRAM and GTT are sampled every second, plus `journalctl -k`.

| Case | Full context | Main tg (alone → with 2nd process) | 2nd process | Peak VRAM | Peak GTT | Errors |
|---|---:|---|---|---:|---:|---|
| C1: 262K q8/q5_1 + MTP, no vision | 182K | 25.4 → **21.5** | 10.6 tok/s (slow) | 24,463 MiB | 2,358 MiB | none |
| C2: 262K q8/q8, no MTP, no vision | 182K | 19.3 → **17.7** | 11.7 tok/s (slow) | 23,801 MiB | 2,204 MiB | none |
| C3: 128K q8/q8 + MTP + vision | 104K | 30.7 → **32.6** | **93.4 tok/s** (normal) | 22,859 MiB | 1,246 MiB | none |

(Reference: at idle, GTT ≈ 460 MiB.)

- With 128K there's enough spare VRAM for another ~2-3 GB application with no penalty (C3: the
  second process runs at full speed, and the main server's tg is unaffected — the slight increase is
  noise).
- With 262K, the main server keeps running with only a modest slowdown (C1: −15%, C2: −8%), and the
  second process is what takes the hit (falling to ~11 tok/s from ~93).
- Test limitation: the second process is Vulkan compute, not a real browser doing VA-API video
  decode. **Pending: repeat with real YouTube playback.**

## Incident: suspend with VRAM full → hang (2026-09-24, 20:12)

With the ROCm server using ~22 GB during a test, KDE suspended the machine on idle timeout
(`PrepareForSleep`). In that same second the lock screen crashed
(`kwin_wayland: Greeter Process ... Crashed`), and on resume (21:31:45) the system hung (the log ends
there). On suspend, amdgpu has to evict VRAM to system RAM; with 22 GB in use by a ROCm process and
RAM under pressure, it couldn't complete that in time.

→ **Rule: never suspend with a model loaded.** `launch.py` wraps the server in
`systemd-inhibit --what=sleep:idle --mode=block`.

## History

- **2026-09-24**: coexistence test (C1-C3) and the suspend-hang incident both recorded the same day.
  `systemd-inhibit` wrapper added to the launcher immediately after the incident.
