#!/usr/bin/env python3
"""Greedy GSM8K over an OpenAI-compatible chat endpoint, scored like maya's tests/ik2_gsm8k.py.

Same questions (file order, --offset/--count), same suffix "End your answer with #### followed by the
number.", thinking off (reasoning_effort "none"), temperature 0, the same max-token cap, and the same
rule: the last number in the final answer text must equal the reference after "####".

usage: gsm8k_http.py <port> <gsm8k-test.jsonl> [--offset 0] [--count 192] [--max-tokens 4096] [--out FILE]
"""
import argparse
from decimal import Decimal
import json
import re
import time
import urllib.request

NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def answer_of(text):
    nums = NUMBER.findall(text or "")
    return Decimal(nums[-1].replace(",", "")) if nums else None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("port")
    ap.add_argument("data")
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--count", type=int, default=192)
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--out")
    ap.add_argument("--raw", action="store_true",
                    help="POST /v1/completions with the exact prompt maya's ik2 template renders (no model"
                         " prefix, so the model picks its channel), instead of the chat endpoint")
    a = ap.parse_args()
    with open(a.data) as f:
        samples = [json.loads(line) for line in f][a.offset:a.offset + a.count]
    out = open(a.out, "w") if a.out else None
    right = cut = 0
    for i, s in enumerate(samples):
        question = s["question"] + "\nEnd your answer with #### followed by the number."
        if a.raw:
            # byte-identical to tools/ik2/chat_template.jinja with reasoning_effort="none", no tools
            body = {"prompt": "<|message_system|><|content_text|>Thinking effort level: 0<|end_message|>"
                               f"<|message_user|><|content_text|>{question}<|end_message|>",
                    "temperature": 0, "max_tokens": a.max_tokens}
            path = "/v1/completions"
        else:
            body = {"messages": [{"role": "user", "content": question}],
                    "temperature": 0, "max_tokens": a.max_tokens, "reasoning_effort": "none"}
            path = "/v1/chat/completions"
        t = time.monotonic()
        req = urllib.request.Request(f"http://127.0.0.1:{a.port}{path}",
                                     json.dumps(body).encode(), {"Content-Type": "application/json"})
        r = json.load(urllib.request.urlopen(req, timeout=900))
        ch = r["choices"][0]
        text = ch.get("text") if a.raw else ch["message"].get("content")
        if a.raw and "<|content_text|>" in (text or ""):
            text = text.rsplit("<|content_text|>", 1)[1]
        pred = answer_of(text)
        exp = Decimal(s["answer"].rsplit("####", 1)[1].strip().replace(",", ""))
        row = dict(question=a.offset + i, correct=pred == exp, expected=str(exp),
                   predicted=None if pred is None else str(pred), finish=ch["finish_reason"],
                   generated=r["usage"]["completion_tokens"], seconds=round(time.monotonic() - t, 2))
        right += row["correct"]
        cut += row["finish"] == "length"
        if out:
            out.write(json.dumps(row) + "\n")
            out.flush()
    summary = dict(correct=right, total=len(samples), truncated=cut)
    print(json.dumps(summary))
    if out:
        out.write(json.dumps(summary) + "\n")


if __name__ == "__main__":
    main()
