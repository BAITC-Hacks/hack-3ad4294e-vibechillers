# Проверка качества Function Lineage Auditor

## Stage 3 — независимая проверка сохранённого partial f104c91, 2026-09-23

Получен и независимо пересчитан **один реальный парный DOCX capture Батырхана**:
deterministic и попытка agent на одинаковых исходных байтах и core
`f104c91006c8d3d6a993881823863030e70aa4af`, schema
`4da43907919867ce4e8579360fe5b2ff43f9a37c`. Agent завершился **partial** по лимиту
ходов, итоговый `mode=deterministic`. Содержательные части обоих Report полностью
совпадают: 31 finding, 7 unit changes, пустые risks, conclusion и coverage.
**Улучшение качества не наблюдается; F1 (Word/PDF/Excel) и Stage 3 не приняты.**
Это проверка сохранённых фактических запусков, не новый inference на машине Алиби.

Исходный [ZIP](stage3-capture-f104c91.zip), опубликованный в `d98e73b`, не изменён.
SHA-256: `b4e484134c1122cd20b00632241b56a39ea0ee8bf30210aeacc80aba900e10a8`.
Run IDs: deterministic `6b5120b9b2c244c589d36d3cb90c655c`,
agent `76f223b2a6b44a9b8b68ac0386152e6f`. Точные хеши 13 членов архива,
настроек, evaluator и gold сохранены в
[summary.json](../../seeds/kt/eval/results/f104c91-independent/summary.json).
Передавались только синтетические control DOCX:

- before: `253413fd6a1b5c69d08959aaffd2838f83d7f1f2976fc02464b4711ba86483e5`;
- after: `cc751b88f6b5cf5910ef6505f02a6c6bc8b7740607fa2734bcafdfd409f01b9a`.

В attestation заявлены `https://xllm.sek.su/v1`,
`local-aigw/alemai/deepseek-ai/DeepSeek-V4-Pro`, 8192 output tokens,
90 s/request, 12 turns / 32 calls / 180 s; temperature и seed не задавались.
Report, reopened Report, SSE, persisted trace и server attestation согласованы.
Attestation — заявление оператора о запущенном процессе; raw upstream responses,
provider request IDs, token usage и стоимость отсутствуют. Эти сведения нельзя
независимо восстановить из host trace. Здесь API/model не вызывались.

### Целостность и воспроизведение

Проверки custody: **39/39**, дополнительные сверки: **16/16**. Проверены точные
байты всех **36/36** tracked Python core файлов через raw Git blobs указанного
commit, полный состав файлов, Report/reopened/SSE/trace и pinned inputs.
Первый запуск прежнего validator по рабочему checkout дал **1 ошибку / 36**:
31 core файл локально имеет CRLF, в capture — LF. Этот исходный отказ сохранён в
`f104c91-independent/integrity.json`. Новый явный `--core-revision` сравнивает
сырые Git blobs; нормализация переводов строк **не используется для принятия**.
Результат и диагностическое объяснение: [core-custody-review.json](../../seeds/kt/eval/results/f104c91-independent/core-custody-review.json).

`review_saved_capture.py` проверяет ZIP и вызывает существующий `score.py`
раздельно для двух Report. Это intake/reproduction, не второй evaluator.
Сохранённые scorer groups совпали с независимым пересчётом. Gold, split,
reviews и `score.py` побайтно совпадают с captured revision; regression и
challenge не изменялись. Holdout не открывался и не оценивался.

```powershell
python -B eval/kt/review_saved_capture.py --archive docs/evidence/stage3-capture-f104c91.zip --sha256 b4e484134c1122cd20b00632241b56a39ea0ee8bf30210aeacc80aba900e10a8 --extract-to seeds/kt/eval/data/stage3-capture-f104c91 --output seeds/kt/eval/data/f104c91-recheck --core-revision f104c91006c8d3d6a993881823863030e70aa4af
python -B eval/kt/test_score.py
python -B eval/kt/test_capture_control.py
python -B eval/kt/test_review_saved_capture.py
```

Интеграционный прогон Алиби: **53/53 scorer**, **15/15 capture guards**,
**10/10 archive/event-pair guards**. Эти offline tests проверяют evaluator и
приём evidence, не успешность model inference. Результаты в
[verification.json](../../seeds/kt/eval/results/f104c91-independent/verification.json).

### Raw counts: предварительное agreement, отдельно для каждого Report

Все **19/19** control labels остаются `pending_human`, human-confirmed **0/19**.
Это agreement с source-first AI-разметкой, а не подтверждённая точность продукта.
Два Report повторяют одни случаи; складывать их как независимую выборку нельзя.

| Выход / оба режима по отдельности | Gold | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| Functions | 9 | 4 | 6 | 5 | 4/10 | 4/9 |
| Unit changes | 7 | 7 | 0 | 0 | 7/7 | 7/7 |
| Положительные risks | 2 | 0 | 0 | 2 | 0/0 — N/A | 0/2 |

Function status counts (TP/FP/FN): changed **2/5/0**, moved **1/0/4**,
added **0/1/0**, missing **1/0/0**, duplicate **0/0/1**; unchanged **0/0/0**.
Оценены 10/31 findings, вне frozen function labels — **21/31**.
Unit changes: retained **3/3**, reorganised **3/3**, created **1/1**.
Отрицательный risk-control корректно отсутствует **1/1**, но одновременно
отсутствуют оба положительных риска: это не доказательство различения агентом.

