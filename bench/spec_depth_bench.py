#!/usr/bin/env python3
"""MTP at depth: which draft n performs best with a 240K context?
Hypothesis (fattn.cu, llama.cpp b11160): on RDNA3 with quantized KV, batches of 1-2 tokens use
the VEC kernel (reads q8/q5_1 directly) and batches of >=3 use TILE (converts each layer's KV
to f16 on every step). MTP n=2 verifies 3 tokens -> TILE. n=1 verifies 2 -> VEC.
One server per variant (per-request speculative-decoding parameters are disabled in b11160).
Temperature 0: text should come out identical across variants; checked with a hash.
Run: systemd-inhibit --what=sleep:idle --mode=block env IA_BENCH_INHIBITED=1 python spec_depth_bench.py --run

Configure via environment variables before running: BENCH_SERVER, BENCH_MODEL, BENCH_WIKI,
BENCH_OUT (see depth_bench.py), and, for the DFlash variants, BENCH_DFLASH_MODEL (DFlash draft
GGUF) and BENCH_MODEL_NO_MTP (the base model without an MTP head).
"""
import argparse, hashlib, json, os, signal, subprocess, time
import depth_bench as b

VARIANTS = {'none': [], 'n1': ['--spec-type', 'draft-mtp', '--spec-draft-n-max', '1'],
            'n2': ['--spec-type', 'draft-mtp', '--spec-draft-n-max', '2'],
            'n3': ['--spec-type', 'draft-mtp', '--spec-draft-n-max', '3'],
            'dfl5': ['-md', os.environ.get('BENCH_DFLASH_MODEL', ''), '-ngld', 'all',
                     '--spec-type', 'draft-dflash', '--spec-draft-n-max', '5', '--spec-draft-p-min', '0.4'],
            'dfl3': ['-md', os.environ.get('BENCH_DFLASH_MODEL', ''), '-ngld', 'all',
                     '--spec-type', 'draft-dflash', '--spec-draft-n-max', '3']}
# DFlash uses the GGUF without an MTP head (saves ~317 MiB of weights that would go unused).
MODEL_NO_MTP = b.Path(os.environ.get('BENCH_MODEL_NO_MTP', ''))
TASKS = {
    # Deliberately Spanish (STYLE.md exception): actual prompts sent to the model.
    'essay': 'Escribe un ensayo detallado que sintetice, explique y conecte las ideas del texto anterior.',
    'copy': 'Copia literalmente, sin cambiar nada, los tres primeros párrafos del texto anterior.',
    'code': 'Escribe una función Python que cuente la frecuencia de cada palabra del texto anterior, con type hints y pruebas unitarias.'}
