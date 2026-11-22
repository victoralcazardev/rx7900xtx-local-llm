"""Tool call + two-turn prefix reuse check against an OpenAI-compatible server. Usage: agent_check.py <port>"""
import json, sys, time, urllib.request
port = sys.argv[1]
def post(body):
    t = time.monotonic()
    r = json.load(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions",
        json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=900))
    return r, time.monotonic() - t
tools = [{"type": "function", "function": {"name": "read_file", "description": "Read a file from the repository",
          "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}}]
doc = open(sys.argv[2]).read() if len(sys.argv) > 2 else ""
msgs = [{"role": "system", "content": "You are a coding agent. Use tools when you need file contents.\n\n" + doc},
        {"role": "user", "content": "Open src/app.py and tell me what the main function does."}]
r, dt = post({"messages": msgs, "tools": tools, "temperature": 1.0, "max_tokens": 1024})
m = r["choices"][0]["message"]; calls = m.get("tool_calls") or []
print(f"turn1 {dt:.1f}s finish={r['choices'][0]['finish_reason']} calls={[ (c['function']['name'], c['function']['arguments']) for c in calls]} usage={r.get('usage')}")
assert calls and calls[0]["function"]["name"] == "read_file" and json.loads(calls[0]["function"]["arguments"])["path"].endswith("app.py"), "no valid tool call"
msgs += [m, {"role": "tool", "tool_call_id": calls[0]["id"], "content": "def main():\n    total = sum(int(x) for x in open('nums.txt'))\n    print(total)\n"}]
r, dt = post({"messages": msgs, "tools": tools, "temperature": 1.0, "max_tokens": 1024})
print(f"turn2 {dt:.1f}s finish={r['choices'][0]['finish_reason']} usage={r.get('usage')}")
print("answer:", (r["choices"][0]["message"].get("content") or "")[:300].replace("\n", " "))
