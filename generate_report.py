"""Generate a comprehensive PDF report of the mcat codebase."""
import os
import ast
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    Preformatted
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


ROOT = Path(__file__).parent.resolve()
OUTPUT = ROOT / "mcat_codebase_report.pdf"
NOW = datetime.now().strftime("%Y-%m-%d %H:%M")


FILES = [
    ("Entry Point", [
        ROOT / "mcat.py",
    ]),
    ("Core Library", [
        ROOT / "cat_tool" / "__init__.py",
        ROOT / "cat_tool" / "ui.py",
        ROOT / "cat_tool" / "tm.py",
        ROOT / "cat_tool" / "glossary.py",
        ROOT / "cat_tool" / "segmentation.py",
        ROOT / "cat_tool" / "suggest.py",
        ROOT / "cat_tool" / "spellcheck.py",
        ROOT / "cat_tool" / "qa.py",
        ROOT / "cat_tool" / "settings.py",
        ROOT / "cat_tool" / "project.py",
        ROOT / "cat_tool" / "file_handler.py",
        ROOT / "cat_tool" / "mcat_format_manager.py",
        ROOT / "cat_tool" / "state_manager.py",
        ROOT / "cat_tool" / "workers.py",
    ]),
    ("Format Handlers", [
        ROOT / "cat_tool" / "formats" / "__init__.py",
        ROOT / "cat_tool" / "formats" / "factory.py",
        ROOT / "cat_tool" / "formats" / "_text_base.py",
        ROOT / "cat_tool" / "formats" / "tag_utils.py",
        ROOT / "cat_tool" / "formats" / "text.py",
        ROOT / "cat_tool" / "formats" / "pdf.py",
        ROOT / "cat_tool" / "formats" / "docx.py",
        ROOT / "cat_tool" / "formats" / "pptx.py",
        ROOT / "cat_tool" / "formats" / "xlsx.py",
        ROOT / "cat_tool" / "formats" / "xls.py",
        ROOT / "cat_tool" / "formats" / "odf.py",
        ROOT / "cat_tool" / "formats" / "mqxliif.py",
        ROOT / "cat_tool" / "formats" / "sdlxliff.py",
        ROOT / "cat_tool" / "formats" / "mcatdb.py",
    ]),
    ("Tests", [
        ROOT / "tests" / "test_cat_logic.py",
        ROOT / "tests" / "test_comprehensive.py",
        ROOT / "tests" / "test_remaining.py",
        ROOT / "tests" / "test_more.py",
    ]),
]


def try_register_fonts():
    fonts = [
        ("CourierNew", "C:\\Windows\\Fonts\\cour.ttf"),
        ("CourierNew-Bold", "C:\\Windows\\Fonts\\courbd.ttf"),
        ("CourierNew-BoldOblique", "C:\\Windows\\Fonts\\courbi.ttf"),
        ("CourierNew-Oblique", "C:\\Windows\\Fonts\\couri.ttf"),
    ]
    registered = {}
    for name, path in fonts:
        p = Path(path)
        if p.exists():
            try:
                pdfmetrics.registerFont(TTFont(name, str(p)))
                registered[name] = name
            except Exception:
                pass
    if "CourierNew" in registered:
        return "CourierNew"
    return None


MONO_FONT = try_register_fonts() or "Courier"

styles = getSampleStyleSheet()

styles.add(ParagraphStyle(
    name='CoverTitle', fontName='Helvetica-Bold', fontSize=28,
    textColor=HexColor('#1a1a2e'), alignment=TA_CENTER, spaceAfter=12))
styles.add(ParagraphStyle(
    name='CoverSubtitle', fontName='Helvetica', fontSize=16,
    textColor=HexColor('#555555'), alignment=TA_CENTER, spaceAfter=6))
styles.add(ParagraphStyle(
    name='SectionTitle', fontName='Helvetica-Bold', fontSize=18,
    textColor=HexColor('#1a1a2e'), spaceBefore=24, spaceAfter=12,
    borderPadding=(0, 0, 4, 0)))
styles.add(ParagraphStyle(
    name='SubSectionTitle', fontName='Helvetica-Bold', fontSize=14,
    textColor=HexColor('#2d3436'), spaceBefore=16, spaceAfter=8))
styles.add(ParagraphStyle(
    name='FileHeading', fontName='Helvetica-Bold', fontSize=12,
    textColor=HexColor('#0984e3'), spaceBefore=12, spaceAfter=4))