Appropriate abstention: **0/0 — N/A**, scoped unresolved **0/10**. В полном Report
есть **1 unresolved finding / 3 unresolved refs**; это разные единицы.
Risk не имеет explicit abstention object; пустой assessed список не считается
обоснованным воздержанием. Проверено **343 цитаты / 0 ошибок** на каждый Report
как по самому Report, так и по закреплённым источникам. Ожидания физических
координат DOCX совпали **3/3** (2 unit + 1 risk source probe); shape checks 72
locations не равны 72 независимо проверенным координатам. Валидность подстрок
не доказывает смысл вывода. Полные counts и ошибки — отдельные
[deterministic-score.json](../../seeds/kt/eval/results/f104c91-independent/deterministic-score.json)
и [agent-score.json](../../seeds/kt/eval/results/f104c91-independent/agent-score.json).

### Что агент фактически сделал

Отдельный reviewer без gold/holdout разобрал все arguments/results:
[trace-review.md](../../seeds/kt/eval/results/f104c91-independent/trace-review.md),
[25 точных пар вызовов](../../seeds/kt/eval/results/f104c91-independent/trace-review.json).
SSE и persisted trace совпадают по seq/type/data **60/60**, call/result pairs
успешны **25/25**. Это 9 read, 7 search, 3 list findings, 3 inspect domain и
3 inspect findings. Proposal calls **0/25**, accepted/rejected proposals **0/0**,
`build_report` **0**, завершённых agent attempts **0/1**.

Есть наблюдаемые зависимости: IDs из result seq 8 использованы в inspect seq 15;
`next_offset=6` из seq 10 — в seq 13; найденный before 7.2 из seq 52 — в read
seq 53. Это последовательность действий по полученным данным, не доступ к
скрытым рассуждениям. Pagination seq 27 потеряла фильтр seq 25 и повторила 6 IDs.
23/31 investigated IDs реконструированы: 22 явно inspected плюс F029 через read
after 2.5. Они означают доступ к evidence, а не 23 решения или полные проверки.
Не отмечены F023–F028, F030, F031. Из цитат трёх reorganisation rows в bounded
tool results опущены пять; семь listed rows не означают полного прочтения.

12 turns заявлены в metadata, но границ model turns в trace нет. Израсходовано
25/32 tool slots. Stop seq 57 — `turn_limit`; final — seq 60. Между start seq 6
и stop прошло **50.515491 s**, поэтому 180-second cap не исчерпан. Итоговую сборку
сделал host; model-issued `build_report` не было. Текст самопроверки закупок
after 7.2/7.4/2.6 достигнут инструментами, но риск не предложен. Второй пункт
дублирования after 10.1 не появился в intermediate result content; F030 был
только кратко перечислен. Report целиком сохранил deterministic baseline.

### Source-backed ошибки, разногласия и границы review

[Source error brief](../../seeds/kt/eval/results/f104c91-independent/source-errors.md)
содержит 56 разрешённых точных цитат, ошибки reviewer-citation **0/56**:

- Before 3.1 → after 4.1 + 10.1: одна регистрация всех клиентских заявок без
  разграничения. F010 changed + F030 added не отражают полный duplicate set;
  cross-unit duplication risk тоже отсутствует.
- Четыре сохранённые обязанности при явных split/merge after 2.3–2.4 названы
  changed вместо provisional moved: before 4.1/4.2/5.1/6.1 → after 5.1/6.1/7.1/7.3.
- After 7.2 + 7.4: ЦС выбирает поставщика и утверждает проверку собственного
  выбора; after 2.6 передаёт ему контроль. Potential-conflict risk пропущен.
- **M5 вне frozen counts:** conclusion называет F002–F005 не имеющими
  подтверждённых преемников, хотя unit_changes и after 2.2–2.4 их подтверждают.
  Из 12 «новых функций» десять — структурные/распорядительные строки F020–F029.
  Ещё F014 preserved transfer и F016 unresolved требуют review. Эти наблюдения
  не добавлены задним числом в TP/FP/FN.

Семь unit outputs поддержаны источниками. Created СЦС цитирует определение
after 1.1/з, но пропускает более сильное явное основание after 2.5; это
неполнота объяснения. Альтернативное представление duplicate как moved + added
с отдельным risk требует human adjudication; сейчас отсутствует и risk.
Новая interpretive sensitivity F017/F018: считать добавленные отрицательные
границы содержательным changed или уточнением при moved. Исторических споров
по этим двум labels не было; новые замечания сохранены отдельно без изменения
frozen gold. Два прежних real-development разногласия ниже остаются открытыми.

Процедурное отклонение раскрыто: source-reviewer после source-derived оценки
вызвал private helpers для диагностики правил, несмотря на запрет private imports
в поручении Алиби. Эти вызовы не использованы в evaluator, gold или пересчёте;
диагностика отделена в source-errors от выводов по источникам. Повторные вызовы
остановлены. Review выполнен отдельными AI-агентами, не человеком; post-capture
error review не объявляется слепой валидацией gold.

Для следующего capture: сохранить этот baseline, выдать отдельные run IDs,
core/configuration, реальные proposals/results и завершение либо честный partial.
Не хватает успешного агентного завершения, human confirmation, интегрированных
PDF/XLSX проверок и общей UI/export/release приёмки. Старые domain diagnostics
ниже — история, а не дополнительные измерения этого core.

