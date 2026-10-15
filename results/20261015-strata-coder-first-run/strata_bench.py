"""Short and deep coding requests against a Strata server on :8080; prints the server timings.

Usage: STRATA_DIR=<strata clone> python3 strata_bench.py [depth_tokens ...]   (filler = the clone's C/C++ source)
"""
import json, os, pathlib, sys, urllib.request

URL = "http://127.0.0.1:8080/v1/chat/completions"
ASK = "Write a Python function that parses an ISO-8601 duration string like P3DT4H5M into total seconds, with tests."


def call(messages, max_tokens=800):
    body = json.dumps({"model": "x", "messages": messages, "max_tokens": max_tokens, "temperature": 0.6}).encode()
    req = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=3600))
    t = r["timings"]
    return t


def filler(target_tokens):
    root = pathlib.Path(os.environ.get("STRATA_DIR", "Strata")) / "src"
    text, out = "", []
    for p in sorted(root.rglob("*.c*")):
        out.append(f"// FILE {p.name}\n{p.read_text(errors='ignore')}")
        text = "\n".join(out)
        if len(text) > target_tokens * 3.2:
            break
    return text


def show(label, t):
    print(f"{label}: prompt {t['prompt_n']} new / {t['cache_n']} cached @ {t['prompt_per_second']:.0f} tok/s, "
          f"gen {t['predicted_n']} @ {t['predicted_per_second']:.1f} tok/s, drafts {t['draft_n_accepted']}/{t['draft_n']}",
          flush=True)


for i in range(2):
    show(f"short#{i + 1}", call([{"role": "user", "content": ASK}]))
for depth in [int(a) for a in sys.argv[1:]]:
    ctx = filler(depth)
    msgs = [{"role": "user", "content": f"Here is source code:\n{ctx}\n\nNow, unrelated: {ASK}"}]
    show(f"deep~{depth // 1000}K", call(msgs))
