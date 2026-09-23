"""Informe PDF de la auditoría de un CV, pensado para descargar y compartir.

Se genera en el servidor con reportlab (Python puro, sin dependencias del
sistema) para que el resultado sea un archivo real e idéntico en cualquier
navegador. La paleta es la misma que la del frontend (`globals.css`).

Las fuentes estándar de PDF solo cubren Windows-1252: cualquier carácter fuera
de ese juego (flechas, emojis que a veces devuelve el LLM) se sustituye o se
descarta en `_t()` para que nunca salga un recuadro negro.
"""

from __future__ import annotations

import io
import re
import unicodedata
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import ArcPath, Circle, Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.schemas.ats import AtsReport
from app.schemas.resume import ResumeData

# --------------------------------------------------------------------------
# Paleta (espejo de frontend/src/app/globals.css, tema claro)
# --------------------------------------------------------------------------
ACCENT = colors.HexColor("#2a78d6")
ACCENT_INK = colors.HexColor("#1c5cab")
ACCENT_SOFT = colors.HexColor("#cde2fb")
ACCENT_DEEP = colors.HexColor("#104281")
INK = colors.HexColor("#0b0b0b")
INK_2 = colors.HexColor("#52514e")
MUTED = colors.HexColor("#898781")
SURFACE = colors.HexColor("#f2f2ee")
GRID = colors.HexColor("#e1e0d9")
GOOD = colors.HexColor("#0ca30c")
WARNING = colors.HexColor("#fab219")
SERIOUS = colors.HexColor("#ec835a")
CRITICAL = colors.HexColor("#d03b3b")

PAGE_W, PAGE_H = A4
MARGIN = 16 * mm
CONTENT_W = PAGE_W - 2 * MARGIN

FONT = "Helvetica"
BOLD = "Helvetica-Bold"


def _style(name: str, **kw) -> ParagraphStyle:
    base = {"fontName": FONT, "fontSize": 9.5, "leading": 13.5, "textColor": INK}
    base.update(kw)
    return ParagraphStyle(name, **base)


S_BODY = _style("body")
S_BODY_2 = _style("body2", textColor=INK_2)
S_SMALL = _style("small", fontSize=8, leading=11, textColor=MUTED)
S_LABEL = _style("label", fontName=BOLD, fontSize=7, leading=9, textColor=MUTED)
S_H2 = _style("h2", fontName=BOLD, fontSize=12.5, leading=16, textColor=INK, spaceBefore=4)
S_H2_SUB = _style("h2sub", fontSize=8.5, leading=11, textColor=MUTED)

_REPLACEMENTS = {
    "→": "->", "←": "<-", "⇒": "=>", "≥": ">=", "≤": "<=", "✓": "", "✔": "",
    "✗": "x", "✕": "x", "★": "*", "☆": "*", "▲": "", "●": "•", "◆": "•", "\u200b": "",
}


def _t(value: object) -> str:
    """Texto seguro para Paragraph: sin caracteres fuera de cp1252 y con XML escapado."""
    text = str(value or "")
    for src, dst in _REPLACEMENTS.items():
        text = text.replace(src, dst)
    text = text.encode("cp1252", errors="ignore").decode("cp1252")
    return escape(text)


def score_label(score: float) -> str:
    if score >= 75:
        return "Fuerte"
    if score >= 55:
        return "Aceptable"
    if score >= 35:
        return "Flojo"
    return "Crítico"


def score_color(score: float) -> colors.Color:
    if score >= 75:
        return GOOD
    if score >= 55:
        return WARNING
    if score >= 35:
        return SERIOUS
    return CRITICAL


SEVERITY = {
    "critical": ("CRÍTICO", CRITICAL),
    "warning": ("AVISO", WARNING),
    "info": ("NOTA", MUTED),
}


def report_filename(data: ResumeData, label: str = "") -> str:
    """Nombre de archivo ASCII: `Informe-CV-Nombre-Apellido.pdf`."""
    base = data.contact.full_name or label or "CV"
    ascii_name = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_name).strip("-") or "CV"
    return f"Informe-CV-{slug[:60]}.pdf"


