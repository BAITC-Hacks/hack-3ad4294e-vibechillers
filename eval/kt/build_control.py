"""Build source-first synthetic controls. No product inference or gold generation.

Use bundled Python (python-docx, reportlab) and Node (@oai/artifact-tool).
The checked-in TXT files are authoritative; formatting never changes their text.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / "seeds/kt/eval/control"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_inputs(dest: Path) -> None:
    """Measure public ingestion only, keeping semantic expectations separate."""
    sys.path.insert(0, str(ROOT / "apps/api"))
    from app.ingest.parsers import parse_any
    from app.audit.parser import parse_clauses, extract_units

    normalize = lambda text: re.sub(r"\s+", " ", text).strip()
    rows = []
    for edition in ("before", "after"):
        canonical = (dest / f"{edition}.txt").read_text(encoding="utf-8")
        expected, _ = parse_clauses(edition, [{"page": 1, "text": canonical}])
        expected = {c.clause_id: c.text for c in expected if c.label}
        for suffix in ("txt", "docx", "pdf", "xlsx"):
            path = dest / f"{edition}.{suffix}"
            if not path.exists():
                continue
            pages, _ = parse_any(path)
            clauses, warnings = parse_clauses(edition, pages)
            units = extract_units(edition, clauses)
            mismatches = [c.clause_id for c in clauses if c.clause_id in expected
                          and normalize(c.text) != normalize(expected[c.clause_id])]
            rows.append({"file": path.name, "sha256": digest(path), "pages_or_blocks": len(pages),
                         "clauses": len(clauses), "units": len(units),
                         "numbered_clause_denominator": len(expected),
                         "numbered_clause_text_mismatches": mismatches,
                         "normalized_extracted_text_matches_canonical":
                             normalize(" ".join(p["text"] for p in pages)) == normalize(canonical),
                         "warnings": warnings})
    record = {"scope": "Source ingestion only. No audit inference or product accuracy claim.",
              "parser_sha256": digest(ROOT / "apps/api/app/audit/parser.py"),
              "ingest_parsers_sha256": digest(ROOT / "apps/api/app/ingest/parsers.py"),
              "formats": rows}
    (dest / "format-qa.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verified_files": len(rows), "qa_record": str(dest / "format-qa.json")}))


def build_docx(lines: list[str], target: Path) -> None:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from datetime import datetime

    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    section.top_margin = section.bottom_margin = Inches(0.65)
    section.left_margin = section.right_margin = Inches(0.7)
    for name in ("Normal", "Title", "Heading 1"):
        style = doc.styles[name]
        style.font.name = "Arial"
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.font.size = Pt(11 if name == "Normal" else 16 if name == "Title" else 12)
        style.paragraph_format.space_after = Pt(6)
    doc.core_properties.title = lines[0]
    doc.core_properties.author = "Alibi synthetic evaluation"
    doc.core_properties.created = doc.core_properties.modified = datetime(2026, 9, 23)
    for n, line in enumerate(lines):
        style = "Title" if n == 0 else "Heading 1" if re.match(r"^\d+\. ", line) else None
        p = doc.add_paragraph(line, style)
        p.paragraph_format.keep_together = True
    doc.save(target)


def build_pdf(lines: list[str], target: Path, font: Path) -> None:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen.canvas import Canvas

    pdfmetrics.registerFont(TTFont("ControlFont", str(font)))
    normal = ParagraphStyle("Body", fontName="ControlFont", fontSize=11, leading=15, spaceAfter=6)
    heading = ParagraphStyle("Heading", parent=normal, fontSize=12, leading=16, spaceBefore=6, keepWithNext=True)
    title = ParagraphStyle("Title", parent=normal, fontSize=16, leading=21, spaceAfter=12, keepWithNext=True)
    flow = []
    for n, line in enumerate(lines):
        style = title if n == 0 else heading if re.match(r"^\d+\. ", line) else normal
        flow.append(Paragraph(escape(line), style))
    doc = SimpleDocTemplate(str(target), pagesize=letter, leftMargin=50, rightMargin=50,
                            topMargin=46, bottomMargin=46, title=lines[0], author="Alibi synthetic evaluation")
    def invariant_canvas(*a, **kw):
        kw["invariant"] = 1
        return Canvas(*a, **kw)
    doc.build(flow, canvasmaker=invariant_canvas)


XLSX_JS = r'''
import fs from "node:fs/promises";
import { pathToFileURL } from "node:url";
const [modulePath, dir, qaDir] = process.argv.slice(2);
const { Workbook, SpreadsheetFile } = await import(pathToFileURL(modulePath).href);
for (const edition of ["before", "after"]) {
  const lines = (await fs.readFile(`${dir}/${edition}.txt`, "utf8")).trim().split(/\r?\n/);
  const wb = Workbook.create();
  const sheet = wb.worksheets.add("Приложение");
  sheet.showGridLines = false;
  sheet.getRange(`A1:A${lines.length}`).values = lines.map(x => [x]);
  const all = sheet.getRange(`A1:A${lines.length}`);
  all.format.font = { name: "Arial", size: 11, color: "#000000" };
  all.format.columnWidth = 110;
  all.format.wrapText = true;
  all.format.verticalAlignment = "center";
  for (let i = 0; i < lines.length; i++) {
    const row = sheet.getRange(`A${i + 1}`);
    row.format.rowHeight = Math.max(25, Math.ceil(lines[i].length / 90) * 17 + 10);
    if (i === 0 || /^\d+\. /.test(lines[i])) {
      row.format.font = {name: "Arial", size: i === 0 ? 15 : 12, bold: true, color: "#000000"};
      row.format.rowHeight = Math.max(i === 0 ? 42 : 30, Math.ceil(lines[i].length / 90) * 19 + 10);
    }
  }
  sheet.freezePanes.freezeRows(2);
  wb.recalculate();
  console.log((await wb.inspect({kind: "table", range: `Приложение!A1:A${lines.length}`, include: "values,formulas", tableMaxRows: 3, tableMaxCols: 1, maxChars: 600})).ndjson);
  const preview = await wb.render({sheetName: "Приложение", range: `A1:A${lines.length}`, scale: 1, format: "png"});
  await fs.writeFile(`${qaDir}/${edition}-xlsx.png`, new Uint8Array(await preview.arrayBuffer()));
  await (await SpreadsheetFile.exportXlsx(wb)).save(`${dir}/${edition}.xlsx`);
  try { await fs.rename(`${dir}/${edition}.xlsx.inspect.ndjson`, `${qaDir}/${edition}.xlsx.inspect.ndjson`); } catch {}
}
'''

TABLE_PROBE_JS = r'''
import fs from "node:fs/promises";
import { pathToFileURL } from "node:url";
const [modulePath, dir, qaDir] = process.argv.slice(2);
const { Workbook, SpreadsheetFile } = await import(pathToFileURL(modulePath).href);
for (const edition of ["before", "after"]) {
  const lines = (await fs.readFile(`${dir}/${edition}.txt`, "utf8")).trim().split(/\r?\n/);
  const boundary = lines.findIndex(line => /^2\. /.test(line));
  const wb = Workbook.create();
  for (const [name, source] of [["Структура", lines.slice(2, boundary)], ["Функции", lines.slice(boundary)]]) {
    const sheet = wb.worksheets.add(name);
    sheet.showGridLines = false;
    sheet.getRange("A1:C1").values = [["Пункт", "Подразделение", "Функция/основание"]];
    let unit = "";
    const rows = source.map(line => {
      const match = line.match(/^([\dа-я]+(?:\.\d+)*\.)\s+(.*)$/u);
      const marker = match ? match[1] : "";
      const body = match ? match[2] : line;
      if (/^\d+\.$/.test(marker)) unit = /^[А-ЯЁ]{2,6}$/.test(body) ? body : "";
      return [marker, unit, body];
    });
    sheet.getRange(`A2:C${rows.length + 1}`).values = rows;
    const all = sheet.getRange(`A1:C${rows.length + 1}`);
    all.format.font = {name: "Arial", size: 11, color: "#000000"};
    all.format.wrapText = true;
    all.format.verticalAlignment = "center";
    sheet.getRange(`A1:A${rows.length + 1}`).format.columnWidth = 11;
    sheet.getRange(`B1:B${rows.length + 1}`).format.columnWidth = 20;
    sheet.getRange(`C1:C${rows.length + 1}`).format.columnWidth = 100;
    sheet.getRange("A1:C1").format = {fill: "#23425E", font: {name: "Arial", size: 11, bold: true, color: "#FFFFFF"}, rowHeight: 30};
    rows.forEach((row, i) => { sheet.getRange(`A${i + 2}:C${i + 2}`).format.rowHeight = Math.max(28, Math.ceil(row[2].length / 82) * 17 + 12); });
    sheet.freezePanes.freezeRows(1);
  }
  wb.recalculate();
  for (const name of ["Структура", "Функции"]) {
    const preview = await wb.render({sheetName: name, autoCrop: "all", scale: 1, format: "png"});
    await fs.writeFile(`${qaDir}/${edition}-table-${name}.png`, new Uint8Array(await preview.arrayBuffer()));
  }
  await (await SpreadsheetFile.exportXlsx(wb)).save(`${dir}/${edition}-table.xlsx`);
  try { await fs.rename(`${dir}/${edition}-table.xlsx.inspect.ndjson`, `${qaDir}/${edition}-table.xlsx.inspect.ndjson`); } catch {}
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT)
    parser.add_argument("--formats", nargs="+", choices=["docx", "pdf", "xlsx"], default=[])
    parser.add_argument("--font", type=Path, default=Path("C:/Windows/Fonts/arial.ttf"))
    parser.add_argument("--node", default="node")
    parser.add_argument("--artifact-module", type=Path,
                        help="Absolute entrypoint for bundled @oai/artifact-tool")
    parser.add_argument("--qa-dir", type=Path,
                        default=Path(tempfile.gettempdir()) / "kt-control-format-qa")
    parser.add_argument("--verify-inputs", action="store_true", help="Public ingestion check; does not run audit inference")
    parser.add_argument("--auxiliary-tables", action="store_true",
                        help="Build separate 3-column / 2-sheet XLSX probes; leave pinned inputs and main manifest unchanged")
    args = parser.parse_args()
    dest = args.directory.resolve()
    args.qa_dir.mkdir(parents=True, exist_ok=True)
    if args.auxiliary_tables:
        if not args.artifact_module:
            parser.error("--artifact-module is required for auxiliary tables")
        script = args.qa_dir / "build_table_probe.mjs"
        script.write_text(TABLE_PROBE_JS, encoding="utf-8")
        subprocess.run([args.node, str(script), str(args.artifact_module.resolve()), str(dest), str(args.qa_dir)], check=True)
        auxiliary = {"bundle_id": "kt-stage3-synthetic-table-probe-v1", "auxiliary": True,
                     "provenance": "synthetic tables derived from canonical control TXT; not organiser data",
                     "expectations_status": "unlabelled_format_probe", "files": []}
        for edition in ("before", "after"):
            path = dest / f"{edition}-table.xlsx"
            auxiliary["files"].append({"path": path.name, "edition": edition, "auxiliary": True,
                                      "sha256": digest(path), "bytes": path.stat().st_size,
                                      "canonical": f"{edition}.txt", "canonical_sha256": digest(dest / f"{edition}.txt")})
        (dest / "table-probe-manifest.json").write_text(json.dumps(auxiliary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("Built auxiliary table probes; pinned manifest and original 8 input files unchanged.")
        return
    for edition in ("before", "after"):
        lines = (dest / f"{edition}.txt").read_text(encoding="utf-8").splitlines()
        if "docx" in args.formats:
            build_docx(lines, dest / f"{edition}.docx")
        if "pdf" in args.formats:
            build_pdf(lines, dest / f"{edition}.pdf", args.font)
    if "xlsx" in args.formats:
        if not args.artifact_module:
            parser.error("--artifact-module is required for xlsx generation")
        script = args.qa_dir / "build_xlsx.mjs"
        script.write_text(XLSX_JS, encoding="utf-8")
        subprocess.run([args.node, str(script), str(args.artifact_module.resolve()), str(dest), str(args.qa_dir)], check=True)
    files = []
    for edition in ("before", "after"):
        canonical = dest / f"{edition}.txt"
        for suffix in ("txt", "docx", "pdf", "xlsx"):
            path = dest / f"{edition}.{suffix}"
            if path.exists():
                files.append({"path": path.name, "edition": edition, "format": suffix,
                              "sha256": digest(path), "bytes": path.stat().st_size,
                              "canonical": canonical.name, "canonical_sha256": digest(canonical)})
    manifest = {"schema_version": 1, "bundle_id": "kt-stage3-synthetic-control-v1",
                "created_date": "2026-09-23", "provenance": "synthetic_author_constructed",
                "author": "Alibi evaluation session", "organiser_supplied": False,
                "split": "development", "expectations_status": "pending_human",
                "expectations": "expectations.preliminary.md", "source_first": True,
                "expectations_sha256": digest(dest / "expectations.preliminary.md"),
                "files": files,
                "usage": "Choose exactly one representation per edition; do not upload equivalent formats together.",
                "rebuild": "TXT is authoritative; preserve recorded binary bytes for paired runs. Regeneration may change container metadata; refresh and record hashes."}
    (dest / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"files": len(files), "manifest": str(dest / "manifest.json"), "qa": str(args.qa_dir)}))
    if args.verify_inputs:
        verify_inputs(dest)


if __name__ == "__main__":
    main()
