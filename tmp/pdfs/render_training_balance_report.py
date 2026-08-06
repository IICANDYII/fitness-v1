from pathlib import Path
import re
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "output/pdf/训练均衡度_运动科学与产品公式研究报告.md")
OUT = ROOT / (sys.argv[2] if len(sys.argv) > 2 else "output/pdf/训练均衡度_运动科学与产品公式研究报告.pdf")
if "全天活动健康评估指标" in SRC.name:
    REPORT_TITLE = "全天活动健康评估指标"
    REPORT_SUBTITLE = "Activity 算法的权威指南、科研证据与产品公式"
elif "运动训练健康评估指标" in SRC.name:
    REPORT_TITLE = "运动训练健康评估指标"
    REPORT_SUBTITLE = "寻找健身领域的 HEI：指南、量表与产品路径"
elif "健身可量化指标" in SRC.name:
    REPORT_TITLE = "健身可量化指标"
    REPORT_SUBTITLE = "官方指南、科学证据与产品可测性研究"
else:
    REPORT_TITLE = "训练均衡度"
    REPORT_SUBTITLE = "运动科学证据与产品公式研究报告"

pdfmetrics.registerFont(TTFont("CN", "/System/Library/Fonts/STHeiti Light.ttc", subfontIndex=0))
pdfmetrics.registerFont(TTFont("CN-Bold", "/System/Library/Fonts/STHeiti Medium.ttc", subfontIndex=0))

PAGE_W, PAGE_H = A4
MARGIN_X = 18 * mm
MARGIN_TOP = 20 * mm
MARGIN_BOTTOM = 18 * mm


def tex_plain(text: str) -> str:
    text = text.replace(r"\(", "").replace(r"\)", "")
    replacements = {
        r"\sum": "Σ", r"\cdot": "×", r"\times": "×", r"\in": "∈",
        r"\ge": "≥", r"\mathbf{1}": "1", r"\boxed": "",
        r"\min": "min", r"\left": "", r"\right": "", r"\text": "",
        r"\tau": "τ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1/\2)", text)
    text = re.sub(r"_\{([^{}]+)\}", r"_\1", text)
    text = re.sub(r"\^\{([^{}]+)\}", r"^\1", text)
    text = text.replace("\\", "")
    text = text.replace("{", "").replace("}", "")
    return text


def esc(text: str) -> str:
    text = tex_plain(text)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<link href="\2" color="#2e6f9e">\1</link>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r'<font face="Courier">\1</font>', text)
    return text


