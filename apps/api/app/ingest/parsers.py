"""Document parsers: pure text extraction, no database access.

Every parser takes a ``pathlib.Path`` and returns ``list[dict]`` of
``{"page": int, "text": str}`` with 1-based page numbers. ``parse_any``
dispatches on the file suffix and additionally reports the detected media
type. PyMuPDF (``fitz``) is banned by the project contract — PDF extraction
here goes through pypdfium2, with pdfplumber and rapidocr-onnxruntime as
per-page fallbacks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

# A page whose pypdfium2 text is shorter than this is treated as (likely)
# scanned/image-only and triggers the fallback chain.
_MIN_PDF_CHARS = 20

# Lazily constructed once per process; OCR model load is expensive.
_OCR_ENGINE = None


def _pdf_page_text_pypdfium2(page) -> str:
    """First-choice extraction for one open pypdfium2 page."""
    textpage = page.get_textpage()
    try:
        return textpage.get_text_range() or ""
    finally:
        textpage.close()


def _pdf_page_text_pdfplumber(pdf_path: Path, page_index: int) -> str:
    """Fallback extraction for a single page via pdfplumber."""
    import pdfplumber

    with pdfplumber.open(str(pdf_path)) as pdf:
        return (pdf.pages[page_index].extract_text() or "").strip()


def _pdf_page_text_ocr(page) -> str:
    """Last-resort extraction: render the page, then run rapidocr-onnxruntime.

    Raises ImportError when rapidocr is not installed so the caller can fall
    through to the placeholder marker.
    """
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR

    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        _OCR_ENGINE = RapidOCR()

    bitmap = page.render(scale=2.0)
    image = bitmap.to_pil()
    result, _elapse = _OCR_ENGINE(np.array(image))
    if not result:
        return ""
    # rapidocr yields [box, text, confidence] triples in reading order.
    return "\n".join(str(line[1]) for line in result if line and line[1])


def parse_pdf(path: Path) -> list[dict]:
    """Extract one entry per PDF page.

    Per page: pypdfium2 text; if under ``_MIN_PDF_CHARS`` characters, retry
    that page with pdfplumber; if still empty, try rapidocr-onnxruntime on a
    rendered bitmap; otherwise mark the page ``"[no extractable text]"``.
    Every fallback is guarded — a failure on one page never kills the run.
    """
    import pypdfium2 as pdfium

    pages: list[dict] = []
    doc = pdfium.PdfDocument(str(path))
    try:
        for index in range(len(doc)):
            text = ""
            try:
                page = doc[index]
                text = _pdf_page_text_pypdfium2(page).strip()
                if len(text) < _MIN_PDF_CHARS:
                    try:
                        alt = _pdf_page_text_pdfplumber(Path(path), index)
                        if alt:
                            text = alt
                    except Exception:
                        pass
                if not text:
                    try:
                        text = _pdf_page_text_ocr(page)
                    except ImportError:
                        text = ""
                    except Exception:
                        text = ""
            except Exception:
                # pypdfium2 itself failed on this page — keep the slot.
                text = ""
            if not text.strip():
                text = "[no extractable text]"
            pages.append({"page": index + 1, "text": text})
    finally:
        doc.close()
    return pages


def parse_xlsx(path: Path) -> list[dict]:
    """One page per worksheet, stat.gov workbook shape.

    Merged ranges are unmerged and the top-left value is propagated across
    the whole range *before* reading cells (openpyxl stores None elsewhere in
    a merge). Rows render as tab-separated lines; fully-empty rows are
    skipped.
    """
    import openpyxl

    wb = openpyxl.load_workbook(str(path), data_only=True, read_only=False)
    pages: list[dict] = []
    try:
        for sheet_index, ws in enumerate(wb.worksheets):
            # Fill merged regions with their anchor value, then unmerge so
            # iter_rows() sees the propagated values.
            for merged in list(ws.merged_cells.ranges):
                min_col, min_row, max_col, max_row = merged.bounds
                top_left = ws.cell(row=min_row, column=min_col).value
                ws.unmerge_cells(str(merged))
                for row in range(min_row, max_row + 1):
                    for col in range(min_col, max_col + 1):
                        ws.cell(row=row, column=col).value = top_left
            lines: list[str] = []
            for row in ws.iter_rows(values_only=True):
                cells = [
                    "" if value is None else str(value).strip() for value in row
                ]
                if not any(cells):
                    continue  # fully-empty row
                lines.append("\t".join(cells).rstrip("\t"))
            pages.append({"page": sheet_index + 1, "text": "\n".join(lines)})
    finally:
        wb.close()
    return pages


def parse_csv(path: Path) -> list[dict]:
    """Detect the encoding with charset_normalizer, read with pandas, render
    header + rows as tab-separated lines, all in a single page."""
    import pandas as pd
    from charset_normalizer import from_path

    best = from_path(str(path)).best()
    encoding = str(best.encoding) if best else "utf-8"
    frame = pd.read_csv(str(path), sep=",", encoding=encoding, dtype=str, keep_default_na=False)
    lines = ["\t".join(str(col) for col in frame.columns)]
    for row in frame.itertuples(index=False, name=None):
        lines.append("\t".join(str(value) for value in row))
    return [{"page": 1, "text": "\n".join(lines)}]


def parse_docx(path: Path) -> list[dict]:
    """Paragraphs and tables in document-body order.

    Page numbering choice: each top-level block (one paragraph, or one table)
    becomes its own sequential page — page N is the Nth block of content.
    This keeps ordering trivially correct and gives chunking page-level
    granularity without attempting to model real Word pagination, which
    python-docx cannot compute. Tables render as tab-separated rows.
    """
    import docx
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = docx.Document(str(path))
    pages: list[dict] = []
    number = 0
    for child in document.element.body:
        if isinstance(child, CT_P):
            text = Paragraph(child, document).text.strip()
            if not text:
                continue  # empty spacer paragraph
            number += 1
            pages.append({"page": number, "text": text})
        elif isinstance(child, CT_Tbl):
            table = Table(child, document)
            lines = []
            for row in table.rows:
                lines.append("\t".join(cell.text.strip() for cell in row.cells))
            number += 1
            pages.append({"page": number, "text": "\n".join(lines)})
        # Anything else in the body (sectPr, etc.) carries no text.
    if not pages:
        pages.append({"page": 1, "text": ""})
    return pages


def parse_txt(path: Path) -> list[dict]:
    """Plain text, utf-8 with errors="replace", one page."""
    return [{"page": 1, "text": path.read_text(encoding="utf-8", errors="replace")}]


_PARSERS: dict[str, tuple[Callable[[Path], list[dict]], str]] = {
    ".pdf": (parse_pdf, "application/pdf"),
    ".docx": (
        parse_docx,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    ".xlsx": (
        parse_xlsx,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    ".csv": (parse_csv, "text/csv"),
    ".txt": (parse_txt, "text/plain"),
}


def parse_any(path: Path) -> tuple[list[dict], str]:
    """Dispatch on suffix; returns (pages, media_type). Raises ValueError for
    unsupported suffixes, naming the supported ones."""
    suffix = Path(path).suffix.lower()
    entry = _PARSERS.get(suffix)
    if entry is None:
        raise ValueError(
            f"Unsupported file suffix {suffix!r}; supported: "
            f"{', '.join(sorted(_PARSERS))}"
        )
    parser, media_type = entry
    return parser(Path(path)), media_type


def supported_suffixes() -> set[str]:
    """Exactly the suffixes ``parse_any`` accepts."""
    return set(_PARSERS)
