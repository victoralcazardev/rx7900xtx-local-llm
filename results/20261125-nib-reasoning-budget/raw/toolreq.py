import json, sys, urllib.request
# streaming request with one tool; prints what an agent harness would receive
body = {"stream": True, "max_tokens": 6000,
        "messages": [{"role": "user", "content": "Read the file src/config.py and tell me which port the server uses. Before calling any tool, reason carefully about which file paths could hold the configuration."}],
        "tools": [{"type": "function", "function": {"name": "read_file", "description": "Read a file from the repository",
                   "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}}]}
req = urllib.request.Request("http://127.0.0.1:4444/v1/chat/completions", json.dumps(body).encode(), {"content-type": "application/json"})
reasoning, content, tool_args, names, finish = "", "", "", [], None
with urllib.request.urlopen(req, timeout=300) as r:
    for line in r:
        line = line.decode().strip()
        if not line.startswith("data: ") or line == "data: [DONE]":
            continue
        ch = json.loads(line[6:])["choices"][0]
        d = ch.get("delta", {})
        reasoning += d.get("reasoning_content") or ""
        content += d.get("content") or ""
        for tc in d.get("tool_calls") or []:
            f = tc.get("function", {})
            if f.get("name"): names.append(f["name"])
            tool_args += f.get("arguments") or ""
        finish = ch.get("finish_reason") or finish
print("finish", finish, "| reasoning chars", len(reasoning), "| tools", names, tool_args[:200])
print("CONTENT:", content[:200].replace("\n", " "))
