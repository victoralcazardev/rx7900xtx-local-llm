"""DSpark round economics on a running nib server: per depth, the server's own mtp timings.
Prompt = repository docs as context + a coding request; sampling = the server defaults (the shipped profile).
usage: drafter_rounds.py <port> [--depths 8192 32768 65536] [--gen 512] [--repeats 2] [--no-mtp]"""
import argparse, json, pathlib, urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("port"); ap.add_argument("--depths", type=int, nargs="+", default=[8192, 32768, 65536])
ap.add_argument("--gen", type=int, default=512); ap.add_argument("--repeats", type=int, default=2)
ap.add_argument("--chars-per-token", type=float, default=2.9)
ap.add_argument("--no-mtp", action="store_true", help="send mtp: false (per-request drafter off)")
a = ap.parse_args()
root = pathlib.Path(__file__).resolve().parents[3]
text = "".join(p.read_text() for p in sorted((root / "docs").rglob("*.md")))
task = ("Write a Python module that parses this repository's models.toml-style tables, validates the sampling "
        "keys and prints a summary. Include type hints, docstrings and unit tests.")
for d in a.depths:
    ctx = (text * (int(d * a.chars_per_token) // len(text) + 2))[: int(d * a.chars_per_token)]
    for r in range(a.repeats):
        body = {"messages": [{"role": "system", "content": f"Run {r}. Reference material:\n{ctx}"},
                             {"role": "user", "content": task}], "max_tokens": a.gen}
        if a.no_mtp:
            body["mtp"] = False
        req = urllib.request.Request(f"http://127.0.0.1:{a.port}/v1/chat/completions", json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        res = json.load(urllib.request.urlopen(req, timeout=900))
        t = res.get("timings", {})
        print(json.dumps(dict(depth=d, rep=r, prompt=res["usage"]["prompt_tokens"],
                              gen=res["usage"]["completion_tokens"], tg=t.get("predicted_per_second"),
                              tok_per_round=t.get("mtp_tok_per_round"), accepted=t.get("mtp_avg_accepted"),
                              draft_ms=t.get("mtp_draft_ms"), verify_ms=t.get("mtp_verify_ms"))), flush=True)
