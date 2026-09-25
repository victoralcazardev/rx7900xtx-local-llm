# SOP: RX 7900 XTX install day

Canonical step list, for both a Linux-only machine and a Windows dual-boot setup. See
`docs/hardware/gpu-7900xtx.md` for the background detail and sources behind each step (specs,
driver notes, the P-state bug, the NTFS mount caveats).

## Windows (if dual-booting)

1. Uninstall the NVIDIA driver from "Apps & features" and reboot, before installing the AMD card.
2. Install the AMD driver: **PRO** if you'll use the HIP SDK (the SDK installer installs it), or
   plain Adrenalin if only using Vulkan for now.
3. Verify Vulkan: `vulkaninfo --summary` must list the RX 7900 XTX.
4. If installing the HIP SDK: verify with `hipInfo` that it detects `gfx1100`, and that
   `amdhip64.dll`/`hipblas.dll`/`rocblas.dll` are on PATH.
5. Disable Fast Startup (Control Panel → Power Options) before using Linux in dual boot — needed
   for Linux to mount a shared Windows partition without corruption.

## Linux

1. Confirm the kernel build (rolling vs. LTS) depending on whether the P-state bug described in
   `docs/hardware/gpu-7900xtx.md` §3 still reproduces that day — try both if in doubt, checking with
   `rocm-smi --showclocks` under real compute load.
2. Uninstall NVIDIA packages (`nvidia`, `nvidia-utils`, `nvidia-settings`, `lib32-nvidia-utils`),
   confirm `nvidia-drm.ko` isn't loading, regenerate the initramfs.
3. Install `vulkan-radeon` + `lib32-vulkan-radeon`; confirm **no** `amdvlk` in parallel.
4. Install `rocm-hip-runtime rocminfo rocm-smi-lib` if using HIP on Linux.
5. Add the user to the `render` and `video` groups, re-login.
6. Verify: `vulkaninfo --summary` lists the 7900 XTX; `rocminfo | grep "Marketing Name"` returns the
   GPU name; `amdgpu_top`/`rocm-smi` show clocks ramping under load (this is where the P-state bug
   would show up if still present).
7. Mount a shared Windows partition read-only via `ntfs3` (fstab line in
   `docs/hardware/gpu-7900xtx.md` §4) **after** confirming Windows shut down cleanly (no Fast
   Startup/hibernation) at least once.

## First smoke test (once a Vulkan or HIP binary is installed)

1. Copy `local.example.toml` to `local.toml` if it doesn't exist yet, and set the real engine path
   for the backend you have under `[engines]`.
2. Run the smoke test for the reference model/profile:
   ```
   python scripts/smoke.py qwen38-iq3s-mtp --profile 262k-q8q8
   ```
3. If it answers with real content and tok/s, continue with the rest of the ladder in
   `docs/models/qwen38-27b-quants.md` §6 (`262k-q8q8-mtp`, `262k-q8q51-mtp`, ...).

## How to verify

- Each section's verification step (`vulkaninfo`, `hipInfo`, `rocminfo`) gives the expected result
  before moving to the next.
- `python scripts/check-sync.py` stops warning "no engine" for the backend you just installed.
- The final smoke test returns `OK` or `OK*` (not `FAILED`).

## Known errors

- **CachyOS/rolling-kernel Linux loses tok/s abnormally**: try the LTS kernel first (known P-state
  bug on some rolling kernel builds, `docs/hardware/gpu-7900xtx.md` §3).
- **Linux can't see the Windows NTFS partition, or it looks corrupted**: check that Fast Startup is
  really disabled (not just hibernation) and that Windows shut down cleanly before mounting from
  Linux.
- **HIP builds without rocblas/hipblas DLLs**: check the PATH before assuming the whole config is
  broken.
