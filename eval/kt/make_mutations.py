"""Create independently labelled, one-change-at-a-time v9 audit fixtures."""

from __future__ import annotations

import codecs
import argparse
import datetime
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "seeds/kt/v9.txt"
LABELS = ROOT / "seeds/kt/eval/labels.jsonl"
OUT = ROOT / "seeds/kt/eval/mutations"


def canonical_sha(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def freeze_stage2() -> None:
    """Write source-first proposals; never derives expected answers from a Report."""
    base = ROOT / "seeds/kt/eval"
    split_path = base / "split.json"
    if split_path.exists():
        raise ValueError("split.json already exists; frozen membership requires an explicit reviewed edit")
    regression = base / "regression.jsonl"
    regression.write_bytes(LABELS.read_bytes())
    rows, metadata = [], {}

    def add(case_id, partition, texts, before, after, status, rationale, category, contexts=(), same_file=False):
        folder = OUT / "stage2" / case_id
        folder.mkdir(parents=True, exist_ok=True)
        documents, sources = [], {}
        for alias, text in texts.items():
            target = folder / ("identical.txt" if same_file else f"{alias}.txt")
            target.write_bytes(text.encode("utf-8"))
            documents.append(doc(alias, target))
            sources[alias] = text
        references = [("before-1", x) for x in before] if all(isinstance(x, str) for x in before) else before
        successors = [("after-1", x) for x in after] if all(isinstance(x, str) for x in after) else after
        cites = []
        for alias, cid in dict.fromkeys(references + successors + list(contexts)):
            # Fixture source text is authored here. Repeated/inline IDs are resolved
            # by the existing evaluator once its boundary fix is in place.
            if cid == "3.11":
                quote = "Работники хранят журнал."
            elif cid == "3.10@2":
                quote = "Дополнительная обязанность по проверке архива."
            else:
                quote = numbered_line(sources[alias], cid)
            cites.append(citation(alias, cid, quote, sources[alias]))
        row = {"id": case_id, "kind": "synthetic", "documents": documents,
               "before": [ref(*r) for r in references], "after": [ref(*r) for r in successors],
               "expected_status": status, "citations": cites, "rationale": rationale,
               "annotator": "AI proposal; Alibi human confirmation pending",
               "mutation": {"operation": category, "source": ref(*references[0]),
                            "description": "Синтетический независимый текст: " + rationale}}
        rows.append(row)
        metadata[case_id] = {"partition": partition, "kind": "synthetic", "categories": [category],
                             "review_status": "pending_human", "selection": "source-first authored fixture",
                             "label_sha256": canonical_sha(row)}

    def pair(case_id, partition, old, new, before, after, status, why, category, contexts=()):
        add(case_id, partition, {"before-1": old, "after-1": new}, before, after,
            status, why, category, contexts)

    pair("dev-owner", "development",
         "2. Обязанности\n2.1. Отдел рисков обязан:\n2.1.1. готовить реестр рисков.\n",
         "2. Обязанности\n2.1. Отдел комплаенса обязан:\n2.1.1. готовить реестр рисков.\n",
         ["2.1.1"], ["2.1.1"], "moved", "Функция сохранена, ответственный отдел сменился в родительском пункте.",
         "owner_change", [("before-1", "2.1"), ("after-1", "2.1")])
    pair("dev-delegate", "development",
         "2. Обязанности\n2.1. Главный аудитор поручает директору ДНМ подготовку отчёта; ответственность сохраняет Главный аудитор.\n",
         "2. Обязанности\n2.1. Главный аудитор поручает директору ДККМ подготовку отчёта; ответственность сохраняет Главный аудитор.\n",
         ["2.1"], ["2.1"], "changed", "Изменён делегат подготовки отчёта, а не ответственный Главный аудитор.", "delegate_change")
    pair("dev-prohibition", "development",
         "2. Ограничения\n2.1. Работникам аудита запрещается:\n2.1.1. подписывать платёжные документы.\n",
         "2. Ограничения\n2.1. Работники аудита обязаны:\n2.1.1. подписывать платёжные документы.\n",
         ["2.1.1"], ["2.1.1"], "changed", "Одинаковый дочерний текст изменил модальность: запрет стал обязанностью.",
         "parent_prohibition", [("before-1", "2.1"), ("after-1", "2.1")])
    pair("dev-split", "development",
         "2. Проверка заявок\n2.1. Аудитор обязан:\n2.1.1. проверять заявки и контролировать исполнение рекомендаций.\n",
         "2. Проверка заявок\n2.1. Аудитор обязан:\n2.1.1. проверять заявки.\n2.1.2. контролировать исполнение рекомендаций.\n",
         ["2.1.1"], ["2.1.1", "2.1.2"], "changed", "Одна составная обязанность разделена на два пункта без утраты частей.", "split")
    pair("dev-merge", "development",
         "2. Учёт материалов\n2.1. Секретарь обязан:\n2.1.1. регистрировать материалы.\n2.1.2. хранить материалы.\n",
         "2. Учёт материалов\n2.1. Секретарь обязан:\n2.1.1. регистрировать материалы и хранить материалы.\n",
         ["2.1.1", "2.1.2"], ["2.1.1"], "changed", "Две обязанности объединены в одном пункте; требуется полное множество refs.", "merge")
    shared = "2. Совместная подготовка плана\n2.1. ДНМ в пределах своего направления:\n2.1.1. готовит предложения в план.\n2.2. ДККМ в пределах своего направления:\n2.2.1. готовит предложения в план.\n"
    for suffix, cid, parent in (("dnm", "2.1.1", "2.1"), ("dkkm", "2.2.1", "2.2")):
        pair("dev-shared-" + suffix, "development", shared, shared, [cid], [cid], "unchanged",
             "Одинаковая формулировка законно применяется к разным направлениям; явного пересечения зон нет.",
             "legitimate_shared", [("before-1", parent), ("after-1", parent)])
    markers = "3. Работа с журналом\n3.9. Рабочее место. 3.10.Работники ведут журнал. 3.11.Работники хранят журнал.\n3.12. Ссылка на пункт 3.10. не вводит новую обязанность.\n3.10. Дополнительная обязанность по проверке архива.\n"
    for suffix, cid in (("inline", "3.11"), ("repeated", "3.10@2")):
        add("dev-identical-" + suffix, "development", {"before-1": markers, "after-1": markers}, [cid], [cid],
            "unchanged", "Один и тот же файл по обе стороны; ссылки различаются стороной, содержание не менялось.",
            "identical_file_markers", same_file=True)
    add("dev-multidoc", "development", {
        "before-1": "2. Служба аудита\n2.1. Служба аудита проверяет закупки.\n",
        "before-2": "1. Секретариат\n1.1. Секретариат регистрирует письма.\n",
        "after-1": "4. Служба аудита\n4.1. Служба аудита проверяет закупки.\n",
        "after-2": "1. Секретариат\n1.1. Секретариат регистрирует письма.\n"},
        ["2.1"], ["4.1"], "moved", "Функция перенумерована в комплекте из четырёх документов; одинаковые файлы секретариата различаются стороной.", "multi_document_aliases")

    # Reserved before any Stage 2 Report is read. Core tuners must not use these answers.
    pair("hold-owner", "holdout",
         "4. Проверки\n4.2. Директор аудита:\n4.2.1. утверждает план проверок.\n",
         "4. Проверки\n4.2. Комитет по аудиту:\n4.2.1. утверждает план проверок.\n",
         ["4.2.1"], ["4.2.1"], "moved", "Полномочие передано другому ответственному органу через родительский пункт.",
         "owner_change", [("before-1", "4.2"), ("after-1", "4.2")])
    pair("hold-delegate", "holdout",
         "4. Делегирование\n4.1. Руководитель аудита поручает секретарю подготовку протокола и отвечает за результат.\n",
         "4. Делегирование\n4.1. Руководитель аудита поручает заместителю подготовку протокола и отвечает за результат.\n",
         ["4.1"], ["4.1"], "changed", "Ответственный прежний; исполнитель поручения изменён.", "delegate_change")
    pair("hold-parent", "holdout",
         "4. Использование данных\n4.1. Аудитор не вправе:\n4.1.1. использовать данные проверки в личных целях.\n",
         "4. Использование данных\n4.1. Аудитор вправе:\n4.1.1. использовать данные проверки в личных целях.\n",
         ["4.1.1"], ["4.1.1"], "changed", "Синтетический контрпример: запрет родителя заменён разрешением; дочерняя строка идентична.",
         "parent_prohibition", [("before-1", "4.1"), ("after-1", "4.1")])
    pair("hold-split", "holdout",
         "4. Согласование проверки\n4.1. Куратор согласует сроки и утверждает состав группы.\n",
         "4. Согласование проверки\n4.1. Куратор согласует сроки.\n4.2. Куратор утверждает состав группы.\n",
         ["4.1"], ["4.1", "4.2"], "changed", "Разделение составного полномочия на два пункта с тем же ответственным.", "split")
    shared_hold = "4. Работа филиалов\n4.1. Аудитор Северного филиала в пределах своего филиала:\n4.1.1. составляет график проверки.\n4.2. Аудитор Южного филиала в пределах своего филиала:\n4.2.1. составляет график проверки.\n"
    pair("hold-shared", "holdout", shared_hold, shared_hold, ["4.2.1"], ["4.2.1"], "unchanged",
         "Разные территории явно указаны в родителях: совпадение текста не доказывает дублирование.",
         "legitimate_shared", [("before-1", "4.1"), ("before-1", "4.2"), ("after-1", "4.1"), ("after-1", "4.2")])
    pair("hold-uncertainty", "holdout",
         "4. Контроль\n4.1. Отдел А контролирует исполнение плана.\n",
         "4. Проект распределения ответственности\n4.1. Применяется ровно один из следующих вариантов по отдельному решению, которое не входит в комплект документов:\n4.1.1. Отдел Б контролирует исполнение плана.\n4.1.2. Отдел В контролирует исполнение плана.\n",
         ["4.1"], ["4.1.1", "4.1.2"], "unresolved", "В источнике два взаимоисключающих варианта и отсутствует решение выбора; уверенный перенос или duplicate не обоснован.",
         "appropriate_abstention", [("after-1", "4.1")])

    for number, cid in ((1, "7.1"), (2, "8.11")):
        before_path, after_path = ROOT / "seeds/kt/v8.txt", SOURCE
        before_quote = numbered_line(raw_text(before_path), cid)
        after_quote = numbered_line(raw_text(after_path), cid)
        assert before_quote == after_quote
        row = {"id": f"hold-real-{number:02}", "kind": "real",
               "documents": [doc("v8", before_path), doc("v9", after_path)],
               "before": [ref("v8", cid)], "after": [ref("v9", cid)], "expected_status": "unchanged",
               "citations": [citation("v8", cid, before_quote, raw_text(before_path)),
                             citation("v9", cid, after_quote, raw_text(after_path))],
               "rationale": "Исходники сопоставлены до запуска: текст и ответственный совпадают; выбран вне исходных §§2–5.",
               "annotator": "AI proposal; Alibi human confirmation pending", "mutation": None}
        rows.append(row)
        metadata[row["id"]] = {"partition": "holdout", "kind": "real", "categories": ["responsibility_context"],
                                "selection": "source-first: 7.1 responsibility and 8.11 resource escalation",
                                "review_status": "pending_human", "label_sha256": canonical_sha(row)}
    challenge = base / "challenge.jsonl"
    challenge.write_text("".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in rows), encoding="utf-8", newline="\n")
    old = [json.loads(x) for x in regression.read_text(encoding="utf-8").splitlines() if x]
    for row in old:
        metadata[row["id"]] = {"partition": "regression", "kind": row["kind"], "categories": ["stage1"],
                                "review_status": "legacy_accepted", "label_sha256": canonical_sha(row)}
    fixtures = {d["file"]: d["sha256"] for row in old + rows for d in row["documents"]}
    split = {"schema_version": 1, "frozen_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
             "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
             "independence": "procedural shared-repository source-first; not technically blind; pending human confirmation",
             "selection_rule": "All baseline unresolved; first 3 per confident status by SHA256(seed + canonical refs), outside regression/holdout; report-selected cases are development.",
             "selection_seed": "alibi-stage2-2026-09-23", "datasets": {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in (LABELS, regression, challenge)},
             "fixtures": fixtures, "cases": metadata}
    split_path.write_text(json.dumps(split, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Frozen regression={len(old)}, challenge proposals={len(rows)}; human review pending")


def review_packet() -> None:
    base = ROOT / "seeds/kt/eval"
    rows = [json.loads(x) for x in (base / "challenge.jsonl").read_text(encoding="utf-8").splitlines() if x]
    split = json.loads((base / "split.json").read_text(encoding="utf-8"))
    out = ["# Пакет проверки Alibi", "", "Это предложения AI по исходникам. Подтверждение человеком пока не получено. "
           "Проверить статус, полный набор refs, область ответственности и родительские условия. "
           "Holdout нельзя передавать для настройки ядра.", ""]
    for row in rows:
        member = split["cases"][row["id"]]
        out += [f"## {row['id']} — {member['partition']} / {row['kind']}", "",
                f"Предложение: **{row['expected_status']}**. {row['rationale']}", "",
                "До: " + json.dumps(row["before"], ensure_ascii=False), "",
                "После: " + json.dumps(row["after"], ensure_ascii=False), ""]
        files = {d["doc"]: d["file"] for d in row["documents"]}
        for c in row["citations"]:
            out += [f"{c['doc']} §{c['clause_id']} — `{files[c['doc']]}`", "", "> " + c["quote"].replace("\n", "\n> "), ""]
    (base / "REVIEW.md").write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    print("Wrote seeds/kt/eval/REVIEW.md")


def capture_reports(labels_path: Path, output: Path, partition: str | None, canonical: bool) -> None:
    """Capture predictions using only the public audit/ingest API, never expected labels."""
    sys.path.insert(0, str(ROOT / "apps/api"))
    from app.audit import make_documents, load_manifest, run_deterministic_audit
    from app.ingest.parsers import parse_docx, parse_txt
    rows = [json.loads(x) for x in labels_path.read_text(encoding="utf-8").splitlines() if x]
    split_path = ROOT / "seeds/kt/eval/split.json"
    split = json.loads(split_path.read_text(encoding="utf-8")) if split_path.exists() else {"cases": {}}
    if partition:
        rows = [r for r in rows if split["cases"][r["id"]]["partition"] == partition]
    output.mkdir(parents=True, exist_ok=True)
    seen, records = set(), []
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    core_files = list((ROOT / "apps/api/app/audit").glob("*.py")) + [ROOT / "apps/api/app/ingest/parsers.py"]
    core_hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in core_files}
    for row in rows:
        # All capture fixtures use explicit conventional aliases. The scorer itself
        # independently tests and supports report-local alias renaming.
        inputs = []
        for d in row["documents"]:
            alias = d["doc"]
            side = "before" if alias == "v8" or alias.startswith("before-") else "after" if alias == "v9" or alias.startswith("after-") else None
            if side is None:
                raise ValueError(f"Capture needs a side for {alias}; score an externally supplied Report instead")
            path = ROOT / d["file"]
            if canonical and d["file"] in ("seeds/kt/v8.txt", "seeds/kt/v9.txt"):
                path = path.with_suffix(".docx")
            inputs.append((side, path, sha(path)))
        key = tuple((side, digest) for side, _, digest in inputs)
        if key in seen:
            continue
        seen.add(key)
        sides = {side: [(digest[:16], digest, p.name) for s, p, digest in inputs if s == side] for side in ("before", "after")}
        documents, warnings = make_documents(sides["before"], sides["after"], load_manifest())
        ordered = [item for side in ("before", "after") for item in inputs if item[0] == side]
        pages = {d.doc: (parse_docx(p) if p.suffix == ".docx" else parse_txt(p)) for d, (_, p, _) in zip(documents, ordered)}
        run_id = "alibi-" + hashlib.sha256(repr(key).encode()).hexdigest()[:12]
        report = run_deterministic_audit(run_id, documents, pages, warnings)
        destination = output / f"{run_id}.json"
        destination.write_text(report.model_dump_json(), encoding="utf-8", newline="\n")
        records.append({"file": destination.relative_to(ROOT).as_posix(), "sha256": sha(destination),
                        "run_id": run_id, "documents": [d.model_dump() for d in documents],
                        "findings": len(report.findings), "coverage": report.coverage.model_dump()})
        print(destination.relative_to(ROOT).as_posix(), len(report.findings))
    if core_hashes != {p.relative_to(ROOT).as_posix(): sha(p) for p in core_files}:
        raise RuntimeError("Core changed during capture; discard this run batch")
    manifest = {"captured_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "revision": revision,
                "core_hashes": core_hashes, "labels_file": labels_path.relative_to(ROOT).as_posix(),
                "labels_sha256": sha(labels_path), "partition": partition, "transport": "public domain API; no HTTP claim",
                "reports": records}
    (output / "capture-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def raw_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8-sig")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def doc(alias: str, path: Path) -> dict:
    return {"doc": alias, "file": path.relative_to(ROOT).as_posix(), "sha256": sha(path)}


def ref(alias: str, clause_id: str) -> dict:
    return {"doc": alias, "clause_id": clause_id}


def numbered_line(text: str, clause_id: str) -> str:
    hits = re.findall(rf"(?m)^{re.escape(clause_id)}\.\s+([^\r\n]*)", text)
    if len(hits) != 1:
        raise ValueError(f"Expected one {clause_id} clause; found {len(hits)}")
    return hits[0]


def letter_line(text: str, section: str, letter: str) -> str:
    start = re.search(rf"(?m)^{re.escape(section)}\.\s", text)
    if not start:
        raise ValueError(section)
    end = re.search(r"(?m)^\d+\.\d+\.\s", text[start.end():])
    block = text[start.end():start.end() + end.start() if end else len(text)]
    hits = re.findall(rf"(?m)^{re.escape(letter)}\.\s+([^\r\n]*)", block)
    if len(hits) != 1:
        raise ValueError(f"Expected one {section}/{letter} clause; found {len(hits)}")
    return hits[0]


def citation(alias: str, clause_id: str, quote: str, text: str) -> dict:
    if quote not in text:
        raise ValueError(f"Quote absent from {alias} {clause_id}")
    return {"doc": alias, "clause_id": clause_id, "quote": quote}


def real_extension(existing: list[dict]) -> list[dict]:
    """The additional matches were selected by reading both source editions."""
    old_path = ROOT / "seeds/kt/v8.txt"
    new_path = SOURCE
    old, new = raw_text(old_path), raw_text(new_path)
    documents = [doc("v8", old_path), doc("v9", new_path)]

    def line(text: str, clause_id: str) -> str:
        if "/" in clause_id:
            section, letter = clause_id.split("/")
            return letter_line(text, section, letter)
        return numbered_line(text, clause_id)

    def case(number: int, before: str | None, after: str | None,
             status: str, rationale: str) -> dict:
        cites = []
        if before:
            cites.append(citation("v8", before, line(old, before), old))
        if after:
            cites.append(citation("v9", after, line(new, after), new))
        if status == "unchanged" and cites[0]["quote"] != cites[1]["quote"]:
            raise ValueError(f"real-{number:03}: unchanged quote differs")
        return {
            "id": f"real-{number:03}", "kind": "real", "documents": documents,
            "before": [ref("v8", before)] if before else [],
            "after": [ref("v9", after)] if after else [],
            "expected_status": status, "citations": cites,
            "rationale": rationale, "annotator": "Alibi", "mutation": None,
        }

    additions = [
        case(11, "2.4.3", "2.4.3", "unchanged", "Иные проверки и поручения сохранены дословно."),
        case(12, "2.4.12", "2.4.12", "unchanged", "Проверки подконтрольных обществ сохранены дословно."),
        case(13, "3.5/б", "3.5/в", "moved", "Директор ДНМ остался в прямом подчинении Главному аудитору; подпункт сдвинулся."),
        case(14, "3.5/в", "3.5/г", "moved", "Директор ДККМ остался в прямом подчинении Главному аудитору; подпункт сдвинулся."),
        case(15, None, "3.5/а", "added", "В прямом подчинении Главному аудитору добавлен директор ДИТААД."),
        case(16, None, "3.5/б", "added", "В прямом подчинении Главному аудитору добавлен директор ДОА."),
        case(17, "4.1", "4.1", "unchanged", "Согласование положения о внутреннем аудите ДЗО дословно сохранено."),
        case(18, "4.2", "4.2", "unchanged", "Согласование руководителя внутреннего аудита ДЗО дословно сохранено."),
        case(19, "5.3.6", "5.3.7", "changed", "Контроль устранения нарушений дополнен развитием системы мониторинга корректирующих мер; круг ответственных расширен."),
        case(20, "5.1.2", "5.1.2", "unchanged", "Утверждение программы и сроков проверок сохранено дословно."),
    ]
    ids = {row["id"] for row in existing}
    return [row for row in additions if row["id"] not in ids]


def write_fixture(name: str, content: str) -> tuple[Path, str]:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.txt"
    path.write_bytes(codecs.BOM_UTF8 + content.encode("utf-8"))
    return path, content


def synthetic_case(name: str, operation: str, source_id: str,
                   status: str, before: list[str], after: list[str],
                   description: str, original: str, mutated: str,
                   path: Path) -> dict:
    return {
        "id": f"synthetic-{name}", "kind": "synthetic",
        "documents": [doc("before-1", SOURCE), doc("after-1", path)],
        "before": [ref("before-1", x) for x in before],
        "after": [ref("after-1", x) for x in after],
        "expected_status": status,
        "citations": [citation("before-1", x, numbered_line(original, x), original) for x in before]
        + [citation("after-1", x, numbered_line(mutated, x), mutated) for x in after],
        "rationale": description, "annotator": "Alibi",
        "mutation": {"operation": operation, "source": ref("before-1", source_id),
                     "description": description},
    }


def make_synthetic() -> list[dict]:
    original = raw_text(SOURCE)
    rows = []

    clause = "2.4.10"
    line = f"{clause}. {numbered_line(original, clause)}\r\n"
    assert original.count(line) == 1
    mutated = original.replace(line, "", 1)
    path, mutated = write_fixture("deleted-function", mutated)
    rows.append(synthetic_case("deleted-function", "delete", clause, "missing", [clause], [],
                               "Удалена функция последующего контроля 2.4.10.", original, mutated, path))

    clause = "5.5.5"
    duplicated = f"5.4.11. {numbered_line(original, clause)}\r\n"
    anchor = "5.5. Директор департамента контроля качества аудита и методологии"
    assert original.count(anchor) == 1 and "5.4.11." not in original
    mutated = original.replace(anchor, duplicated + anchor, 1)
    path, mutated = write_fixture("duplicated-function", mutated)
    rows.append(synthetic_case("duplicated-function", "duplicate", clause, "duplicate", [clause],
                               [clause, "5.4.11"], "Функция контроля качества устранения нарушений также приписана ДНМ.",
                               original, mutated, path))

    clause = "5.5.4"
    line = f"{clause}. {numbered_line(original, clause)}\r\n"
    assert original.count(line) == 1
    moved = f"5.4.11. {numbered_line(original, clause)}\r\n"
    mutated = original.replace(line, "", 1).replace(anchor, moved + anchor, 1)
    path, mutated = write_fixture("moved-function", mutated)
    rows.append(synthetic_case("moved-function", "move", clause, "moved", [clause], ["5.4.11"],
                               "Методические материалы перенесены от ДККМ к ДНМ.", original, mutated, path))

    mutated, count = re.subn(r"(?m)^5\.4(?=\.)", "5.11", original)
    assert count == 11, count
    path, mutated = write_fixture("renumbered-section", mutated)
    rows.append(synthetic_case("renumbered-section", "renumber", "5.4.5", "moved", ["5.4.5"],
                               ["5.11.5"], "Раздел ДНМ и его подпункты перенумерованы без потери функции.",
                               original, mutated, path))

    clause = "2.4.9"
    old = numbered_line(original, clause)
    new = old.replace("осуществление мониторинга", "осуществление  мониторинга", 1)
    assert new != old
    mutated = original.replace(f"{clause}. {old}", f"{clause}. {new}", 1)
    path, mutated = write_fixture("whitespace-only", mutated)
    rows.append(synthetic_case("whitespace-only", "whitespace", clause, "unchanged", [clause], [clause],
                               "В функции изменён только межсловный пробел.", original, mutated, path))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage2-freeze", action="store_true", help="Freeze source-first Stage 2 proposals once")
    parser.add_argument("--review-packet", action="store_true")
    parser.add_argument("--capture-reports", type=Path, help="Output directory for public pipeline predictions")
    parser.add_argument("--labels", type=Path, default=LABELS)
    parser.add_argument("--partition", choices=["regression", "development", "holdout"])
    parser.add_argument("--canonical-docx", action="store_true")
    args = parser.parse_args()
    if args.stage2_freeze:
        freeze_stage2()
        return
    if args.review_packet:
        review_packet()
        return
    if args.capture_reports:
        capture_reports(args.labels.resolve(), args.capture_reports.resolve(), args.partition, args.canonical_docx)
        return
    existing = [json.loads(line) for line in LABELS.read_text(encoding="utf-8").splitlines() if line.strip()]
    real = [row for row in existing if row["kind"] == "real"]
    real.extend(real_extension(real))
    if len(real) != 20:
        raise ValueError(f"Expected 20 real labels, got {len(real)}")
    synthetic = make_synthetic()
    with LABELS.open("w", encoding="utf-8", newline="\n") as stream:
        for row in real + synthetic:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"Wrote {len(real)} real and {len(synthetic)} synthetic labels")


if __name__ == "__main__":
    main()