# --------------------------------------------------------------------------
# Piezas gráficas
# --------------------------------------------------------------------------
def _score_ring(score: float, size: float = 34 * mm) -> Drawing:
    d = Drawing(size, size)
    cx = cy = size / 2
    r = size / 2 - 5
    d.add(Circle(cx, cy, r, strokeColor=GRID, strokeWidth=8, fillColor=None))
    pct = max(0.0, min(score, 100.0)) / 100
    if pct > 0:
        arc = ArcPath(strokeColor=score_color(score), strokeWidth=8, fillColor=None,
                      strokeLineCap=1)
        arc.addArc(cx, cy, r, 90 - 360 * pct, 90)
        d.add(arc)
    d.add(String(cx, cy - 4, f"{round(score)}", fontName=BOLD, fontSize=24,
                 fillColor=INK, textAnchor="middle"))
    d.add(String(cx, cy - 15, "/100", fontName=FONT, fontSize=8, fillColor=MUTED,
                 textAnchor="middle"))
    return d


def _meter(label: str, value: float, width: float) -> Drawing:
    h = 20
    d = Drawing(width, h)
    d.add(String(0, 11, _plain(label), fontName=FONT, fontSize=8.5, fillColor=INK_2))
    d.add(String(width, 11, f"{round(value)}", fontName=BOLD, fontSize=8.5, fillColor=INK,
                 textAnchor="end"))
    d.add(Rect(0, 2, width, 5, rx=2.5, ry=2.5, fillColor=GRID, strokeColor=None))
    filled = width * max(0.0, min(value, 100.0)) / 100
    if filled > 0:
        d.add(Rect(0, 2, max(filled, 5), 5, rx=2.5, ry=2.5, fillColor=score_color(value),
                   strokeColor=None))
    return d


def _keyword_bars(items: list[tuple[str, int]], width: float) -> Drawing:
    row_h = 15
    label_w = 38 * mm
    d = Drawing(width, row_h * len(items))
    top = max((v for _, v in items), default=1) or 1
    bar_w = width - label_w - 12 * mm
    for i, (name, value) in enumerate(items):
        y = row_h * (len(items) - 1 - i) + 4
        d.add(String(0, y + 1, _plain(name)[:26], fontName=FONT, fontSize=8.5, fillColor=INK_2))
        w = max(bar_w * value / top, 3)
        d.add(Rect(label_w, y, w, 8, rx=2, ry=2, fillColor=ACCENT, strokeColor=None))
        d.add(String(label_w + w + 4, y + 1, f"{value}x", fontName=BOLD, fontSize=8,
                     fillColor=INK))
    return d


def _plain(value: object) -> str:
    """Como `_t` pero sin escapar XML: para `String` de reportlab.graphics."""
    text = str(value or "")
    for src, dst in _REPLACEMENTS.items():
        text = text.replace(src, dst)
    return text.encode("cp1252", errors="ignore").decode("cp1252")


class Chips(Flowable):
    """Etiquetas redondeadas que saltan de línea solas (el stack del perfil)."""

    def __init__(self, items: list[str], max_width: float, fill=ACCENT_SOFT, ink=ACCENT_INK):
        super().__init__()
        self.items = [_plain(i) for i in items if i]
        self.max_width = max_width
        self.fill, self.ink = fill, ink
        self.font_size, self.pad_x, self.chip_h, self.gap = 8, 5, 14, 4
        self._layout: list[tuple[float, float, float, str]] = []

    def wrap(self, avail_width, avail_height):
        width = min(self.max_width, avail_width)
        x = y = 0.0
        self._layout = []
        for item in self.items:
            w = stringWidth(item, FONT, self.font_size) + 2 * self.pad_x
            if x and x + w > width:
                x = 0
                y += self.chip_h + self.gap
            self._layout.append((x, y, w, item))
            x += w + self.gap
        self.height = (y + self.chip_h) if self.items else 0
        self.width = width
        return width, self.height

    def draw(self):
        c = self.canv
        for x, y, w, item in self._layout:
            top = self.height - y - self.chip_h
            c.setFillColor(self.fill)
            c.roundRect(x, top, w, self.chip_h, 4, stroke=0, fill=1)
            c.setFillColor(self.ink)
            c.setFont(FONT, self.font_size)
            c.drawString(x + self.pad_x, top + 4, item)


