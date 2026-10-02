#!/bin/bash
# Compressed final round (~45 min): build b11301 in parallel with candidate quality, then candidate speed 240K, then llama.cpp A/B 128K.
R="<repo>"; T=$R/_tmp/final; L=$R/bench/res/longctx_quality
M=~/models/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp/Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf
. "$R/results/20260930-kvmem-trial-round2/scripts/build-result.sh"
NEW=~/src/llama.cpp-b11301/build-rocm10/bin; BUILD_BIN=$NEW/llama-server
(
  set -e
  cd ~/src/llama.cpp-b11301
  source ~/src/rocm10-venv/bin/activate
  export ROCM_PATH=$(rocm-sdk path --root) HIP_PATH=$(rocm-sdk path --root) CMAKE_PREFIX_PATH=$(rocm-sdk path --cmake) PATH=$(rocm-sdk path --bin):$PATH
  cmake -B build-rocm10 -S . -DCMAKE_HIP_COMPILER="$(hipconfig -l)/clang" -DCMAKE_BUILD_TYPE=Release \
    -DGGML_BACKEND_DL=ON -DGGML_NATIVE=OFF -DCMAKE_INSTALL_RPATH='$ORIGIN' -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON \
    -DGGML_CPU_ALL_VARIANTS=ON -DGPU_TARGETS=gfx1100 -DGGML_HIP=ON -DHIP_PLATFORM=amd \
    -DGGML_CUDA_FA_QUANTS="f16-f16;bf16-bf16;q8_0-q8_0;q8_0-q5_1;q8_0-q4_1;q4_0-q4_0" > "$T/cmake.log" 2>&1
  cmake --build build-rocm10 -j 10 --target llama-server > "$T/build.log" 2>&1
) &
BP=$!
K=~/engines/kvmem-llama.cpp-src; B=$K/build-hip-linux/bin/llama-kvmem-server
export LD_LIBRARY_PATH=$K/build-hip-linux/lib:$K/build-hip-linux/bin:/opt/rocm/lib
KF="--device ROCm0 -ngl 99 --host 127.0.0.1 --port 8080 -c 262144 -b 512 -n 16384 --kvmem --kvmem-gen-reserve 16384 --kvmem-query-policy user -ctk q8_0 -ctv q8_0 --kvmem-mtp-state replay --spec-type draft-mtp --spec-draft-n-max 2 --kvmem-budget 28672 --kvmem-block-tokens 32"
$B -m $M $KF --temp 0 --top-k 20 --min-p 0 > $T/server-quality.log 2>&1 &
SP=$!
until curl -sf localhost:8080/health >/dev/null; do kill -0 $SP || exit 1; sleep 3; done
timeout 1800 python3 $R/_tmp/kvmem_quality.py --out $T/q-cand.jsonl $L/longctx-20260925-170146/documents/d190000-n00.json $L/longctx-20260926-095911/documents/d220000-n00.json
kill -9 $SP
check_build_result "$BP" "$BUILD_BIN" >> "$T/build.log" || exit $?
sleep 10
python3 $R/_tmp/kvmem_depth.py --label cand-b28k-bt32 --out $T --depths 240000 -- $B -m $M $KF --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --reasoning-effort medium --enable-thinking
unset LD_LIBRARY_PATH
OLD=~/engines/hip-kvmix
$NEW/llama-server --version > $T/version-b11301.txt 2>&1; $NEW/llama-server --help > $T/help-b11301.txt 2>&1; $OLD/llama-server --help > $T/help-b11160.txt 2>&1
sha256sum $NEW/llama-server > $T/sha256-b11301.txt
P="-m $M --port 8080 -c 262144 -ctk q8_0 -ctv q5_1 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 -fa on -np 1 --ctx-checkpoints 4 -ngl all --metrics --spec-type draft-mtp --spec-draft-n-max 3 -ub 256 --reasoning-effort medium"
LD_LIBRARY_PATH=$NEW python3 $R/_tmp/kvmem_depth.py --label b11301 --out $T --depths 128000 -- $NEW/llama-server $P
LD_LIBRARY_PATH=$OLD python3 $R/_tmp/kvmem_depth.py --label b11160-rep --out $T --depths 128000 -- $OLD/llama-server $P
echo DONE
