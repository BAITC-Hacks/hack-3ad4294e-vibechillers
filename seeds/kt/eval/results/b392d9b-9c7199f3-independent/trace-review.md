# Независимая проверка trace b392d9b / 9c7199f3

Рассмотрен новый сохранённый DOCX-run, core `b392d9bd18687eb4905f296897399d0a5eb581e9`, schema `4da43907919867ce4e8579360fe5b2ff43f9a37c`. Gold, labels и holdout не открывались; private core helpers не выполнялись; provider calls не делались. Точные аргументы, call IDs, result IDs/refs и SHA-256 результатов находятся в `trace-review.json`.

**A1 проходит в пределах этого saved-run:** содержательная цепочка от полученных источников к решению и последующей финализации есть. Полный D1, точность и приёмка Stage 3 этим trace-review не установлены; они требуют отдельных source/scoring/format проверок. Исторические попытки не включены в сравнение нового ядра.

53/53 события trace совпадают с SSE по seq/type/data и округлённым timestamp; seq 1–53 непрерывны. Все 22/22 call/result пары имеют уникальный согласованный call_id и ok=true. Один final (seq 53) равен agent Report; reopened Report также равен ему. От старта расследования (seq 6) до final: 50.622443 с.

7 ходов указаны в metadata и подтверждаются 7 provider receipts (#16–22) внутри временного окна. В ledger нет run_id и прямой привязки request_id к tool batch: связь выводится из времени. Восстановленные по времени группы вызовов: 7/9/11/13; 15/17/19; 21/23/25/27/29/31/33/35; 37/39/41/43; 45; 47; 49. Вызовы одной группы выбраны до получения их результатов. Поэтому list result 8 → pagination call 9 не считается адаптивным выбором.

| Полученный результат | Следующий выбор в позднем ходе | Доказательство |
|---|---|---|
| 8, 10: список 19 findings | 15, 17, 19: inspect_findings | Те же run-local IDs выбраны для чтения. |
| 18: F009 unresolved с before 7.1 / after 7.4 + 2.6 | 21: read_clauses | Запрошены точные спорные пункты. |
| 22, 32: полный текст передачи контроля и поиска | 37: offer_candidates | Тот же набор источников; accepted, но no-op. |
| 22, 38, 42, 44: тексты передачи, собственного контроля и реорганизации | 45: resolve_alignment | Причина прямо использует 2.6 и 7.4; result 46 меняет F009. |
| 24, 42, 46: источники и принятое решение | 47: verify_citations | Выбраны 7 точных цитат; result 48: valid 7 / invalid 0. |
| 48: верификация | 49: build_report | В позднем ходе все findings и conclusion=null; validated result 50, completed 51, mode 52, final 53. |

На seq 45 модель обосновала `changed` для F009 прямой передачей проверки из ОФК в ЦС (after 2.6) и изменением независимого контроля на проверку собственного решения (after 7.4). Полные тексты ранее пришли в результатах 22, 32, 42. Это наблюдаемая содержательная зависимость, не утверждение о скрытом рассуждении модели. Offer 37/38 был accepted=true, changed=false: уже существовавшие кандидаты, не второе улучшение.

Всего 2 вызова семейства предложений: 1 offer/no-op и 1 resolve/изменение. Принято 2/2, отклонено 0/2; реально изменён 1 finding. `propose_unit_change`: 0; `propose_risk`: 0. Host создал исходный deterministic Report, проверял инструменты, пересобрал итог и написал русское заключение; оно не приписывается свободному тексту модели.

Listed 19/19 и inspected 19/19. Полные тексты 31/31 пунктов, классифицированных parser как function, встречаются в промежуточных inspection results. Прочитаны все 15 различных определений подразделений; перечислены 7 unit_changes и 2 risks. Это экспозиция источников, не 31 верное решение. В inspect_domain были опущены 5 unit-citations и 6 risk-citations; поздние чтения включили основания преобразований 2.1–2.4 и обязанности 4.1/7.2/7.4/10.1. Четыре поиска вернули по 8 элементов с omitted_after 11/23/4/11; отдельный поиск не выдаётся за исчерпывающую семантическую проверку.

Для created-unit `U0def3b8dea71` агент действительно проверял предшественников: call 23/result 24 прочитал полный after 2.5 о создании впервые; call 33/result 34 прочитал все 7 before-unit definitions; call 35 `search_units(predecessor_for=after-1:1.1/з,limit=12)` / result 36 вернул все 7 before units, scanned_scope=7, next_offset=null, omitted=0. Это подтверждённый выбор поиска, а не только прочитанная формулировка host. Однако агент не предложил изменения unit-row: итоговый created вывод наследует baseline и по-прежнему цитирует только определение after 1.1/з, без прямого основания 2.5. Само ранжирование search не доказывает семантическое отсутствие предшественника.

Только F009 отличается между Report: status unresolved→changed, method lexical→llm, reason заменён host-шаблоном. Его before/after refs, все citations и review_required=true сохранены. Остальные 18/19 findings, 7/7 unit_changes, 2/2 risks, documents/clauses/units совпадают полностью. Coverage.unresolved 3→0 отражает 3 refs одного finding, не 3 исправления. Host-заключение убрало unresolved-пункт и включило F009 в changed 8→9. Риски уже были в deterministic; агент их не обнаружил заново. Этот reviewer не читал gold и не приписывает изменению F009 прирост замороженной метрики.

| Область ledger | Requests | Input | Cached в input | Output | Reasoning в output | Total | Оценка стоимости ledger |
|---|---:|---:|---:|---:|---:|---:|---:|
| Новый run #16–22 | 7 | 130312 | 1664 | 3339 | 1625 | 133651 | $0.744242 |
| Прошлые попытки #1–15 | 15 | 296244 | 1664 | 7274 | 3450 | 303518 | $1.691952 |
| Весь ledger | 22 | 426556 | 3328 | 10613 | 5075 | 437169 | $2.436194 |

22/22 token-sum checks и 22/22 арифметических cost checks проходят. Расчёт соответствует подразумеваемым ledger ставкам $5/M input, $0.5/M cached, $30/M output; текущая цена и счёт провайдера отдельно не проверялись. Reservations не суммируются как расходы. Заявленный общий лимит $10; накопленный ledger $2.436194. Старый request 7 имеет status=started при наличии HTTP 200/usage/cost; к новому run это не относится. Текущие 7/7 requests имеют completed, HTTP 200, request/response IDs и response_model=gpt-5.5-2026-04-23. Один completed capture не является success rate всех development-попыток.

Идентичность OpenAI записана в сохранённых метаданных ответов и server-attestation. ZIP не содержит raw upstream bodies, счёт или исходник transport с attested hash. Независимо подтвердить прозрачность proxy и живое соблюдение cap по одним этим файлам нельзя. Это предел доказательности, не свидетельство mock. Заявление только о сохранённом внешнем запуске; inference на машине reviewer не выполнялся.

Воспроизведение: все seq относятся к `capture-docx/agent-trace.json` архива. Сопоставить каждый tool_call с соседним tool_result по call_id; сравнить 53 SSE data envelopes с trace, затем final.payload/reopened с agent.json. Для usage выбрать requests с started_unix от 1790165763.403791 до 1790165814.0262337: получатся #16–22. `trace-review.json` содержит хеши исходных артефактов и каждого result object, канонизированного через json.dumps(ensure_ascii=False,sort_keys=True,separators=(',',':')).
