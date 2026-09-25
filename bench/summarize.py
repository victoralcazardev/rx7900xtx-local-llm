#!/usr/bin/env python3
"""Summarizes res/depth-* folders: throughput, warm turn and process memory (fdinfo) per phase.
Usage: python summarize.py res/depth-A res/depth-B ...  (Markdown output)"""
import json, sys
from pathlib import Path

MIB = 1024 * 1024


def fmt(x, d=0):
    return f"{x:,.{d}f}"


def phases(tel):
    out = {}
    for line in tel.open():
        r = json.loads(line)
        m = r["process"]["bytes_by_metric"]; s = r["safety"]
        f = out.setdefault(r["phase"], {"vram": 0, "gtt": 0, "evicted": 0, "edge": 0, "hot": 0})
        f["vram"] = max(f["vram"], m.get("drm-memory-vram", 0))
        f["gtt"] = max(f["gtt"], m.get("drm-memory-gtt", 0))
        f["evicted"] = max(f["evicted"], m.get("amd-evicted-vram", 0))
        f["edge"] = max(f["edge"], s.get("edge_c") or 0); f["hot"] = max(f["hot"], s.get("hotspot_c") or 0)
    return out


print("| Case | Prompt | pp tok/s | tg tok/s | MTP accept. | Warm: reused / new | warm tg | proc. VRAM max (MiB) | proc. GTT max (MiB) | evicted max | hotspot max |")
print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for d in sys.argv[1:]:
    for case in sorted(Path(d).glob("kv-*")):
        res = case / "result.json"
        if not res.exists():
            print(f"| {case.parent.name}/{case.name} | - no result.json (incomplete or failed) |"); continue
        r = json.loads(res.read_text()); t = r["response_final"]["timings"]
        w = r.get("warm") or {}; wt = w.get("timings", {})
        f = phases(case / "telemetry.jsonl")
        vram = max(x["vram"] for x in f.values()) / MIB; gtt = max(x["gtt"] for x in f.values()) / MIB
        ev = max(x["evicted"] for x in f.values()) / MIB; hot = max(x["hot"] for x in f.values())
        acc = t["draft_n_accepted"] / t["draft_n"] if t.get("draft_n") else None
        warm = f"{fmt(wt['cache_n'])} / {fmt(wt['prompt_n'])}" if wt else (w.get("error", "-")[:40] if w else "-")
        print(f"| {case.parent.name}/{case.name} | {fmt(r['depth_actual'])} | {fmt(t['prompt_per_second'])} | **{fmt(t['predicted_per_second'], 1)}** | "
              f"{fmt(100*acc) if acc is not None else '-'} % | {warm} | {fmt(wt.get('predicted_per_second', 0), 1)} | {fmt(vram)} | {fmt(gtt, 1)} | {fmt(ev)} | {fmt(hot)} °C |")
        per = ", ".join(f"{k}: {fmt(v['vram']/MIB)}" for k, v in f.items())
        print(f"|  ↳ VRAM by phase (MiB) | {per} |||||||||")
