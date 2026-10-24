# SOP: add a new model to the manifest

## Steps

1. **Check the vendor's model card on Hugging Face first**, even if another quant of the same
   family is already configured. That's where recommended sampling, native context, thinking
   format, and any variant-specific requirement come from (`AGENTS.md` rule: "what the vendor
   doesn't say, don't set").

2. **Read the GGUF's local metadata** (architecture, MTP, cheap/expensive KV, recorded sampling):
   ```
   python3 scripts/gguf_info.py <models_root>/<file>.gguf
   ```
   Compare against the card: if they disagree, the card wins, and the discrepancy gets a comment in
   `models.toml`.

3. **Add the entry in `models.toml`**: `gguf` (path relative to `models_root`), model-level
   `backend` (`hip` or `vulkan`, decided with `docs/sop/measure-backend.md` if there's no prior
   data), `sampling` (only the keys the vendor sets explicitly), `mtp`, `mmproj` if applicable,
   and at least one profile under `[models.<alias>.profiles.<name>]` with `context` and `kv`.
   An optional profile-level `backend` overrides the model-level backend when that profile needs
   another engine; use `hip-kvmix` for asymmetric-KV profiles that need its additional
   FlashAttention kernels.

4. **Find the real max context** with `--fit` (don't guess, don't copy from
   `docs/models/qwen38-27b-quants.md` §3, which is unmeasured arithmetic):
   ```
   <engine>/llama-server -m <gguf> --port 8080 -ctk q8_0 -ctv q8_0 -fa on --fit on --fit-target 400
   ```
   Read the log line `context size reduced from X to Y` (or its absence, if the requested context
   fit). Set `context` in the profile to the real value.

5. **Smoke-test the new profile**:
   ```
   python3 scripts/smoke.py <alias> --profile <profile>
   ```

6. **Harness wiring**: the project has exactly one fixed provider, `local-262k`, for
   `context = 262144` (see `AGENTS.md`). Do not add a provider for another model or profile.
   `scripts/launch.py` prints `local-262k` for the supported context and reports no harness
   provider for any other context. Only touch harness config if the family uses a thinking format
   other than `<think>`/channels already covered (check `tokenizer.chat_template` with
   `gguf_info.py`) — document it in `AGENTS.md` before changing anything.

## Qwen4 day-one checklist

Prepared 2026-10-23, before release (the Hugging Face API query `models?author=Qwen&search=Qwen4`
returned no models that day). Run in
order; each step's evidence goes where [`../STYLE.md`](../STYLE.md) §8 says. Gate for adoption:
[`../ENGINES-EXPERIMENTS.md`](../ENGINES-EXPERIMENTS.md#current-plan-2026-10-18) C1.

1. **Card** (steps 1-2 above): record architecture, total/active params, native context, attention
   layout (full, linear, sliding window or other), head dim, KV heads, MTP head
   (`nextn_predict_layers`), sampling and thinking format. Take these from the card, not from an
   earlier Qwen model.
2. **Engine support**: `llama-server -m <gguf>` on the current `hip-kvmix` build. If it fails to
   load, build the newest upstream release with the same recipe ([`../ENGINES.md`](../ENGINES.md)), and
   check whether the local `pr30792-q5_1.patch` still applies; without it, expect the pre-2026-10-23
   decode speed with quantized KV.
3. **FA shape check**: the native `q8_0`/`q5_1` TILE path was measured only at head dim 256, GQA 6.
   For another shape, run `test-backend-ops test -b ROCm0 -o FLASH_ATTN_EXT` filtered on the new
   `hsk`/`nh`/`nr23` before trusting quantized KV speed.
4. **Fit at 262K**: step 4 above with `-ctk q8_0 -ctv q5_1` and with `q8_0`/`q8_0`; hybrid or linear
   attention layers keep little KV, so `q8/q8` (or `f16`) may fit where it did not for the 27B.
5. **Quality**: KV KLD vs. `f16` (`llama-perplexity --kl-divergence`, method in
   [`../measurements/kv-quality.md`](../measurements/kv-quality.md)), then the coding suite
   (`bench/coding_suite.py --run`, `--compare` with the 27B baseline).
6. **Speed**: `bench/spec_depth_bench.py --run --depth 240000 --variants none n3-map --reps 3
   --extra "-ub 256"`; add `n4-map` only if acceptance at n=3 is above ~0.85.
7. **A MoE that does not fit in 24 GB** (e.g. a Flash size): first `-ngl all --n-cpu-moe N` on
   llama.cpp with N from `--fit on`, then the same plus `--moe-cache-mib` (b11718+: a GPU cache for the
   experts kept on the CPU, default 0) as the A/B arm; Strata only after that, per [`strata.md`](strata.md).

## How to verify

- `python3 scripts/check-sync.py` reports no PROBLEM for the new alias (a WARNING is fine if the
  backend's engine isn't configured yet).
- `python3 scripts/launch.py <alias> --profile <profile> --dry-run` prints the expected command.
- `python3 scripts/smoke.py <alias> --profile <profile>` answers with real content.

## Known errors

- **`context < 131072`**: this batch is long-context only; a profile below 128K is rejected unless
  it's an explicit test manifest with a low-context override — never in `models.toml`.
- **`general.file_type` doesn't match the filename**: happens with GSQ-RCO (each tensor has its own
  quantization type, see `docs/models/qwen38-27b-quants.md` §1). Not a script bug — the card and the
  filename are the correct source.
- **MTP not available**: only GGUFs with `nextn_predict_layers` in metadata can use
  `--spec-type draft-mtp` (`mtp = true` in the TOML). Check with `gguf_info.py` before setting
  `mtp = true` blindly.
