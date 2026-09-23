"""Prepare source-only review packets and an immutable audit snapshot; not an evaluator."""
import datetime, hashlib, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
if (OUT/'initial-state.json').exists():
    raise SystemExit('Initial review snapshot already exists; refusing to overwrite custody evidence.')
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name, value): (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
rows = [json.loads(s) for s in (ROOT/'seeds/kt/eval/challenge.jsonl').read_text(encoding='utf-8').splitlines() if s]
split = json.loads((ROOT/'seeds/kt/eval/split.json').read_text(encoding='utf-8'))
paths = subprocess.check_output(['git','ls-files','-c','-o','--exclude-standard'], cwd=ROOT, text=True).splitlines()
snapshot = {p:digest(ROOT/p) for p in paths if (ROOT/p).is_file() and not p.startswith('seeds/kt/eval/independent-review/')}
write('initial-state.json', {'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(), 'git_status':subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True), 'sha256':snapshot})
plan=(ROOT/'docs/plan.md').read_text(encoding='utf-8')
(OUT/'contract.md').write_text(plan[plan.index('## 3. Contract'):plan.index('## 4. Individual modules')],encoding='utf-8')
mapping={}
for partition,kind,prefix in [('development','real','DR'),('development','synthetic','DS'),('holdout','real','HR'),('holdout','synthetic','HS')]:
    packet=[]
    for r in rows:
        if r['kind']!=kind or split['cases'][r['id']]['partition']!=partition: continue
        blind_id=f'{prefix}{len(packet)+1:02}'
        mapping[blind_id]=r['id']
        docs=[]
        for d in r['documents']:
            content=(ROOT/d['file']).read_text(encoding='utf-8-sig')
            if kind=='real':
                # Whole governing sections, preserving original numbered text.
                sections=['1','3','5','9'] if partition=='development' else ['7','8']
                lines=content.splitlines(keepends=True); chosen=[]; active=False
                import re
                for line in lines:
                    m=re.match(r'^(\d+)\.\s',line)
                    if m: active=m.group(1) in sections
                    if active: chosen.append(line)
                content=''.join(chosen)
            docs.append({'doc':d['doc'],'file':d['file'],'sha256':digest(ROOT/d['file']),'source_text':content})
        packet.append({'blind_id':blind_id,'partition':partition,'kind':kind,'before':r['before'],'after':r['after'],'documents':docs})
    write(f'blind-{partition}-{kind}.json',packet)
write('case-map.json',mapping)
print('Prepared four source-only packets:',len(rows),'cases. Snapshot files:',len(snapshot))