styles.add(ParagraphStyle(
    name='StatsText', fontName='Helvetica', fontSize=10,
    textColor=HexColor('#333333'), spaceAfter=2, leading=14))
styles.add(ParagraphStyle(
    name='CodeStyle', fontName=MONO_FONT, fontSize=6.5, leading=8.5,
    textColor=HexColor('#2d3436'), leftIndent=4, spaceBefore=0, spaceAfter=0,
    backColor=HexColor('#f8f9fa'), borderPadding=4))
styles.add(ParagraphStyle(
    name='TOCEntry', fontName='Helvetica', fontSize=10, leading=18,
    textColor=HexColor('#333333'), leftIndent=12))
styles.add(ParagraphStyle(
    name='TOCHeading', fontName='Helvetica-Bold', fontSize=14,
    textColor=HexColor('#1a1a2e'), spaceBefore=16, spaceAfter=12))
styles.add(ParagraphStyle(
    name='FooterStyle', fontName='Helvetica', fontSize=8,
    textColor=HexColor('#999999'), alignment=TA_CENTER))


def get_class_info(filepath):
    """Parse Python source to extract class/function definitions."""
    try:
        with open(filepath, encoding='utf-8') as f:
            tree = ast.parse(f.read())
    except Exception:
        return [], []
    classes = []
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = [ast.dump(b) for b in node.bases]
            classes.append((node.name, node.lineno))
        elif isinstance(node, ast.FunctionDef):
            functions.append((node.name, node.lineno))
    return classes, functions


