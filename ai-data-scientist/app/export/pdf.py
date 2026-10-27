"""
A document as a PDF file, drawn with reportlab.

Fonts: DejaVu Sans, which ships with matplotlib, so accented letters, the minus sign and
arrows all print. reportlab's built-in Helvetica cannot show them.
"""
from __future__ import annotations

import io
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (HRFlowable, Image, KeepTogether, ListFlowable, ListItem,
                                Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from . import markdown as md

FONT_DIR = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
INK = colors.HexColor("#0b0b0b")
MUTED = colors.HexColor("#52514e")
LINE = colors.HexColor("#e1e0d9")
PANEL = colors.HexColor("#f3f4f6")
ACCENT = colors.HexColor("#2a78d6")
PAGE_W = A4[0] - 4 * cm        # usable width with 2 cm margins

_registered = False


def _fonts() -> None:
    global _registered
    if _registered:
        return
    pdfmetrics.registerFont(TTFont("Sans", str(FONT_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("Sans-Bold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("Sans-Italic", str(FONT_DIR / "DejaVuSans-Oblique.ttf")))
    pdfmetrics.registerFont(TTFont("Sans-BoldItalic", str(FONT_DIR / "DejaVuSans-BoldOblique.ttf")))
    pdfmetrics.registerFont(TTFont("Mono", str(FONT_DIR / "DejaVuSansMono.ttf")))
    pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="Sans-Bold", italic="Sans-Italic",
                                  boldItalic="Sans-BoldItalic")
    _registered = True


def _styles() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle("base", fontName="Sans", fontSize=10, leading=14, textColor=INK,
                          alignment=TA_LEFT, spaceAfter=6)
    return {
        "body": base,
        "title": ParagraphStyle("title", parent=base, fontName="Sans-Bold", fontSize=22,
                                leading=27, spaceAfter=4),
        "subtitle": ParagraphStyle("subtitle", parent=base, fontSize=10, textColor=MUTED,
                                   spaceAfter=14),
        "h1": ParagraphStyle("h1", parent=base, fontName="Sans-Bold", fontSize=16, leading=20,
                             spaceBefore=16, spaceAfter=8, textColor=INK),
        "h2": ParagraphStyle("h2", parent=base, fontName="Sans-Bold", fontSize=13, leading=17,
                             spaceBefore=12, spaceAfter=6),
        "h3": ParagraphStyle("h3", parent=base, fontName="Sans-Bold", fontSize=11, leading=15,
                             spaceBefore=10, spaceAfter=4),
        "question": ParagraphStyle("question", parent=base, fontName="Sans-Bold", fontSize=13,
                                   leading=17, spaceBefore=18, spaceAfter=8, textColor=ACCENT,
                                   borderPadding=(0, 0, 0, 6)),
        "quote": ParagraphStyle("quote", parent=base, leftIndent=12, textColor=MUTED,
                                fontName="Sans-Italic"),
        "code": ParagraphStyle("code", parent=base, fontName="Mono", fontSize=8, leading=10.5,
                               backColor=PANEL, borderPadding=6, leftIndent=4, spaceBefore=4,
                               spaceAfter=8),
        "cell": ParagraphStyle("cell", parent=base, fontSize=8.5, leading=11, spaceAfter=0),
        "cellhead": ParagraphStyle("cellhead", parent=base, fontName="Sans-Bold", fontSize=8.5,
                                   leading=11, spaceAfter=0),
        "caption": ParagraphStyle("caption", parent=base, fontSize=9, textColor=MUTED,
                                  spaceAfter=10),
        "footer": ParagraphStyle("footer", parent=base, fontSize=8.5, textColor=MUTED),
    }


def runs_xml(runs: list[dict]) -> str:
    """Runs as the small XML reportlab paragraphs understand."""
    parts = []
    for r in runs:
        t = escape(r["text"])
        if r.get("code"):
            t = f'<font face="Mono" size="8.5">{t}</font>'
        if r.get("bold"):
            t = f"<b>{t}</b>"
        if r.get("italic"):
            t = f"<i>{t}</i>"
        if r.get("link"):
            t = f'<link href="{escape(r["link"])}" color="#2a78d6">{t}</link>'
        parts.append(t)
    return "".join(parts) or " "


def _image(path: Path, title: str, st) -> list:
    try:
        from PIL import Image as PILImage
        with PILImage.open(path) as im:
            w, h = im.size
    except Exception:
        w, h = 1600, 1000
    width = min(PAGE_W, 15 * cm)
    height = width * h / w
    max_h = 17 * cm
    if height > max_h:
        width, height = width * max_h / height, max_h
    items = [Image(str(path), width=width, height=height)]
    if title:
        items.append(Paragraph(escape(title), st["caption"]))
    return [KeepTogether(items)]


def _table(block: dict, st) -> list:
    head = [Paragraph(runs_xml(c), st["cellhead"]) for c in block["head"]]
    rows = [[Paragraph(runs_xml(c), st["cell"]) for c in r] for r in block["rows"]]
    ncols = max(1, len(head))
    width = PAGE_W / ncols
    t = Table([head] + rows, colWidths=[width] * ncols, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PANEL),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, LINE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return [t, Spacer(1, 8)]


def _code(text: str, st) -> list:
    lines = []
    for line in text.splitlines() or [""]:
        lines += textwrap.wrap(line, 100, replace_whitespace=False, drop_whitespace=False) or [""]
    return [Preformatted("\n".join(lines[:200]), st["code"])]


def _list(block: dict, st) -> list:
    items = [ListItem(Paragraph(runs_xml(it["runs"]), st["body"]),
                      leftIndent=14 + 12 * it.get("level", 0), value=None)
             for it in block["items"]]
    kind = "1" if block.get("ordered") else "bullet"
    return [ListFlowable(items, bulletType=kind, start="•" if kind == "bullet" else None,
                         bulletFontName="Sans", bulletFontSize=9, leftIndent=14),
            Spacer(1, 4)]


def blocks_flowables(blocks: list[dict], images: dict[str, Path], st) -> list:
    out: list = []
    for b in blocks:
        kind = b["type"]
        if kind == "heading":
            out.append(Paragraph(runs_xml(b["runs"]), st["h%d" % min(max(b["level"], 1), 3)]))
        elif kind == "paragraph":
            out.append(Paragraph(runs_xml(b["runs"]), st["body"]))
        elif kind == "quote":
            out.append(Paragraph(runs_xml(b["runs"]), st["quote"]))
        elif kind == "list":
            out += _list(b, st)
        elif kind == "table":
            out += _table(b, st)
        elif kind == "code":
            out += _code(b["text"], st)
        elif kind == "rule":
            out.append(HRFlowable(width="100%", thickness=0.5, color=LINE, spaceBefore=6, spaceAfter=6))
        elif kind == "image":
            path = images.get(b["file"])
            if path:
                out += _image(path, b.get("title") or "", st)
            else:
                out.append(Paragraph(escape(f"[chart not available: {b['file']}]"), st["caption"]))
    return out


def render(doc: dict) -> bytes:
    """The document as PDF bytes."""
    _fonts()
    st = _styles()
    buf = io.BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm, title=doc["title"],
                            author="AI Data Scientist")
    story: list = [Paragraph(escape(doc["title"]), st["title"]),
                   Paragraph(escape(doc.get("subtitle", "")), st["subtitle"])]
    if doc.get("context"):
        for label, value in doc["context"]:
            story.append(Paragraph(f"<b>{escape(label)}.</b> {escape(value)}", st["body"]))
        story.append(Spacer(1, 6))
    if doc.get("datasets"):
        story.append(Paragraph("<b>Data.</b> " + "; ".join(
            f'{escape(d["name"])} ({d["rows"]:,} rows, {d["columns_count"]} columns)'
            for d in doc["datasets"]), st["body"]))
    story.append(HRFlowable(width="100%", thickness=0.8, color=LINE, spaceBefore=4, spaceAfter=10))

    for i, section in enumerate(doc["sections"]):
        if section.get("heading"):
            story.append(Paragraph(escape(section["heading"]), st["question"]))
        story += blocks_flowables(section["blocks"], doc.get("images", {}), st)
        if i < len(doc["sections"]) - 1:
            story.append(Spacer(1, 10))

    footer = doc.get("footer", "")

    def page(canvas, document):
        canvas.saveState()
        canvas.setFont("Sans", 8.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(2 * cm, 1.2 * cm, footer[:110])
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {document.page}")
        canvas.restoreState()

    pdf.build(story, onFirstPage=page, onLaterPages=page)
    return buf.getvalue()

