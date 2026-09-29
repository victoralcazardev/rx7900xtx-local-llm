#!/usr/bin/env python3
"""Paired speculative-decoding variants at empty context (MTP alone vs. MTP stacked with n-gram).

Server flags follow the adopted profile 262k-q8q51-mtp. Run inside systemd-inhibit; reuses
depth_bench's instrumentation. Configure via environment variables before running:
BENCH_SERVER, BENCH_MODEL, BENCH_OUT (see depth_bench.py).
Run (n-gram question only): systemd-inhibit --what=sleep:idle --mode=block env IA_BENCH_INHIBITED=1 BENCH_SERVER=... BENCH_MODEL=... python3 bench/spec_bench.py --run --variants mtp3 mtp3-mod mtp3-moddef mtp3-map --tag ngram-stack
"""
import argparse, json, os, subprocess, time, statistics
from pathlib import Path
import depth_bench as b

# Deliberately Spanish (STYLE.md exception): these are the actual prompts sent to the model,
# matching how this project's models are used day to day.
PROMPTS = {
 'code': 'Escribe una implementación Python de un cliente HTTP asíncrono con límite de concurrencia, timeout y reintentos exponenciales. Usa type hints y añade pruebas unitarias sin red real.',
 'editing': 'Devuelve el código completo añadiendo anotaciones de tipos, validación de negativos y docstrings. Mantén los nombres públicos.\n'+ '\n'.join(f'def calcular_{i}(valores):\n    total = 0\n    for valor in valores:\n        total += valor * {i+1}\n    return total\n' for i in range(16)),
 'spanish': 'Redacta en español un procedimiento de recuperación tras una caída del servidor de una biblioteca municipal: diagnóstico, copias, restauración y comunicación. Incluye ejemplos concretos y criterios de comprobación.',
 'extraction': 'Devuelve solo JSON con total, promedio y mayores_que_20 para estos valores: 12, 18, 25, 31, 14. No redondees el promedio.',
 'agent': 'Eres un agente de código. Devuelve el fichero COMPLETO, sin omitir nada, con un único cambio: la función procesar_7 debe ignorar los valores None. No expliques nada.\n```python\n'+'\n'.join(f'def procesar_{i}(registros, factor={i+2}):\n    """Suma los importes del lote {i} multiplicados por el factor."""\n    resultado = []\n    for registro in registros:\n        importe = registro.get("importe", 0)\n        resultado.append({{"id": registro["id"], "total": importe * factor, "lote": {i}}})\n    return resultado\n' for i in range(30))+'```',
 'reasoning': 'En una biblioteca hay 120 libros. El lunes se prestan 35 y se devuelven 12; el martes se prestan 28 y se devuelven 19. De los disponibles el miércoles se reservan 17. Explica cuántos quedan sin reservar y comprueba las cuentas.'}
VARIANTS={'none':[], 'mtp2':['--spec-type','draft-mtp','--spec-draft-n-max','2'],
 'mtp3':['--spec-type','draft-mtp','--spec-draft-n-max','3'],
 'mtp2-map':['--spec-type','draft-mtp,ngram-map-k4v','--spec-draft-n-max','2'],
 'mtp2-mod':['--spec-type','draft-mtp,ngram-mod','--spec-draft-n-max','2','--spec-ngram-mod-n-match','24','--spec-ngram-mod-n-min','8','--spec-ngram-mod-n-max','32'],
 'mtp2-moddef':['--spec-type','draft-mtp,ngram-mod','--spec-draft-n-max','2'],
 'mtp3-mod':['--spec-type','draft-mtp,ngram-mod','--spec-draft-n-max','3','--spec-ngram-mod-n-match','24','--spec-ngram-mod-n-min','8','--spec-ngram-mod-n-max','32'],
 'mtp3-moddef':['--spec-type','draft-mtp,ngram-mod','--spec-draft-n-max','3'],
 'mtp3-map':['--spec-type','draft-mtp,ngram-map-k4v','--spec-draft-n-max','3']}
def aggregate_rows(rows):
 incomplete_count=sum(x['incomplete'] for x in rows)
 summary={}
 for variant in VARIANTS:
  r=[x for x in rows if x['variant']==variant and not x['incomplete']];speeds=[x['predicted_per_second'] for x in r if 'predicted_per_second' in x]
  if speeds:summary[variant]={'n':len(speeds),'median_tg':statistics.median(speeds),'min_tg':min(speeds),'max_tg':max(speeds),'total_wall_s':sum(x['wall_s'] for x in r),'draft_n':sum(x.get('draft_n',0) for x in r),'accepted_n':sum(x.get('draft_n_accepted',0) for x in r)}
 for variant in VARIANTS:
  for kind in PROMPTS:
   r=[x for x in rows if x['variant']==variant and x['task']==kind and not x['incomplete']]
   speeds=[x['predicted_per_second'] for x in r if 'predicted_per_second' in x]
   if speeds:summary[f'{variant}/{kind}']={'n':len(speeds),'median_tg':statistics.median(speeds),'median_wall_s':statistics.median(x['wall_s'] for x in r),'accept':sum(x.get('draft_n_accepted',0) for x in r)/max(1,sum(x.get('draft_n',0) for x in r)),'predicted_n':[x.get('predicted_n') for x in r]}
 return summary,incomplete_count