## История подготовки Stage 3 — до получения capture, 2026-09-23

Следующий раздел фиксирует состояние до доставки пакета f104c91. Его ожидания
пакета и прежние числа тестов сохранены как история; текущие результаты выше.

Подготовка выполнена; **финальное сравнение deterministic/actual agent ещё не измерено**.
По уточнению Алиби реальные HTTP/model-прогоны выполняет Батырхан в своей среде.
Здесь не устанавливались OMP, зависимости или API-ключи, не выбирался собственный provider.
Ожидается пакет фактических Report/trace и конфигурация интегрированного запуска.
Schema commit `4da43907919867ce4e8579360fe5b2ff43f9a37c` получен и подключён;
это фиксация схем, а не свидетельство работающего или измеренного агента.

Ранний input handoff: `76986e3` (первоначальный локальный ID `abfc85c`).
Все форматы и source-first proposals: `d7e0354` (до rebase — `8401066`).
Эти два ID переписаны обычным rebase при получении schema commit; исторические
capture manifests сохраняют фактическую ревизию на момент запуска, а не задним числом
подставленную новую. Runtime-файлы локальных диагностик соответствовали Stage 2 `c0658ff`.
Полные SHA исходников, runtime и raw Reports сохранены в `results/stage3-local-evidence.json`.

### Контрольные данные и custody

`seeds/kt/eval/control/`: before/after в TXT, DOCX, PDF, XLSX, восемь закреплённых
файлов с SHA-256 в `manifest.json`. Происхождение — авторская синтетика, **не документы
организатора**. Есть retained, created, rename, split 1:2, merge 2:1, потеря архивной
обязанности, настоящее пересечение регистрации заявок, потенциальная самопроверка
закупок и отрицательный пример сотрудничества с разными предметами ответственности.
Дополнительные before/after-table.xlsx содержат три колонки и два листа;
их отдельные хеши/происхождение в `table-probe-manifest.json`. Это auxiliary input probe,
не замена закреплённых представлений gold и не доказательство понимания произвольных оргсхем.

В `control/labels.jsonl` **19 pending_human**: 9 function, 7 unit_change, 3 risk,
из последних 2 положительных и 1 отрицательный. Human-confirmed новых меток: **0/19**.
Source-first статусы/refs зафиксированы до локального domain capture. Позднее добавлены
9 ожиданий физических координат для 3 refs × 3 формата: XML-порядок DOCX блоков,
ячейки XLSX, физические страницы PDF независимо проверены по файлам. Эти координаты
добавлены после capture, без использования предсказаний для выбора координат; статусы,
refs, quotes и байты исходников не менялись. Предыдущая версия сохранена в
`control/review/labels-v1-before-location-probes.jsonl`, причины и хеши — `review/intake.json`.

Исходные labels/regression (25 строк) и challenge (30 строк) побайтно сохранены.
Regression SHA: `87965da85193a0420dd2383fae056211c7cba5b1976bdc0e3f2783534526b7ed`.
Challenge SHA: `b31e4f1a124548cee9bacda752de78f216432c3dfb0b75dad445d19bd00e80b9`.
В split добавлены только control dataset/fixtures/19 случаев; прежние memberships и
review statuses сохранены. Holdout не оценивался и не передавался для настройки.

### Независимый AI review и открытые разногласия

Три отдельных встроенных reviewer-агента Codex проверили структуру/источники,
обязанности/риски и техническую целостность. Source-reviewers сначала получили TXT и
контракт без expected labels и Report. Их артефакты в `control/review/` сохраняют
цитаты, хеши, первичные решения и ограничения. Независимость процедурная: общий репозиторий
доступен технически; автор gold не считается независимым голосом. Reviewer обязанностей
раскрыл случайное чтение всего stage-3.md вместо §4; gold/Report при этом не читал.
Согласие с предложениями — проверка разметки, **не точность продукта**.

Оставлены открытыми два development-разногласия с сохранением прежних challenge-ответов:

- `dev-real-shared-information`: changed против предложенного moved. §5.3 меняет круг
  исполнителей при сохранении запроса/контроля информации; §5.4.3 существовал в обеих редакциях.
- `dev-real-audit-goals`: moved против предложенного changed. v8 §9.36/з → v9 §9.36/е
  сохраняет процедуру, но §9.37 меняет допустимого делегата. Это не фактическая передача
  общей ответственности Главного аудитора; требуется решение о границе контекста.

Новые disagreement events добавлены в reviews.json, прежние события и human-статусы
не переписаны. Ошибочные буквенные refs в промежуточном поручении reviewer исправлены
по источнику и раскрыты; это не объявлялось дефектом существующей разметки.

### Scorer, capture и проверки

Расширен существующий `eval/kt/score.py`, а не создан второй evaluator. Раздельные
function/unit/risk counts сохраняют exact N:M refs, editions, aliases при одинаковых
байтах, source quotes, форматные координаты, negative controls и appropriate abstention.
`agent=null`/missing и отсутствующие domain sections дают not_assessed; явный assessed
пустой список даёт FN положительных меток и отдельно проверяемое отсутствие риска.
Risk не имеет explicit abstention object, поэтому отсутствие риска не считается
appropriate abstention. 0/0 публикуется как N/A. Semantic agreement и provenance разделены.

