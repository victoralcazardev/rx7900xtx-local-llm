# Running alongside other GPU applications, and suspend

## Current conclusion

- **The inference server doesn't crash when VRAM runs out — the desktop can.** When a second GPU
  process starts and there's no VRAM left, amdgpu/TTM usually places the newcomer's allocations in
  **GTT (system RAM)** instead of failing. The `llama-server` process keeps its VRAM and keeps
  working, just somewhat slower because it now shares the GPU. **Whichever process arrives late is
  the one that degrades.** In the controlled test below that meant a slow second process; in daily
  use at 262K it has also meant **KWin failing to create a context and quitting, which ends the
  whole Plasma Wayland session** (incident below). The same card drives the display, so the
  desktop needs real VRAM headroom, not just GTT fallback.
- **Mitigations that keep the 262K profile**: disable hardware acceleration in the browser (the
  first allocation to fail in the incident came from a Flatpak GPU client), and avoid GPU-heavy
  applications while the model is loaded. The complete fix is a second, display-only GPU (see
  below).
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

## Incident: VRAM full → KWin quits, session lost (2026-09-29, 20:44)

Setup: `262k-q8q51-mtp` loaded on the ROCm build (IQ3_S-mtp, `-c 262144`, KV `q8_0`/`q5_1`,
MTP n=3, `-ub 256`), with the desktop in normal use. `mem_info_vram_used` afterwards read
**23,332 of 24,560 MiB**, leaving ~1.2 GiB for the compositor and every other GPU client.
CachyOS, kernel 7.2.8, Plasma/KWin 6.7.5 (Wayland), Mesa 26.2.3.

Kernel and user journal, in order:

```
amdgpu 0000:0a:00.0: [drm] *ERROR* Not enough memory for command submission!   (x4, 20:44:22-32)
flatpak[...]: MESA: error: amdgpu: Failed to allocate a buffer:  size: 2097152 bytes
kwin_wayland: Create Context failed "EGL_BAD_MATCH"
kwin_wayland: The used windowing system requires compositing
kwin_wayland: We are going to quit KWin now as it is broken
```

KWin quitting ends the Wayland session: every open application closes and the display returns to
the login screen. `llama-server` itself kept running. Milder episodes (a frozen application, the
same `Not enough memory for command submission` line without a session loss) come from the same
cause. A similar KWin crash from a full VRAM pool on Plasma 6.7.5 was reported with LM Studio
([lmstudio-bug-tracker #2425](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/2425)).

Check for recurrences with `journalctl -b -k | grep "Not enough memory"`.

→ **Rule: at 262K on a single card that also drives the display, keep GPU-heavy desktop use to a
minimum.** Lowering context or quantizing the KV further would free VRAM but was rejected: 262K
with `q8_0`/`q5_1` stays the chosen quality/context trade-off.

### Options evaluated (not measured)

- **Browser hardware acceleration off**: free and reversible; costs some CPU and desktop
  smoothness. First step.
- **A second, display-only GPU**: moves the compositor off the 7900 XTX so the full 24 GiB is
  available to the model. The CPU on this machine (Ryzen 7 5700X) has no integrated graphics, so
  this needs a card in a second PCIe slot. Prefer an AMD card, so the whole stack stays on Mesa and
  amdgpu/radeon, instead of mixing NVIDIA and AMD drivers under KWin. An old TeraScale card
  (Radeon HD 5000/6000) works with the `radeon` kernel driver and Mesa r600 (OpenGL ES only, no
  Vulkan); confirm with `eglinfo -B` that the renderer is the card and not `llvmpipe`. Limits: the
  whole desktop, including the browser, renders on the weak card; hardware video decode is H.264
  only; HDMI 1.4 caps 4K at 30 Hz; games need `DRI_PRIME=1` to run on the 7900 XTX.
- **A second NVIDIA card (e.g. GTX 1660 SUPER) to add VRAM for the model**: rejected. Splitting a
  model across AMD and NVIDIA requires a Vulkan build (this setup uses ROCm). `draft-mtp` roughly
  halves prompt processing under a multi-GPU layer split, reported on exactly an RX 7900 XTX + RTX
  4090 pair ([llama.cpp #27428](https://github.com/ggml-org/llama.cpp/issues/27428), open). A
  Vulkan multi-GPU slowdown against a single GPU was also reported in
  [#16767](https://github.com/ggml-org/llama.cpp/issues/16767) (closed). `-devd` only places a
  **separate** draft model; MTP heads live inside the main GGUF, so it doesn't apply. The only real
  use would be a second, independent small-model server.

## History

- **2026-09-24**: coexistence test (C1-C3) and the suspend-hang incident both recorded the same day.
  `systemd-inhibit` wrapper added to the launcher immediately after the incident.
- **2026-09-29**: KWin session-loss incident at 262K recorded; the "nobody crashes" conclusion
  corrected to cover the compositor, and display-headroom options evaluated.
