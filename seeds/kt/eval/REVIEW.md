# Пакет проверки Alibi

Это предложения AI по исходникам. Подтверждение человеком пока не получено. Проверить статус, полный набор refs, область ответственности и родительские условия. Holdout нельзя передавать для настройки ядра.

## dev-owner — development / synthetic

Предложение: **moved**. Функция сохранена, ответственный отдел сменился в родительском пункте.

До: [{"doc": "before-1", "clause_id": "2.1.1"}]

После: [{"doc": "after-1", "clause_id": "2.1.1"}]

before-1 §2.1.1 — `seeds/kt/eval/mutations/stage2/dev-owner/before-1.txt`

> готовить реестр рисков.

after-1 §2.1.1 — `seeds/kt/eval/mutations/stage2/dev-owner/after-1.txt`

> готовить реестр рисков.

before-1 §2.1 — `seeds/kt/eval/mutations/stage2/dev-owner/before-1.txt`

> Отдел рисков обязан:

after-1 §2.1 — `seeds/kt/eval/mutations/stage2/dev-owner/after-1.txt`

> Отдел комплаенса обязан:

## dev-delegate — development / synthetic

Предложение: **changed**. Изменён делегат подготовки отчёта, а не ответственный Главный аудитор.

До: [{"doc": "before-1", "clause_id": "2.1"}]

После: [{"doc": "after-1", "clause_id": "2.1"}]

before-1 §2.1 — `seeds/kt/eval/mutations/stage2/dev-delegate/before-1.txt`

> Главный аудитор поручает директору ДНМ подготовку отчёта; ответственность сохраняет Главный аудитор.

after-1 §2.1 — `seeds/kt/eval/mutations/stage2/dev-delegate/after-1.txt`

> Главный аудитор поручает директору ДККМ подготовку отчёта; ответственность сохраняет Главный аудитор.

## dev-prohibition — development / synthetic

Предложение: **changed**. Одинаковый дочерний текст изменил модальность: запрет стал обязанностью.

До: [{"doc": "before-1", "clause_id": "2.1.1"}]

После: [{"doc": "after-1", "clause_id": "2.1.1"}]

before-1 §2.1.1 — `seeds/kt/eval/mutations/stage2/dev-prohibition/before-1.txt`

> подписывать платёжные документы.

after-1 §2.1.1 — `seeds/kt/eval/mutations/stage2/dev-prohibition/after-1.txt`

> подписывать платёжные документы.

before-1 §2.1 — `seeds/kt/eval/mutations/stage2/dev-prohibition/before-1.txt`

> Работникам аудита запрещается:

after-1 §2.1 — `seeds/kt/eval/mutations/stage2/dev-prohibition/after-1.txt`

> Работники аудита обязаны:

## dev-split — development / synthetic

Предложение: **changed**. Одна составная обязанность разделена на два пункта без утраты частей.

До: [{"doc": "before-1", "clause_id": "2.1.1"}]

После: [{"doc": "after-1", "clause_id": "2.1.1"}, {"doc": "after-1", "clause_id": "2.1.2"}]

before-1 §2.1.1 — `seeds/kt/eval/mutations/stage2/dev-split/before-1.txt`

> проверять заявки и контролировать исполнение рекомендаций.

after-1 §2.1.1 — `seeds/kt/eval/mutations/stage2/dev-split/after-1.txt`

> проверять заявки.

after-1 §2.1.2 — `seeds/kt/eval/mutations/stage2/dev-split/after-1.txt`

> контролировать исполнение рекомендаций.

## dev-merge — development / synthetic

Предложение: **changed**. Две обязанности объединены в одном пункте; требуется полное множество refs.

До: [{"doc": "before-1", "clause_id": "2.1.1"}, {"doc": "before-1", "clause_id": "2.1.2"}]

После: [{"doc": "after-1", "clause_id": "2.1.1"}]

before-1 §2.1.1 — `seeds/kt/eval/mutations/stage2/dev-merge/before-1.txt`

> регистрировать материалы.

before-1 §2.1.2 — `seeds/kt/eval/mutations/stage2/dev-merge/before-1.txt`

> хранить материалы.

after-1 §2.1.1 — `seeds/kt/eval/mutations/stage2/dev-merge/after-1.txt`

> регистрировать материалы и хранить материалы.

## dev-shared-dnm — development / synthetic

Предложение: **unchanged**. Одинаковая формулировка законно применяется к разным направлениям; явного пересечения зон нет.

До: [{"doc": "before-1", "clause_id": "2.1.1"}]

После: [{"doc": "after-1", "clause_id": "2.1.1"}]

before-1 §2.1.1 — `seeds/kt/eval/mutations/stage2/dev-shared-dnm/before-1.txt`

> готовит предложения в план.

after-1 §2.1.1 — `seeds/kt/eval/mutations/stage2/dev-shared-dnm/after-1.txt`

> готовит предложения в план.

before-1 §2.1 — `seeds/kt/eval/mutations/stage2/dev-shared-dnm/before-1.txt`

> ДНМ в пределах своего направления:

