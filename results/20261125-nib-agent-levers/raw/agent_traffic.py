"""Reading vs generation in real agent sessions, from nib server logs ([serve] chat lines).
usage: agent_traffic.py <nib-log>...   (agent turns = prompts above 5,000 tokens)"""
import re, statistics, sys

pat = re.compile(r"\[serve\] chat (?:stream|sync) \[s\d\] \| prompt=(\d+) \(cached=(\d+), (\d+) ms\) \| gen=(\d+) in (\d+) ms")
rows = [tuple(map(int, m.groups())) for f in sys.argv[1:] for m in map(pat.search, open(f, errors="replace")) if m]
agent = [r for r in rows if r[0] > 5000]
loops = [r for r in agent if r[3] >= 16384]
P, C = sum(r[0] for r in agent), sum(r[1] for r in agent)
read_ms, gen_ms = sum(r[2] for r in agent), sum(r[4] for r in agent)
gen_ms_noloop = gen_ms - sum(r[4] for r in loops)
print(f"requests {len(rows)}, agent turns {len(agent)}, loops at the cap {len(loops)}")
print(f"prompt tokens {P}, from cache {C} ({100 * C / P:.1f}%)")
print(f"reading {read_ms / 1000:.0f} s, generating {gen_ms / 1000:.0f} s ({(gen_ms - gen_ms_noloop) / 1000:.0f} s in loops)")
print(f"reading share {100 * read_ms / (read_ms + gen_ms):.1f}%, without loops {100 * read_ms / (read_ms + gen_ms_noloop):.1f}%")
big = [r for r in agent if r[0] - r[1] > 10000]
print(f"turns re-reading >10K new tokens: {len(big)}, {sum(r[2] for r in big) / 1000:.0f} s of the reading time")
for r in big:
    print(f"  prompt {r[0]}, cached {r[1]}, read {r[2] / 1000:.1f} s")
print(f"median agent turn: read {statistics.median(r[2] for r in agent):.0f} ms, gen {statistics.median(r[3] for r in agent)} tokens in {statistics.median(r[4] for r in agent):.0f} ms")
