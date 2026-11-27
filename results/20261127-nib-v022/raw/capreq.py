import json, sys, urllib.request
body = {"messages": [{"role": "user", "content": "A train leaves at 9:40 and travels 337 km at 74 km/h, then 128 km at 96 km/h. At what time does it arrive? Think carefully."}], "max_tokens": 6000}
if len(sys.argv) > 1: body.update(json.loads(sys.argv[1]))
r = json.load(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:4444/v1/chat/completions", json.dumps(body).encode(), {"content-type": "application/json"}), timeout=300))
c = r["choices"][0]; m = c["message"]
print("finish", c["finish_reason"], "| usage", r["usage"]["completion_tokens"], "| reasoning chars", len(m.get("reasoning_content") or ""), "| tool_calls", json.dumps(m.get("tool_calls") or [])[:200])
print("CONTENT:", (m.get("content") or "")[:300].replace("\n", " "))
print("REASONING TAIL:", (m.get("reasoning_content") or "")[-200:].replace("\n", " "))