after-1 §2.1 — `seeds/kt/eval/mutations/stage2/dev-shared-dnm/after-1.txt`

> ДНМ в пределах своего направления:

## dev-shared-dkkm — development / synthetic

Предложение: **unchanged**. Одинаковая формулировка законно применяется к разным направлениям; явного пересечения зон нет.

До: [{"doc": "before-1", "clause_id": "2.2.1"}]

После: [{"doc": "after-1", "clause_id": "2.2.1"}]

before-1 §2.2.1 — `seeds/kt/eval/mutations/stage2/dev-shared-dkkm/before-1.txt`

> готовит предложения в план.

after-1 §2.2.1 — `seeds/kt/eval/mutations/stage2/dev-shared-dkkm/after-1.txt`

> готовит предложения в план.

before-1 §2.2 — `seeds/kt/eval/mutations/stage2/dev-shared-dkkm/before-1.txt`

> ДККМ в пределах своего направления:

after-1 §2.2 — `seeds/kt/eval/mutations/stage2/dev-shared-dkkm/after-1.txt`

> ДККМ в пределах своего направления:

## dev-identical-inline — development / synthetic

Предложение: **unchanged**. Один и тот же файл по обе стороны; ссылки различаются стороной, содержание не менялось.

До: [{"doc": "before-1", "clause_id": "3.11"}]

После: [{"doc": "after-1", "clause_id": "3.11"}]

before-1 §3.11 — `seeds/kt/eval/mutations/stage2/dev-identical-inline/identical.txt`

> Работники хранят журнал.

after-1 §3.11 — `seeds/kt/eval/mutations/stage2/dev-identical-inline/identical.txt`

> Работники хранят журнал.

## dev-identical-repeated — development / synthetic

Предложение: **unchanged**. Один и тот же файл по обе стороны; ссылки различаются стороной, содержание не менялось.

До: [{"doc": "before-1", "clause_id": "3.10@2"}]

После: [{"doc": "after-1", "clause_id": "3.10@2"}]

before-1 §3.10@2 — `seeds/kt/eval/mutations/stage2/dev-identical-repeated/identical.txt`

> Дополнительная обязанность по проверке архива.

after-1 §3.10@2 — `seeds/kt/eval/mutations/stage2/dev-identical-repeated/identical.txt`

> Дополнительная обязанность по проверке архива.

## dev-multidoc — development / synthetic

Предложение: **moved**. Функция перенумерована в комплекте из четырёх документов; одинаковые файлы секретариата различаются стороной.

До: [{"doc": "before-1", "clause_id": "2.1"}]

После: [{"doc": "after-1", "clause_id": "4.1"}]

before-1 §2.1 — `seeds/kt/eval/mutations/stage2/dev-multidoc/before-1.txt`

> Служба аудита проверяет закупки.

after-1 §4.1 — `seeds/kt/eval/mutations/stage2/dev-multidoc/after-1.txt`

> Служба аудита проверяет закупки.

## hold-owner — holdout / synthetic

Предложение: **moved**. Полномочие передано другому ответственному органу через родительский пункт.

До: [{"doc": "before-1", "clause_id": "4.2.1"}]

После: [{"doc": "after-1", "clause_id": "4.2.1"}]

before-1 §4.2.1 — `seeds/kt/eval/mutations/stage2/hold-owner/before-1.txt`

> утверждает план проверок.

after-1 §4.2.1 — `seeds/kt/eval/mutations/stage2/hold-owner/after-1.txt`

> утверждает план проверок.

before-1 §4.2 — `seeds/kt/eval/mutations/stage2/hold-owner/before-1.txt`

> Директор аудита:

after-1 §4.2 — `seeds/kt/eval/mutations/stage2/hold-owner/after-1.txt`

> Комитет по аудиту:

## hold-delegate — holdout / synthetic

Предложение: **changed**. Ответственный прежний; исполнитель поручения изменён.

До: [{"doc": "before-1", "clause_id": "4.1"}]

После: [{"doc": "after-1", "clause_id": "4.1"}]

before-1 §4.1 — `seeds/kt/eval/mutations/stage2/hold-delegate/before-1.txt`

> Руководитель аудита поручает секретарю подготовку протокола и отвечает за результат.

after-1 §4.1 — `seeds/kt/eval/mutations/stage2/hold-delegate/after-1.txt`

> Руководитель аудита поручает заместителю подготовку протокола и отвечает за результат.

## hold-parent — holdout / synthetic

Предложение: **changed**. Синтетический контрпример: запрет родителя заменён разрешением; дочерняя строка идентична.

До: [{"doc": "before-1", "clause_id": "4.1.1"}]

После: [{"doc": "after-1", "clause_id": "4.1.1"}]

before-1 §4.1.1 — `seeds/kt/eval/mutations/stage2/hold-parent/before-1.txt`

> использовать данные проверки в личных целях.

after-1 §4.1.1 — `seeds/kt/eval/mutations/stage2/hold-parent/after-1.txt`

> использовать данные проверки в личных целях.

before-1 §4.1 — `seeds/kt/eval/mutations/stage2/hold-parent/before-1.txt`

> Аудитор не вправе:

after-1 §4.1 — `seeds/kt/eval/mutations/stage2/hold-parent/after-1.txt`

> Аудитор вправе:

## hold-split — holdout / synthetic

Предложение: **changed**. Разделение составного полномочия на два пункта с тем же ответственным.

До: [{"doc": "before-1", "clause_id": "4.1"}]

После: [{"doc": "after-1", "clause_id": "4.1"}, {"doc": "after-1", "clause_id": "4.2"}]

before-1 §4.1 — `seeds/kt/eval/mutations/stage2/hold-split/before-1.txt`

> Куратор согласует сроки и утверждает состав группы.

after-1 §4.1 — `seeds/kt/eval/mutations/stage2/hold-split/after-1.txt`

> Куратор согласует сроки.

after-1 §4.2 — `seeds/kt/eval/mutations/stage2/hold-split/after-1.txt`

> Куратор утверждает состав группы.

## hold-shared — holdout / synthetic

Предложение: **unchanged**. Разные территории явно указаны в родителях: совпадение текста не доказывает дублирование.

До: [{"doc": "before-1", "clause_id": "4.2.1"}]

После: [{"doc": "after-1", "clause_id": "4.2.1"}]

before-1 §4.2.1 — `seeds/kt/eval/mutations/stage2/hold-shared/before-1.txt`

> составляет график проверки.

after-1 §4.2.1 — `seeds/kt/eval/mutations/stage2/hold-shared/after-1.txt`

> составляет график проверки.

before-1 §4.1 — `seeds/kt/eval/mutations/stage2/hold-shared/before-1.txt`

> Аудитор Северного филиала в пределах своего филиала:

before-1 §4.2 — `seeds/kt/eval/mutations/stage2/hold-shared/before-1.txt`

> Аудитор Южного филиала в пределах своего филиала:

after-1 §4.1 — `seeds/kt/eval/mutations/stage2/hold-shared/after-1.txt`

> Аудитор Северного филиала в пределах своего филиала:

after-1 §4.2 — `seeds/kt/eval/mutations/stage2/hold-shared/after-1.txt`

> Аудитор Южного филиала в пределах своего филиала:

## hold-uncertainty — holdout / synthetic

Предложение: **unresolved**. В источнике два взаимоисключающих варианта и отсутствует решение выбора; уверенный перенос или duplicate не обоснован.

До: [{"doc": "before-1", "clause_id": "4.1"}]

После: [{"doc": "after-1", "clause_id": "4.1.1"}, {"doc": "after-1", "clause_id": "4.1.2"}]

before-1 §4.1 — `seeds/kt/eval/mutations/stage2/hold-uncertainty/before-1.txt`

> Отдел А контролирует исполнение плана.

after-1 §4.1.1 — `seeds/kt/eval/mutations/stage2/hold-uncertainty/after-1.txt`

> Отдел Б контролирует исполнение плана.

after-1 §4.1.2 — `seeds/kt/eval/mutations/stage2/hold-uncertainty/after-1.txt`

> Отдел В контролирует исполнение плана.

after-1 §4.1 — `seeds/kt/eval/mutations/stage2/hold-uncertainty/after-1.txt`

> Применяется ровно один из следующих вариантов по отдельному решению, которое не входит в комплект документов:

## hold-real-01 — holdout / real

Предложение: **unchanged**. Исходники сопоставлены до запуска: текст и ответственный совпадают; выбран вне исходных §§2–5.

До: [{"doc": "v8", "clause_id": "7.1"}]

После: [{"doc": "v9", "clause_id": "7.1"}]

v8 §7.1 — `seeds/kt/v8.txt`

> Ответственность за деятельность БВА и его структурных подразделений несет Главный аудитор.

v9 §7.1 — `seeds/kt/v9.txt`

> Ответственность за деятельность БВА и его структурных подразделений несет Главный аудитор.

## hold-real-02 — holdout / real

Предложение: **unchanged**. Исходники сопоставлены до запуска: текст и ответственный совпадают; выбран вне исходных §§2–5.

До: [{"doc": "v8", "clause_id": "8.11"}]

После: [{"doc": "v9", "clause_id": "8.11"}]

v8 §8.11 — `seeds/kt/v8.txt`

> В случае если внутренние ресурсы не позволяют реализовать все плановые проверки и прочие мероприятия, указанные в плане, Главный аудитор информирует Совет директоров (Комитет по аудиту) о необходимости принятия соответствующего решения (например, выделения дополнительных ресурсов для выполнения плана посредством увеличения численности работников БВА, привлечения сторонних организаций (аутсорсинг/косорсинг) или сокращения объема задач).

v9 §8.11 — `seeds/kt/v9.txt`

> В случае если внутренние ресурсы не позволяют реализовать все плановые проверки и прочие мероприятия, указанные в плане, Главный аудитор информирует Совет директоров (Комитет по аудиту) о необходимости принятия соответствующего решения (например, выделения дополнительных ресурсов для выполнения плана посредством увеличения численности работников БВА, привлечения сторонних организаций (аутсорсинг/косорсинг) или сокращения объема задач).

