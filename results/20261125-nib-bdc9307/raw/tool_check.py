#!/usr/bin/env python3
"""One OpenAI tool-call request plus its follow-up turn over /v1/chat/completions.

Small on purpose: it only proves that the tools path still parses and that a second turn answers
from the tool result. Writes the two turns (finish reason, calls, usage, answer) to --out.

usage: tool_check.py <port> [--sampling '{"temperature":1.0,"top_k":256}'] [--out FILE]

Exit: 0 = PASS, 1 = FAIL.
"""
import argparse
import json
import sys
import time
import urllib.request

TOOLS = [{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a text file from the workspace and return its contents.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Relative path of the file"}},
            "required": ["path"],
        },
    },
}]

FILE = ("def main():\n"
        "    total = sum(int(x) for x in open('nums.txt'))\n"
        "    print(total)\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n")


def post(port, body, timeout=900):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions",
                                 json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("port")
    ap.add_argument("--sampling", default='{"temperature":1.0,"top_k":256}')
    ap.add_argument("--out")
    a = ap.parse_args()
    samp = json.loads(a.sampling)
    lines = []
    t = time.monotonic()
    r1 = post(a.port, dict(messages=[{"role": "user",
                                      "content": "Read src/app.py and tell me what main() does."}],
                           tools=TOOLS, max_tokens=256, reasoning_effort="none", **samp))
    c1 = r1["choices"][0]
    msg = c1["message"]
    calls = [(c["function"]["name"], c["function"]["arguments"]) for c in (msg.get("tool_calls") or [])]
    lines.append(f"turn1 {time.monotonic() - t:.1f}s finish={c1['finish_reason']} calls={calls} "
                 f"usage={r1['usage']}")
    ok = c1["finish_reason"] == "tool_calls" and len(calls) == 1 and calls[0][0] == "read_file"
    try:
        path = json.loads(calls[0][1]).get("path") if calls else None
    except json.JSONDecodeError:
        path = None
    ok = ok and path == "src/app.py"
    r2 = None
    if calls:
        t = time.monotonic()
        r2 = post(a.port, dict(messages=[{"role": "user", "content": "Read src/app.py and tell me what main() does."},
                                         msg,
                                         {"role": "tool", "tool_call_id": msg["tool_calls"][0]["id"],
                                          "content": FILE}],
                               tools=TOOLS, max_tokens=384, reasoning_effort="none", **samp))
        c2 = r2["choices"][0]
        text = (c2["message"].get("content") or "").strip()
        lines.append(f"turn2 {time.monotonic() - t:.1f}s finish={c2['finish_reason']} usage={r2['usage']}")
        lines.append("answer: " + " ".join(text.split())[:600])
        ok = ok and c2["finish_reason"] == "stop" and "nums.txt" in text
    else:
        lines.append("turn2 skipped: turn 1 returned no tool call")
        ok = False
    lines.append("result: " + ("PASS" if ok else "FAIL"))
    print("\n".join(lines))
    if a.out:
        with open(a.out, "w") as f:
            f.write("\n".join(lines) + "\n")
            f.write(json.dumps(dict(turn1=r1, turn2=r2)) + "\n")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
