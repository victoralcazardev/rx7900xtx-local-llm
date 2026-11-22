Raw evidence for ../README.md (Inkling-2-Mini-Uncensored AD-Q4_K, 2026-11-22).

Model: ~/IA/Modelos/Inkling-2-Mini-Uncensored-AD/Inkling-2-Mini-Uncensored-AD-Q4_K.gguf
  sha256 36e99f1f56ca33cb356f19d7e3822938f65af1cde978ad13170238928d4c955f, 16,525,559,776 bytes.
Engines:
  upstream  llama-b12633-pr30792q51-linux-rocm10-gfx1100-kvmix  (build 12633, 9c10c94e1)
  fork      llama-inkling-rdna3-cb0e46960-linux-rocm10-gfx1100-kvmix (build 12606, cb0e46960)
Both engine folders carry the libamdhip64.so.7 symlink to Arch's generic ROCm 10.1 build
(hip-runtime-amd-10.1-2), see docs/sop/install.md "Known errors".

Request (all arms): POST /v1/chat/completions on 127.0.0.1:8090, streamed, one short prompt
(33 tokens: an iterative-Fibonacci "code only" ask), sent twice per arm. Temperature 0 / greedy.

upstream-b12633-fit-262k-q8q51.log
  llama-server ... -c 262144 -ctk q8_0 -ctv q5_1 -np 1 --port 8090 -lv 4, with the --fit step
  active (the log shows the fit projection and offload decision; whether the flag was explicit is
  not recorded). Trimmed: the
  server-init and --fit block, the tensor/KV allocations and the timer summary plus memory
  breakdown; model-load and prompt-cache lines are elided and the elision is marked inline.

upstream-b12633-fit-262k-q8q8-attempt.log, upstream-b12633-fit-262k-q8q51-attempt.log
  The two earlier upstream starts at 262144 (KV q8_0/q8_0 and q8_0/q5_1) that died with
  "graph_reserve: failed to allocate compute buffers" before loading. Verbatim from the job log.

upstream-b12633-64k-f16.log / .json
  llama-server ... -c 65536 -ctk f16 -ctv f16 -np 1 --port 8090 -lv 3; server log and the single
  chat.completion response (usage + timings).

fork-cb0e46960-64k-f16.log / .json        fork, -c 65536, KV f16/f16, two turns.
fork-cb0e46960-262k-q8q8.log / .json      fork, -c 262144, KV q8_0/q8_0, two turns.
fork-cb0e46960-262k-q8q51.log / .json     fork, -c 262144, KV q8_0/q5_1, two turns.
  Each .json is the second (warm-slot) response; the first turn's numbers are in the .log.

Applied to every file: /home/victor replaced by ~ (docs/STYLE.md section 7 allows path
normalisation in raw evidence). No other edit. VRAM figures quoted in ../README.md come from the
runner's per-run readout, not from these logs (the logs are -lv 3, no memory breakdown, for the
fork arms).
