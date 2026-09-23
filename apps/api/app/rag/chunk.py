"""Deterministic page-aware chunking for the RAG pipeline.

`split_pages` turns parser output (`[{"page": int, "text": str}]`) into
embedding-ready chunks (`[{"ordinal": int, "page": int | None, "text": str}]`).

Splitting strategy, in order:

1. paragraph boundaries (``\\n\\n`` and wider blank-line gaps) are kept whole
   whenever they fit the chunk budget;
2. oversized paragraphs split at sentence terminators (``. ! ? …``, optionally
   followed by a closing quote/bracket) — text without any terminators simply
   yields no boundary and survives as one sentence;
3. a single sentence longer than ``target_chars`` is hard-cut into pieces of at
   most ``target_chars`` characters.

Consecutive chunks from the same page share a character overlap: the next
chunk is prefixed with the last ``overlap`` characters of the previous one so
that no sentence exists entirely inside a boundary. Chunks never exceed
``target_chars`` (the overlap tail is charged against the budget); pages whose
text is blank after ``strip()`` are skipped entirely. The function is pure and
deterministic: same input, same output, no external state.
"""

import re

__all__ = ["chunk_id", "split_pages"]

# A blank line (optionally containing spaces/tabs) or wider gap separates paragraphs.
_PARAGRAPH_SEP = re.compile(r"\n[ \t]*\n+")
# Zero-width split point: right after a sentence terminator, before whitespace
# (possibly with a closing quote/bracket in between). Never crashes on text
# without terminators — the pattern simply finds no boundary.
_SENTENCE_SEP = re.compile(r"(?<=[.!?…])(?=[\"'»”)\]]*\s)")


def chunk_id(doc_id: str, ordinal: int) -> str:
    """Stable identifier for the `ordinal`-th chunk of `doc_id`."""
    return f"{doc_id}:{ordinal:05d}"


def _units(text: str, target_chars: int) -> list[tuple[str, str]]:
    """Decompose one page into `(separator, unit)` packing atoms.

    A paragraph that fits the budget stays a single unit joined with ``\\n\\n``;
    an oversized paragraph becomes its sentences joined with ``" "``, with the
    first sentence still joined to the preceding unit by ``\\n\\n``.
    """
    units: list[tuple[str, str]] = []
    for paragraph in _PARAGRAPH_SEP.split(text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= target_chars:
            units.append(("\n\n", paragraph))
            continue
        first = True
        for sentence in _SENTENCE_SEP.split(paragraph):
            sentence = sentence.strip()
            if not sentence:
                continue
            units.append(("\n\n" if first else " ", sentence))
            first = False
    return units


def split_pages(
    pages: list[dict],
    *,
    target_chars: int = 1200,
    overlap: int = 150,
) -> list[dict]:
    """Split parsed pages into overlapping chunks (see module docstring).

    Each input row is ``{"page": int, "text": str}``; each output row is
    ``{"ordinal": int, "page": int | None, "text": str}`` with ordinals
    contiguous from 0 across all pages.
    """
    if target_chars < 1:
        raise ValueError("target_chars must be >= 1")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    overlap = min(overlap, target_chars - 1)  # a chunk must always host new content

    out: list[dict] = []

    for row in pages:
        raw_text = row.get("text")
        text = "" if raw_text is None else str(raw_text)
        if not text.strip():
            continue
        page = row.get("page")

        buf = ""             # chunk currently being filled (always <= target_chars)
        prefix_only = False  # True while buf holds only the carried overlap tail
        prev_chunk = ""      # last emitted chunk on this page (already stripped)

        def emit(chunk: str) -> None:
            nonlocal buf, prefix_only, prev_chunk
            chunk = chunk.strip()
            buf = ""
            prefix_only = False
            if not chunk:
                return
            out.append({"ordinal": len(out), "page": page, "text": chunk})
            prev_chunk = chunk

        def carry() -> None:
            """Start the next chunk with the overlap tail of the previous one."""
            nonlocal buf, prefix_only
            buf = prev_chunk[-overlap:] if overlap and prev_chunk else ""
            prefix_only = bool(buf)

        for sep, unit in _units(text, target_chars):
            cur_sep, cur = sep, unit
            while True:
                candidate = buf + cur_sep + cur if buf else cur
                if len(candidate) <= target_chars:
                    buf = candidate
                    prefix_only = False
                    break
                if buf and not prefix_only:
                    # Real accumulated content that no longer fits: close the
                    # chunk, open the next one with the overlap tail, retry.
                    emit(buf)
                    carry()
                    continue
                if prefix_only and len(cur) <= target_chars:
                    # Only the carried tail blocks this unit; the tail's text is
                    # fully inside the previous chunk, so drop it and keep the
                    # unit whole rather than hard-cutting a fitting paragraph.
                    buf = ""
                    prefix_only = False
                    continue
                # `cur` is an oversized sentence (longer than target_chars):
                # hard-cut it into pieces of at most target_chars.
                budget = target_chars - (len(buf) + len(cur_sep) if buf else 0)
                piece = cur[:budget]
                keep = piece.rstrip() or piece  # give trailing whitespace back to `cur`
                emit((buf + cur_sep + keep) if buf else keep)
                cur = cur[len(keep):]
                carry()
                cur_sep = ""  # continuation resumes exactly where the cut fell
        if buf:
            emit(buf)
        # No overlap carries across pages: prev_chunk restarts empty per page.

    return out
