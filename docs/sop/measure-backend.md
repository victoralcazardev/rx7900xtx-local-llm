# SOP: measure Vulkan vs. HIP to decide a model's backend

`AGENTS.md` is explicit: **the backend is decided by measuring with `llama-bench`, not assumed.**
Vulkan supports every K/V mix out of the box and is the documented starting point, but each model
gets compared before `backend` is set in `models.toml`.

## Steps

1. **Run `llama-bench` with both binaries**, same model, same parameter range (full protocol in
   `docs/measurements/engines.md`):
   ```bash
   # Vulkan
   <engine-vulkan>/llama-bench -m <models_root>/<model>.gguf \
       -ngl 999 -fa 0,1 -p 512 -n 128 -d 0,4096,16384 -ctk f16,q8_0 -ctv f16,q8_0 -r 5 -o json > vulkan.json

   # ROCm/HIP
   <engine-hip>/llama-bench -m <models_root>/<model>.gguf \
       -ngl 999 -fa 0,1 -p 512 -n 128 -d 0,4096,16384 -ctk f16,q8_0 -ctv f16,q8_0 -r 5 -o json > hip.json
   ```

2. **For MTP**, `llama-bench` has no `--spec-type`: measure with a real `llama-server`, with and
   without `--spec-type draft-mtp`, in each single-backend binary separately (never a dual binary —
   issue #23199, `docs/measurements/engines.md`).

3. **Compare generation tok/s (`-n 128`) at the context depth you'll actually use** (`-d`), not just
   at `-d 0`: the Vulkan/ROCm gap is not constant across model sizes — see
   `docs/measurements/engines.md` for the measured gap on this GPU.

4. **Record the result in `docs/measurements/engines.md`**: model, backend, `-d`, `-ctk`/`-ctv`,
   prefill/generation tok/s, date, engine version.

5. **Set `backend` in `models.toml`** to the winner. If they're close (<5%), prefer HIP if it's
   already ahead on this system (see `docs/measurements/engines.md` for why), or Vulkan for its
   wider K/V mix support if no build with the mix you need exists yet.

## How to verify

- `docs/measurements/engines.md` has a new row with date and engine version.
- `python3 scripts/check-sync.py` stays OK after changing `backend` in `models.toml`.

## Known errors

- **Quantized `-ctv` without `-fa 1`**: fails with "requires Flash Attention" — expected (see
  `docs/measurements/engines.md`), not a backend fault.
- **Comparing only at `-d 0`**: doesn't represent real long-context use; always include at least one
  `-d` close to the target profile (128K or 200K+).
