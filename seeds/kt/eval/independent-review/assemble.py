"""Root-only assembly of review notes. This does not score a system or modify labels."""
import collections, datetime, hashlib, importlib.util, json, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]; OUT=Path(__file__).resolve().parent
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,x): (OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
spec=importlib.util.spec_from_file_location('existing_scorer',ROOT/'eval/kt/score.py')
sc=importlib.util.module_from_spec(spec);spec.loader.exec_module(sc)
rows=sc.load_labels(ROOT/'seeds/kt/eval/challenge.jsonl'); split=read(ROOT/'seeds/kt/eval/split.json')
mapping=read(OUT/'case-map.json'); inverse={v:k for k,v in mapping.items()}
first={};second={};addendum={}
for pattern, target in [('first-*.json',first),('second-*.json',second),('addendum-*.json',addendum)]:
    for p in sorted(OUT.glob(pattern)):
        for n in read(p): target[n['blind_id']]={**n,'notes_file':p.name}
assert len(first)==30 and len(second)==16
def key(n): return n.get('proposed_status',n.get('expected_status')),sc.signature(n)
def refs(rs): return ', '.join(f"`{r['doc']} §{r['clause_id']}`" for r in rs) or '∅'
def decision(r):
    cid=r['id']; status=r['expected_status']; outcome='согласие'; note='Статус и полные целевые множества refs поддержаны исходниками.'
    if cid in ('dev-split','dev-merge'):
        status='moved'; outcome='предлагаемая поправка'
        note=('Предложение главного проверяющего: changed → moved при трактовке сохранённой функции по смыслу. '
              'Оба действия и ответственный сохранены, изменилось распределение по пунктам. Первый reviewer выбрал changed '
              'по изменению текста/структуры, второй — moved по сохранению функции. Контракт не задаёт приоритет '
              'для семантически эквивалентного split/merge; человек должен закрепить единое правило. До решения не менять gold.')
    elif cid=='dev-real-shared-information':
        status='moved';outcome='предлагаемая поправка'
        note=('Предложение changed → moved: запрос информации и контроль своевременности/полноты сохранены; '
              'изменились номер и круг исполнителей, грамматика согласована с множественным субъектом. Это соответствует '
              '«preserved function with changed location/owner». Первый reviewer трактует расширение исполнителей как changed; '
              'второй — moved. Оставить спор человеку. Параллельная функция ДНМ в §5.4.3 обеих редакций не доказывает duplicate; '
              'не включать её в целевые refs только из-за сходных слов.')
    elif cid=='dev-real-audit-goals':
        outcome='предлагаемая поправка'
        note=('Поправка к evidence/rationale, статус moved пока сохранить для узкой целевой процедуры: добавить контекст '
              'v8/v9 §9.37. Общая ответственность Главного аудитора сохранена, но допустимый делегат меняется с '
              'Директора направления внутреннего аудита на Директора операционного аудита. Оба reviewer считают это '
              'отдельным изменением общей нормы, не изменяющим целевое действие. Главный проверяющий считает более широкую '
              'трактовку changed также обоснованной, если delegated execution входит в контекст каждой процедуры. '
              'Человеку решить границу контекста; нельзя описывать весь контекст контроля как неизменный. '
              'Буквы з→е подтверждены каноническими DOCX; отсутствие а/б у v8 уже есть в DOCX, это не ошибка TXT.')
    elif cid=='dev-real-roles':
        note=('Сохранить changed как изменение управляющего заголовка §5.3. Это структурная норма о круге исполнителей, '
              'а не самостоятельная функция; не использовать этот единственный heading как доказательство переноса всех дочерних обязанностей.')
    elif cid=='dev-real-merge':
        note=('Сохранить changed и текущий 2:1 набор на уровне целевых пунктов. Родительские заголовки и буквенные '
              'детализации включены в evidence, но не молча считаются целевыми refs. Норма ДНМ §5.4.2 отдельно сохранена '
              'в обеих редакциях; её нельзя присоединять лишь по совпадению формулировки. Для оценки всего поддерева '
              'понадобятся явно объявленные дополнительные строки/refs; текущий случай не доказывает покрытие всех потомков.')
    elif cid=='dev-real-correspondence':
        note=('Сохранить changed и 2:1 refs. В v9 не повторены явно подразделения Общества и ДЗО из права ДНМ; '
              'это текстовое изменение охвата. Оно не доказывает фактический запрет переписки или полную потерю права. '
              'Номер v9 §5.7.3 сам по себе не является преемником старого §5.7.3.')
    elif cid=='dev-real-staffing':
        note=('Сохранить changed и 2:1 refs. Изменены формулировки круга работников и адресата предложения; отсутствие '
              'слов «Главному аудитору» не доказывает назначение другого фактического адресата. Учитывать ограничение зоны деятельности.')
    elif cid=='hold-split':
        status='moved';outcome='предлагаемая поправка'
        note=('Оба независимых reviewer предложили moved, текущая метка changed. Действия и ответственный сохранены, '
              'изменена структура пунктов 1:2. Предлагается moved по сохранению функции, но факт согласия моделей не '
              'устраняет неопределённость контракта между изменением текста пунктов и изменением смысла. Решение человека обязательно.')
    return status,outcome,note

technical=read(OUT/'technical-checks.json')
supplement={'dev-split':[('before-1','2.1'),('after-1','2.1')],
            'dev-merge':[('before-1','2.1'),('after-1','2.1')],
            'dev-real-merge':[('v8','5.4.2'),('v9','5.4.2')]}
counts={};case_records=[]
for partition in ['development','holdout']:
    selected=[r for r in rows if split['cases'][r['id']]['partition']==partition]
    lines=[f'# Независимая проверка: {partition}', '',
           'Дата: 2026-09-23. Все выводы — AI review GPT-6 Sol и сводка главного агента; человеческого подтверждения нет. '
           'Итоговая разметка не изменена; все 30 challenge-строк остаются pending_human.', '',
           ('HOLDOUT: не передавать этот файл и его первичные заметки для настройки ядра. Система не запускалась, '
            'системные ответы проверяющим не показывались.' if partition=='holdout' else
            'Этот файл содержит только development. Содержимое и ответы holdout находятся отдельно в holdout.md.'), '',
           'Первые оценки сохранены до сопоставления с текущими метками. Вторые проверяющие получили исходники и refs, '
           'но не первые ответы. Главный агент видел текущую разметку и сводил результаты; его рекомендации не выдаются за слепую оценку. '
           'Отделение процедурное в общем workspace, не техническая изоляция. Семантические имена synthetic-файлов были видны. '
           'В слепых пакетах переводы строк представлены LF; все цитаты дополнительно проверены существующим scorer на исходных байтах.', '',
           'Короткие поля proposed_status в первичных заметках — форма рабочих review notes, не новый формат labels/Report. '
           'Везде использован только enum действующего контракта.', '',
           '| ID | Вид | Текущая | Первый Sol | Второй Sol | Рекомендация главного | Итог |',
           '| --- | --- | --- | --- | --- | --- | --- |']
    stats={'cases':len(selected),'kind_counts':dict(collections.Counter(r['kind'] for r in selected)),
           'first_matches_current':0,'first_disagrees_current':0,'second_reviewed':0,'reviewer_agreements':0,
           'reviewer_disagreements':0,'proposed_status_changes':0,'evidence_corrections_only':0}
    for r in selected:
        b=inverse[r['id']];a=first[b];s=second.get(b); proposed,outcome,note=decision(r)
        stats['first_matches_current' if key(a)==key(r) else 'first_disagrees_current']+=1
        if s:
            stats['second_reviewed']+=1; stats['reviewer_agreements' if key(a)==key(s) else 'reviewer_disagreements']+=1
        if proposed!=r['expected_status']: stats['proposed_status_changes']+=1
        elif outcome=='предлагаемая поправка': stats['evidence_corrections_only']+=1
        lines.append(f"| {r['id']} | {r['kind']} | {r['expected_status']} | {a['proposed_status']} | {s['proposed_status'] if s else 'не назначен'} | {proposed} | {outcome} |")
    counts[partition]=stats
    lines+=['','Числа: '+json.dumps(stats,ensure_ascii=False), '',
            'Это число согласий review с проектом разметки, не точность системы. Непроверенный вторым reviewer случай не считается согласием двух моделей.', '']
    for r in selected:
        b=inverse[r['id']];a=first[b];s=second.get(b);d=addendum.get(b); proposed,outcome,note=decision(r)
        lines += [f"## {r['id']}",'',f"**{r['kind']} / {partition}; слепой ID {b}.** "+('Искусственный тест; это не ситуация, доказанная реальным регламентом.' if r['kind']=='synthetic' else 'Реальный пример из v8/v9; цитаты проверены также по каноническим DOCX.'),'',
                  f"Текущая метка: `{r['expected_status']}`. Независимое первое предложение: `{a['proposed_status']}`. Рекомендация главного: `{proposed}`.",'',
                  'Текущие before: '+refs(r['before'])+'.', 'Текущие after: '+refs(r['after'])+'.',
                  'Независимые before: '+refs(a['before'])+'.', 'Независимые after: '+refs(a['after'])+'.','',
                  'Первое обоснование: '+a['explanation'],'',
                  'Неопределённости первого reviewer: '+(' '.join(a.get('uncertainties',[])) or 'не заявлены'),'',
                  'Первичные записи: '+', '.join('`'+n['notes_file']+'`' for n in [a,*([s] if s else []),*([d] if d else [])])+'.']
        if s:
            lines+=['',f"Второй reviewer: `{s['proposed_status']}`; "+('согласие с первым по статусу и полным refs.' if key(a)==key(s) else 'расхождение с первым сохранено.'),
                    'Его before: '+refs(s['before'])+'. Его after: '+refs(s['after'])+'.',
                    s['explanation'],'Неопределённости второго: '+(' '.join(s.get('uncertainties',[])) or 'не заявлены')]
        else: lines+=['','Второй reviewer: не назначен; наличие согласия не установлено.']
        if d: lines+=['','Дополнительная проверка первого reviewer после указания на §§9.34–9.37: '+d['explanation'],
                      'Первоначальная оценка и addendum сохранены отдельно; текущая метка ему не раскрывалась.']
        lines+=['',f'**Итог: {outcome}.** '+note,'','Точные цитаты и необходимый контекст:','']
        docs={doc['doc']:doc for doc in r['documents']}; cites=[];seen=set()
        for n in [r,a,*([s] if s else []),*([d] if d else [])]:
            for c in n['citations']:
                k=(c['doc'],c['clause_id'],c['quote'])
                if k not in seen:seen.add(k);cites.append(c)
        for alias,cid in supplement.get(r['id'],[]):
            quote=sc.clause_text((ROOT/docs[alias]['file']).read_bytes().decode('utf-8-sig'),cid)
            k=(alias,cid,quote)
            if k not in seen:seen.add(k);cites.append({'doc':alias,'clause_id':cid,'quote':quote})
        target=sc.refs(r['before']+r['after'])
        for c in cites:
            raw=(ROOT/docs[c['doc']]['file']).read_bytes().decode('utf-8-sig')
            assert c['quote'] in sc.clause_text(raw,c['clause_id']), (r['id'],c)
            role='целевой пункт' if (c['doc'],c['clause_id']) in target else 'контекст'
            lines+=[f"{role}: `{c['doc']} §{c['clause_id']}` — `{docs[c['doc']]['file']}`",'',
                    '> '+c['quote'].replace('\r\n','\n').replace('\n','\n> '),'']
        lines+=['Техника: текущие refs/citations и хеши прошли существующий scorer; цитаты первичных notes проверены тем же clause_text. '
                'Для real принадлежность 58/58 цитат текущей разметки подтверждена и в соответствующих DOCX-пунктах. '
                'Отсутствие ошибок цитирования не разрешает спор о статусе.','']
        case_records.append({'id':r['id'],'blind_id':b,'partition':partition,'kind':r['kind'],
            'label_sha256':sc.label_sha256(r),'first_review_file':a['notes_file'],'second_review_file':s['notes_file'] if s else None,
            'addendum_file':d['notes_file'] if d else None,'review_status':'pending_human'})
    if partition=='development':
        lines+=['## Ограничения покрытия','',
                'В challenge нет ни одного положительного expected missing или duplicate. Проверены основания не объявлять '
                'потерю при переносе/слиянии и не объявлять дублирование по сходным словам. Положительные missing/duplicate '
                'из regression прошли лишь техническую валидацию, новая семантическая проверка regression не проводилась. '
                'Новое реальное дублирование не установлено. Полнота всего документа, все функции и точность ядра не измерялись.','']
    else:
        lines+=['## Спорный holdout-случай','',
                'Для hold-split текущая метка changed, оба независимых reviewer предлагают moved при тех же полных refs. '
                'Аргументы, цитаты и предлагаемое решение приведены в его карточке. Согласие двух моделей не заменяет '
                'решение по контракту и человеческое подтверждение. Остальные семь первых оценок совпали с текущими метками. '
                'Эти сведения не переносить в development-brief и не использовать для настройки ядра.','']
    (OUT/f'{partition}.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

dis=['# Разногласия и решения для человека','',
     'Здесь только development. Holdout-аргументы и ответы находятся исключительно в holdout.md и его отдельных первичных notes. '
     'Главный агент не голосует по числу моделей: рекомендация определяется источником и контрактом. Все решения — pending_human.','',
     'Development: первая слепая оценка совпала с текущими status+refs в 22/22 случаях. Вторая проведена для 10: '
     '7 согласий с первым, 3 расхождения по статусу, 0 расхождений по полным refs. Первые ответы не переписаны.','',
     'Действующий контракт: `moved = preserved function with changed location/owner`; `changed = supported match with content changes`. '
     'Он не устанавливает приоритет изменения текстового разбиения относительно сохранённого содержания функций.','']
for cid in ['dev-split','dev-merge','dev-real-shared-information','dev-real-audit-goals']:
    r=next(r for r in rows if r['id']==cid);b=inverse[cid];a=first[b];s=second[b];p,o,n=decision(r)
    dis += [f'## {cid}','',f"Текущая: `{r['expected_status']}`; первый Sol: `{a['proposed_status']}`; второй Sol: `{s['proposed_status']}`; предложение главного: `{p}`.",'',
            'Before: '+refs(r['before'])+'. After: '+refs(r['after'])+'.','',
            'Аргумент первого: '+a['explanation'],'','Аргумент второго: '+s['explanation'],'','Рекомендуемое решение: '+n,'',
            'Дословные цитаты, контекст, неопределённости и ссылки на первичные notes: соответствующая карточка в development.md.','']
dis+=['## Дополнительные оговорки без изменения метки','',
      '- dev-real-roles: явно назвать §5.3 управляющим заголовком; изменение heading не доказывает перенос каждой функции.',
      '- dev-real-merge: сохранить разделение целевых refs и контекстных детей; не включать параллельную §5.4.2 только по одинаковому действию.',
      '- dev-real-correspondence и dev-real-staffing: описывать наблюдаемые изменения формулировок, не выводить фактический запрет или нового адресата из умолчания.',
      '', '## Что решает человек','',
      'Утвердить единое правило для семантически эквивалентных split/merge; выбрать changed/moved для сохранённой функции '
      'при расширении круга исполнителей; определить, распространяется ли изменение возможного делегата общей нормы '
      'на статус каждой процедуры. Затем отдельно проверить/подтвердить все 30 предложений по источникам. '
      'Ни один reviewer и главный агент не меняли pending_human на confirmed.','']
(OUT/'disagreements.md').write_text('\n'.join(dis),encoding='utf-8')
initial=read(OUT/'initial-state.json')
changed=[p for p,h in initial['sha256'].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
protected=[p for p in initial['sha256'] if p.startswith(('seeds/kt/','eval/kt/','apps/')) or p in ['docs/stage-2.md','docs/plan.md','docs/evidence/kt-quality.md']]
assert not set(changed)&set(protected),set(changed)&set(protected)
tracked_now=subprocess.check_output(['git','ls-files','-c','-o','--exclude-standard'],cwd=ROOT,text=True).splitlines()
new_outside=[p for p in tracked_now if p not in initial['sha256'] and not p.startswith('seeds/kt/eval/independent-review/')]
concurrent_changes=[{'file':p,'initial_sha256':initial['sha256'][p],
                     'final_sha256':sha(ROOT/p) if (ROOT/p).is_file() else None} for p in changed]
source_paths=sorted({d['file'] for r in rows for d in r['documents']}|{'seeds/kt/v8.docx','seeds/kt/v9.docx'})
label_paths=['seeds/kt/eval/'+n for n in ['challenge.jsonl','regression.jsonl','labels.jsonl','split.json','reviews.json','REVIEW.md']]
manifest={'schema_version':1,'review_date':'2026-09-23','completed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'timezone':'Asia/Qyzylorda','repository':str(ROOT),'initial_head':initial['head'],
 'final_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
 'scope':'all 30 challenge examples; independent AI label review; no system scoring',
 'counts':counts,'cases':case_records,'source_sha256':{p:sha(ROOT/p) for p in source_paths},
 'label_and_custody_sha256':{p:sha(ROOT/p) for p in label_paths},
 'contract_and_tool_sha256':{p:sha(ROOT/p) for p in ['docs/stage-2.md','docs/plan.md','docs/evidence/kt-quality.md','eval/kt/SELECTION.md','eval/kt/make_mutations.py','eval/kt/score.py']},
 'reviewers':[
  {'agent':'/root','role':'unblinded source/context verification and sole synthesis; never represented as independent blind vote'},
  {'agent':'/root/dev_real_blind','model':'gpt-6-sol','first':'development/real DR01..DR12','second':'development/synthetic DS01,DS02,DS04,DS05','addendum':'DR08 governing context and canonical DOCX'},
  {'agent':'/root/dev_synthetic_blind','model':'gpt-6-sol','first':'development/synthetic DS01..DS10','second':'development/real DR02,DR03,DR08,DR10,DR11,DR12'},
  {'agent':'/root/hold_real_blind','model':'gpt-6-sol','first':'holdout/real HR01..HR02','second':'holdout/synthetic HS01..HS06'},
  {'agent':'/root/hold_synthetic_blind','model':'gpt-6-sol','first':'holdout/synthetic HS01..HS06'}],
 'independence':{'fresh_context':'all four spawned with fork_turns=none and explicit gpt-6-sol',
  'withheld':['current expected_status','current rationale','system reports','other reviewer conclusions until notes frozen'],
  'provided':['contract excerpt','neutral blind case ID','target before/after refs','source filenames and raw hashes','full synthetic texts or full relevant real sections'],
  'limitations':['procedural separation in shared repository, not access control','source filenames may suggest synthetic operation','target refs constrain proposed lineage; reviewers were allowed to change them','root read requested docs/evidence and current labels; root was not blind','real partitions share source editions but were assigned to separate agents; no development assignments went to holdout agents']},
 'verification':{'existing_scorer':'30 challenge and 25 regression validate-labels, exit 0',
  'real_current_citations_exact_in_correct_docx_clause':'58/58','review_hash_mismatches':0,
  'details':'technical-checks.json','no_system_reports_read_by_reviewers':True,'no_holdout_run_or_tuning':True,
  'human_confirmation_performed':False,'labels_modified':False},
 'preservation':{'initial_snapshot':'initial-state.json','initial_files_count':len(initial['sha256']),
  'protected_files_unchanged':True,'concurrent_changes_outside_package':concurrent_changes,
  'new_files_outside_package':new_outside,
  'new_concurrent_file_sha256':{p:sha(ROOT/p) for p in new_outside if (ROOT/p).is_file()},
  'writes_by_this_review':'only seeds/kt/eval/independent-review/',
  'concurrent_work_note':'Other shared-workspace work advanced HEAD, changed six delivery documents, and added scripts/export_report.py. This review did not edit, reset, commit, or push them. Initial snapshot and current hashes are retained.',
  'git_status_final':subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True)},
 'commands':technical['commands']+[
  {'command':'python seeds/kt/eval/independent-review/prepare.py (initial invocation)','exit_code':0,
   'result':'four source-only packets, 30 cases, initial snapshot of 137 files; repeat execution now guarded'},
  {'command':'python -B seeds/kt/eval/independent-review/technical_audit.py','result':'existing scorer validation + DOCX raw text/numbered clause provenance + reviewer citation checks; see technical-checks.json'},
  {'command':'python -B seeds/kt/eval/independent-review/assemble.py (first invocation)','exit_code':1,
   'result':'Conservative all-files preservation assertion detected six concurrent delivery-document changes; no outside files altered by this review. Manifest had not yet been written.'},
  {'command':'python -B seeds/kt/eval/independent-review/assemble.py (final invocation)','exit_code':0,
   'result':'root-only synthesis; protected inputs preservation assertion passes; concurrent documentation changes recorded separately'},
  {'command':'git status --short','result':'three pre-existing modified paths and results/ preserved; only new independent-review/ added'}],
 'artifacts_sha256':{p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='manifest.json'}}
write('manifest.json',manifest)
print(json.dumps({'counts':counts,'unchanged_initial_files':len(initial['sha256'])-len(changed),
                  'protected_inputs_unchanged':True,'concurrent_changes_outside_package':len(changed),
                  'new_files_outside_package':len(new_outside)},ensure_ascii=True))