def build_parser():
 ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--smoke',action='store_true');ap.add_argument('--run',action='store_true')
 ap.add_argument('--variants',nargs='+',choices=tuple(VARIANTS),default=list(VARIANTS));ap.add_argument('--tag',default='');return ap

def main():
 ap=build_parser();a=ap.parse_args()
 if os.environ.get('IA_BENCH_INHIBITED')!='1':ap.error('requires systemd-inhibit and IA_BENCH_INHIBITED=1')
 if not (a.smoke or a.run):ap.error('--run or --smoke')
 out=b.BASE/('spec-'+time.strftime('%Y%m%d-%H%M%S')+(f'-{a.tag}' if a.tag else ''));out.mkdir(parents=True)
 helptext=subprocess.check_output([str(b.SERVER),'--help'],stderr=subprocess.STDOUT,text=True);(out/'help.txt').write_text(helptext)
 for extra in (VARIANTS[v] for v in a.variants):
  for flag in extra[::2]:
   if flag.startswith('--') and flag not in helptext:raise ValueError('Missing flag '+flag)
 rows=[]
 for variant,extra in ((v,VARIANTS[v]) for v in a.variants):
  b.cool_down();case=out/variant;case.mkdir()
  cmd=[str(b.SERVER),'-m',str(b.MODEL),'--port',str(b.PORT),'-c','262144','-ctk','q8_0','-ctv','q5_1','-fa','on','-np','1','--ctx-checkpoints','4','-ngl','all','-ub','256','--temp','1','--top-p','0.95','--top-k','20','--min-p','0','--reasoning-effort','medium']+extra
  (case/'command.json').write_text(json.dumps(cmd))
  with (case/'server.log').open('w') as log,(case/'telemetry.jsonl').open('w') as tel:
   proc=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT);mon=b.Monitor(proc.pid,tel);mon.start()
   try:
    b.wait_health(proc, mon);mon.set_phase('ready')
    for kind,prompt in (list(PROMPTS.items())[:1] if a.smoke else PROMPTS.items()):
     rendered=b.http_json('/apply-template',{'messages':[{'role':'user','content':prompt}]})['prompt']
     ids=b.http_json('/tokenize',{'content':rendered,'add_special':False})['tokens']
     for seed in ([42] if a.smoke else [42,43,44]):
      name=f'{kind}-{seed}';payload={'prompt':ids,'n_predict':32 if a.smoke else (4096 if kind=='agent' else 1500),'temperature':1,'top_p':0.95,'top_k':20,'min_p':0,'seed':seed,'cache_prompt':False,'ignore_eos':False,'stream':True,'return_progress':True}
      (case/(name+'-request.json')).write_text(json.dumps(payload,ensure_ascii=False));mon.set_phase('prefill');start=time.monotonic()
      final,content=b.stream_completion(payload,case/(name+'.sse'),mon)
      row={'variant':variant,'task':kind,'seed':seed,'wall_s':time.monotonic()-start,'input_n':len(ids),'response':final,'content':content}
      row['incomplete']=bool(not final or not final.get('stop') or final.get('truncated'))
      if mon.error:raise RuntimeError(str(mon.error))
      t=(final or {}).get('timings',{});row.update(t)
      if kind=='extraction':
       import re
       matches=re.findall(r'\{[^{}]*\}',content);score=False
       for raw in matches:
        try:
         obj=json.loads(raw);score=obj.get('total')==100 and obj.get('promedio')==20 and obj.get('mayores_que_20')==[25,31]
        except ValueError:pass
       row['verified_extraction']=score
      rows.append(row)
      with (out/'summary.jsonl').open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
      mon.set_phase('ready');print(variant,kind,seed,round(t.get('predicted_per_second',0),2),flush=True)
   finally:
    try:mon.stop()
    finally:
     proc.terminate()
     try:proc.wait(timeout=20)
     except subprocess.TimeoutExpired:proc.kill();proc.wait()
 summary,incomplete_count=aggregate_rows(rows)
 print(f'{incomplete_count} incomplete rows excluded from aggregates')
 (out/'aggregate.json').write_text(json.dumps(summary,indent=2));print(out)
if __name__=='__main__':main()
