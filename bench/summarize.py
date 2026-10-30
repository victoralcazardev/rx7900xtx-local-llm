#!/usr/bin/env python3
"""Summarizes res/depth-* folders: throughput, warm turn and process memory (fdinfo) per phase.
Usage: python summarize.py res/depth-A res/depth-B ...  (Markdown output)"""
import json, sys
from pathlib import Path

from depth_bench import overall_peak, telemetry_peaks

MIB = 1024 * 1024


def fmt(x, d=0):
    return "-" if x is None else f"{x:,.{d}f}"


print("| Case | Prompt | pp tok/s | tg tok/s | MTP accept. | Warm: reused / new | warm tg | proc. VRAM max (MiB) | proc. GTT max (MiB) | evicted max | hotspot max |")
print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for d in sys.argv[1:]:
    for case in sorted(Path(d).glob("kv-*")):
        res = case / "result.json"
        if not res.exists():
            print(f"| {case.parent.name}/{case.name} | - no result.json (incomplete or failed) |"); continue
        r = json.loads(res.read_text()); t = r["response_final"]["timings"]
        w = r.get("warm") or {}; wt = w.get("timings", {})
        f = telemetry_peaks(case / "telemetry.jsonl"); peak = overall_peak(f)
        vram, gtt, ev, hot = peak["vram"] / MIB, peak["gtt"] / MIB, peak["evicted"] / MIB, peak["hotspot"]
        acc = t["draft_n_accepted"] / t["draft_n"] if t.get("draft_n") else None
        warm = f"{fmt(wt['cache_n'])} / {fmt(wt['prompt_n'])}" if wt else (w.get("error", "-")[:40] if w else "-")
        print(f"| {case.parent.name}/{case.name} | {fmt(r['depth_actual'])} | {fmt(t['prompt_per_second'])} | **{fmt(t['predicted_per_second'], 1)}** | "
              f"{fmt(100*acc) if acc is not None else '-'} % | {warm} | {fmt(wt.get('predicted_per_second', 0), 1)} | {fmt(vram)} | {fmt(gtt, 1)} | {fmt(ev)} | {fmt(hot)} °C |")
        per = ", ".join(f"{k}: {fmt(v['vram']/MIB)}" for k, v in f.items())
        print(f"|  ↳ VRAM by phase (MiB) | {per} |||||||||")
