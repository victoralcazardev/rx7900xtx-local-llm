Raw evidence for ../BUILD.md (2026-11-22). All commands were run from the engine folder
~/IA/Motores/llama-inkling-rdna3-cb0e46960-linux-rocm10-gfx1100-kvmix, GPU otherwise idle,
no llama-server running. ANSI colour escapes were stripped from the logs; nothing else was changed.

commits.txt          git log --oneline b12600..cb0e46960 of the fork (6 commits)
version.txt          ./llama-server --version
devices.txt          ./llama-server --list-devices (ROCm0 only, no Vulkan/CUDA backend)
sha256.txt           sha256sum of the binaries and shared libraries in the engine folder
test-ink-rel-bias-op.log   ./test-backend-ops test -b ROCm0 -o INK_REL_BIAS
test-fa-hsk128.log         ./test-backend-ops test -b ROCm0 -o FLASH_ATTN_EXT -p 'hsk=128'
test-ink-all.log           ./test-backend-ops test -b ROCm0 -o 'INK_.*' (every case the fork adds)
test-ink-rel-bias-bin.log  ./test-ink-rel-bias (fork's own op oracle: CPU chain + FA parity on ROCm0)
