# engine-patches

Versioned patches for `scripts/build_engine.py` ([`docs/sop/update-engine.md`](../docs/sop/update-engine.md)).
Each file applies to the base named in its own filename, with `git apply` and **no fuzz**, in the
order given on the command line:

```
python3 scripts/build_engine.py --ref b12633 \
  --patch engine-patches/tests-kvmix-cases-b12633.patch \
  --patch engine-patches/pr30792-q5_1-b12633.patch
```

A patch that does not apply to a newer base stops the build and names the patch and its files;
rebasing it onto the new base is a human job (a worktree, `git apply --reject`, resolve, export
with `git diff`). Never edit a patch that a published engine was built with; add a new file named
after its base instead (`…-b<N>.patch`).

| Patch | Base | What it adds |
|---|---|---|
| `tests-kvmix-cases-b12633.patch` | b12633 | the local FlashAttention op cases for the Qwen3.8 shape (head 256, GQA 6): the `q8_0`/`q5_1` and `q8_0`/`q8_0` eval widths, the tile boundary, KV pad, permuted KV, softcap, long context, and the two agent-depth perf sets |
| `pr30792-q5_1-b12633.patch` | b12633 (PR #30792 rebased) | native `q8_0` KV plus the local `q5_1` V loader in the `flash_attn_tile` kernel, `ne[1] <= 8` guard |

Both are byte-identical copies of the patches under
[`results/20261122-engine-b12633/`](../results/20261122-engine-b12633/README.md), which stay the
measurement record (`docs/STYLE.md` §7): the rebase notes, the op-test log and the SHA256s are
there. Why the build needs `-DGGML_CUDA_FA_QUANTS` at all is in
[`docs/ENGINES.md`](../docs/ENGINES.md).

A patch that changes only files under `tests/` adds no tag to the default engine folder name, so
the pair above yields `llama-b12633-pr30792q51-linux-rocm-gfx1100-kvmix`: the name points at the
kernel patch, not at the test cases.
