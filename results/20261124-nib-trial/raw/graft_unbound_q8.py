#!/usr/bin/env python3
"""Graft nokeepai Unbound v2.1's edited attention tensors onto the Nib-Pack GGUF.

Unbound v2.1 changes only the q/k/v/output/gate attention projections of the 24 layers (120 tensors;
experts byte-identical to the release, per its card). The Nib-Pack keeps those tensors as Q8_0 copied
from ggml-org's Q8_0, so the graft overwrites each one, in a copy of the pack, with the Q8_0 bytes of
the same tensor in Inkling-2-Mini-Unbound-v2.1-Q8_0.gguf, read with HTTP range requests (no 26 GB
download). Shapes and types must match exactly or the script stops before writing.

usage: graft_unbound_q8.py <nib-pack.gguf> <out.gguf> [--url URL] [--dry-run]
"""
import argparse
import os
import re
import shutil
import struct
import sys
import urllib.request

URL = ("https://huggingface.co/nokeepai/Inkling-2-Mini-Unbound-GGUF/resolve/main/"
       "Inkling-2-Mini-Unbound-v2.1-Q8_0.gguf")
ATTN = re.compile(r"^blk\.(\d+)\.attn_(q|k|v|output|gate)\.weight$")
Q8_0 = 8
# fixed-size GGUF metadata value types -> byte size (8 = string, 9 = array handled apart)
SCALAR = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}


class Src:
    """Sequential reader over a local file or a remote URL (HTTP range requests, buffered)."""

    def __init__(self, path_or_url):
        self.url = path_or_url if path_or_url.startswith("http") else None
        self.f = None if self.url else open(path_or_url, "rb")
        self.pos, self.buf, self.buf_at = 0, b"", 0

    def read_at(self, off, n):
        if not self.url:
            self.f.seek(off)
            return self.f.read(n)
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={off}-{off + n - 1}"})
        with urllib.request.urlopen(req) as r:
            data = r.read()
        if len(data) != n:
            raise IOError(f"short range read at {off}: {len(data)} of {n}")
        return data

    def read(self, n):
        end = self.pos + n
        if not (self.buf_at <= self.pos and end <= self.buf_at + len(self.buf)):
            self.buf_at = self.pos
            self.buf = self.read_at(self.pos, max(n, 8 << 20))
        out = self.buf[self.pos - self.buf_at:end - self.buf_at]
        self.pos = end
        return out


def parse(src):
    """Return (tensor dict name -> (type, dims, abs_offset), data_start)."""
    u32 = lambda: struct.unpack("<I", src.read(4))[0]
    u64 = lambda: struct.unpack("<Q", src.read(8))[0]
    string = lambda: src.read(u64()).decode("utf-8", "replace")

    def skip_value(t):
        if t in SCALAR:
            src.read(SCALAR[t])
        elif t == 8:
            string()
        elif t == 9:
            et, n = u32(), u64()
            for _ in range(n):
                skip_value(et)
        else:
            raise ValueError(f"unknown metadata type {t}")

    if src.read(4) != b"GGUF":
        raise ValueError("not a GGUF file")
    version = u32()
    if version != 3:
        raise ValueError(f"GGUF version {version}, expected 3")
    n_tensors, n_kv = u64(), u64()
    align = 32
    for _ in range(n_kv):
        key = string()
        t = u32()
        if key == "general.alignment":
            align = struct.unpack("<I", src.read(4))[0]
        else:
            skip_value(t)
    tensors = {}
    for _ in range(n_tensors):
        name = string()
        dims = tuple(u64() for _ in range(u32()))
        ttype, off = u32(), u64()
        tensors[name] = (ttype, dims, off)
    data_start = (src.pos + align - 1) // align * align
    return {k: (t, d, o + data_start) for k, (t, d, o) in tensors.items()}


def q8_bytes(dims):
    n = 1
    for d in dims:
        n *= d
    return n // 32 * 34


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pack")
    ap.add_argument("out")
    ap.add_argument("--url", default=URL)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    dst_src, rem = Src(a.pack), Src(a.url)
    dst, src = parse(dst_src), parse(rem)
    names = sorted(n for n in src if ATTN.match(n))
    problems = []
    if len(names) != 120:
        problems.append(f"expected 120 attention tensors in the source, found {len(names)}")
    for n in names:
        if n not in dst:
            problems.append(f"{n}: missing in the pack")
        elif dst[n][:2] != src[n][:2] or src[n][0] != Q8_0:
            problems.append(f"{n}: pack {dst[n][:2]} vs source {src[n][:2]}")
    if problems:
        sys.exit("refusing to graft:\n  " + "\n  ".join(problems))
    total = sum(q8_bytes(src[n][1]) for n in names)
    print(f"{len(names)} tensors, {total / 2**20:.1f} MiB to graft, all Q8_0 with matching shapes")
    if a.dry_run:
        return
    if os.path.exists(a.out):
        sys.exit(f"{a.out} exists; not overwriting")
    tmp = a.out + ".part"
    shutil.copyfile(a.pack, tmp)
    changed = 0
    with open(tmp, "r+b") as f:
        for n in names:
            size = q8_bytes(src[n][1])
            new = rem.read_at(src[n][2], size)
            old = dst_src.read_at(dst[n][2], size)
            changed += new != old
            f.seek(dst[n][2])
            f.write(new)
    os.replace(tmp, a.out)
    print(f"wrote {a.out}; {changed} of {len(names)} tensors differed from the pack")


if __name__ == "__main__":
    main()
