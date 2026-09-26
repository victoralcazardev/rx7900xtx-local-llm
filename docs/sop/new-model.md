# SOP: add a new model to the manifest

## Steps

1. **Check the vendor's model card on Hugging Face first**, even if another quant of the same
   family is already configured. That's where recommended sampling, native context, thinking
   format, and any variant-specific requirement come from (`AGENTS.md` rule: "what the vendor
   doesn't say, don't set").

2. **Read the GGUF's local metadata** (architecture, MTP, cheap/expensive KV, recorded sampling):
   ```
   python scripts/gguf_info.py <models_root>/<file>.gguf
   ```
   Compare against the card: if they disagree, the card wins, and the discrepancy gets a comment in
   `models.toml`.

3. **Add the entry in `models.toml`**: `gguf` (path relative to `models_root`), `backend` (`hip` or
   `vulkan`, decided with `docs/sop/measure-backend.md` if there's no prior data), `sampling` (only
   the keys the vendor sets explicitly), `mtp`, `mmproj` if applicable, and at least one profile
   under `[models.<alias>.profiles.<name>]` with `context` and `kv`.

4. **Find the real max context** with `--fit` (don't guess, don't copy from
   `docs/models/qwen38-27b-quants.md` §3, which is unmeasured arithmetic):
   ```
   <engine>/llama-server -m <gguf> --port 8080 -ctk q8_0 -ctv q8_0 -fa on --fit on --fit-target 400
   ```
   Read the log line `context size reduced from X to Y` (or its absence, if the requested context
   fit). Set `context` in the profile to the real value.

5. **Smoke-test the new profile**:
   ```
   python scripts/smoke.py <alias> --profile <profile>
   ```

6. **Harness wiring**: usually nothing to change — the two fixed providers (`local-128k`,
   `local-262k`) don't depend on the alias. Only touch harness config if the family uses a thinking
   format other than `<think>`/channels already covered (check `tokenizer.chat_template` with
   `gguf_info.py`) — document it in `AGENTS.md` before changing anything.

## How to verify

- `python scripts/check-sync.py` reports no PROBLEM for the new alias (a WARNING is fine if the
  backend's engine isn't configured yet).
- `python scripts/launch.py <alias> --profile <profile> --dry-run` prints the expected command.
- `python scripts/smoke.py <alias> --profile <profile>` answers with real content.

## Known errors

- **`context < 131072`**: this batch is long-context only; a profile below 128K is rejected unless
  it's an explicit test manifest with a low-context override — never in `models.toml`.
- **`general.file_type` doesn't match the filename**: happens with GSQ-RCO (each tensor has its own
  quantization type, see `docs/models/qwen38-27b-quants.md` §1). Not a script bug — the card and the
  filename are the correct source.
- **MTP not available**: only GGUFs with `nextn_predict_layers` in metadata can use
  `--spec-type draft-mtp` (`mtp = true` in the TOML). Check with `gguf_info.py` before setting
  `mtp = true` blindly.