OUTPUT_TOKENS = 400

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run', action='store_true', required=True)
    ap.add_argument('--depth', type=int, default=240000)
    ap.add_argument('--reps', type=int, default=2)
    ap.add_argument('--kv', default='q5_1', help='V cache type')
    ap.add_argument('--kv-k', default='q8_0', help='K cache type (e.g. kvarn8 on BeeLlama)')
    ap.add_argument('--ctx', type=int, default=262144)
    ap.add_argument('--variants', nargs='+', default=list(VARIANTS))
    ap.add_argument('--server', help='alternate llama-server binary (e.g. the vec4 engine)')
    ap.add_argument('--tag', default='')
    ap.add_argument('--extra', default='',
                     help='extra llama-server flags appended to every variant, for A/B-testing '
                          'a new flag without editing this script, e.g. '
                          '--extra "--spec-draft-p-min 0.3"')
    a = ap.parse_args()
    if a.server: b.SERVER = b.Path(a.server)
    if os.environ.get('IA_BENCH_INHIBITED') != '1': ap.error('requires systemd-inhibit and IA_BENCH_INHIBITED=1')
    if any(v.startswith('dfl') for v in a.variants) and (not os.environ.get('BENCH_DFLASH_MODEL') or not MODEL_NO_MTP.is_file()):
        ap.error('dfl variants need BENCH_DFLASH_MODEL and BENCH_MODEL_NO_MTP set to existing files')
    out = b.BASE / (time.strftime('spec-depth-%Y%m%d-%H%M%S') + (f'-{a.tag}' if a.tag else '')); out.mkdir(parents=True)
    helptext = subprocess.check_output([str(b.SERVER), '--help'], stderr=subprocess.STDOUT, text=True)
    (out / 'server-help.txt').write_text(helptext)
    wiki = b.WIKI.read_text(errors='replace')
    for v in a.variants:
        cooldown = b.cool_down()
        case = out / v; case.mkdir()
        argv = [str(b.SERVER), '-m', str(MODEL_NO_MTP if v.startswith('dfl') else b.MODEL), '--port', str(b.PORT), '-c', str(a.ctx), '-ctk', a.kv_k,
                '-ctv', a.kv, '-fa', 'on', '-np', '1', '--ctx-checkpoints', '4', '-ngl', 'all',
                '--temp', '1', '--top-k', '20', '--min-p', '0'] + VARIANTS[v]
        hardcoded = {'-m', '--port', '-c', '-ctk', '-ctv', '-fa', '-np', '--ctx-checkpoints', '-ngl',
                     '--temp', '--top-k', '--min-p'} | {tok for tok in VARIANTS[v] if tok.startswith('-')}
        argv += b.extra_argv(a.extra, hardcoded)
        (case / 'command.json').write_text(json.dumps(argv, indent=2))
        with (case / 'server.log').open('w') as log, (case / 'telemetry.jsonl').open('w') as tel:
            proc = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            mon = b.Monitor(proc.pid, tel); mon.start()
            try:
                b.wait_health(proc, mon); mon.set_phase('ready')
                # Shared document: depth_bench's corpus trimmed to the exact depth (without the instruction).
                _, _, doc = b.build_prompt(wiki, a.depth)
                doc = doc.rsplit('\n\nEscribe un ensayo', 1)[0]
                for task, instr in TASKS.items():
                    msgs = [{'role': 'user', 'content': doc + '\n\n' + instr}]
                    rendered = b.http_json('/apply-template', {'messages': msgs})['prompt']
                    ids = b.http_json('/tokenize', {'content': rendered, 'add_special': False})['tokens']
                    for rep in range(1, a.reps + 2):  # the 1st is a prefill warm-up, doesn't count
                        payload = {'prompt': ids, 'n_predict': OUTPUT_TOKENS, 'temperature': 0, 'top_k': 20, 'min_p': 0,
                                   'seed': 7, 'stream': True, 'return_progress': True, 'cache_prompt': True,
                                   'ignore_eos': False, 'timings_per_token': True}
                        mon.set_phase('prefill' if rep == 1 else 'warm')
                        t0 = time.monotonic()
                        final, content = b.stream_completion(payload, case / f'{task}-{rep}.sse', mon)
                        t = (final or {}).get('timings', {})
                        row = {'variant': v, 'server': str(b.SERVER), 'task': task, 'rep': rep, 'warmup': rep == 1, 'input_n': len(ids),
                               'wall_s': time.monotonic() - t0, 'timings': t, 'cooldown_s': cooldown,
                               'content_sha256': hashlib.sha256(content.encode()).hexdigest(),
                               'stop_type': (final or {}).get('stop_type'), 'truncated': (final or {}).get('truncated')}
                        with (out / 'summary.jsonl').open('a') as f: f.write(json.dumps(row) + '\n')
                        print(v, task, rep, t.get('cache_n'), t.get('prompt_n'), round(t.get('predicted_per_second', 0), 2),
                              t.get('draft_n_accepted'), t.get('draft_n'), flush=True)
            finally:
                mon.running = False; mon.thread.join(timeout=3)
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try: proc.wait(timeout=20)
                    except subprocess.TimeoutExpired: os.killpg(proc.pid, signal.SIGKILL); proc.wait()
    print(out)

if __name__ == '__main__': main()
