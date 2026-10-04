#!/usr/bin/env python3
"""Build the frozen E3 request bodies (A, A', B, cold A') from repository files."""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "requests"
OUT.mkdir(exist_ok=True)

def read(p):
    return (REPO / p).read_text()

TAIL = (
    "Answer in one short paragraph. Before you answer, consider the following background, "
    "which matters for the decision: the card is an RX 7900 XTX with 24 GB of VRAM, the engine "
    "is a single-backend ROCm build, the context window is 262144 tokens with quantized KV, and the "
    "speculative decoding path combines a multi-token-prediction draft head with an n-gram map. "
    "The checkpoints are kept in host memory, and the prompt cache is limited to twelve gigabytes. "
    "Given all of that, which engine build should a new owner of this card start with, and what is "
    "the single most important reason for that choice according to the documents above?"
)
# A' replaces one word ~100 tokens before the end of the last user message.
EDIT_FROM, EDIT_TO = "host memory", "system memory"
assert TAIL.count(EDIT_FROM) == 1

def body(messages, **extra):
    b = {"messages": messages, "temperature": 0, "max_tokens": 48,
         "logprobs": True, "top_logprobs": 5}
    b.update(extra)
    return b

def chat_a(tail):
    return [
        {"role": "system", "content": "You are a concise assistant for a local LLM setup."},
        {"role": "user", "content": "Here is the engine document:\n\n" + read("docs/ENGINES.md")
         + "\n\nSummarize it in one sentence."},
        {"role": "assistant", "content": "It lists the llama.cpp builds used on this card, how each "
         "was built, and which one is current."},
        {"role": "user", "content": "Here is the list of things already tried:\n\n" + read("docs/TRIED.md")
         + "\n\nWhich entry looks most relevant to engine choice?"},
        {"role": "assistant", "content": "The entries about the kvmix patches and ROCm toolchains are "
         "the most relevant to engine choice."},
        {"role": "user", "content": "Here is the current status:\n\n" + read("docs/STATUS.md") + "\n\n" + tail},
    ]

reqs = {
    "A": body(chat_a(TAIL)),
    "A_prime": body(chat_a(TAIL.replace(EDIT_FROM, EDIT_TO))),
    "A_prime_cold": body(chat_a(TAIL.replace(EDIT_FROM, EDIT_TO)), cache_prompt=False),
    "B": body([
        {"role": "system", "content": "You are a concise assistant."},
        {"role": "user", "content": "Here is a decision log:\n\n" + read("docs/DECISIONS.md")
         + "\n\nWhat is the oldest decision recorded here? One sentence."},
    ]),
}
for name, b in reqs.items():
    (OUT / f"{name}.json").write_text(json.dumps(b, indent=1))
print("wrote", sorted(reqs))