Независимый technical review нашёл и помог исправить ошибки проверки координат,
пропуска знаменателя из-за ошибочного SHA, чрезмерного требования копировать unit
citations в Risk, QA-пропусков missing/extra refs и capture custody. Исторический
`technical.json` содержит воспроизводимые замечания и хеши просмотренной версии;
schema-intake addendum относится к последующей интеграции.
Финальные целевые проверки: **53/53 scorer tests** (25 прежних и 28 новых),
**8/8 capture guard tests**. Валидация datasets: regression **25/25**, challenge **30/30**,
control **19/19**. Это тесты evaluator/custody, а не успешность agent-прогонов.

Capture встроен в `make_mutations.py --capture-control`. `capture_control.py` готовит
несекретную attestation, сохраняет реальные HTTP/SSE/Report/reopened/trace, сверяет
входные байты и стабильность ядра. Приёмка отдельно проверяет хеши всех artifacts,
run_id, последовательность, terminal-last, равенство Report и trace, core hashes.
Она **не утверждает inference по наличию событий**. Проверка зависимости последующих
действий от результатов, provider evidence и охвата рассмотренных finding IDs остаётся
отдельным анализом фактического пакета. Команды Батырхану: `eval/kt/BATYRKHAN-CAPTURE.md`.

Контроль ухудшения scorer на копии настоящего локального TXT Report: намеренная замена
статуса missing у before §2.2 на changed дала TP **4→3**, FP **6→7**, FN **5→6**.
Это явно искусственное повреждение для проверки evaluator, не product/model run.
Исходный raw Report не изменён; counts сохранены в `results/stage3-local-evidence.json`.

### Реальные локальные диагностики старого ядра: provisional

Четыре публичных domain-API deterministic запуска выполнены на одной ревизии `8401066`
до получения схемы. Это **не HTTP, не agent и не измерение ядра после `4da4390`**.
Raw Reports tracked в `results/stage3-domain-reports/`; полные per-status counts,
refs ошибок и знаменатели — `results/stage3-domain-{txt,docx,pdf,xlsx}.json`.

| Формат | Function gold | TP | FP | FN | Precision denominator | Recall denominator | Неоценённые findings |
|---|---:|---:|---:|---:|---:|---:|---:|
| TXT | 9 | 4 | 6 | 5 | 10 | 9 | 21/31 |
| DOCX | 9 | 4 | 6 | 5 | 10 | 9 | 21/31 |
| XLSX | 9 | 4 | 6 | 5 | 10 | 9 | 21/31 |
| PDF | 9 | 3 | 7 | 6 | 10 | 9 | 22/32 |

Четыре представления повторяют одни случаи; **36 evaluations не являются 36 независимыми
примерами**. Во всех четырёх scoped unresolved findings = 0; appropriate abstention
**0/0, N/A**. Domain-выходы старого Report отсутствуют: **7 unit и 3 risk метки not_assessed**
в каждом формате. Положительные risks/negative cooperation нельзя объявлять успешными.
Ожидания координат: **0/3** совпадений на DOCX, PDF и XLSX, для TXT — **0/0 N/A**.

Report-internal и source-backed цитаты: **0 ошибок / 307** для каждого TXT/DOCX/XLSX;
PDF **0 / 317**. Это точность происхождения проверенных подстрок, не полнота цитирования
всего пункта и не подтверждение смысла вывода. PDF сохраняет извлечённый полный текст,
но parser разрывает wrapped clauses: **21/29** точных numbered clauses before и **25/39**
after; 8 и 14 текстовых несовпадений. Для остальных трёх форматов — **29/29** и **39/39**.
Пропусков/лишних/повторных numbered refs в этом контроле не найдено. Ожидаемые refs
получены независимым source resolver, не тем же product parser. Полнота реальных
организаторских документов и arbitrary diagrams этим не измерена.

PDF страницы и XLSX листы визуально проверены. DOCX visual QA остаётся незавершённой:
LibreOffice отсутствует; XML/text round-trip не заменяет рендер. Source-backed error
brief с конкретными пунктами и повторяемыми командами передан в `eval/kt/HANDOFF.md`.

### Воспроизведение и оставшийся integration gate

```powershell
python -B eval/kt/test_score.py
python -B eval/kt/test_capture_control.py
python -B eval/kt/score.py --labels seeds/kt/eval/control/labels.jsonl --validate-labels
python -B eval/kt/score.py --labels seeds/kt/eval/regression.jsonl --validate-labels
python -B eval/kt/score.py --labels seeds/kt/eval/challenge.jsonl --validate-labels
python -B eval/kt/score.py --labels seeds/kt/eval/control/labels.jsonl --partition development --json-out seeds/kt/eval/data/recheck-docx.json seeds/kt/eval/results/stage3-domain-reports/docx.json
```

Для повторения локального domain capture нужен Python с уже имеющимися parser-зависимостями:

```powershell
$taskPython = 'C:/Users/torre/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
& $taskPython -B eval/kt/build_control.py --verify-inputs
& $taskPython -B eval/kt/build_control.py --verify-tables
& $taskPython -B eval/kt/make_mutations.py --capture-reports seeds/kt/eval/data/new-domain-docx --labels seeds/kt/eval/control/labels.jsonl --partition development --control-format docx
```

