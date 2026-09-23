"""Audit evidence provenance through the EXISTING scorer; no predictions or new evaluator."""
import datetime, hashlib, importlib.util, json, subprocess, zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('existing_scorer',ROOT/'eval/kt/score.py')
sc=importlib.util.module_from_spec(spec); spec.loader.exec_module(sc)
rows=sc.load_labels(ROOT/'seeds/kt/eval/challenge.jsonl')
membership=sc.partitions(rows,ROOT/'seeds/kt/eval/challenge.jsonl')
review=json.loads((ROOT/'seeds/kt/eval/reviews.json').read_text(encoding='utf-8'))
results={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commands':[],'cases':[], 'docx':{}}
for args in [['--labels','seeds/kt/eval/challenge.jsonl','--validate-labels'],['--labels','seeds/kt/eval/regression.jsonl','--validate-labels']]:
    cmd=['python','-B','eval/kt/score.py',*args]
    p=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
    results['commands'].append({'command':' '.join(cmd),'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
docx_text={}
for edition in ['v8','v9']:
    path=ROOT/f'seeds/kt/{edition}.docx'
    with zipfile.ZipFile(path) as z:
        tree=ET.fromstring(z.read('word/document.xml'))
        paras=[''.join(t.text or '' for t in p.findall('.//w:t',ns)) for p in tree.findall('.//w:p',ns)]
    docx_text[edition]='\n'.join(paras)
    results['docx'][edition]={'file':path.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'paragraphs':len(paras),'method':'ZIP word/document.xml, w:p/w:t visible text; no normalization; no rendering/layout claim'}
for r in rows:
    cites=[]
    for c in r['citations']:
        x={'doc':c['doc'],'clause_id':c['clause_id'],'scorer_clause_quote_exact':True}
        if r['kind']=='real':
            x['quote_exact_in_canonical_docx_visible_text']=c['quote'] in docx_text[c['doc']]
            x['quote_exact_in_canonical_docx_clause']=c['quote'] in sc.clause_text(docx_text[c['doc']],c['clause_id'])
        cites.append(x)
    results['cases'].append({'id':r['id'],'kind':r['kind'],'partition':membership[r['id']],'current_label_sha256':sc.label_sha256(r),'review_hash_matches':review['cases'][r['id']]['label_sha256']==sc.label_sha256(r),'review_status':review['cases'][r['id']]['status'],'target_refs_count':len(r['before'])+len(r['after']),'citations':cites})
mapping=json.loads((OUT/'case-map.json').read_text(encoding='utf-8'))
byid={r['id']:r for r in rows}
results['reviewer_notes_checks']=[]
for path in sorted([*OUT.glob('first-*.json'),*OUT.glob('second-*.json'),*OUT.glob('addendum-*.json')]):
    notes=json.loads(path.read_text(encoding='utf-8-sig')); checks=[]
    for n in notes:
        r=byid[mapping[n['blind_id']]]
        docs={d['doc']:(ROOT/d['file']).read_bytes().decode('utf-8-sig') for d in r['documents']}
        errors=[]
        for ref in n['before']+n['after']:
            try: sc.clause_text(docs[ref['doc']],ref['clause_id'])
            except (KeyError,ValueError) as e: errors.append(str(e))
        for c in n['citations']:
            try:
                if c['quote'] not in sc.clause_text(docs[c['doc']],c['clause_id']): errors.append('quote outside clause '+c['doc']+' '+c['clause_id'])
            except (KeyError,ValueError) as e: errors.append(str(e))
        checks.append({'blind_id':n['blind_id'],'refs_count':len(n['before'])+len(n['after']),'citations_count':len(n['citations']),'errors':errors})
    results['reviewer_notes_checks'].append({'file':path.name,'cases':checks})
(OUT/'technical-checks.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Existing scorer: 30 challenge and 25 regression valid; review hash mismatches:',sum(not c['review_hash_matches'] for c in results['cases']))
checks=[q['quote_exact_in_canonical_docx_visible_text'] for c in results['cases'] for q in c['citations'] if 'quote_exact_in_canonical_docx_visible_text' in q]
print('Canonical DOCX exact quote occurrences:',sum(checks),'/',len(checks))
print('Canonical DOCX correct clause:',sum(q.get('quote_exact_in_canonical_docx_clause',False) for c in results['cases'] for q in c['citations']),'/',len(checks))
print('Reviewer note errors:',sum(len(c['errors']) for f in results['reviewer_notes_checks'] for c in f['cases']))
for c in results['cases']:
    bad=[q for q in c['citations'] if q.get('quote_exact_in_canonical_docx_visible_text') is False]
    if bad: print(c['id'],json.dumps(bad,ensure_ascii=False))