# --------------------------------------------------------------------------
# Secciones
# --------------------------------------------------------------------------
def _section(title: str, subtitle: str = "") -> list:
    head = [Paragraph(_t(title), S_H2)]
    if subtitle:
        head.append(Paragraph(_t(subtitle), S_H2_SUB))
    bar = Table([[""]], colWidths=[18 * mm], rowHeights=[2.2])
    bar.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ACCENT)]))
    bar.hAlign = "LEFT"
    return [Spacer(1, 12), *head, Spacer(1, 4), bar, Spacer(1, 8)]


def _with_section(title: str, subtitle: str, first, *rest) -> list:
    """Título pegado a su primer bloque: nunca queda un encabezado solo al pie de página."""
    return [KeepTogether([*_section(title, subtitle), first]), *rest]


def _header(data: ResumeData, target_role: str | None, generated: datetime) -> Table:
    name = data.contact.full_name or "Candidato"
    headline = data.contact.headline or target_role or ""
    left = [
        Paragraph("INFORME DE AUDITORÍA ATS", _style("k", fontName=BOLD, fontSize=7.5,
                                                    textColor=ACCENT_SOFT, leading=10)),
        Spacer(1, 3),
        Paragraph(_t(name), _style("n", fontName=BOLD, fontSize=20, leading=24,
                                   textColor=colors.white)),
    ]
    if headline:
        left.append(Paragraph(_t(headline), _style("hl", fontSize=10.5, leading=14,
                                                   textColor=colors.white)))
    right_lines = [f"Generado el {generated.strftime('%d/%m/%Y')}"]
    if target_role:
        right_lines.append(f"Rol objetivo: {target_role}")
    right_lines.append("Career Copilot")
    right = Paragraph(
        "<br/>".join(_t(line) for line in right_lines),
        _style("r", fontSize=8, leading=12, textColor=ACCENT_SOFT, alignment=2),
    )
    table = Table([[left, right]], colWidths=[CONTENT_W * 0.66, CONTENT_W * 0.34])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ACCENT_DEEP),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("TOPPADDING", (0, 0), (-1, -1), 16),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
    ]))
    return table


def _score_block(report: AtsReport) -> Table:
    score = report.overall_score
    caption = (
        "Listo para postular." if score >= 75 else "Aplica los quick wins antes de enviarlo."
    )
    left = [
        _score_ring(score),
        Spacer(1, 4),
        Paragraph(f"<b>{_t(score_label(score))}</b>",
                  _style("sl", alignment=TA_CENTER, textColor=score_color(score), fontSize=10.5)),
        Paragraph(_t(caption), _style("sc", alignment=TA_CENTER, fontSize=8, leading=10.5,
                                      textColor=INK_2)),
    ]
    meter_w = CONTENT_W * 0.62 - 20
    b = report.breakdown
    meters = [
        _meter("Relevancia técnica", b.technical_relevance, meter_w),
        _meter("Claridad y formato", b.clarity_format, meter_w),
        _meter("Cuantificación de logros", b.achievement_quantification, meter_w),
        _meter("Cobertura de habilidades", b.skill_coverage, meter_w),
        _meter("Legibilidad para el ATS", b.ats_parseability, meter_w),
    ]
    right = []
    for m in meters:
        right.extend([m, Spacer(1, 5)])
    table = Table([[left, right]], colWidths=[CONTENT_W * 0.38, CONTENT_W * 0.62])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
    ]))
    return table


def _numbered(items: list[str]) -> Table:
    rows = [
        [Paragraph(f"<b>{i}</b>", _style(f"num{i}", textColor=colors.white, alignment=TA_CENTER,
                                         fontSize=8.5, leading=11)),
         Paragraph(_t(text), S_BODY)]
        for i, text in enumerate(items, 1)
    ]
    table = Table(rows, colWidths=[7 * mm, CONTENT_W - 7 * mm])
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (1, 0), (1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        # Separa los números en fichas sueltas en vez de una barra continua.
        ("LINEBELOW", (0, 0), (0, -1), 5, colors.white),
    ]
    for i in range(len(rows)):
        style.append(("BACKGROUND", (0, i), (0, i), ACCENT))
    table.setStyle(TableStyle(style))
    return table