Последняя команда на новом ядре даст новый эксперимент, не восстановит старую ревизию.
Для реального paired HTTP capture и оценки пакета использовать точные команды
`BATYRKHAN-CAPTURE.md`. Полученных external agent-пакетов сейчас **0**, agent TP/FP/FN,
успешные/partial/fallback inference counts и result-dependent actions **не измерены**.
Ожидаются actual integrated core, Report/trace/run_id, несекретная конфигурация и
human confirmation; Stage 3 release acceptance пока не закрыт.

Checkpoint 2026-09-23 11:04 UTC: ранние inputs закоммичены, source review/evaluator реализованы.
Проверено: baseline gold bytes, source/format evidence, отдельные технические guard tests.
Осталось: принять фактический пакет Батырхана, оценить оба режима и зафиксировать release gaps.

После финального autostash обнаружено изменение сырых SHA Python-файлов evaluator из-за
Windows-переводов строк. Исторические снимки не переписаны. `eval/kt/.gitattributes`
теперь закрепляет LF для Python; отдельный `control/review/final-bytes.json` проверяет
равенство нормализованных файлов Git blobs и сохраняет конечные SHA. Семантических
изменений в этой операции нет; 53 scorer и 8 capture tests повторно прошли.

## Разметка и проверка источников

В Stage 1 приняты 20 реальных пар редакций v8→v9 (§§2.4, 3, 4, 5) и пять случаев из отдельных копий v9: удаление, дублирование, перенос, перенумерация и изменение пробела. Они сохранены без изменений как regression. Этот набор не является blind holdout: в частности, ссылка real-019 была исправлена после первоначального просмотра расхождения.

Команда из корня репозитория:

```sh
uv run --no-sync python eval/kt/score.py --validate-labels
```

Результат: `Validated 25 labels: 20 real, 5 synthetic; all fixture hashes, clause refs and quotes resolve`. Проверены SHA-256 каждого файла, наличие каждого `clause_id` и точное вхождение каждой цитаты в соответствующий пункт.

## Первое измерение

23.09.2026: запущен `sh scripts/demo.sh` против локального API без `LLM_API_KEY`, загружены `seeds/kt/v8.docx` и `v9.docx`. Скрипт сохранил поток SSE в `data/demo-events.sse` и финальный `Report` в `data/demo-report.json`. Запущен `uv run --no-sync python eval/kt/score.py data/demo-report.json`; отдельно тем же `run_deterministic_audit` сформированы отчёты для пяти сравнений v9.txt с `seeds/kt/eval/mutations/*.txt` и оценены тем же скриптом. HTTP/SSE, сохранение и чтение по `GET /audits/{run_id}` дополнительно проверены отдельным smoke-прогоном.

Реальный отчёт содержит 457 находок. Покрытие распознанных функций: 420/420 до, 413/413 после. Исправление интерпретации в Stage 2: `coverage.unresolved=33` — это 33 уникальные ссылки в **16 находках unresolved**, а не 33 находки. В выбранных 20 эталонах одно воздержание. В записи Stage 1 опубликованные цитаты и цитаты заключения проверены на точное вхождение: 0 неподтверждённых цитат и 0 пунктов заключения без цитат. Эти числа не доказывают полноту извлечения из исходных документов.

| Набор | Статус | Precision, TP/(TP+FP) | Recall, TP/эталоны | Abstentions/эталоны |
| --- | --- | ---: | ---: | ---: |
| Реальные, 20 | unchanged | 9/9 (100%) | 9/9 (100%) | 0/9 |
| Реальные, 20 | changed | 1/1 (100%) | 1/2 (50%) | 1/2 |
| Реальные, 20 | moved | 4/4 (100%) | 4/4 (100%) | 0/4 |
| Реальные, 20 | added | 4/4 (100%) | 4/4 (100%) | 0/4 |
| Реальные, 20 | missing | 1/1 (100%) | 1/1 (100%) | 0/1 |
| Реальные, 20 | duplicate / unresolved | 0/0 (н/п) | 0/0 (н/п) | 0/0 |
| Синтетические, 5 | unchanged | 1/1 (100%) | 1/1 (100%) | 0/1 |
| Синтетические, 5 | moved | 2/2 (100%) | 2/2 (100%) | 0/2 |
| Синтетические, 5 | missing | 1/1 (100%) | 1/1 (100%) | 0/1 |
| Синтетические, 5 | duplicate | 1/1 (100%) | 1/1 (100%) | 0/1 |
| Синтетические, 5 | changed / added / unresolved | 0/0 (н/п) | 0/0 (н/п) | 0/0 |

Итого точных совпадений: 19/20 реальных и 5/5 синтетических; пересекающихся с разметкой ложных выводов — 0. Эталонный `real-019` (§5.3.6→§5.3.7) остался `unresolved`; это воздержание, а не доказательство отсутствия связи. Нельзя подставлять ответ из разметки вместо подтверждённой текстом связи — нужна проверка эксперта.

Оценщик сравнивает точные множества ссылок и статус. Precision считает только находки, пересекающиеся с размеченными ссылками; вне этих ссылок эталон не утверждает правильность или ошибку. `unresolved` считается воздержанием. Проверить новый отчёт можно командой `uv run --no-sync python eval/kt/score.py path/to/report.json`.

## Stage 2: разделение наборов и процедура

