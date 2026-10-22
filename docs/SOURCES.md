# Sources

A catalog of third-party claims and their evidence, with links to relevant local measurements in
`docs/measurements/`. Status labels describe the evidence for the claim, not whether this hardware reproduced it:
**source-checked** means the primary source was read directly; **locally reproduced** means this
repository measured or exercised the claim and links that evidence in "Own test"; **hypothesis**
means not independently established; **refuted** means contradicted by a primary source or local
result; **not applicable** means it does not transfer to this setup. Existing status labels are
legacy: read their evidence qualifier and the separate "Own test" cell; a bare **Verified** does
not claim local reproduction. New or edited rows should use the explicit labels above.

## Where claims live

| File | Contents |
|---|---|
| [`SOURCES-upstream.md`](SOURCES-upstream.md) | Upstream primary sources: llama.cpp issues, PRs and source reads, MTP and speculative decoding, KV and weight quantization, GPU firmware, OS and driver, methodology, harness/API context |
| [`SOURCES-community.md`](SOURCES-community.md) | Community posts, third-party tuning repositories, forks, the awesome-local-ai catalog, and the verify-kernel references behind T29 |
| [`SOURCES-alternatives.md`](SOURCES-alternatives.md) | vLLM on ROCm, HyperQwen and low-bit forks, items not pursued, ideas for future MoE models |

Add a new row to the file whose topic fits. When a section moves, keep its heading below as a one-line pointer so existing links keep working.

## Optimization queue source checks (2026-10-03)

Moved to [SOURCES-upstream.md](SOURCES-upstream.md#optimization-queue-source-checks-2026-10-03).

## Engine / backend

Moved to [SOURCES-upstream.md](SOURCES-upstream.md#engine--backend).

## MTP / speculative decoding

Moved to [SOURCES-upstream.md](SOURCES-upstream.md#mtp--speculative-decoding).

## KV / weight quantization quality

Moved to [SOURCES-upstream.md](SOURCES-upstream.md#kv--weight-quantization-quality).

## GPU firmware, thermals and power

Moved to [SOURCES-upstream.md](SOURCES-upstream.md#gpu-firmware-thermals-and-power).

## OS / driver

Moved to [SOURCES-upstream.md](SOURCES-upstream.md#os--driver).

## Methodology references

Moved to [SOURCES-upstream.md](SOURCES-upstream.md#methodology-references).

## Agent harness / API compatibility (context only)

Moved to [SOURCES-upstream.md](SOURCES-upstream.md#agent-harness--api-compatibility-context-only).

## Community claims reviewed 2026-09-26

Moved to [SOURCES-community.md](SOURCES-community.md#community-claims-reviewed-2026-09-26).

## Context length and compaction claims reviewed 2026-09-30

Moved to [SOURCES-community.md](SOURCES-community.md#context-length-and-compaction-claims-reviewed-2026-09-30).

## Third-party tuning repositories reviewed 2026-10-02

Moved to [SOURCES-community.md](SOURCES-community.md#third-party-tuning-repositories-reviewed-2026-10-02).

## cafe-llama.cpp fork and the @quimedesu X thread (2026-10-02)

Moved to [SOURCES-community.md](SOURCES-community.md#cafe-llamacpp-fork-and-the-quimedesu-x-thread-2026-10-02).

## llama.cpp fork survey (2026-10-02)

Moved to [SOURCES-community.md](SOURCES-community.md#llamacpp-fork-survey-2026-10-02).

## awesome-local-ai catalog (2026-10-10)

Moved to [SOURCES-community.md](SOURCES-community.md#awesome-local-ai-catalog-2026-10-10).

## tinygrad-qwen38 fork, verify-kernel references and TurboQuant KV (2026-10-18)

Moved to [SOURCES-community.md](SOURCES-community.md#tinygrad-qwen38-fork-verify-kernel-references-and-turboquant-kv-2026-10-18).

## vLLM on ROCm and HyperQwen (2026-10-03)

Moved to [SOURCES-alternatives.md](SOURCES-alternatives.md#vllm-on-rocm-and-hyperqwen-2026-10-03).

## vLLM ROCm forks and low-bit llama.cpp forks (2026-10-03)

Moved to [SOURCES-alternatives.md](SOURCES-alternatives.md#vllm-rocm-forks-and-low-bit-llamacpp-forks-2026-10-03).

## Not pursued

Moved to [SOURCES-alternatives.md](SOURCES-alternatives.md#not-pursued).

## Ideas for future MoE models (not pursued, 2026-09-29)

Moved to [SOURCES-alternatives.md](SOURCES-alternatives.md#ideas-for-future-moe-models-not-pursued-2026-09-29).