def _bullets(items: list[str], color=GOOD, mark: str = "+") -> Table:
    rows = [
        [Paragraph(f"<b>{mark}</b>", _style("mk", textColor=color)), Paragraph(_t(t), S_BODY)]
        for t in items
    ]
    table = Table(rows, colWidths=[5 * mm, CONTENT_W - 5 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def _finding(finding) -> KeepTogether:
    label, color = SEVERITY.get(finding.severity, SEVERITY["info"])
    head = f'<font color="{color.hexval().replace("0x", "#")}"><b>{_t(label)}</b></font>'
    if finding.area:
        head += f'  <font color="#898781">·  {_t(finding.area.upper())}</font>'
    body = [Paragraph(head, _style("fh", fontSize=7.5, leading=10)),
            Spacer(1, 2),
            Paragraph(_t(finding.message), S_BODY)]
    if finding.fix:
        body.append(Spacer(1, 2))
        body.append(Paragraph(f"<b>Solución:</b> {_t(finding.fix)}", S_BODY_2))
    table = Table([[body]], colWidths=[CONTENT_W])
    table.setStyle(TableStyle([
        ("LINEBEFORE", (0, 0), (0, 0), 3, color),
        ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return KeepTogether([table, Spacer(1, 5)])


def _rewrite(rewrite) -> KeepTogether:
    inner = []
    if rewrite.invented_facts:
        inner.append(Paragraph(
            "<b>Atención:</b> contiene datos que no estaban en el CV. Verifícalos antes de usarlo.",
            _style("warn", fontSize=8, leading=11, textColor=CRITICAL)))
        inner.append(Spacer(1, 4))
    inner += [
        Paragraph("ANTES", S_LABEL),
        Paragraph(_t(rewrite.original), S_BODY_2),
        Spacer(1, 6),
        Paragraph("DESPUÉS", _style("after", fontName=BOLD, fontSize=7, leading=9,
                                    textColor=ACCENT_INK)),
        Paragraph(_t(rewrite.suggestion), S_BODY),
    ]
    if rewrite.rationale:
        inner += [Spacer(1, 4), Paragraph(_t(rewrite.rationale), S_SMALL)]
    table = Table([[inner]], colWidths=[CONTENT_W])
    table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, GRID),
        ("LINEBEFORE", (0, 0), (0, 0), 3, ACCENT),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    return KeepTogether([table, Spacer(1, 6)])


def _profile(data: ResumeData, report: AtsReport | None) -> list:
    c = data.contact
    years = f"{data.total_years_experience:g} años" if data.total_years_experience else ""
    rows = [
        ("Nombre", c.full_name), ("Titular", c.headline), ("Email", c.email),
        ("Teléfono", c.phone), ("Ubicación", c.location), ("LinkedIn", c.linkedin),
        ("GitHub", c.github), ("Portafolio", c.portfolio), ("Experiencia", years),
        ("Seniority", data.detected_seniority),
    ]
    rows = [(k, v) for k, v in rows if v]
    out: list = []
    if rows:
        table = Table(
            [[Paragraph(_t(k), S_SMALL), Paragraph(_t(v), S_BODY)] for k, v in rows],
            colWidths=[28 * mm, CONTENT_W - 28 * mm],
        )
        table.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, -2), 0.4, GRID),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        out.append(table)

    if data.summary:
        out += [Spacer(1, 10), Paragraph("RESUMEN PROFESIONAL", S_LABEL), Spacer(1, 3),
                Paragraph(_t(data.summary), S_BODY_2)]

    stack = data.skills.flat()
    if stack:
        out += [Spacer(1, 10), Paragraph("STACK", S_LABEL), Spacer(1, 4),
                Chips(stack[:40], CONTENT_W)]
    if data.skills.soft_skills:
        out += [Spacer(1, 8), Paragraph("HABILIDADES BLANDAS", S_LABEL), Spacer(1, 4),
                Chips(data.skills.soft_skills[:20], CONTENT_W, fill=SURFACE, ink=INK_2)]

    if data.experience:
        out += [Spacer(1, 10), Paragraph("EXPERIENCIA", S_LABEL), Spacer(1, 3)]
        for item in data.experience[:8]:
            period = " - ".join(p for p in (item.start_date, item.end_date) if p)
            line = f"<b>{_t(item.role)}</b>"
            if item.company:
                line += f" · {_t(item.company)}"
            if period:
                line += f'  <font color="#898781">{_t(period)}</font>'
            out.append(Paragraph(line, S_BODY))

    if data.education:
        out += [Spacer(1, 10), Paragraph("EDUCACIÓN", S_LABEL), Spacer(1, 3)]
        for ed in data.education[:5]:
            field = ed.field_of_study
            if field and field.lower() in (ed.degree or "").lower():
                field = ""
            title = " en ".join(p for p in (ed.degree, field) if p)
            line = f"<b>{_t(title or ed.institution)}</b>"
            if title and ed.institution:
                line += f" · {_t(ed.institution)}"
            out.append(Paragraph(line, S_BODY))

    if data.languages:
        langs = ", ".join(
            f"{lang.language} ({lang.level})" if lang.level else lang.language
            for lang in data.languages if lang.language
        )
        out += [Spacer(1, 10), Paragraph("IDIOMAS", S_LABEL), Spacer(1, 3),
                Paragraph(_t(langs), S_BODY)]

    if report and report.missing_sections:
        out += [Spacer(1, 10), Paragraph(
            f"<b>Secciones ausentes:</b> {_t(', '.join(report.missing_sections))}",
            _style("miss", fontSize=8.5, leading=12, textColor=SERIOUS))]
    return out


# --------------------------------------------------------------------------
# Documento
# --------------------------------------------------------------------------
def build_report_pdf(
    data: ResumeData,
    report: AtsReport | None,
    target_role: str | None = None,
    label: str = "",
    generated: datetime | None = None,
) -> bytes:
    """Devuelve los bytes del PDF con toda la auditoría del CV."""
    generated = generated or datetime.now()
    name = data.contact.full_name or label or "CV"
    buffer = io.BytesIO()

    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(GRID)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, 12 * mm, PAGE_W - MARGIN, 12 * mm)
        canvas.setFont(FONT, 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN, 8 * mm, _plain(f"Career Copilot · Informe ATS de {name}"))
        canvas.drawRightString(PAGE_W - MARGIN, 8 * mm, f"Página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=18 * mm,
        title=_plain(f"Informe de CV - {name}"),
        author="Career Copilot",
        subject="Auditoría ATS del CV",
    )

    story: list = [_header(data, target_role, generated), Spacer(1, 12)]

    if report is None:
        story.append(Paragraph("Este CV todavía no tiene auditoría. Re-audítalo desde "
                               "Career Copilot y vuelve a generar el informe.", S_BODY_2))
    else:
        story.append(_score_block(report))

        if report.quick_wins:
            story += _with_section("Quick wins", "Máximo impacto, mínimo esfuerzo",
                                   _numbered(report.quick_wins))

        if report.strengths:
            story += _with_section("Fortalezas", "Lo que ya funciona y conviene mantener",
                                   _bullets(report.strengths))

        if report.findings:
            order = {"critical": 0, "warning": 1, "info": 2}
            findings = [
                _finding(f)
                for f in sorted(report.findings, key=lambda f: order.get(f.severity, 3))
            ]
            story += _with_section(
                "Hallazgos de la auditoría",
                f"{len(report.findings)} puntos detectados, ordenados por gravedad",
                *findings,
            )

        if report.rewrites:
            story += _with_section(
                "Reescrituras propuestas",
                "Fórmula X-Y-Z: logré [X] medido por [Y] haciendo [Z]",
                *[_rewrite(r) for r in report.rewrites],
            )

        keywords = sorted(report.keyword_density.items(), key=lambda kv: (-kv[1], kv[0]))[:15]
        if keywords:
            story += _with_section("Densidad de keywords", "Cuántas veces aparece cada tecnología",
                                   _keyword_bars(keywords, CONTENT_W))

    profile = _profile(data, report)
    if profile:
        story += _with_section("Perfil extraído", "Lo que un ATS entiende al leer el CV", *profile)

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