Заморозка `07a1708` сохранила исходные 25 строк побайтово в `seeds/kt/eval/regression.jsonl` и зафиксировала исходные предложения holdout до нового запуска. SHA-256 regression/labels: `87965da85193a0420dd2383fae056211c7cba5b1976bdc0e3f2783534526b7ed`. Коммит `4af5b5b` зафиксировал development-предложения и исправления scorer до оцениваемого development-запуска. Исходные ответы не получены импортом aligner: чтение источников и авторские синтетические ситуации отделены от публичного вызова `run_deterministic_audit`, который создаёт только предсказания.

| Partition | Real | Synthetic | Состояние |
| --- | ---: | ---: | --- |
| regression | 20 | 5 | Унаследованный принятый Stage 1; не независимый тест |
| development | 12 | 10 | AI-предложения по источникам, ожидают подтверждения Alibi |
| holdout | 2 | 6 | Source-first резерв; ожидает подтверждения, **не оценивался** |

`split.json` хранит membership, хеши наборов, каждой строки и фикстур. `reviews.json` хранит назначенного человеческого reviewer, решения и разногласия без изменения контракта JSONL. Alibi подтвердил, что будет проверять пакет здесь; это не является подтверждением отдельных ответов. До подтверждения результаты development ниже — только согласие с проектом разметки. Scorer и генератор отчётов запрещают оценку неподтверждённого holdout.

Holdout процедурный в общем репозитории, технической слепоты нет. Два реальных held-out пункта используют те же редакции, что development, и не образуют независимую выборку документов. Если пример использован для изменения ядра, его необходимо перевести в development с записью причины. Перед запуском подтверждённого holdout требуется новый коммит gold, затем свежий capture с уникальным run_id; результаты старого baseline не подменяют этот запуск.

## Выбор и разбор development

Правило до просмотра нового отчёта записано в `eval/kt/SELECTION.md`: все unresolved, затем первые три по детерминированному SHA-256 рангу в каждом уверенном статусе changed/moved/missing/duplicate, исключая ссылки regression и holdout. Воспроизведённые DOCX и TXT отчёты одинаково дали 457 находок, **16 unresolved / 33 уникальные ссылки**. Из пулов выбраны changed 3/39, moved 3/66, missing 3/21, duplicate 1/1. Итого проверены по источникам 26 групп: 16 unresolved и 10 уверенных.

Membership выборки, исходные цитаты и все 26 заключений находятся в `seeds/kt/eval/triage.json`, `TRIAGE.md` и `eval/kt/TRIAGE-NOTES.md`. Три спорных случая (triage-014/015/024) оставлены без утверждённого semantic gold. Новый реальный duplicate не выдумывался: единственная выбранная duplicate-находка требует опровержения предположения о пересечении ролей, поскольку похожие обязанности существовали у разных ответственных ещё в v8.

## Фактические результаты повторного запуска

Отчёты созданы публичным доменным API ядра, без ключа и без изменения `apps/**`; HTTP/SSE в Stage 2 этим запуском не проверяется. Для real использован канонический DOCX; для синтетики — исходные TXT фикстуры. Полные отчёты хранятся в игнорируемом `seeds/kt/eval/data/`. Хеши отчётов, время, git revision и хеши файлов ядра сохранены в `seeds/kt/eval/results/regression-capture.json` и `development-capture.json`. Scorer остаётся единственным evaluator; raw counts и ошибки по ID — в `results/regression.json` и `results/development-provisional.json`.

| Partition / kind | Статус | Gold | TP | FP | FN | Precision | Recall | Воздержания с пересечением refs |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| regression / real | unchanged | 9 | 9 | 0 | 0 | 9/9 | 9/9 | 0/9 |
| regression / real | changed | 2 | 1 | 0 | 1 | 1/1 | 1/2 | 1/2 |
| regression / real | moved | 4 | 4 | 0 | 0 | 4/4 | 4/4 | 0/4 |
| regression / real | added | 4 | 4 | 0 | 0 | 4/4 | 4/4 | 0/4 |
| regression / real | missing | 1 | 1 | 0 | 0 | 1/1 | 1/1 | 0/1 |
| regression / synthetic | unchanged | 1 | 1 | 0 | 0 | 1/1 | 1/1 | 0/1 |
| regression / synthetic | moved | 2 | 2 | 0 | 0 | 2/2 | 2/2 | 0/2 |
| regression / synthetic | missing | 1 | 1 | 0 | 0 | 1/1 | 1/1 | 0/1 |
| regression / synthetic | duplicate | 1 | 1 | 0 | 0 | 1/1 | 1/1 | 0/1 |
| development draft / real | changed | 9 | 3 | 1 | 6 | 3/4 | 3/9 | 3/9 |
| development draft / real | moved | 3 | 3 | 1 | 0 | 3/4 | 3/3 | 0/3 |
| development draft / real | missing | 0 | 0 | 2 | 0 | 0/2 | N/A (0) | N/A (0) |
| development draft / real | duplicate | 0 | 0 | 1 | 0 | 0/1 | N/A (0) | N/A (0) |
| development draft / synthetic | unchanged | 4 | 4 | 2 | 0 | 4/6 | 4/4 | 0/4 |
| development draft / synthetic | changed | 4 | 1 | 2 | 3 | 1/3 | 1/4 | 0/4 |
| development draft / synthetic | moved | 2 | 1 | 0 | 1 | 1/1 | 1/2 | 0/2 |
| development draft / synthetic | added | 0 | 0 | 1 | 0 | 0/1 | N/A (0) | N/A (0) |
| development draft / synthetic | missing | 0 | 0 | 1 | 0 | 0/1 | N/A (0) | N/A (0) |

