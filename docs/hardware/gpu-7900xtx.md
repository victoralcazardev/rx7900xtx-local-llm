# RX 7900 XTX — hardware, driver and OS

Research notes written before the GPU was installed, since confirmed or superseded by real
measurements. Read this for specs, driver setup and the install-day checklist; read
`docs/measurements/` for what was actually measured on this GPU (throughput, thermals, VRAM).
This doc does not cover llama.cpp build flags — see `docs/ENGINES.md`.

## 1. Specs relevant to inference

From AMD's official product page
([amd.com — RX 7900 XTX](https://www.amd.com/en/products/graphics/desktops/radeon/7000-series/amd-radeon-rx-7900xtx.html)):

- **VRAM**: 24 GB GDDR6, up to 20 Gbps.
- **Memory bandwidth**: up to **960 GB/s** (physical GDDR6 bus). AMD also quotes an "effective
  bandwidth up to 3,500 GB/s" that includes the 96 MB Infinity Cache — **not the number to use for
  a conservative theoretical ceiling**, since it depends on how much of the working set fits in
  that cache.
- **Compute units**: 96 CU, 6,144 stream processors, boost up to 2,500 MHz, 61.4 TFLOPs FP32 peak.
- **AI accelerators**: 192, one per CU pair — the units that run WMMA instructions (below).
- **TBP**: 355 W typical, 800 W minimum recommended PSU.
- **PCIe**: a PCIe 4.0 x16 slot has no bus bottleneck for inference (the relevant transfer in
  `llama-server` is the initial model load and occasional CPU↔GPU traffic, not a constant flow that
  saturates x16 4.0). This is a logical inference from the specs, not a measurement.

### Matrix cores (WMMA) on RDNA3

RDNA3 (gfx1100) adds **WMMA (Wave Matrix Multiply-Accumulate)** instructions, run by each CU's AI
accelerators: 16×16 matrices, FP16/BF16/INT8/INT4 support — AMD documents them as RDNA's equivalent
to Tensor Cores; the ROCm library that exposes them in C++ is **rocWMMA**
([gpuopen.com — Using Matrix Cores of RDNA3](https://gpuopen.com/learn/wmma_on_rdna3/)). Important
caveat: WMMA's theoretical throughput on RDNA3 is the same as the existing DOT instructions already
gave — WMMA is not a throughput jump, it's a more direct way to express the operation for the
compiler. RDNA4 (not relevant here) changed WMMA's VGPR layout and breaks backward compatibility
with RDNA3.

### Theoretical tok/s ceiling by bandwidth (formula, not a measurement)

For a dense model, each generated token in decode requires reading (roughly) all the weights once
from VRAM:

```
tok/s_max ≈ memory_bandwidth / model_size_in_bytes
```

With the physical bandwidth of 960 GB/s and a dense model of ~15 GB:

```
960 GB/s / 15 GB ≈ 64 tok/s (theoretical ceiling, no compute overhead, no KV cache, no Infinity Cache)
```

This is an optimistic upper bound — it ignores matmul compute time, KV cache reads (which grow with
context), and real-world memory efficiency losses (typically 60-85% of the theoretical peak on
modern GPUs). The real number is only known by measuring with `llama-bench` — see
`docs/measurements/`.

## 2. Windows 11

- **gfx1100 is officially supported** by the HIP SDK for Windows, both Runtime and full SDK (the
  ROCm Debugger for Windows is the only piece not available for this GPU)
  ([rocm.docs.amd.com — Windows system requirements](https://rocm.docs.amd.com/projects/install-on-windows/en/latest/reference/system-requirements.html)).
- **Windows 11 x86-64 is the only officially supported OS**, validated against the 22H2 (GA) update.
  Whether Windows 11 IoT Enterprise LTSC 2024 (build 26100) specifically falls inside that
  validation is **not confirmed** — AMD's docs say "Windows 11" without distinguishing LTSC/IoT SKUs
  from the standard edition.
- **The HIP SDK installer bundles its own display driver**: it installs "AMD Radeon Software PRO"
  (not Adrenalin), with three install modes (Full, Minimal, Driver Only) and requires a reboot. So
  a purely prebuilt HIP-backend llama.cpp build is not guaranteed to just work by copying DLLs next
  to the `.exe` without the SDK — the AMD-supported path installs the full SDK, which installs/
  updates the driver. Whether copying `amdhip64.dll`/`hipblas.dll` etc. next to the executable works
  on a plain Adrenalin driver (no SDK) is plausible (this is how many llama.cpp/koboldcpp AMD
  releases work) but not confirmed by an AMD primary source.
- **Vulkan ships inside the regular driver** (Adrenalin or PRO) — no separate download needed for a
  Vulkan-backend llama.cpp build.
- **hipBLASLt on Windows** is only available from HIP SDK 6.4.2 and only for gfx1101 (RX 7800/7700
  XT), **not gfx1100** — some optimized matmul library paths may not be available on Windows for
  this GPU even though they are on Linux.

## 3. Linux (Arch-based distributions)

- **Kernel driver**: `amdgpu` is in mainline Linux, loads automatically, no extra package needed.
- **Vulkan (Mesa RADV)**: package `vulkan-radeon` (+ `lib32-vulkan-radeon` for 32-bit apps) — no
  proprietary driver needed, just the `amdgpu` kernel driver. Avoid having `amdvlk` installed at the
  same time: it can get injected into the ICD loader and shadow RADV.
- **ROCm packages** are in Arch's official `extra` repo: `rocm-hip-runtime`, `rocminfo`,
  `rocm-smi-lib` (installs the `rocm-smi` binary), plus `hip-runtime-amd`, `rocm-core`, `rocm-llvm`,
  `rocm-cmake` as dependencies. No AUR package needed for the basics.
- **Monitoring tools**: `amdgpu_top` (modern Rust alternative to `radeontop`, TUI + JSON + GUI
  modes) and `rocm-smi` for clocks/power/VRAM from the ROCm side.
- **`power_dpm_force_performance_level`**: sysfs at `/sys/class/drm/card*/device/`. Values: `auto`
  (dynamic), `low`, `high`, `manual` (fine control via `pp_dpm_mclk`/`pp_dpm_sclk`/`pp_dpm_pcie`).
  Write `manual`, then pick a mode via `pp_power_profile_mode` (`BOOTUP_DEFAULT`, `3D_FULL_SCREEN`,
  `POWER_SAVING`, `VIDEO`, `VR`, `COMPUTE`, `CUSTOM`).
- **P-state bug on some `linux-cachyos` kernel builds** (confirmed upstream, with a caveat): a
  known issue on CachyOS's rolling kernel (fixed builds 7.0.11/7.0.12, reported mid-2026) describes
  the RX 7900 XTX getting stuck at the lowest P-state (`sclk` ~227-293 MHz) under ROCm compute load,
  with a task that should take <1s taking ~100x longer. Reported workaround: boot the LTS kernel
  variant instead. The upstream tracker was closed without a fix in that distribution's kernel and
  redirected to an upstream `drm/amd` work item — **not confirmed fixed**; check whether this still
  reproduces on the kernel available at install time, with `rocm-smi --showclocks` under real
  compute load.

## 4. Reading a Windows NTFS partition from Linux (dual-boot)

If model weights live on a Windows partition shared with a dual-boot Linux install:

- **`ntfs3` vs. `ntfs-3g`**: since Linux 5.15 the kernel ships `ntfs3` in-tree (read-write). `ntfs-3g`
  is the classic FUSE userspace driver. Neither is a clear winner; `ntfs3` has no userspace utilities
  of its own (formatting/repair still needs `ntfsprogs` from `ntfs-3g`, or doing it from Windows).
- **Recommended read-only fstab line**:
  ```
  UUID=<volume-uuid>  /mnt/models  ntfs3  ro,uid=1000,gid=1000,umask=022  0  0
  ```
- **Fast Startup / hibernation problem**: Windows Fast Startup (on by default since Windows 8) marks
  the volume as "unsafely" shut down on suspend instead of a clean shutdown, and Linux then refuses
  a read-write mount. Fix: fully shut down/restart Windows (never hibernate/Fast Startup) before
  booting Linux, or mount `ro` to read without touching the journal. `ntfs3` explicitly refuses to
  mount a "dirty" volume without the `force` option — for read-only GGUF access, disabling Fast
  Startup and mounting `ro` is the simple, safe path; avoid `force`.
- **`mmap` on large files**: no primary source found documenting `mmap()` limitations on
  `ntfs3`/`ntfs-3g` for large (15-20 GB) GGUF files. llama.cpp uses `mmap` by default on Linux; test
  directly by loading a large GGUF and confirming it doesn't degrade to swap or fail.

## 5. Install-day checklist

See `docs/sop/install-day.md` for the ordered step list (Windows and Linux).

## Open questions (not resolved by this hardware's measurements either)

- Whether Windows 11 IoT Enterprise LTSC 2024 specifically is covered by AMD's HIP SDK validation.
- Whether a purely prebuilt HIP-backend llama.cpp Windows build works without installing the full
  HIP SDK, on a plain Adrenalin driver.
- Exact feature differences between the Adrenalin and PRO drivers beyond what the HIP SDK installer
  bundles.
- Whether `mmap()` has any practical limitation on `ntfs3`/`ntfs-3g` with large GGUF files — test
  directly rather than assume.
