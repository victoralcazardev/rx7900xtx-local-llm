#!/usr/bin/env python3
"""Throwaway KVMem-trial depth bench over /v1/chat/completions only (llama-kvmem-server has no
/tokenize, /apply-template or /completion). Fresh server per case; the same harness runs the
baseline llama-server so both arms are measured identically.

usage: kvmem_depth.py --label L --out DIR --depths 128000 240000 -- <server argv...>
"""
import argparse, glob, json, os, signal, subprocess, sys, threading, time, urllib.request
from pathlib import Path

WIKI = Path(os.environ.get("BENCH_WIKI", str(Path.home() / "ia-bench/wikitext-2-raw/wiki.train.raw")))
URL = "http://127.0.0.1:8080"
INSTR = ("\n\nEscribe un ensayo detallado de al menos 2000 palabras que sintetice, explique y conecte "
         "las ideas del texto anterior. Continúa hasta completar el ensayo.")
HOTSPOT_ABORT = 104


def post(path, body, timeout):
    req = urllib.request.Request(URL + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def chat(content, max_tokens, timeout=4 * 3600):
    return post("/v1/chat/completions", {"messages": [{"role": "user", "content": content}],
                                         "max_tokens": max_tokens, "seed": 42}, timeout)


def hwmon_temp(label):
    for f in glob.glob("/sys/class/drm/card*/device/hwmon/hwmon*/temp*_label"):
        if open(f).read().strip() == label:
            return int(open(f.replace("_label", "_input")).read()) / 1000
    return None


def mem_available_gib():
    for line in open("/proc/meminfo"):
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 2**20


class Monitor(threading.Thread):
    def __init__(self, pid):
        super().__init__(daemon=True)
        self.pid, self.run_ = pid, True
        self.vram_mib = self.rss_gib = self.hotspot = 0.0
        self.min_avail_gib = 1e9
        self.abort = None

    def run(self):
        while self.run_:
            try:
                vram = 0
                for f in glob.glob(f"/proc/{self.pid}/fdinfo/*"):
                    for line in open(f):
                        if line.startswith("drm-memory-vram:"):
                            vram = max(vram, int(line.split()[1]))
                self.vram_mib = max(self.vram_mib, vram / 1024)
                for line in open(f"/proc/{self.pid}/status"):
                    if line.startswith("VmRSS:"):
                        self.rss_gib = max(self.rss_gib, int(line.split()[1]) / 2**20)
            except OSError:
                pass
            self.min_avail_gib = min(self.min_avail_gib, mem_available_gib())
            h = hwmon_temp("junction") or 0
            self.hotspot = max(self.hotspot, h)
            if h >= HOTSPOT_ABORT:
                self.abort = f"hotspot {h} C"
            time.sleep(1)


def start(argv, log):
    proc = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(1800):
        if proc.poll() is not None:
            raise RuntimeError(f"server exited {proc.returncode}")
        try:
            urllib.request.urlopen(URL + "/health", timeout=2)
            return proc
        except Exception:
            time.sleep(1)
    raise RuntimeError("server never became healthy")


def stop(proc):
    if proc.poll() is None:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(30)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL); proc.wait()


def cool_down(max_edge=55, limit_s=900):
    t0 = time.monotonic()
    while time.monotonic() - t0 < limit_s and (hwmon_temp("edge") or 0) > max_edge:
        time.sleep(10)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--depths", nargs="+", type=int, required=True)
    ap.add_argument("--max-tokens", type=int, default=1500)
    ap.add_argument("server", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    argv = a.server[1:] if a.server[:1] == ["--"] else a.server
    a.out.mkdir(parents=True, exist_ok=True)
    wiki = WIKI.read_text(encoding="utf-8", errors="replace")
    for depth in a.depths:
        cool_down()
        case = a.out / f"{a.label}_d-{depth}"
        case.mkdir(exist_ok=False)
        (case / "command.json").write_text(json.dumps(argv, indent=2) + "\n")
        with (case / "server.log").open("w") as log:
            proc = start(argv, log)
            mon = Monitor(proc.pid); mon.start()
            try:
                # Calibrate chars/token on the same text; the leading "~" breaks prefix reuse.
                probe = "~" + wiki[:int(min(depth, 64000) * 4.2)] + INSTR
                ratio = len(probe) / chat(probe, 1, 600)["usage"]["prompt_tokens"]
                content = wiki[:int(depth * ratio) - len(INSTR)] + INSTR
                t0 = time.monotonic()
                resp = chat(content, a.max_tokens)
                elapsed = time.monotonic() - t0
                if mon.abort:
                    raise RuntimeError(mon.abort)
                msg = resp["choices"][0]["message"]
                row = {"label": a.label, "depth_target": depth, "usage": resp.get("usage"),
                       "timings": resp.get("timings"), "finish": resp["choices"][0]["finish_reason"],
                       "reasoning_chars": len(msg.get("reasoning_content") or ""),
                       "content_chars": len(msg.get("content") or ""), "elapsed_s": round(elapsed, 1),
                       "peak_vram_mib": round(mon.vram_mib), "peak_rss_gib": round(mon.rss_gib, 2),
                       "min_mem_available_gib": round(mon.min_avail_gib, 2), "peak_hotspot_c": mon.hotspot}
                (case / "response.json").write_text(json.dumps(resp, ensure_ascii=False, indent=2) + "\n")
            except Exception as e:
                row = {"label": a.label, "depth_target": depth, "error": repr(e)}
            finally:
                mon.run_ = False
                stop(proc)
        with (a.out / "summary.jsonl").open("a") as f:
            f.write(json.dumps(row) + "\n")
        t = row.get("timings") or {}
        print(depth, row.get("error") or f"prompt={row['usage']['prompt_tokens']} pp={t.get('prompt_per_second')} "
              f"tg={t.get('predicted_per_second')} n={t.get('predicted_n')} vram={row['peak_vram_mib']}MiB "
              f"rss={row['peak_rss_gib']}GiB avail_min={row['min_mem_available_gib']}GiB hot={row['peak_hotspot_c']}",
              flush=True)


if __name__ == "__main__":
    sys.exit(main())