Не приведённые статусы имеют нулевые TP/FP/FN/gold и N/A при нулевом знаменателе; полный вывод хранит все шесть semantic-статусов. Appropriate abstention проверяется отдельно: в этих измеренных наборах нет gold `unresolved`, поэтому **0/0, N/A**, а не semantic TP. Для неподтверждённого holdout показатели не вычислялись.

Регрессия сохранена: real TP=19, FP=0, FN=1; synthetic TP=5, FP=0, FN=0. Development draft: real TP=6, FP=5, FN=6 из 12; synthetic TP=6, FP=6, FN=4 из 10. В real regression вне размеченной области остаются 437/457 находок; в real development — 441/457. Они не объявляются правильными. Эти области пересекаются между группами, их знаменатели нельзя складывать как уникальные находки.

Категории расхождений: regression — `abstention_on_resolvable=1`; development real — `abstention_on_resolvable=3`, `wrong_match=3`; development synthetic — `wrong_match=2`, `wrong_status=2`. Категории описывают случаи и могут пересекаться. Отсутствующих распознанных refs в размеченных случаях не обнаружено; это не оценка полноты извлечения. Внутренняя проверка Report.citations: regression 0 ошибок на 10430 цитатах, development 0 на 1834; это происхождение внутри Report, не доказательство истинности выводов.

## Границы scorer и контроль ухудшения

Исправлены доказанные дефекты: SHA+edition различают один файл по сторонам; aliases каждой строки нормализуются отдельно; неоднозначный matching документов вызывает ошибку вместо молчаливого исключения; соседний встроенный пункт не попадает в цитату предыдущего; повторные @2 и буквы разрешаются; контекстные цитаты родителя допускаются и проверяются. Exact-set семантика N:M сохранена: перестановка refs допустима, потеря одного ref — ошибка.

25 изолированных unittest проверок прошли. Контроль на копии реального Report намеренно заменил `real-001` unchanged→changed при прежних refs: **TP 19→18, FP 0→1, FN 1→2**. Это искусственно испорченный отчёт для проверки scorer, не ответ ядра; raw counts в `results/scorer-controls.json`. Отдельный boundary test даёт appropriate abstention 1/1 при exact refs и 0/1 после удаления одного кандидата. Semantic TP при этом остаётся 0. Неподтверждённый holdout не запускается.

## Команды и ограничения среды

Предписанные точки входа сохранены:

```sh
uv run --no-sync python eval/kt/score.py --validate-labels
uv run --no-sync python eval/kt/score.py --labels seeds/kt/eval/challenge.jsonl --validate-labels
uv run --no-sync python eval/kt/test_score.py
uv run --no-sync python eval/kt/score.py --labels seeds/kt/eval/challenge.jsonl --partition development <report.json>
```

В этой Windows-среде `uv` не найден. Фактически проверки стандартной библиотеки выполнены как `python eval/kt/test_score.py` и `python eval/kt/score.py ...`. Для capture использован уже установленный bundled Python с pydantic/python-docx; зависимости не устанавливались. В PowerShell:

```powershell
$taskPython = 'C:\Users\torre\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $taskPython eval/kt/make_mutations.py --capture-reports seeds/kt/eval/data/fresh-regression --labels seeds/kt/eval/regression.jsonl --canonical-docx
& $taskPython eval/kt/make_mutations.py --capture-reports seeds/kt/eval/data/fresh-development --labels seeds/kt/eval/challenge.jsonl --partition development --canonical-docx
$taskReports = (Get-ChildItem seeds/kt/eval/data/fresh-development -Filter 'alibi-*.json').FullName
python eval/kt/score.py --labels seeds/kt/eval/challenge.jsonl --partition development --json-out seeds/kt/eval/data/fresh-development-metrics.json @taskReports
```

Известное ограничение воспроизводимости: Git blobs оригинальных `v8.txt`/`v9.txt` используют LF, а текущие исходные хеши соответствуют checkout с CRLF. Валидация намеренно падает при отличающихся байтах; она не нормализует SHA ради успешного результата. В разрешённом eval-поддереве добавлен `.gitattributes` для сохранения байтов фикстур. Исправление политики исходников вне scope передано интегратору в `eval/kt/HANDOFF.md`.

Не измерены candidate recall (в Report нет полного списка кандидатов), полнота извлечения из всего источника, точность всех 457 находок и новый HTTP/UI путь. Общая сборка/тесты, зависимости, lock-файлы и `apps/**` не менялись. Краткий development-only brief для Batyrkhan опубликован в общем репозитории: `eval/kt/HANDOFF.md`; holdout-ответов в нём нет.

## Независимая проверка разметки агентами — 2026-09-23

Принят пакет `seeds/kt/eval/independent-review/`: отдельные development/holdout отчёты, первичные ответы четырёх GPT-6 Sol, разногласия, исходные задания и manifest. Проверяющие сначала получили исходники, целевые refs и контракт без текущих expected_status/rationale и ответов системы. Главный агент проверки видел разметку; его сводка не является слепым голосом. Независимость процедурная: файлы доступны в общем репозитории, имена синтетических фикстур подсказывают операцию, а предоставленные refs ограничивают поиск связей.

