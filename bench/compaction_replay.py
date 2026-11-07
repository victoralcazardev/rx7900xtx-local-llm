#!/usr/bin/env python3
"""Replay the shape of a compacting coding-agent session against a running llama-server.

Synthetic stand-in for a real agent session (cache-sweet-spot plan, steps 3-4), so two server
configurations can be compared on identical traffic. Each epoch:
  - the same system prompt (~28K tokens, the system prompt + tool schemas of omp/Gentle Shell),
  - a growing history of user "tool output" turns (~4K tokens) and the model's short replies,
  - a compaction once the prompt passes 35% of the window: the history is replaced by a new
    summary (~16K tokens), so the next prompt shares only the system prompt with the slot.
The text is deterministic random words, so every run sends the same prompts. Thinking is off and
replies are short: only the prompt cache is measured. Analyze the server log afterwards with
scripts/cache_misses.py; this script prints one CSV row per request (prompt and prefill tokens,
prefill ms from the server's `timings`).

Usage: python3 bench/compaction_replay.py [--port 8080] [--epochs 4] [--ctx 262144]
"""
from __future__ import annotations

import argparse
import json
import random
import time
import urllib.request

SYSTEM_TOKENS, TURN_TOKENS, SUMMARY_TOKENS, REPLY_TOKENS = 28_000, 4_000, 16_000, 32
COMPACT_AT = 0.35
VOCAB = ("cache slot token prompt server model context checkpoint request reply tool file test "
         "build commit branch merge parser config value error output input buffer kernel memory "
         "layer weight batch thread queue index table column row field record schema module "
         "function method class object string number list map set path line word page block").split()


def text(seed: str, tokens: int, tokens_per_word: float) -> str:
    rng = random.Random(seed)
    return " ".join(rng.choice(VOCAB) for _ in range(int(tokens / tokens_per_word)))


def compact(messages: list[dict], summary: str) -> list[dict]:
    """Keep the system prompt byte-identical; replace the whole history with a summary."""
    return [messages[0], {"role": "user", "content": "Summary of the work so far:\n" + summary}]


def post(port: int, path: str, body: dict) -> dict:
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.load(r)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--epochs", type=int, default=4, help="compactions to run")
    ap.add_argument("--ctx", type=int, default=262144, help="window the harness compacts against")
    a = ap.parse_args()
    sample = text("calibrate", 2000, 1.0)
    tpw = len(post(a.port, "/tokenize", {"content": sample})["tokens"]) / len(sample.split())
    messages = [{"role": "system", "content": text("system", SYSTEM_TOKENS, tpw)}]
    epoch, turn = 0, 0
    print("n,epoch,turn,prompt_tokens,prefill_tokens,prefill_ms,wall_s", flush=True)
    while epoch < a.epochs:
        messages.append({"role": "user", "content": text(f"turn-{epoch}-{turn}", TURN_TOKENS, tpw)})
        t0 = time.monotonic()
        r = post(a.port, "/v1/chat/completions", {
            "messages": messages, "max_tokens": REPLY_TOKENS, "temperature": 0,
            "chat_template_kwargs": {"enable_thinking": False}})
        tm, prompt = r.get("timings", {}), r["usage"]["prompt_tokens"]
        print(f"{turn + 1000 * epoch},{epoch},{turn},{prompt},{tm.get('prompt_n')},{tm.get('prompt_ms', 0):.0f},"
              f"{time.monotonic() - t0:.1f}", flush=True)
        messages.append({"role": "assistant", "content": r["choices"][0]["message"]["content"] or ""})
        turn += 1
        if prompt >= COMPACT_AT * a.ctx:
            epoch, turn = epoch + 1, 0
            messages = compact(messages, text(f"summary-{epoch}", SUMMARY_TOKENS, tpw))


if __name__ == "__main__":
    main()
