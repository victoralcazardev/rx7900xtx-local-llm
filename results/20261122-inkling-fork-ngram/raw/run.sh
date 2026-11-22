#!/usr/bin/env bash
# Fork + n-gram self-speculation (the playbook's "copy proposals" analogue) vs. none, temp 0, 32K depth.
set -u
cd ~/IA/rx7900xtx-local-llm/bench
export IA_BENCH_INHIBITED=1 BENCH_EXPECT_POWER_CAP_W=272
export BENCH_SERVER=~/IA/Motores/llama-inkling-rdna3-cb0e46960-linux-rocm10-gfx1100-kvmix/llama-server
export BENCH_MODEL=~/IA/Modelos/Inkling-2-Mini-Uncensored-Abiray/Inkling-2-Mini-Uncensored-IQ4_NL.gguf
export BENCH_WIKI=~/ia-bench/wikitext-2-raw/wiki.train.raw
export BENCH_OUT=~/IA/rx7900xtx-local-llm/_tmp/maya/ngram
mkdir -p "$BENCH_OUT"
for spec in none ngram-map-k4v ngram-mod; do
  extra=""; [ "$spec" != none ] && extra="--spec-type $spec"
  python3 spec_depth_bench.py --run --depth 32000 --kv q8_0 --kv-k q8_0 --variants none --reps 2 --tag "inkling-$spec" --extra "$extra"
done
echo done
