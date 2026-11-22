Raw evidence for ../README.md (2026-11-22).

help-v0.9.0.txt / help-b12633.txt / help-diff.txt are in the parent folder, not here.

test-flash-attn-hsk256-q8_0.log
    Last captured attempt of
    ./test-backend-ops test -b ROCm0 -o FLASH_ATTN_EXT -p 'hsk=256.*type_K=q8_0'
    on the new engine. It is a CRASH log, not a pass: the process dies inside
    libamdhip64.so.7 before the first test case prints. Four earlier runs of the same
    binary and command DID complete with "30/30 tests passed" (console output, summed
    up in ../README.md); no log file survived those runs because the capture file was
    reused by the retry loop.

test-flash-attn-hsk256-q8_0-crash.log
    Another crash capture of the same command (backend load lines only, then SIGSEGV).

test-mul-mat-id.log (= .txt)
    ./test-backend-ops test -b ROCm0 -o MUL_MAT_ID  ->  1077/1077 tests passed.
    Trimmed in place to the head and the summary: the full capture is 1270 case lines.

test-flash-attn-support.log (= .txt)
    ./test-backend-ops support -b ROCm0 -o FLASH_ATTN_EXT  ->  every case SUPPORTED,
    2/2 backends passed. This mode does not upload tensor data, so it does not hit the
    crash. Trimmed in place to the head and the summary: the full capture is 5794
    SUPPORTED case lines.

gdb-backtrace.txt
    gdb captures of the crash: SIGSEGV inside /opt/rocm/lib/libamdhip64.so.7 while
    ggml_backend_cuda_buffer_init_tensor() runs hipMemsetAsync()/its first
    hipStreamPerThread use. Faulting instruction is a host-side vmovdqa to a 32-byte
    misaligned or unmapped address.
