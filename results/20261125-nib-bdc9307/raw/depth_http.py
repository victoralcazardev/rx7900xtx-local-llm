#!/usr/bin/env python3
"""Decode/prefill speed at context depths over an OpenAI-compatible chat endpoint (server timings).

Each request is uncached: a unique nonce line starts the prompt, then this repo's docs text repeated
up to about --depth tokens, then a request to keep writing. Reports the server's prompt_per_second and
predicted_per_second (median of --repeats), plus the actual prompt token count.

usage: depth_http.py <port> --depths 512 8192 32768 131072 250000 [--gen 256] [--repeats 3]
       [--sampling '{"temperature":1.0,"top_k":256}'] [--chars-per-token 3.4] [--out FILE] [--label L]
"""
import argparse
import json
import pathlib
import statistics
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[3]


def corpus():
    text = "\n\n".join(p.read_text() for p in sorted((ROOT / "docs").rglob("*.md")))
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("port")
    ap.add_argument("--depths", type=int, nargs="+", required=True)
    ap.add_argument("--gen", type=int, default=256)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--sampling", default='{"temperature":1.0,"top_k":256}')
    ap.add_argument("--chars-per-token", type=float, default=3.4)
    ap.add_argument("--label", default="")
    ap.add_argument("--out")
    a = ap.parse_args()
    base = corpus()
    samp = json.loads(a.sampling)
    out = open(a.out, "a") if a.out else None
    for depth in a.depths:
        rows = []
        for rep in range(a.repeats):
            need = int(depth * a.chars_per_token)
            filler = (base * (need // len(base) + 1))[:need]
            prompt = (f"Session {time.time_ns()}.\n\n{filler}\n\nContinue the documentation above with a new "
                      f"section of at least 2,000 words about tuning long-context inference.")
            body = dict(messages=[{"role": "user", "content": prompt}], max_tokens=a.gen,
                        reasoning_effort="none", **samp)
            req = urllib.request.Request(f"http://127.0.0.1:{a.port}/v1/chat/completions",
                                         json.dumps(body).encode(), {"Content-Type": "application/json"})
            r = json.load(urllib.request.urlopen(req, timeout=3600))
            t = r.get("timings", {})
            rows.append(dict(prompt_tokens=r["usage"]["prompt_tokens"], gen=r["usage"]["completion_tokens"],
                             pp=t.get("prompt_per_second"), tg=t.get("predicted_per_second"),
                             mtp_tok_per_round=t.get("mtp_tok_per_round"),
                             mtp_avg_accepted=t.get("mtp_avg_accepted")))
        res = dict(label=a.label, depth=depth, prompt_tokens=rows[0]["prompt_tokens"],
                   pp=round(statistics.median(x["pp"] for x in rows), 1),
                   tg=round(statistics.median(x["tg"] for x in rows), 2),
                   gen=[x["gen"] for x in rows], tg_all=[round(x["tg"], 2) for x in rows],
                   mtp=[x["mtp_tok_per_round"] for x in rows],
                   accept=[None if x["mtp_avg_accepted"] is None else round(x["mtp_avg_accepted"], 3)
                           for x in rows])
        print(json.dumps(res), flush=True)
        if out:
            out.write(json.dumps(res) + "\n")
            out.flush()


if __name__ == "__main__":
    main()
