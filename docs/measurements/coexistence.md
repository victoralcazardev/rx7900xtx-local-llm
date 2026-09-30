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

### Display-GPU plan for this machine (2026-09-30, not built)

- **Free slot**: the Gigabyte B450 AORUS PRO has one PCIEX4 slot (x16 physical, PCIe 2.0 x4 from
  the chipset). It shares lanes only with PCIEX1_1/PCIEX1_2 (drops to x2 if either is populated),
  not with the M2B socket, which shares with SATA ports 2-3
  ([Gigabyte spec](https://www.gigabyte.com/Motherboard/B450-AORUS-PRO-WIFI-rev-1x/sp)). ~2 GB/s
  is enough for a desktop and only lengthens model load for a compute card.
- **Cards already owned**:
  - **Radeon HD 6450** (TeraScale, ~20 W): keeps the whole stack on AMD/Mesa, but OpenGL only
    (no Vulkan), HDMI 1.4 and H.264-only video decode; marginal for several or 4K monitors.
  - **GTX 1660 SUPER** (Turing, 6 GB, 125 W): stronger display card; the proprietary `nvidia`
    module coexists with `amdgpu` at kernel level, but KWin then needs `KWIN_DRM_DEVICES` to pick
    the display GPU and games need PRIME offload to reach the 7900 XTX. Power: 272 W cap + 65 W
    CPU + 125 W stays well under the 850 W PSU.
  - **GTX 950** (Maxwell): not considered; outside the current NVIDIA driver branch (not verified
    against a release note).
- **Measured 2026-09-30** (KDE Plasma Wayland, two 1920x1080@60 monitors on HDMI + DP, light
  apps: Chrome, Slack, an Electron messenger, Spotify, Telegram): without the model the card uses
  834 MiB of VRAM (+1,228 MiB GTT); with `262k-q8q51-mtp` loaded and an empty context,
  `llama-server` holds 21,716 MiB (fdinfo) of 22,700 MiB used, so the desktop takes ~984 MiB and
  1,860 MiB are free. The launcher expects the profile to reach 22.2 GiB at full context, leaving
  ~0.8 GiB. Per-process `drm-memory-vram` sums (~3.9 GiB) over-count shared buffers; use the
  sysfs `mem_info_vram_used` difference instead.
- **Order**: first measure how much VRAM the desktop takes on the 7900 XTX (fdinfo /
  `amdgpu_top`) with the model loaded; add a display card only if it is more than ~1 GiB or the
  KWin incident recurs. Try the HD 6450 first (same driver stack); move to the 1660 SUPER if the
  desktop is too slow on it.
- **Small-model server on the 1660 SUPER** (separate CUDA or Vulkan `llama-server`, own port,
  `CUDA_VISIBLE_DEVICES` / `GGML_VK_VISIBLE_DEVICES`, 2B-4B GGUF such as MiniCPM5-2B): technically
  fine (~5 GB left after the desktop), but **not pursued**: a 2B model is weak as a coding
  subagent, it cannot act as the 27B's draft (MTP lives inside the main GGUF, same process), and
  cheap hosted models cover summaries/titles/classification at negligible cost without another
  server to maintain. Revisit only for an offline or privacy requirement.

## History

- **2026-09-24**: coexistence test (C1-C3) and the suspend-hang incident both recorded the same day.
  `systemd-inhibit` wrapper added to the launcher immediately after the incident.
- **2026-09-29**: KWin session-loss incident at 262K recorded; the "nobody crashes" conclusion
  corrected to cover the compositor, and display-headroom options evaluated.