styles = getSampleStyleSheet()
base = dict(fontName="CN", textColor=colors.HexColor("#263746"), leading=17)
S = {
    "body": ParagraphStyle("body", parent=styles["BodyText"], fontSize=9.5, alignment=TA_JUSTIFY,
                           spaceAfter=5, **base),
    "quote": ParagraphStyle("quote", parent=styles["BodyText"], fontSize=9.2, leftIndent=8 * mm,
                            rightIndent=5 * mm, borderColor=colors.HexColor("#2e6f9e"),
                            borderWidth=1.5, borderPadding=6, backColor=colors.HexColor("#f3f7fa"),
                            spaceBefore=4, spaceAfter=8, **base),
    "h1": ParagraphStyle("h1", fontName="CN-Bold", fontSize=22, leading=30,
                         textColor=colors.HexColor("#174f73"), spaceAfter=12),
    "h2": ParagraphStyle("h2", fontName="CN-Bold", fontSize=15, leading=22,
                         textColor=colors.HexColor("#1b7554"), spaceBefore=13, spaceAfter=7),
    "h3": ParagraphStyle("h3", fontName="CN-Bold", fontSize=12, leading=18,
                         textColor=colors.HexColor("#2d75a5"), spaceBefore=10, spaceAfter=5),
    "h4": ParagraphStyle("h4", fontName="CN-Bold", fontSize=10.5, leading=16,
                         textColor=colors.HexColor("#68447a"), spaceBefore=8, spaceAfter=4),
    "formula": ParagraphStyle("formula", fontName="CN", fontSize=10.5, leading=18,
                              alignment=TA_CENTER, textColor=colors.HexColor("#173a52"),
                              backColor=colors.HexColor("#eef4f7"), borderPadding=7,
                              spaceBefore=4, spaceAfter=8),
    "bullet": ParagraphStyle("bullet", parent=styles["BodyText"], fontName="CN", fontSize=9.4,
                             leading=16, leftIndent=5 * mm, firstLineIndent=-3.5 * mm,
                             textColor=colors.HexColor("#263746"), spaceAfter=3),
    "table_head": ParagraphStyle("table_head", parent=styles["BodyText"], fontName="CN-Bold",
                                 fontSize=9.4, leading=14, textColor=colors.white),
}


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("CN", 8)
    canvas.setFillColor(colors.HexColor("#6b7c89"))
    if doc.page > 1:
        canvas.drawString(MARGIN_X, 10 * mm, f"{REPORT_TITLE} 官方指南与科学证据研究")
        canvas.drawRightString(PAGE_W - MARGIN_X, 10 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def cover(canvas, doc):
    if doc.page != 1:
        return
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#174f73"))
    canvas.rect(0, PAGE_H - 72 * mm, PAGE_W, 72 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("CN-Bold", 25)
    canvas.drawString(22 * mm, PAGE_H - 34 * mm, REPORT_TITLE)
    canvas.setFont("CN", 14)
    canvas.drawString(22 * mm, PAGE_H - 46 * mm, REPORT_SUBTITLE)
    canvas.setFillColor(colors.HexColor("#263746"))
    canvas.setFont("CN", 10)
    canvas.drawString(22 * mm, PAGE_H - 92 * mm, "普通健身人群 × 消费级第一人称记录设备")
    canvas.drawString(22 * mm, PAGE_H - 101 * mm, "研究日期：2026-06-30")
    canvas.drawString(22 * mm, PAGE_H - 110 * mm, "结论性质：提示性产品指标，不构成训练处方")
    canvas.setStrokeColor(colors.HexColor("#1b7554"))
    canvas.setLineWidth(3)
    canvas.line(22 * mm, PAGE_H - 120 * mm, 88 * mm, PAGE_H - 120 * mm)
    canvas.restoreState()


def parse_table(lines, i):
    rows = []
    while i < len(lines) and lines[i].strip().startswith("|"):
        cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
        if not all(re.fullmatch(r":?-{3,}:?", c or "") for c in cells):
            cell_style = S["table_head"] if not rows else S["body"]
            rows.append([Paragraph(esc(c), cell_style) for c in cells])
        i += 1
    if not rows:
        return None, i
    n = len(rows[0])
    usable = PAGE_W - 2 * MARGIN_X
    widths = [usable / n] * n
    t = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#174f73")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "CN-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#b8c5ce")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f8fa")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t, i


def build_story(text):
    lines = text.splitlines()
    story = [Spacer(1, 62 * mm), PageBreak()]
    i = 2  # skip title and metadata, already represented on cover
    in_formula = False
    formula = []
    while i < len(lines):
        raw = lines[i].rstrip()
        s = raw.strip()
        if s == r"\[":
            in_formula = True
            formula = []
            i += 1
            continue
        if in_formula:
            if s == r"\]":
                compact = " ".join(formula)
                story.append(Paragraph(esc(compact), S["formula"]))
                in_formula = False
            else:
                formula.append(s)
            i += 1
            continue
        if not s:
            i += 1
            continue
        if s.startswith("|"):
            table, i = parse_table(lines, i)
            story.extend([table, Spacer(1, 5)])
            continue
        if s.startswith("#### "):
            story.append(Paragraph(esc(s[5:]), S["h4"]))
        elif s.startswith("### "):
            story.append(Paragraph(esc(s[4:]), S["h3"]))
        elif s.startswith("## "):
            story.append(Paragraph(esc(s[3:]), S["h2"]))
        elif s.startswith("# "):
            story.append(Paragraph(esc(s[2:]), S["h1"]))
        elif s.startswith("> "):
            story.append(Paragraph(esc(s[2:]), S["quote"]))
        elif re.match(r"^[-*] ", s):
            story.append(Paragraph("• " + esc(s[2:]), S["bullet"]))
        elif re.match(r"^\d+\. ", s):
            story.append(Paragraph(esc(s), S["bullet"]))
        else:
            story.append(Paragraph(esc(s), S["body"]))
        i += 1
    return story


doc = BaseDocTemplate(
    str(OUT),
    pagesize=A4,
    leftMargin=MARGIN_X,
    rightMargin=MARGIN_X,
    topMargin=MARGIN_TOP,
    bottomMargin=MARGIN_BOTTOM,
    title=f"{REPORT_TITLE}：{REPORT_SUBTITLE}",
    author="Codex",
)
frame = Frame(MARGIN_X, MARGIN_BOTTOM, PAGE_W - 2 * MARGIN_X,
              PAGE_H - MARGIN_TOP - MARGIN_BOTTOM, id="normal")
doc.addPageTemplates([PageTemplate(id="report", frames=frame, onPage=footer, onPageEnd=cover)])
doc.build(build_story(SRC.read_text(encoding="utf-8")))
print(OUT)
