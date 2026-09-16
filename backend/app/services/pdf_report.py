"""Shared ReportLab document builder for Kuantra PDF reports.

The renderer is deliberately small: one font pair (vendored Bitstream Vera Sans,
which covers Turkish), headings, paragraphs, repeating table headers, numbered
pages and a footer.  No images, no external resources, no network access.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable, Sequence
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
REGULAR_FONT = "KuantraSans"
BOLD_FONT = "KuantraSans-Bold"

_registered = False


def register_report_fonts() -> None:
    """Register the vendored fonts once per process."""

    global _registered
    if _registered:
        return
    pdfmetrics.registerFont(TTFont(REGULAR_FONT, str(FONT_DIR / "Vera.ttf")))
    pdfmetrics.registerFont(TTFont(BOLD_FONT, str(FONT_DIR / "VeraBd.ttf")))
    pdfmetrics.registerFontFamily(REGULAR_FONT, normal=REGULAR_FONT, bold=BOLD_FONT)
    _registered = True


@dataclass(frozen=True)
class TableBlock:
    headers: Sequence[str]
    rows: Sequence[Sequence[str]]
    widths: Sequence[float] | None = None
    font_size: float = 8.5


class _NumberedCanvas:
    """Canvas proxy that draws the footer with the final page count."""

    def __init__(self, *args, footer_text: str = "", page_word: str = "", **kwargs):
        from reportlab.pdfgen import canvas as _canvas

        self._canvas = _canvas.Canvas(*args, **kwargs)
        self._footer_text = footer_text
        self._page_word = page_word
        self._saved_states: list[dict[str, Any]] = []

    def __getattr__(self, name: str) -> Any:
        return getattr(self._canvas, name)

    def showPage(self) -> None:
        self._saved_states.append(dict(self._canvas.__dict__))
        self._canvas._startPage()

    def save(self) -> None:
        total = len(self._saved_states)
        for index, state in enumerate(self._saved_states, start=1):
            self._canvas.__dict__.update(state)
            self._draw_footer(index, total)
            self._canvas.showPage()
        self._canvas.save()

    def _draw_footer(self, number: int, total: int) -> None:
        self._canvas.saveState()
        self._canvas.setFont(REGULAR_FONT, 7.5)
        self._canvas.setFillColor(colors.HexColor("#555555"))
        width, _ = A4
        label = f"{self._page_word} {number} / {total}".strip()
        self._canvas.drawRightString(width - 1.6 * cm, 1.1 * cm, label)
        if self._footer_text:
            text = self._footer_text
            if len(text) > 95:
                text = text[:94] + "…"
            self._canvas.drawString(1.6 * cm, 1.1 * cm, text)
        self._canvas.restoreState()


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "KuantraTitle", parent=base["Title"], fontName=BOLD_FONT, fontSize=15,
            leading=19, alignment=TA_LEFT, spaceAfter=6, textColor=colors.HexColor("#111827"),
        ),
        "meta": ParagraphStyle(
            "KuantraMeta", parent=base["Normal"], fontName=REGULAR_FONT, fontSize=8.5,
            leading=11.5, textColor=colors.HexColor("#374151"),
        ),
        "heading": ParagraphStyle(
            "KuantraHeading", parent=base["Heading2"], fontName=BOLD_FONT, fontSize=11,
            leading=14, spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#111827"),
        ),
        "body": ParagraphStyle(
            "KuantraBody", parent=base["Normal"], fontName=REGULAR_FONT, fontSize=8.5,
            leading=12, textColor=colors.HexColor("#111827"),
        ),
        "warn": ParagraphStyle(
            "KuantraWarn", parent=base["Normal"], fontName=REGULAR_FONT, fontSize=8.5,
            leading=12, textColor=colors.HexColor("#92400e"),
        ),
        "cell": ParagraphStyle(
            "KuantraCell", parent=base["Normal"], fontName=REGULAR_FONT, fontSize=8,
            leading=10.5, textColor=colors.HexColor("#111827"),
        ),
        "cell_header": ParagraphStyle(
            "KuantraCellHeader", parent=base["Normal"], fontName=BOLD_FONT, fontSize=8,
            leading=10.5, textColor=colors.white,
        ),
        "note": ParagraphStyle(
            "KuantraNote", parent=base["Normal"], fontName=BOLD_FONT, fontSize=8.5,
            leading=11.5, textColor=colors.HexColor("#111827"),
        ),
    }


def _paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)


def _table(block: TableBlock, styles: dict[str, ParagraphStyle]) -> Table:
    data = [[_paragraph(header, styles["cell_header"]) for header in block.headers]]
    for row in block.rows:
        data.append([_paragraph(cell, styles["cell"]) for cell in row])
    table = Table(data, colWidths=list(block.widths) if block.widths else None, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    return table


def render_report_pdf(
    *,
    title: str,
    meta_lines: Iterable[str],
    blocks: Iterable[tuple[str, Any]],
    footer_text: str = "",
    page_word: str = "",
) -> bytes:
    """Render a small report and return the PDF bytes.

    Supported blocks: ``("heading", text)``, ``("paragraph", text)``,
    ``("warning", text)``, ``("table", TableBlock)``, ``("spacer", points)``,
    ``("keep", [blocks])``.
    """

    register_report_fonts()
    styles = _styles()
    buffer = BytesIO()
    frame = Frame(1.6 * cm, 1.6 * cm, A4[0] - 3.2 * cm, A4[1] - 3.2 * cm, id="body")
    template = PageTemplate(id="report", frames=[frame])
    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        title=title,
        author="Kuantra Terminal",
        subject="Local journal report",
        creator="Kuantra Terminal",
        pageTemplates=[template],
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
    )

    def canvas_factory(*args, **kwargs):
        return _NumberedCanvas(*args, footer_text=footer_text, page_word=page_word, **kwargs)

    story: list[Any] = [_paragraph(title, styles["title"])]
    for line in meta_lines:
        story.append(_paragraph(line, styles["meta"]))
    story.append(Spacer(1, 6))

    def append_blocks(items: Iterable[tuple[str, Any]]) -> None:
        for kind, payload in items:
            if kind == "heading":
                story.append(_paragraph(payload, styles["heading"]))
            elif kind == "paragraph":
                story.append(_paragraph(payload, styles["body"]))
            elif kind == "warning":
                story.append(_paragraph(payload, styles["warn"]))
            elif kind == "note":
                story.append(_paragraph(payload, styles["note"]))
            elif kind == "spacer":
                story.append(Spacer(1, float(payload)))
            elif kind == "table":
                assert isinstance(payload, TableBlock)
                story.append(_table(payload, styles))
            elif kind == "keep":
                story.append(KeepTogether([_paragraph(text, styles["body"]) for text in payload]))
            else:  # pragma: no cover - defensive
                raise ValueError(f"unsupported report block: {kind}")

    append_blocks(blocks)
    doc.build(story, canvasmaker=canvas_factory)
    return buffer.getvalue()