При приёмке повторно сверены SHA-256: 36/36 исходных файлов, 6/6 файлов разметки и учёта, 22/22 артефакта пакета совпали с manifest. Повторные команды `python -B eval/kt/score.py --labels seeds/kt/eval/challenge.jsonl --validate-labels` и аналогичная для `regression.jsonl` завершились успешно: 30 и 25 строк соответственно. Сохранённая техническая проверка пакета сообщает 58/58 real-цитат в соответствующих пунктах DOCX и 205 проверенных цитат reviewer notes без ошибок. Это проверка происхождения цитат, а не семантической правильности. Байты пакета закреплены через `.gitattributes`, чтобы Git не нарушил manifest преобразованием переводов строк.

Для development первая независимая оценка совпала с текущими status+refs в 22/22 случаях. Второй reviewer проверил 10/22: 7 совпадений и 3 расхождения по статусу, 0 расхождений по полным refs. Эти числа описывают согласие проверяющих с проектом разметки, не качество системы. Holdout проверен отдельно: 8 случаев, 2 real + 6 synthetic; ответы и аргументы не включены в brief для настройки.

Открытые development-решения человека:

- `dev-split`, `dev-merge`: changed или moved для семантически сохранённых действий при разбиении/объединении пунктов. Контракт допускает moved при сохранённой функции с изменением расположения; предложение независимого пакета — moved. Исходные ответы и разногласия сохранены.
- `dev-real-shared-information`: changed или moved при сохранении запроса информации и контроля её предоставления, смене номера и круга исполнителей. Предложение пакета — moved; наличие отдельной обязанности ДНМ в обеих редакциях не доказывает duplicate.
- `dev-real-audit-goals`: добавить к рассмотрению §9.37 обеих редакций, меняющий возможного делегата контроля при сохранении общей ответственности Главного аудитора. Требуется решение о границе контекста целевой процедуры; нельзя утверждать неизменность всего контекста по одному дочернему тексту.

Текущие 30 challenge-меток и их хеши при приёмке не изменены, статус остаётся `pending_human`. Человеческого подтверждения нет. Опубликованные выше development-метрики относятся к прежней версии предложений; изменение ожидаемых статусов потребует отдельной версии и пересчёта с явным указанием причины. Новых запусков системы и оценки holdout при приёмке не проводилось. В challenge нет положительных gold missing/duplicate, поэтому recall этих классов на challenge не измерен; их наличие в regression не восполняет это ограничение.

### Решение по dev-split / dev-merge после приёмки

Пользователь делегировал главному агенту решение этих двух споров. Для обоих выбрано **moved**: действия и ответственный сохранены, изменилось только расположение действий между пунктами. Само число пунктов не доказывает изменения содержания функции. Это решение агента по контракту, не подтверждение личного чтения источников человеком; `pending_human` сохранён. Другие метки, все refs и holdout остались прежними.

`results/development-adjudication.json` сохраняет оба прежних ответа, основания, время, хеши до/после и ссылку на исходный снимок `ad3cbf5`. `reviews.json` и `split.json` отражают изменение и историю. Пакет `independent-review/` остаётся неизменным историческим свидетельством проверки версии из `ad3cbf5`; его хеши разметки относятся к этой версии, а не к изменённым двум строкам. Первая таблица development выше также относится к версии до решения.

Тем же scorer повторно оценены **прежние development-предсказания** из `data/stage2-development/`, без нового запуска ядра. Это пересчёт после изменения development-разметки, не независимая оценка и не улучшение системы. Результат: `results/development-adjudicated-provisional.json`. Real: TP=6, FP=5, FN=6 из 12. Synthetic: TP=6, FP=6, FN=4 из 10 — суммы не изменились. Изменилось распределение знаменателей и FN по двум статусам synthetic:

| Статус synthetic после решения | Gold | TP | FP | FN | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| unchanged | 4 | 4 | 2 | 0 | 4/6 | 4/4 |
| changed | 2 | 1 | 2 | 1 | 1/3 | 1/2 |
| moved | 4 | 1 | 0 | 3 | 1/1 | 1/4 |
| added | 0 | 0 | 1 | 0 | 0/1 | N/A (0) |
| missing | 0 | 0 | 1 | 0 | 0/1 | N/A (0) |
| duplicate | 0 | 0 | 0 | 0 | N/A (0) | N/A (0) |

Appropriate abstention: 0/0, N/A отдельно от semantic TP; synthetic ошибки по-прежнему wrong_match=2, wrong_status=2. Валидация всех 30 challenge-строк после изменения успешна; refs, цитаты и хеши разрешаются. Holdout не оценивался.

Команды этого пересчёта:

```powershell
python -B eval/kt/make_mutations.py --review-packet
python -B eval/kt/score.py --labels seeds/kt/eval/challenge.jsonl --validate-labels
$taskReports = (Get-ChildItem seeds/kt/eval/data/stage2-development -Filter 'alibi-*.json').FullName
python -B eval/kt/score.py --labels seeds/kt/eval/challenge.jsonl --partition development --json-out seeds/kt/eval/results/development-adjudicated-provisional.json @taskReports
```
