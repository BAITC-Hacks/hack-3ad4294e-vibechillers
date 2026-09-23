# Проверка качества Function Lineage Auditor

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
