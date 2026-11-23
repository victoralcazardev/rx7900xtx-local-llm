"""Exact copy / single-line edit over an OpenAI-compatible HTTP server. Usage:

    python3 http_copy_edit.py --variant sfx128 --out http-suffix.jsonl [--port 8080] [--repeats 3]

Sends, for each case, a ~40-line archive inventory and asks (a) to copy it verbatim and (b) to
return it with exactly one change ("box 46" -> "box forty-six"). The prompt idea is the maya
port's tests/ik2_copy_edit.py; nothing is imported from the port. Thinking is off with
"reasoning_effort": "none", the port's direct-answer path (`<|message_model|><|content_text|>`).

Every request appends one JSON object to --out: variant, case, exact, completion tokens, wall
seconds and the decode rate from the server's `timings` (llama.cpp names, the engine's own
clock: predicted_n / predicted_ms), plus the suffix lookup counters when the server reports
them (`timings.draft_n` / `draft_n_accepted`, the engine's DONE accepted/offered fields).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import statistics
import sys
import time
import urllib.request

NAMES = ("notebooks", "folders", "maps", "letters")


def inventory(lines: int) -> str:
    return "\n".join("The archive shelf contains " + ", ".join(
        f"box {j} storing {NAMES[j % 4]}" for j in range(i, i + 9)) + "."
        for i in range(0, lines * 9, 9))


def cases(lines: int) -> list[tuple[str, str, str]]:
    text = inventory(lines)
    copy_q = "Copy the following archive inventory verbatim. Return only the inventory, with every line."
    edit_q = ("Return this inventory verbatim with exactly one change: replace 'box 46' with "
              "'box forty-six'.")
    target = "box 46 storing"  # the whole number: a bare "box 46" also matches box 460-469 at 52+ lines
    expected_edit = text.replace(target, "box forty-six storing")
    # Self-check: the edit text differs from the original in exactly one line and nowhere else.
    assert text.count(target) == 1, f"inventory must contain {target!r} exactly once, found {text.count(target)}"
    original_lines, edited_lines = text.splitlines(), expected_edit.splitlines()
    assert len(original_lines) == len(edited_lines) == lines, (len(original_lines), len(edited_lines), lines)
    changed = [i for i, (a, b) in enumerate(zip(original_lines, edited_lines)) if a != b]
    assert changed == [5], f"the edit must change exactly line 6 (index 5), changed {changed}"
    return [("copy", copy_q, text), ("edit", edit_q, expected_edit)]


def post(port: int, body: dict, timeout: float) -> tuple[dict, float]:
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions",
                                 json.dumps(body).encode(), {"Content-Type": "application/json"})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    return data, time.monotonic() - t0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--variant", required=True, choices=("sfx128", "plain"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--lines", type=int, default=40, help="inventory lines of nine boxes each")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--max-tokens", type=int, default=12288)
    ap.add_argument("--timeout", type=float, default=1800)
    args = ap.parse_args()
    if args.lines < 7 or args.repeats < 1 or args.max_tokens < 1:
        ap.error("--lines must be at least 7 (box 46), --repeats and --max-tokens positive")
    rows = []
    for case, question, expected in cases(args.lines):
        prompt = question + "\n\n" + inventory(args.lines)
        for repeat in range(1, args.repeats + 1):
            body = {"messages": [{"role": "user", "content": prompt}], "temperature": 0,
                    "stream": False, "reasoning_effort": "none", "max_tokens": args.max_tokens}
            data, wall = post(args.port, body, args.timeout)
            choice = data["choices"][0]
            answer = (choice["message"].get("content") or "").strip()
            exact = answer == expected.strip()
            timings = data.get("timings") or {}
            row = {
                "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                "variant": args.variant, "case": case, "repeat": repeat,
                "exact": exact, "finish_reason": choice.get("finish_reason"),
                "prompt_tokens": data.get("usage", {}).get("prompt_tokens"),
                "completion_tokens": data.get("usage", {}).get("completion_tokens"),
                "wall_s": round(wall, 2),
                "predicted_n": timings.get("predicted_n"),
                "predicted_ms": timings.get("predicted_ms"),
                "decode_tok_s": timings.get("predicted_per_second"),
                "decode_source": "timings.predicted_per_second (engine DONE predicted_n/predicted_ms)",
                "prompt_per_second": timings.get("prompt_per_second"),
                "draft_n": timings.get("draft_n"), "draft_n_accepted": timings.get("draft_n_accepted"),
                "answer_sha256": hashlib.sha256(answer.encode()).hexdigest()[:16],
                "answer_chars": len(answer),
                "max_tokens": args.max_tokens,
            }
            if not exact:
                got = answer.splitlines()
                want = expected.strip().splitlines()
                first = next((i for i, (a, b) in enumerate(zip(got, want)) if a != b), min(len(got), len(want)))
                row["mismatch"] = {"line": first, "got": (got[first][:200] if first < len(got) else None),
                                   "want": (want[first][:200] if first < len(want) else None)}
            with open(args.out, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            rows.append(row)
            print(f"{case} #{repeat} exact={exact} tokens={row['completion_tokens']} "
                  f"wall={row['wall_s']}s decode={row['decode_tok_s']} tok/s "
                  f"suffix={row['draft_n_accepted']}/{row['draft_n']}", flush=True)
    for case in ("copy", "edit"):
        marsh = [r for r in rows if r["case"] == case and r["decode_tok_s"]]
        if marsh:
            print(f"{case}: exact {sum(r['exact'] for r in rows if r['case'] == case)}/{len(marsh)}, "
                  f"median decode {statistics.median(r['decode_tok_s'] for r in marsh):.2f} tok/s")
    return 0 if all(r["exact"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
