#!/usr/bin/env python3
"""List prompt-cache misses in one omp harness session file.

Usage: session_misses.py <session.jsonl> [--since-ms EPOCH_MS] [--provider local-262k]

A miss is an assistant turn whose uncached input (`usage.input`) exceeds 8,000 tokens.
For each miss it prints the local time, uncached input, cache read, the previous turn's
depth, time to first token and whether a compaction happened since the previous turn.
"""
import argparse
import datetime
import json

p = argparse.ArgumentParser()
p.add_argument("session")
p.add_argument("--since-ms", type=int, default=0)
p.add_argument("--provider", default="local-262k")
a = p.parse_args()

turns = out = uncached = cached = 0
ttft_s = 0.0
prev_depth = None
compacted = False
for line in open(a.session):
    d = json.loads(line)
    if d.get("type") == "compaction":
        compacted = True
        continue
    m = d.get("message", {})
    if d.get("type") != "message" or m.get("role") != "assistant" or m.get("provider") != a.provider:
        continue
    if m["timestamp"] < a.since_ms:
        continue
    u = m["usage"]
    turns += 1
    out += u["output"]
    uncached += u["input"]
    cached += u["cacheRead"]
    ttft_s += (m.get("ttft") or 0) / 1000
    if u["input"] > 8000:
        t = datetime.datetime.fromtimestamp(m["timestamp"] / 1000).strftime("%H:%M")
        print(f"{t} uncached={u['input']} cacheRead={u['cacheRead']} prev_depth={prev_depth} "
              f"ttft_s={round((m.get('ttft') or 0) / 1000)} compaction_before={compacted}")
    prev_depth = u["input"] + u["cacheRead"]
    compacted = False

print(f"turns={turns} output={out} uncached={uncached} cacheRead={cached} ttft_s={round(ttft_s)}")
