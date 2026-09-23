"""Report-local document aliases and input sanity checks."""

from __future__ import annotations

import json
from pathlib import Path

from .models import Document

# apps/api/app/audit/documents.py -> repository root is four levels up.
DEFAULT_MANIFEST_PATH = Path(__file__).resolve().parents[4] / "seeds" / "kt" / "manifest.json"


def load_manifest(path: str | Path | None = None) -> list[dict]:
    """Case manifest entries (``file``, ``sha256``, ``source`` …); ``[]`` when the file is absent."""
    target = Path(path) if path is not None else DEFAULT_MANIFEST_PATH
    if not target.is_file():
        return []
    data = json.loads(target.read_text(encoding="utf-8"))
    return [entry for entry in data if isinstance(entry, dict)] if isinstance(data, list) else []


def make_documents(
    before: list[tuple[str, str, str]],
    after: list[tuple[str, str, str]],
    manifest: list[dict] | None = None,
) -> tuple[list[Document], list[str]]:
    """Build ``Document`` records from ``(doc_id, sha256, source)`` tuples per side.

    The alias is the manifest file stem (``v8``) when the full SHA-256 matches a
    manifest entry, otherwise ``before-1``/``after-1`` … . Returns the documents and
    warnings about inputs that should not be compared as they are.
    """
    by_sha = {str(e.get("sha256", "")).lower(): e for e in (manifest or []) if e.get("sha256")}
    documents: list[Document] = []
    warnings: list[str] = []
    taken: set[str] = set()
    for edition, files in (("before", before), ("after", after)):
        for index, (doc_id, sha256, source) in enumerate(files, start=1):
            entry = by_sha.get(sha256.lower())
            alias = Path(str(entry["file"])).stem if entry and entry.get("file") else f"{edition}-{index}"
            if alias in taken:
                alias = f"{alias}-{edition}-{index}"
            taken.add(alias)
            documents.append(Document(doc=alias, doc_id=doc_id, sha256=sha256.lower(), edition=edition, source=source))

    seen_sha: dict[str, Document] = {}
    seen_origin: dict[str, Document] = {}
    for document in documents:
        prior = seen_sha.get(document.sha256)
        if prior is not None:
            warnings.append(
                f"{prior.doc} ({prior.edition}) and {document.doc} ({document.edition}) are byte-identical files."
            )
        seen_sha.setdefault(document.sha256, document)
        entry = by_sha.get(document.sha256)
        origin = str(entry.get("source") or "") if entry else ""
        if origin:
            prior = seen_origin.get(origin)
            if prior is not None and prior.sha256 != document.sha256:
                warnings.append(
                    f"{prior.doc} and {document.doc} are two exports of the same source document; "
                    "compare one canonical export (DOCX) per edition."
                )
            seen_origin.setdefault(origin, document)
    return documents, warnings
