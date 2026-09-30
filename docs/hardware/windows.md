# Windows and NTFS notes for the RX 7900 XTX

Windows-specific driver/HIP SDK notes and the dual-boot NTFS caveats, split out of
[`gpu-7900xtx.md`](gpu-7900xtx.md) (specs, Linux driver notes). Nothing in this repository is
measured on Windows unless a measurement doc says so.

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
