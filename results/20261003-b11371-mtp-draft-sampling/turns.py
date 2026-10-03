#!/usr/bin/env python3
"""S2b: does the EOG draft fix (#29638) keep the prefix cache across chat turns with MTP?
Starts llama-server (adopted flags, 32K ctx is enough), runs 4 chat turns appending each answer,
and records prompt_n / cache_n per turn from the response timings."""
import json, os, subprocess, sys, time, urllib.request
srv, tag = sys.argv[1], sys.argv[2]
KEEP_REASONING = len(sys.argv) > 3 and sys.argv[3] == "keep"  # send reasoning_content back
MODEL = os.environ["BENCH_MODEL"]
PORT = 18081
cmd = [srv, "-m", MODEL, "--port", str(PORT), "-c", "32768", "-ctk", "q8_0", "-ctv", "q5_1", "-fa", "on",
       "-np", "1", "--ctx-checkpoints", "4", "-ngl", "all", "-ub", "256", "--temp", "1", "--top-p", "0.95",
       "--top-k", "20", "--min-p", "0", "--reasoning-effort", "medium", "--spec-type", "draft-mtp",
       "--spec-draft-n-max", "3"]
log = open(f"server-{tag}.log", "w")
p = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
try:
    for _ in range(300):
        try:
            if json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health")).get("status") == "ok": break
        except Exception: pass
        time.sleep(1)
    msgs = [{"role": "system", "content": "You are a concise coding assistant."}]
    qs = ["Write a Python function that parses an ISO date string and returns a datetime.",
          "Now add error handling for invalid input.", "Add a docstring and type hints.",
          "Write two unit tests for it."]
    for i, q in enumerate(qs, 1):
        msgs.append({"role": "user", "content": q})
        body = json.dumps({"messages": msgs, "max_tokens": 1500, "seed": 42}).encode()
        r = json.load(urllib.request.urlopen(urllib.request.Request(
            f"http://127.0.0.1:{PORT}/v1/chat/completions", body, {"Content-Type": "application/json"}), timeout=600))
        t = r.get("timings", {})
        msg = r["choices"][0]["message"]
        turn = {"role": "assistant", "content": msg.get("content", "")}
        if KEEP_REASONING and msg.get("reasoning_content"):
            turn["reasoning_content"] = msg["reasoning_content"]
        msgs.append(turn)
        print(json.dumps({"tag": tag, "turn": i, "prompt_n": t.get("prompt_n"), "cache_n": t.get("cache_n"),
                          "predicted_n": t.get("predicted_n"), "finish": r["choices"][0]["finish_reason"], "keep_reasoning": KEEP_REASONING}), flush=True)
finally:
    p.terminate(); p.wait(30)
