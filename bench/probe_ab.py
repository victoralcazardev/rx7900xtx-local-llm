#!/usr/bin/env python3
"""Paired A/B with the unmodified `probe.py` from sudoingX/qwen38-mtp (the community table's
instrument): one server per arm, identical serving flags, only the speculative-decoding flags
change, three complete probe passes per arm (each pass: 1 warm-up + 3 prompts x 3 runs).
Records system VRAM/GTT (sysfs) before load, after load and after the passes, and the per-request
`draft acceptance` lines from the server log (warm-up requests excluded when summarizing).

Run: systemd-inhibit --what=sleep:idle --mode=block env IA_BENCH_INHIBITED=1 \\
         python3 bench/probe_ab.py --probe /path/to/qwen38-mtp/probe.py [arm ...]

Configure via BENCH_SERVER, BENCH_MODEL and BENCH_OUT (see bench/README.md). The serving flags
are the `262k-q8q51-mtp` profile's; port 8080 because probe.py's default URL points there.
"""
import argparse, json, os, pathlib, re, signal, subprocess, sys, time, urllib.request

BASE = ["--port", "8080", "-c", "262144", "-ctk", "q8_0", "-ctv", "q5_1",
        "--temp", "1.0", "--top-p", "0.95", "--top-k", "20", "--min-p", "0.0", "-fa", "on", "-np", "1",
        "--ctx-checkpoints", "4", "-ngl", "all", "--metrics", "-ub", "256", "--reasoning-effort", "medium"]
MTP = lambda n, *x: ["--spec-type", "draft-mtp", "--spec-draft-n-max", str(n), *x]
ARMS = {"none": [], "n2": MTP(2), "n3": MTP(3), "n4": MTP(4),
        "n3-pmin060": MTP(3, "--spec-draft-p-min", "0.60"), "n3-pmin075": MTP(3, "--spec-draft-p-min", "0.75")}
ACCEPT = re.compile(r"draft acceptance = [\d.]+ \(\s*(\d+) accepted /\s*(\d+) generated")


def amdgpu():
    """The first DRM device exposing VRAM counters (the discrete card)."""
    return next(p.parent for p in sorted(pathlib.Path("/sys/class/drm").glob("card?/device/mem_info_vram_used")))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--probe", required=True, help="path to the unmodified probe.py")
    ap.add_argument("--passes", type=int, default=3)
    ap.add_argument("arms", nargs="*", help=f"subset of {list(ARMS)} (default: all)")
    a = ap.parse_args()
    a.arms = a.arms or list(ARMS)
    if set(a.arms) - set(ARMS): ap.error(f"unknown arm(s): {sorted(set(a.arms) - set(ARMS))}")
    if os.environ.get("IA_BENCH_INHIBITED") != "1": ap.error("requires systemd-inhibit and IA_BENCH_INHIBITED=1")
    server, model = os.environ.get("BENCH_SERVER", ""), os.environ.get("BENCH_MODEL", "")
    if not (os.path.isfile(server) and os.path.isfile(model)): ap.error("set BENCH_SERVER and BENCH_MODEL to existing files")
    dev = amdgpu(); hw = next(dev.glob("hwmon/hwmon*"))
    mib = lambda f: int((dev / f).read_text()) // 2**20
    temps = lambda: {(hw / f"temp{i}_label").read_text().strip(): int((hw / f"temp{i}_input").read_text()) // 1000
                     for i in (1, 2, 3) if (hw / f"temp{i}_label").exists()}
    def health():
        try: return json.load(urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=2)).get("status") == "ok"
        except Exception: return False
    out = pathlib.Path(os.environ.get("BENCH_OUT", pathlib.Path(__file__).parent / "res")) / time.strftime("probe-ab-%Y%m%d-%H%M%S")
    out.mkdir(parents=True)
    for arm in a.arms:
        while temps().get("junction", 0) > 55: time.sleep(10)  # chained arms heat up
        rec = {"arm": arm, "argv": [server, "-m", model] + BASE + ARMS[arm],
               "pre_vram_mib": mib("mem_info_vram_used"), "pre_gtt_mib": mib("mem_info_gtt_used")}
        log = open(out / f"{arm}.server.log", "w")
        p = subprocess.Popen(rec["argv"], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while not health():
                if p.poll() is not None: raise SystemExit(f"{arm}: server exited while loading")
                time.sleep(2)
            rec["loaded_vram_mib"], rec["loaded_gtt_mib"] = mib("mem_info_vram_used"), mib("mem_info_gtt_used")
            rec["passes"] = []
            for i in range(a.passes):
                r = subprocess.run([sys.executable, a.probe], capture_output=True, text=True, check=True)
                (out / f"{arm}.pass{i + 1}.txt").write_text(r.stdout)
                rec["passes"].append(r.stdout)
                print(arm, i + 1, r.stdout.strip().splitlines()[-1], flush=True)
            rec["post_vram_mib"], rec["post_gtt_mib"], rec["post_temps"] = mib("mem_info_vram_used"), mib("mem_info_gtt_used"), temps()
        finally:
            os.killpg(p.pid, signal.SIGTERM); p.wait(timeout=30); log.close()
        rec["acceptance"] = [list(map(int, m)) for m in ACCEPT.findall((out / f"{arm}.server.log").read_text())]
        with open(out / "summary.jsonl", "a") as f: f.write(json.dumps(rec) + "\n")
    print(out)


if __name__ == "__main__":
    main()
