#!/usr/bin/env python3
"""Spanish-language RULER test. Smoke: `python longctx_quality.py --smoke` (no GPU used).
Run: `systemd-inhibit --what=sleep:idle --mode=block --why='longctx quality' env
IA_BENCH_INHIBITED=1 python longctx_quality.py --run --inhibitor-ok`.

Running it creates reproducible documents at an exact tokenized depth, records
needles/prompts/SSE/timings, and reuses depth_bench.py's Monitor/transport.

Deliberately Spanish (STYLE.md exception): the whole synthetic retrieval corpus and the
questions asked about it are Spanish on purpose -- this project's models are driven in
Spanish day to day, and RULER-style needle tests are language-sensitive.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import random
import re
import os
import signal
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

AQUI = pathlib.Path(__file__).resolve().parent
OUTPUT_DIR = AQUI / "res" / "longctx_quality"
DEPTHS = (32_000, 128_000, 240_000)
# Order: target profile first; q8q8 and q8q51 without MTP isolate the KV effect (greedy, deterministic).
VARIANTS = (("q8q51", True), ("q8q8", False), ("q8q51", False))
DOCS = 5
QUESTIONS_PER_DOC = 4  # per document; they reuse the document's KV (cache_prompt)
MAX_OUTPUT_TOKENS = 200
BASE_SEED = 262_024

# Vocabulary mixed across records, chronicle, popular-science and administrative-note
# registers; no external source and no paragraph-level repeated text.
SUBJECTS = ("la cooperativa", "el archivo municipal", "un equipo de campo", "la oficina técnica",
            "el observatorio", "la biblioteca", "la comisión vecinal", "el laboratorio", "la estación",
            "el taller", "la asociación", "el centro de datos", "la brigada", "el museo", "la escuela")
ACTIONS = ("anotó", "contrastó", "recogió", "revisó", "describió", "clasificó", "midió", "ordenó",
           "comprobó", "registró", "comparó", "trasladó", "consultó", "resumió", "documentó")
OBJECTS = ("los cambios del cauce", "las fichas del inventario", "la ruta de mantenimiento",
           "el calendario de visitas", "las muestras del terreno", "el estado de los equipos",
           "las actas de la reunión", "la evolución del barrio", "los datos de humedad",
           "la señal de referencia", "las incidencias del turno", "el plano de la zona",
           "los resultados preliminares", "la colección de mapas", "el informe de seguimiento")
PLACES = ("junto al puente viejo", "en la nave norte", "durante la mañana", "cerca del depósito",
          "en el distrito central", "a orillas del canal", "en la sala de consulta", "tras la última revisión",
          "en el camino de servicio", "durante la campaña de otoño", "en el edificio anexo",
          "desde la mesa de control", "en la zona de cultivo", "al final del recorrido")
CLOSINGS = ("El equipo dejó constancia de las dudas pendientes.",
            "La siguiente comprobación quedó prevista para la semana posterior.",
            "Los datos se conservaron con la fecha y el origen de cada observación.",
            "La nota se incorporó al expediente general para facilitar su consulta.",
            "Antes de cerrar la jornada se revisaron las copias y sus referencias.")
TYPES = ("muestra", "registro", "paquete", "sector", "lote", "expediente", "tramo", "informe",
         "archivo", "medición", "plano", "turno", "serie", "ficha", "conjunto", "parte")


def request_json(url: str, payload: dict | None = None, timeout: int = 3600):
    data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    req = urllib.request.Request(url, data, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


class Tokenizer:
    def __init__(self, url: str):
        self.url = url.rstrip("/") + "/tokenize"

    def count(self, text: str) -> int:
        r = request_json(self.url, {"content": text, "add_special": False}, timeout=600)
        toks = r.get("tokens")
        if not isinstance(toks, list):
            raise RuntimeError(f"Unexpected /tokenize response: {r!r}")
        return len(toks)


def sentence(rng: random.Random) -> str:
    return (f"{rng.choice(SUBJECTS).capitalize()} {rng.choice(ACTIONS)} {rng.choice(OBJECTS)} "
            f"{rng.choice(PLACES)}. {rng.choice(CLOSINGS)}")


def fill_to(tok: Tokenizer, text: str, target: int, rng: random.Random) -> str:
    """Searches a Spanish filler suffix for a cut that gives exactly the requested total."""
    current = tok.count(text)
    if current > target:
        raise ValueError(f"The fixed block exceeds the budget ({current-target} tokens)")
    missing = target - current
    if not missing:
        return text
    tail = " " + " ".join(sentence(rng) for _ in range(max(60, int(missing / 24) + 80)))
    lo, hi, best = 0, len(tail), text
    while lo <= hi:
        mid = (lo + hi) // 2
        candidate = text + tail[:mid]
        n = tok.count(candidate)
        if n <= target:
            best, lo = candidate, mid + 1
        else:
            hi = mid - 1
    # Searches locally around the cut in case the character limit crosses a BPE piece that
    # makes the count jump past the target.
    base = len(best) - len(text)
    for end in range(max(0, base - 64), min(len(tail), base + 64) + 1):
        candidate = text + tail[:end]
        if tok.count(candidate) == target:
            return candidate
    raise RuntimeError(f"Could not fit exactly {target} tokens without cutting a needle")


_RATIO = None
def chars_per_token(tok: Tokenizer) -> float:
    global _RATIO
    if _RATIO is None:
        rng = random.Random(1)
        sample = " ".join(sentence(rng) for _ in range(400))
        _RATIO = len(sample) / tok.count(sample)
    return _RATIO


def build_document(tok: Tokenizer, depth: int, index: int, seed: int) -> dict:
    rng = random.Random(seed)
    ids = [f"{rng.choice(TYPES).upper()}-{index:02d}-{j:02d}-{rng.randrange(100, 999)}" for j in range(20)]
    values = [rng.randrange(1000, 9999) for _ in ids]
    # Near-identical-looking false pairs: one digit of the ID changes and carries a different value.
    fakes = []
    for entry_id in ids:
        fake = entry_id[:-1] + str((int(entry_id[-1]) + 1) % 10)
        fakes.append((fake, rng.randrange(1000, 9999)))
    intro = ("Cuaderno de observaciones. El texto reúne notas de varias jornadas y lugares. "
             "Cada asiento conserva su identificador literal. Los datos de este cuaderno no están ordenados "
             "por importancia; la posición depende de cuándo se incorporó cada nota.\n\n")
    text = intro
    positions = []
    # 20 needles spread evenly. Each is padded to its local token target, then the entry is
    # appended and its tokenized offset recorded.
    margin = max(700, depth // 45)
    char_offsets = []
    for j, (entry_id, value) in enumerate(zip(ids, values)):
        target = margin + round((depth - 2 * margin) * j / 19)
        # Approximate character spacing (about 4.5 letters/token in this Spanish text); the
        # real positions are computed at the end with the tokenizer endpoint.
        target_chars = round(target * chars_per_token(tok) * 0.97)
        while len(text) < target_chars:
            text += (" " if text else "") + sentence(rng)
        block = (f"\nAsiento {j + 1}: {entry_id} = {value}. "
                 f"Referencia próxima: {fakes[j][0]} = {fakes[j][1]}.\n\n")
        start = len(text)
        text += block
        char_offsets.append(start + block.index(entry_id))
        positions.append({"id": entry_id, "value": value, "fake_id": fakes[j][0],
                           "fake_value": fakes[j][1], "char_offset": char_offsets[-1]})
    text = fill_to(tok, text, depth, rng)
    # Verifies the observed location of each string after joins/real tokenization.
    for p in positions:
        idx = p["char_offset"]
        p["verified_start_token"] = tok.count(text[:idx])
        if p["verified_start_token"] >= depth:
            raise RuntimeError("Needle ended up outside the document")
    # Each question combines one needle from the first half and one from the second.
    order = list(range(20)); rng.shuffle(order)
    firsts = [i for i in order if i < 10][:QUESTIONS_PER_DOC]; seconds = [i for i in order if i >= 10][:QUESTIONS_PER_DOC]
    questions = []
    for a, b in zip(firsts, seconds):
        if rng.random() < .5: a, b = b, a
        prompt = (f"Documento:\n{text}\n\nPregunta: localiza el valor asociado exactamente a {ids[a]} y a {ids[b]}. "
                  f"Devuelve solo JSON con claves \"{ids[a]}\", \"{ids[b]}\" y \"suma\", usando la suma aritmética. "
                  "No uses los identificadores parecidos.")
        questions.append({"question_ids": [ids[a], ids[b]], "needle_index": [a, b],
                          "needle_token": [positions[a]["verified_start_token"], positions[b]["verified_start_token"]],
                          "expected": {ids[a]: values[a], ids[b]: values[b], "suma": values[a] + values[b]},
                          "prompt": prompt, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()})
    return {"schema": 2, "depth_tokens": depth, "index": index, "seed": seed,
            "document": text, "document_tokens": tok.count(text), "needles": positions,
            "questions": questions}


def normalize(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I)
    return text.strip()


def evaluate(output: str, expected: dict) -> dict:
    clean = normalize(output)
    # The model may wrap JSON in a markdown block; the first object is extracted.
    m = re.search(r"\{[^{}]*\}", clean, flags=re.S)
    parsed = None
    if m:
        try:
            parsed = json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    pairs = {k: int(v) for k, v in parsed.items()
             if isinstance(v, (int, float)) or (isinstance(v, str) and v.strip().isdigit())} if parsed else {}
    correct = {k: pairs.get(k) == v for k, v in expected.items()}
    return {"parsed": parsed, "exact_match": bool(all(correct.values())),
            "field_accuracy": sum(correct.values()) / len(correct), "field_correct": correct,
            "loop_detected": detect_loop(clean)}


def detect_loop(s: str) -> bool:
    words = re.findall(r"\w+|[^\w\s]", s.lower())
    if len(words) < 80:
        return False
    # Conservative signal: the same 12-token block repeated at least 4 times.
    for n in (8, 12, 16):
        seen: dict[tuple[str, ...], int] = {}
        for i in range(0, len(words) - n + 1, n):
            k = tuple(words[i:i+n])
            seen[k] = seen.get(k, 0) + 1
            if seen[k] >= 4:
                return True
    return False


def save(path: pathlib.Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def resolve_monitor_abort(monitor_abort: BaseException, original_exc: BaseException | None) -> bool:
    """Decides what to do with a monitor abort (thermal/eviction/fdinfo) caught while cleaning
    up a run, when an exception from the run itself (`original_exc`, or None if the try body
    completed cleanly) may already be propagating.

    Returns True if the caller should raise `monitor_abort` (nothing else was propagating).
    Returns False if `original_exc` was already propagating: `original_exc` keeps propagating
    unchanged, mutated only by attaching `monitor_abort` as a note (`BaseException.add_note`,
    Python 3.11+) -- a plain `raise monitor_abort` from a `finally` block would otherwise mask
    `original_exc` (visible only as `__context__`), and overwriting `original_exc.__cause__`
    would silently discard an existing explicit cause (e.g. from `raise X from Y`). Either way
    the monitor abort is never silently dropped: it is either raised directly or left visible on
    whatever exception is already propagating.
    """
    if original_exc is None:
        return True
    original_exc.add_note(f"monitor abort during cleanup: {monitor_abort!r}")
    return False


def _parse_port(url: str) -> int:
    port = urllib.parse.urlparse(url).port
    if not port:
        raise SystemExit(f"--tokenizer-url must include a port: {url}")
    return port


_VARIANT_RE = re.compile(r"^(q8q8|q8q51)-mtp([01])$")


def parse_variants(values: list[str]) -> tuple[tuple[str, bool], ...]:
    """Parses --variants values like 'q8q51-mtp1' into (kv, mtp) pairs.

    Raises ValueError (with a usage-style message) on the first value that
    doesn't match <kv>-mtp<0|1>, kv in q8q8/q8q51.
    """
    parsed = []
    for v in values:
        m = _VARIANT_RE.match(v)
        if not m:
            raise ValueError(
                f"--variants: {v!r} must match <kv>-mtp<0|1>, kv in q8q8/q8q51 (e.g. q8q51-mtp1)"
            )
        parsed.append((m.group(1), m.group(2) == "1"))
    return tuple(parsed)


def main() -> int:
    global DEPTHS, DOCS, VARIANTS
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--smoke", action="store_true", help="validates the CLI and matrix without a server/GPU")
    default_query_count = DOCS * QUESTIONS_PER_DOC * len(DEPTHS) * len(VARIANTS)
    g.add_argument("--run", action="store_true",
                   help=f"runs {default_query_count} queries (with the default matrix); "
                        "requires systemd-inhibit")
    ap.add_argument("--tokenizer-url", default="http://127.0.0.1:18080")
    ap.add_argument("--runner", default=str(AQUI / "depth_bench.py"))
    ap.add_argument("--output", type=pathlib.Path, default=OUTPUT_DIR)
    ap.add_argument("--inhibitor-ok", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--depths", type=int, nargs="+", help="overrides DEPTHS")
    ap.add_argument("--docs", type=int, help="documents per depth")
    ap.add_argument("--variants", nargs="+", help="e.g. q8q51-mtp1 q8q8-mtp0")
    ap.add_argument("--ctx", type=int, default=262144)
    ap.add_argument("--server", help="alternate llama-server")
    ap.add_argument("--mtp-n", type=int, default=2, help="--spec-draft-n-max for mtp1 variants")
    ap.add_argument("--extra", default="",
                    help='extra llama-server flags appended to every variant, e.g. --extra "-ub 256"')
    args = ap.parse_args()
    if args.depths: DEPTHS = tuple(args.depths)
    if args.docs: DOCS = args.docs
    if args.variants:
        try:
            VARIANTS = parse_variants(args.variants)
        except ValueError as e:
            ap.error(str(e))
    if args.smoke:
        print(json.dumps({"ok": True, "cli": "longctx_quality.py --smoke", "depths": DEPTHS,
                          "documents_per_depth": DOCS, "questions_per_doc": QUESTIONS_PER_DOC, "variants": VARIANTS,
                          "requests": DOCS * QUESTIONS_PER_DOC * len(DEPTHS) * len(VARIANTS),
                          "temperature": 0, "max_tokens": MAX_OUTPUT_TOKENS, "ignore_eos": False}, ensure_ascii=False))
        return 0
    if os.environ.get("IA_BENCH_INHIBITED") != "1" or not args.inhibitor_ok:
        ap.error("requires systemd-inhibit, IA_BENCH_INHIBITED=1 and --inhibitor-ok; see the docstring")
    runner_path = pathlib.Path(args.runner)
    if not runner_path.is_file():
        raise SystemExit(f"Required runner does not exist: {runner_path}")
    spec = importlib.util.spec_from_file_location("depth_bench", runner_path)
    runner = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(runner)
    # Single source of truth for the port: the server is launched on the port parsed from
    # --tokenizer-url, so the imported runner's PORT/URL (used by wait_health, http_json and
    # stream_completion) are overridden to match instead of hitting depth_bench's own fixed port.
    port = _parse_port(args.tokenizer_url)
    runner.PORT = port
    runner.URL = f"http://127.0.0.1:{port}"
    run_matrix(args, runner)
    return 0


def run_matrix(args, runner):
    out = args.output / time.strftime("longctx-%Y%m%d-%H%M%S")
    docs_dir = out / "documents"
    out.mkdir(parents=True)
    docs_dir.mkdir()
    out_summary = out / "summary.jsonl"
    tok = Tokenizer(args.tokenizer_url)
    # Importing depth_bench reuses exactly its Monitor and SSE transport. This test controls
    # its own cycle to fix temp=0, max_tokens=MAX_OUTPUT_TOKENS and ignore_eos=false.
    model_path = pathlib.Path(runner.MODEL)
    server_path = pathlib.Path(args.server or runner.SERVER)
    if not model_path.is_file() or not server_path.is_file():
        raise SystemExit(f"Missing server/model: {server_path} / {model_path}")
    power_cap = runner.check_power_cap(max(max(DEPTHS), args.ctx))
    run_meta = {"created": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "runner": str(args.runner),
                "server": str(server_path), "model": str(model_path), "context": args.ctx,
                "depths": DEPTHS, "docs_per_depth": DOCS, "questions_per_doc": QUESTIONS_PER_DOC,
                "variants": VARIANTS, "seed_base": BASE_SEED, "temperature": 0,
                "max_tokens": MAX_OUTPUT_TOKENS, "thinking": False, "ignore_eos": False,
                "cache_prompt": True, "power_cap": power_cap}
    save(out / "metadata.json", run_meta)
    # For each depth a single series of documents (DOCS per depth) is fixed and reused
    # unchanged across all configured variants.
    documents = {}
    for kv, mtp in VARIANTS:
        variant_name = f"{kv}-mtp{int(mtp)}"
        variant_dir = out / variant_name
        variant_dir.mkdir()
        argv = [str(server_path), "-m", str(model_path), "--port", str(runner.PORT), "-c", str(args.ctx),
                "-ctk", "q8_0", "-ctv", "q8_0" if kv == "q8q8" else "q5_1",
                "--temp", "0", "--top-k", "20", "--min-p", "0", "-fa", "on", "-np", "1",
                "--ctx-checkpoints", "4", "-ngl", "all"]
        hardcoded = {tok for tok in argv if tok.startswith("-")}
        if mtp:
            argv += ["--spec-type", "draft-mtp", "--spec-draft-n-max", str(args.mtp_n)]
            hardcoded |= {"--spec-type", "--spec-draft-n-max"}
        argv += runner.extra_argv(args.extra, hardcoded)
        (variant_dir / "command.json").write_text(json.dumps(argv, indent=2) + "\n")
        with (variant_dir / "server.log").open("w") as log:
            proc = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            monitor = None
            run_exc = None  # the exception (if any) propagating out of the try body below,
            # captured explicitly in the `except` clause instead of read back from
            # sys.exc_info() in `finally` -- exc_info() reflects whatever is "currently
            # handled" on the call stack, which is only this run's own exception in the exact
            # shape exercised here (a bare try/finally with no other handler in between); it
            # would silently pick up the wrong exception if this ever ran nested inside another
            # except clause.
            try:
                monitor = runner.Monitor(proc.pid, (variant_dir / "telemetry.jsonl").open("w"))
                monitor.start()
                runner.wait_health(proc)
                monitor.set_phase("ready")
                if not documents:
                    for depth in DEPTHS:
                        documents[depth] = []
                        for i in range(DOCS):
                            seed = BASE_SEED + depth * 10 + i
                            doc = build_document(tok, depth, i, seed)
                            if doc["document_tokens"] != depth:
                                raise RuntimeError("document depth doesn't match target")
                            path = docs_dir / f"d{depth}-n{i:02d}.json"
                            save(path, doc)
                            doc["path"] = str(path)
                            documents[depth].append(doc)
                for depth in DEPTHS:
                    for i, doc in enumerate(documents[depth]):
                      runner.cool_down()
                      for q, question in enumerate(doc["questions"]):
                       try:
                        msg = [{"role": "user", "content": question["prompt"]}]
                        rendered = runner.http_json("/apply-template", {"messages": msg,
                            "chat_template_kwargs": {"enable_thinking": False}})["prompt"]
                        if "<think>" in rendered and "</think>" not in rendered:
                            raise RuntimeError("the template did not disable thinking")
                        input_ids = runner.http_json("/tokenize", {"content": rendered, "add_special": False})["tokens"]
                        payload = {"prompt": input_ids, "n_predict": MAX_OUTPUT_TOKENS, "temperature": 0,
                                   "top_k": 20, "min_p": 0, "seed": doc["seed"], "stream": True,
                                   "return_progress": True, "cache_prompt": True, "ignore_eos": False,
                                   "timings_per_token": True}
                        case = variant_dir / f"d{depth}-n{i:02d}-q{q}"
                        case.mkdir()
                        save(case / "request.json", {**payload, "prompt": rendered,
                               "prompt_tokens": len(input_ids), "document_file": doc["path"],
                               "document_sha256": hashlib.sha256(doc["document"].encode()).hexdigest()})
                        monitor.set_phase("prefill")
                        started = time.monotonic()
                        response, content = runner.stream_completion(payload, case / "response.sse", monitor)
                        elapsed = time.monotonic() - started
                        monitor.set_phase("complete")
                        score = evaluate(content, question["expected"])
                        timings = (response or {}).get("timings", {})
                        result = {"variant": variant_name, "kv": kv, "mtp2": mtp, "depth": depth,
                                  "document_index": i, "question": q, "needle_index": question["needle_index"],
                                  "needle_token": question["needle_token"], "seed": doc["seed"], "document_tokens": doc["document_tokens"],
                                  "prompt_tokens": len(input_ids), "question_ids": question["question_ids"],
                                  "expected": question["expected"], "response_text": content,
                                  "response_final": response, "timings": timings, "elapsed_s": elapsed,
                                  "exact_match": score["exact_match"], "field_accuracy": score["field_accuracy"],
                                  "field_correct": score["field_correct"], "parsed": score["parsed"],
                                  "loop_detected": score["loop_detected"],
                                  "truncated": bool((response or {}).get("truncated")),
                                  "finish_reason": (response or {}).get("stop_type"),
                                  "request_file": str(case / "request.json"),
                                  "raw_sse_file": str(case / "response.sse")}
                        with out_summary.open("a") as f:
                            f.write(json.dumps(result, ensure_ascii=False) + "\n")
                       except Exception as e:
                        # A failure on a single question is recorded and the run continues; if the
                        # server or the monitor died, it stops.
                        with out_summary.open("a") as f:
                            f.write(json.dumps({"variant": variant_name, "depth": depth, "document_index": i,
                                                "question": q, "failure": repr(e)}) + "\n")
                        if proc.poll() is not None or monitor.error or monitor.bad:
                            raise
            except BaseException as e:
                # BaseException, not Exception: KeyboardInterrupt/SystemExit must also be
                # captured here so a monitor abort discovered in `finally` never replaces an
                # interrupt (resolve_monitor_abort only defers to `run_exc` when it's not None).
                run_exc = e
                raise
            finally:
                monitor_abort = None
                if monitor:
                    try:
                        monitor.stop()
                    except Exception as e:
                        # monitor.stop() re-raises a thermal/eviction/fdinfo abort recorded by
                        # the background thread; the server cleanup below must still run, so
                        # record it here and re-raise once that cleanup is done.
                        monitor_abort = e
                    finally:
                        monitor.file.close()
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait()
                if monitor_abort is not None:
                    with out_summary.open("a") as f:
                        f.write(json.dumps({"variant": variant_name,
                                            "monitor_abort": repr(monitor_abort)}) + "\n")
                    if resolve_monitor_abort(monitor_abort, run_exc):
                        raise monitor_abort
    # Exact-match score aggregated by depth and configuration, plus loop incidents.
    rows = [json.loads(line) for line in out_summary.read_text().splitlines() if line.strip()]
    failures = [r for r in rows if "failure" in r]
    rows = [r for r in rows if "failure" not in r]
    scores = []
    for kv, mtp in VARIANTS:
        name = f"{kv}-mtp{int(mtp)}"
        for depth in DEPTHS:
            subset = [r for r in rows if r["variant"] == name and r["depth"] == depth]
            scores.append({"variant": name, "depth": depth, "n": len(subset),
                           "exact": sum(r["exact_match"] for r in subset),
                           "exact_rate": sum(r["exact_match"] for r in subset) / len(subset) if subset else None,
                           "field_accuracy": sum(r["field_accuracy"] for r in subset) / len(subset) if subset else None,
                           "loops": sum(r["loop_detected"] for r in subset),
                           "truncated": sum(r["truncated"] for r in subset),
                           "failures": sum(1 for r in failures if r["variant"] == name and r["depth"] == depth)})
    save(out / "scores.json", scores)
    print(out)


if __name__ == "__main__":
    raise SystemExit(main())
