"""A->B->A prefix-cache retention on one nib server: two distinct long prompts alternated.
usage: abab.py <port> <label> <tokensA> [<long-tokens>]"""
import json, sys, time, urllib.request, pathlib
port, label, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
longn = int(sys.argv[4]) if len(sys.argv) > 4 else 0
docs = pathlib.Path(__file__).resolve().parents[3] / "docs"
text = "".join(p.read_text() for p in sorted(docs.rglob("*.md")))
def prompt(seed, ntok):
    chars = int(ntok * 2.9)
    body = (text * (chars // len(text) + 2))[seed * 7919: seed * 7919 + chars]
    return [{"role": "system", "content": f"Agent {seed}. Reference:\n" + body},
            {"role": "user", "content": "Reply with one short sentence."}]
def call(msgs):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions",
        data=json.dumps({"messages": msgs, "max_tokens": 64, "temperature": 0}).encode(),
        headers={"Content-Type": "application/json"})
    t = time.time(); r = json.load(urllib.request.urlopen(req, timeout=600)); dt = time.time() - t
    u = r["usage"]; tm = r.get("timings", {})
    return dict(prompt=u["prompt_tokens"], cached=u.get("prompt_cache_hit_tokens"), wall_s=round(dt, 2),
                slot=tm.get("slot"), tg=tm.get("predicted_per_second"))
A, B = prompt(1, n), prompt(2, n)
seq = [("A", A), ("B", B), ("A", A), ("B", B), ("A", A)]
if longn: seq += [("L", prompt(3, longn)), ("A", A), ("B", B)]
for name, m in seq:
    print(json.dumps(dict(label=label, req=name, **call(m))), flush=True)