def read_file_content(filepath):
    try:
        with open(filepath, encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"# Error reading {filepath}: {e}"


def escape_for_pdf(text):
    """Escape special XML characters for PDF."""
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text


def footer(canvas_obj, doc):
    canvas_obj.setFont('Helvetica', 8)
    canvas_obj.setFillColor(HexColor('#999999'))
    canvas_obj.drawCentredString(
        letter[0] / 2, 0.5 * inch,
        f"mcat v1.0 Codebase Report  |  Page {doc.page}  |  Generated {NOW}"
    )


def build():
    print("Building comprehensive PDF report...")

    total_lines = 0
    file_stats = []
    for category, files in FILES:
        for fp in files:
            if fp.exists():
                content = read_file_content(fp)
                lines = content.count('\n')
                total_lines += lines
                classes, funcs = get_class_info(fp)
                file_stats.append((category, fp, lines, classes, funcs))
            else:
                print(f"  WARNING: {fp} not found")

    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=letter,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
    )

    story = []
    w = letter[0] - 1.5 * inch  # usable width

    # ===== COVER PAGE =====
    story.append(Spacer(1, 2 * inch))
    story.append(Paragraph("mcat", styles['CoverTitle']))
    story.append(Paragraph("Computer-Assisted Translation Tool", styles['CoverSubtitle']))
    story.append(Paragraph("Version 1.0", styles['CoverSubtitle']))
    story.append(Spacer(1, 0.5 * inch))
    story.append(Paragraph("Codebase Comprehensive Report", styles['CoverSubtitle']))
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(f"Generated: {NOW}", styles['CoverSubtitle']))
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(f"Total: {total_lines} lines across {len(file_stats)} Python files", styles['CoverSubtitle']))
    story.append(Spacer(1, 2 * inch))
    story.append(Paragraph("Repository: https://github.com/skarmohdi2006/mcat", styles['CoverSubtitle']))
    story.append(PageBreak())

    # ===== TABLE OF CONTENTS =====
    story.append(Paragraph("Table of Contents", styles['SectionTitle']))
    story.append(Spacer(1, 0.2 * inch))

    toc_items = [
        ("1", "Overview & Statistics"),
        ("2", "Entry Point"),
        ("3", "Core Library Modules"),
        ("4", "Format Handlers"),
        ("5", "Test Suites"),
    ]
    for num, title in toc_items:
        story.append(Paragraph(f"<b>{num}.</b>  {title}", styles['TOCEntry']))

    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph("Files (alphabetical within each category):", styles['TOCEntry']))
    for cat, fp, lines, classes, funcs in file_stats:
        rel = os.path.relpath(fp, ROOT)
        story.append(Paragraph(f"&bull;  {rel}  ({lines} lines)", styles['TOCEntry']))

    story.append(PageBreak())

    # ===== OVERVIEW =====
    story.append(Paragraph("1. Overview &amp; Statistics", styles['SectionTitle']))
    story.append(Spacer(1, 0.15 * inch))

    total_classes = sum(len(c) for _, _, _, c, _ in file_stats)
    total_funcs = sum(len(f) for _, _, _, _, f in file_stats)

    core_count = len([s for s in file_stats if s[0] == "Core Library"])
    format_count = len([s for s in file_stats if s[0] == "Format Handlers"])
    test_count = len([s for s in file_stats if s[0] == "Tests"])

    overview_data = [
        ["Metric", "Value"],
        ["Total Python Files", str(len(file_stats))],
        ["Total Lines of Code", str(total_lines)],
        ["Total Classes Defined", str(total_classes)],
        ["Total Functions Defined", str(total_funcs)],
        ["Core Library Modules", str(core_count)],
        ["Format Handlers", str(format_count)],
        ["Test Files", str(test_count)],
        ["Lines per File (avg)", f"{total_lines // max(len(file_stats), 1)}"],
        ["GUI Framework", "PyQt5"],
        ["Database Engine", "SQLite3 + sqlite-vec"],
        ["Fuzzy Matching", "rapidfuzz"],
        ["Embedding Models", "fastembed (sentence-transformers)"],
        ["Spell Checking", "spylls (Hunspell)"],
    ]
    t = Table(overview_data, colWidths=[2.2 * inch, 3.8 * inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#dfe6e9')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#f8f9fa')]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3 * inch))

    # Supported formats
    story.append(Paragraph("Supported File Formats", styles['SubSectionTitle']))
    formats = [
        ("Format", "Handler Class", "Libraries Used"),
        ("Plain Text (.txt)", "TextHandler", "builtins"),
        ("PDF (.pdf)", "PdfHandler", "pdfplumber, pypdf, reportlab"),
        ("Word (.docx)", "DocxHandler", "python-docx"),
        ("PowerPoint (.pptx/.ppsx)", "PptxHandler", "python-pptx"),
        ("Excel (.xlsx)", "XlsxHandler", "openpyxl"),
        ("Excel (.xls)", "XlsHandler", "xlrd, xlutils"),
        ("OpenDocument (.odt/.ods/.odp)", "OdfHandler", "odfpy"),
        ("memoQ XLIFF (.mqxliff)", "MqxliffHandler", "xml.etree"),
        ("SDL Trados XLIFF (.sdlxliff)", "SdlxliffHandler", "xml.etree"),
        ("Native MCAT (.mcat.db)", "McatDbHandler", "sqlite3"),
        ("PO / XLIFF / TMX / TBX / CSV", "FactoryHandler", "translate-toolkit"),
    ]
    t2 = Table(formats, colWidths=[2.0 * inch, 2.0 * inch, 2.2 * inch])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#0984e3')),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#dfe6e9')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#f8f9fa')]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t2)
    story.append(PageBreak())

    # ===== FILE LISTINGS =====
    page_num = 5  # rough tracking

    for cat_idx, (category, files) in enumerate(FILES):
        section_num = cat_idx + 2
        story.append(Paragraph(f"{section_num}. {category}", styles['SectionTitle']))
        story.append(Spacer(1, 0.1 * inch))

        for fp in files:
            if not fp.exists():
                continue
            rel = os.path.relpath(fp, ROOT)
            content = read_file_content(fp)
            lines = content.count('\n')
            classes, funcs = get_class_info(fp)

            story.append(Paragraph(f"<b>{rel}</b>  &mdash;  {lines} lines", styles['FileHeading']))

            if classes or funcs:
                info_lines = []
                if classes:
                    for cname, lineno in classes:
                        info_lines.append(f"  &bull; Class <b>{cname}</b> (line {lineno})")
                if funcs:
                    for fname, lineno in funcs:
                        info_lines.append(f"  &bull; Function <b>{fname}</b> (line {lineno})")
                story.append(Paragraph("<br/>".join(info_lines), ParagraphStyle(
                    'FileInfo', parent=styles['StatsText'], fontSize=8, leading=12)))
                story.append(Spacer(1, 4))

            # Code listing
            escaped = escape_for_pdf(content)
            code = Preformatted(escaped, styles['CodeStyle'])
            story.append(code)
            story.append(Spacer(1, 0.15 * inch))

        story.append(PageBreak())

    # ===== BUILD PDF =====
    print(f"Building PDF with {len(story)} flowables...")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"Report generated: {OUTPUT}")
    print(f"  Total lines in report generation: {sum(s.count('\\n') for s in [read_file_content(fp) for _, files in FILES for fp in files if fp.exists()])}")
    return OUTPUT


if __name__ == '__main__':
    build()
