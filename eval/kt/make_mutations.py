"""Create independently labelled, one-change-at-a-time v9 audit fixtures."""

from __future__ import annotations

import codecs
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "seeds/kt/v9.txt"
LABELS = ROOT / "seeds/kt/eval/labels.jsonl"
OUT = ROOT / "seeds/kt/eval/mutations"


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
