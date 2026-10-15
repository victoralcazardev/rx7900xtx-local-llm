"""Short and deep coding requests against a Strata server on :8080; prints the server timings.

Usage: STRATA_DIR=<strata clone> python3 strata_bench.py [depth_tokens ...]   (filler = the clone's C/C++ source)
Unlike ../20261015-strata-coder-first-run/strata_bench.py, the filler is cut to depth_tokens * 3.4 characters
(3.40 chars/token measured on this filler: 582,332 chars = 171,250 tokens), so the depth is the requested one.
"""
import json, os, pathlib, sys, time, urllib.request

URL = "http://127.0.0.1:8080/v1/chat/completions"
ASK = "Write a Python function that parses an ISO-8601 duration string like P3DT4H5M into total seconds, with tests."
CHARS_PER_TOKEN = 3.4


def call(messages, max_tokens=800):
    body = json.dumps({"model": "x", "messages": messages, "max_tokens": max_tokens, "temperature": 0.6}).encode()
    req = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
    t0 = time.time()
    r = json.load(urllib.request.urlopen(req, timeout=3600))
    return r["timings"], time.time() - t0


def filler(target_tokens):
    root = pathlib.Path(os.environ.get("STRATA_DIR", "Strata")) / "src"
    limit, out, n = int(target_tokens * CHARS_PER_TOKEN), [], 0
    for p in sorted(root.rglob("*.c*")):
        out.append(f"// FILE {p.name}\n{p.read_text(errors='ignore')}")
        n += len(out[-1]) + 1
        if n > limit:
            break
    return "\n".join(out)[:limit]


def show(label, t, wall):
    print(f"{label}: prompt {t['prompt_n']} new / {t['cache_n']} cached @ {t['prompt_per_second']:.0f} tok/s, "
          f"gen {t['predicted_n']} @ {t['predicted_per_second']:.1f} tok/s, drafts {t['draft_n_accepted']}/{t['draft_n']}, "
          f"wall {wall:.0f} s", flush=True)


for i in range(2):
    show(f"short#{i + 1}", *call([{"role": "user", "content": ASK}]))
for depth in [int(a) for a in sys.argv[1:]]:
    ctx = filler(depth)
    msgs = [{"role": "user", "content": f"Here is source code:\n{ctx}\n\nNow, unrelated: {ASK}"}]
    show(f"deep~{depth // 1000}K", *call(msgs))
