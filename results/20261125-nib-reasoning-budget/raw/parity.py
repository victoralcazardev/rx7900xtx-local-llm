import json, sys, urllib.request
# greedy replies for a fixed prompt set; writes one JSON line per prompt to argv[1]
prompts = ["A train leaves at 9:40 and travels 337 km at 74 km/h, then 128 km at 96 km/h. At what time does it arrive?",
           "Write a Python function that returns the n-th Fibonacci number iteratively.",
           "Explain in three sentences why the sky is blue.",
           "List the prime numbers between 50 and 100."]
with open(sys.argv[1], "w") as out:
    for p in prompts:
        body = {"messages": [{"role": "user", "content": p}], "max_tokens": 1500, "temperature": 0, "top_k": 1}
        r = json.load(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:4444/v1/chat/completions",
            json.dumps(body).encode(), {"content-type": "application/json"}), timeout=300))
        m = r["choices"][0]["message"]
        out.write(json.dumps({"p": p, "reasoning": m.get("reasoning_content"), "content": m.get("content")}) + "\n")
