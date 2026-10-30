"""Short and deep coding requests against a Strata server on :8080, with a RAM/VRAM watcher.

Usage: STRATA_DIR=<strata clone at v0.2.8> python3 strata_bench.py --out <file.jsonl> [--fresh] [depth_tokens ...]
Changes from ../20261015-strata-coder-context-steps/strata_bench.py: temperature 0 (same text across arms, so MTP
acceptance is comparable), SHA-256 of reasoning + content per request, one JSON line per request, and a 2 s watcher
(MemAvailable, swap, pswpin, VRAM, GTT) whose minimum/maximum go into each line. --fresh puts a unique first line in
every deep prompt so no prefix is reused from the previous request (clean prefill numbers).
Filler: the clone's C/C++ source cut to depth * 3.4 characters; pin the clone's tag, the filler changes with it.
"""
import argparse, hashlib, json, os, pathlib, threading, time, urllib.request

URL = "http://127.0.0.1:8080/v1/chat/completions"
ASK = "Write a Python function that parses an ISO-8601 duration string like P3DT4H5M into total seconds, with tests."
CHARS_PER_TOKEN = 3.4
DRM = pathlib.Path("/sys/class/drm")


def gpu_dir():
    cards = [p for p in DRM.glob("card[0-9]*/device") if (p / "mem_info_vram_total").exists()]
    return max(cards, key=lambda p: int((p / "mem_info_vram_total").read_text()), default=None)


class Watcher(threading.Thread):
    def __init__(self, path):
        super().__init__(daemon=True)
        self.f, self.gpu, self.rows, self.stop = open(path, "a"), gpu_dir(), [], False

    def sample(self):
        mem = {k: int(v.split()[0]) for k, v in (l.split(":", 1) for l in open("/proc/meminfo"))}
        vm = dict(l.split() for l in open("/proc/vmstat"))
        g = (lambda n: int((self.gpu / n).read_text()) / 2**30) if self.gpu else (lambda n: float("nan"))
        return {"t": time.time(), "mem_avail_gib": mem["MemAvailable"] / 2**20,
                "swap_used_gib": (mem["SwapTotal"] - mem["SwapFree"]) / 2**20, "pswpin": int(vm["pswpin"]),
                "vram_used_gib": g("mem_info_vram_used"), "gtt_used_gib": g("mem_info_gtt_used")}

    def run(self):
        while not self.stop:
            s = self.sample()
            self.rows.append(s)
            self.f.write(json.dumps(s) + "\n")
            self.f.flush()
            time.sleep(2)

    def window(self, t0):
        rows = [r for r in self.rows if r["t"] >= t0] or self.rows[-1:]
        return {"min_mem_avail_gib": round(min(r["mem_avail_gib"] for r in rows), 2),
                "max_swap_used_gib": round(max(r["swap_used_gib"] for r in rows), 2),
                "pswpin_delta": rows[-1]["pswpin"] - rows[0]["pswpin"],
                "max_vram_used_gib": round(max(r["vram_used_gib"] for r in rows), 2),
                "max_gtt_used_gib": round(max(r["gtt_used_gib"] for r in rows), 2)}


def call(messages, max_tokens):
    body = json.dumps({"model": "x", "messages": messages, "max_tokens": max_tokens, "temperature": 0}).encode()
    t0 = time.time()
    r = json.load(urllib.request.urlopen(urllib.request.Request(URL, body, {"Content-Type": "application/json"}),
                                         timeout=3600))
    msg = r["choices"][0]["message"]
    text = (msg.get("reasoning_content") or "") + "\x00" + (msg.get("content") or "")
    return r, time.time() - t0, hashlib.sha256(text.encode()).hexdigest()[:16]


def filler(target_tokens):
    root = pathlib.Path(os.environ.get("STRATA_DIR", "Strata")) / "src"
    limit, out, n = int(target_tokens * CHARS_PER_TOKEN), [], 0
    for p in sorted(root.rglob("*.c*")):
        out.append(f"// FILE {p.name}\n{p.read_text(errors='ignore')}")
        n += len(out[-1]) + 1
        if n > limit:
            break
    return "\n".join(out)[:limit]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("depths", nargs="*", type=int)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    ap.add_argument("--label", default="")
    ap.add_argument("--short", type=int, default=2, help="short requests before the deep ones")
    ap.add_argument("--max-tokens", type=int, default=800)
    ap.add_argument("--fresh", action="store_true")
    a = ap.parse_args()
    w = Watcher(a.out.with_suffix(".mem.jsonl"))
    w.start()
    jobs = [(f"short#{i + 1}", [{"role": "user", "content": ASK}]) for i in range(a.short)]
    for d in a.depths:
        head = f"Run {time.time_ns()}.\n" if a.fresh else ""
        jobs.append((f"deep~{d // 1000}K", [{"role": "user", "content":
                                            f"{head}Here is source code:\n{filler(d)}\n\nNow, unrelated: {ASK}"}]))
    with open(a.out, "a") as f:
        for name, msgs in jobs:
            t0 = time.time()
            r, wall, sha = call(msgs, a.max_tokens)
            t = r.get("timings", {})
            row = {"label": a.label, "request": name, "prompt_new": t.get("prompt_n"), "prompt_cached": t.get("cache_n"),
                   "prefill_tps": round(t.get("prompt_per_second", 0), 1), "gen_n": t.get("predicted_n"),
                   "gen_tps": round(t.get("predicted_per_second", 0), 2), "drafts": [t.get("draft_n_accepted"), t.get("draft_n")],
                   "finish": r["choices"][0].get("finish_reason"), "wall_s": round(wall, 1), "sha": sha, **w.window(t0)}
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(json.dumps(row), flush=True)
    w.stop = True


if __name__ == "__main__":
    main()
