from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas


OUT_DIR = Path(__file__).resolve().parent
PDF_PATH = OUT_DIR / "fitness_action_recognition_flowchart.pdf"
PNG_PATH = OUT_DIR / "fitness_action_recognition_flowchart.png"


CANVAS_W = 2300
CANVAS_H = 690
Y_SHIFT = 78
PAGE_W, PAGE_H = landscape(A3)
MARGIN = 38

COLORS = {
    "input": colors.HexColor("#E9F2FF"),
    "vision": colors.HexColor("#E8F7EF"),
    "sensor": colors.HexColor("#FFF3D9"),
    "llm": colors.HexColor("#F0EAFE"),
    "gate": colors.HexColor("#FCE8EC"),
    "tool": colors.HexColor("#E7F8F8"),
    "final": colors.HexColor("#ECEFF3"),
    "line": colors.HexColor("#394150"),
    "text": colors.HexColor("#1F2933"),
    "muted": colors.HexColor("#687385"),
}

NODES = {
    "input": (55, 280, 150, 72, "输入\n原始视频\n可选心率 / 胸口IMU", "input"),
    "p1": (245, 96, 166, 72, "Phase 1\n视频预处理", "vision"),
    "frames": (455, 40, 178, 64, "抽帧 / 关键帧\n生成动作拼图", "vision"),
    "stage": (455, 124, 178, 64, "阶段切分\n准备 / 发力 / 回程 / 结束", "vision"),
    "vfeat": (455, 208, 178, 64, "视觉结构化特征\n器械 / 姿态 / 关键点", "vision"),
    "sensor": (245, 424, 166, 72, "传感器预处理\n可缺省", "sensor"),
    "hr": (455, 376, 178, 62, "心率摘要\n强度 / 是否训练中", "sensor"),
    "imu": (455, 462, 178, 72, "胸口IMU摘要\n躯干角度 / 晃动\n节奏 / 周期性", "sensor"),
    "llm": (695, 232, 190, 92, "Phase 2\nLLM 粗识别\n候选动作 + 证据\n不确定性 + 混淆组", "llm"),
    "gate": (940, 232, 168, 92, "Gate\nTop1是否明显领先?\n证据是否完整?", "gate"),
    "direct": (1160, 110, 162, 66, "直接输出\n高置信动作结果", "final"),
    "amb": (1160, 252, 162, 78, "进入专项\nAgent / Verifier\n解决易混动作", "tool"),
    "low": (1160, 420, 162, 70, "低置信 / 无已知混淆组\n人工样本池\n或更强模型复核", "final"),
    "smith": (1390, 110, 186, 62, "Smith Press Verifier\n胸推 vs 推肩", "tool"),
    "add": (1390, 198, 186, 62, "Adductor Verifier\n内收 vs 外展", "tool"),
    "pull": (1390, 286, 186, 62, "Pull Family Verifier\n划船 vs 下拉", "tool"),
    "leg": (1390, 374, 186, 62, "Leg Machine Verifier\n腿举 vs 哈克", "tool"),
    "merge": (1648, 244, 176, 78, "Final Decision\n合并粗识别\n专项复核与证据", "final"),
    "out": (1885, 176, 170, 66, "最终动作识别结果\n动作 + 置信等级 + 证据", "final"),
    "uncertain": (1885, 342, 170, 66, "仍冲突 / 证据不足\n不确定输出", "final"),
    "log": (2110, 260, 160, 72, "记录日志\n候选 / 证据 / tool结果\n失败原因", "final"),
}

EDGES = [
    ("input", "p1"),
    ("p1", "frames"),
    ("p1", "stage"),
    ("p1", "vfeat"),
    ("input", "sensor"),
    ("sensor", "hr"),
    ("sensor", "imu"),
    ("frames", "llm"),
    ("stage", "llm"),
    ("vfeat", "llm"),
    ("hr", "llm"),
    ("imu", "llm"),
    ("llm", "gate"),
    ("gate", "direct", "是"),
    ("gate", "amb", "否，且属于易混淆组"),
    ("gate", "low", "否，且不属于已知组"),
    ("amb", "smith"),
    ("amb", "add"),
    ("amb", "pull"),
    ("amb", "leg"),
    ("direct", "merge"),
    ("smith", "merge"),
    ("add", "merge"),
    ("pull", "merge"),
    ("leg", "merge"),
    ("low", "merge"),
    ("merge", "out", "证据足够"),
    ("merge", "uncertain", "仍不确定"),
    ("out", "log"),
    ("uncertain", "log"),
]

LANES = [
    (30, 20, 615, 295, "视频主证据层", "#F5FBF7"),
    (30, 340, 615, 230, "可选传感器辅助层", "#FFF9EC"),
    (660, 80, 470, 420, "LLM 粗识别与路由", "#FAF7FF"),
    (1130, 70, 470, 465, "专项复核工具", "#F2FCFC"),
    (1610, 135, 700, 320, "结果合成与闭环", "#F7F8FA"),
]

NODES = {
    key: (x, y + Y_SHIFT, w, h, text, kind)
    for key, (x, y, w, h, text, kind) in NODES.items()
}
LANES = [
    (x, y + Y_SHIFT, w, h, title, bg)
    for (x, y, w, h, title, bg) in LANES
]


def node_center(node_id: str) -> tuple[float, float]:
    x, y, w, h, _, _ = NODES[node_id]
    return x + w / 2, y + h / 2


def edge_points(src: str, dst: str) -> tuple[tuple[float, float], tuple[float, float]]:
    sx, sy, sw, sh, *_ = NODES[src]
    dx, dy, dw, dh, *_ = NODES[dst]
    scx, scy = node_center(src)
    dcx, dcy = node_center(dst)
    if abs(dcx - scx) >= abs(dcy - scy):
        start = (sx + sw if dcx >= scx else sx, scy)
        end = (dx if dcx >= scx else dx + dw, dcy)
    else:
        start = (scx, sy + sh if dcy >= scy else sy)
        end = (dcx, dy if dcy >= scy else dy + dh)
    return start, end


def wrap_lines(draw, text, font, max_width):
    lines = []
    for paragraph in text.split("\n"):
        current = ""
        for ch in paragraph:
            trial = current + ch
            bbox = draw.textbbox((0, 0), trial, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = ch
        if current:
            lines.append(current)
    return lines


def arrowhead_points(start, end, size=10):
    sx, sy = start
    ex, ey = end
    angle = math.atan2(ey - sy, ex - sx)
    left = (ex - size * math.cos(angle - math.pi / 6), ey - size * math.sin(angle - math.pi / 6))
    right = (ex - size * math.cos(angle + math.pi / 6), ey - size * math.sin(angle + math.pi / 6))
    return [end, left, right]


def draw_pdf():
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    c = canvas.Canvas(str(PDF_PATH), pagesize=(CANVAS_W, CANVAS_H))
    c.setTitle("Fitness Action Recognition Flowchart")

    c.setFillColor(colors.white)
    c.rect(0, 0, CANVAS_W, CANVAS_H, fill=1, stroke=0)

    c.setFillColor(COLORS["text"])
    c.setFont("STSong-Light", 22)
    c.drawString(MARGIN, CANVAS_H - 36, "健身动作识别 Flowchart：视频拼图 + 可选胸口 IMU / 心率 + LLM + Verifier")
    c.setFont("STSong-Light", 10)
    c.setFillColor(COLORS["muted"])
    c.drawString(MARGIN, CANVAS_H - 56, "原则：视频是主证据；胸口 IMU 主要用于躯干姿态、节奏和片段状态；心率只作弱辅助。")

    for x, y, w, h, title, bg in LANES:
        c.setFillColor(colors.HexColor(bg))
        c.roundRect(x, y, w, h, 12, fill=1, stroke=0)
        c.setFillColor(COLORS["muted"])
        c.setFont("STSong-Light", 12)
        c.drawString(x + 14, y + h - 24, title)

    c.setStrokeColor(COLORS["line"])
    c.setLineWidth(1.4)
    for src, dst, *label in EDGES:
        start, end = edge_points(src, dst)
        c.line(start[0], CANVAS_H - start[1], end[0], CANVAS_H - end[1])
        pts = arrowhead_points((start[0], CANVAS_H - start[1]), (end[0], CANVAS_H - end[1]), 9)
        c.setFillColor(COLORS["line"])
        c.line(pts[0][0], pts[0][1], pts[1][0], pts[1][1])
        c.line(pts[0][0], pts[0][1], pts[2][0], pts[2][1])
        if label:
            mx = (start[0] + end[0]) / 2
            my = CANVAS_H - ((start[1] + end[1]) / 2)
            c.setFillColor(colors.white)
            c.roundRect(mx - 45, my - 9, 90, 18, 5, fill=1, stroke=0)
            c.setFillColor(COLORS["muted"])
            c.setFont("STSong-Light", 8)
            c.drawCentredString(mx, my - 3, label[0])

    for x, y, w, h, text, kind in NODES.values():
        c.setFillColor(COLORS[kind])
        c.setStrokeColor(colors.HexColor("#C7D0DD"))
        c.setLineWidth(1)
        c.roundRect(x, CANVAS_H - y - h, w, h, 9, fill=1, stroke=1)
        c.setFillColor(COLORS["text"])
        c.setFont("STSong-Light", 11)
        lines = text.split("\n")
        total_h = len(lines) * 14
        start_y = CANVAS_H - y - (h - total_h) / 2 - 11
        for idx, line in enumerate(lines):
            c.drawCentredString(x + w / 2, start_y - idx * 14, line)

    c.save()


def find_font():
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def draw_png():
    scale = 2
    img = Image.new("RGB", (CANVAS_W * scale, CANVAS_H * scale), "white")
    draw = ImageDraw.Draw(img)
    font_path = find_font()
    font_title = ImageFont.truetype(font_path, 38) if font_path else ImageFont.load_default()
    font_lane = ImageFont.truetype(font_path, 22) if font_path else ImageFont.load_default()
    font_node = ImageFont.truetype(font_path, 20) if font_path else ImageFont.load_default()
    font_label = ImageFont.truetype(font_path, 16) if font_path else ImageFont.load_default()

    def s(v):
        return int(v * scale)

    draw.text((s(MARGIN), s(22)), "健身动作识别 Flowchart：视频拼图 + 可选胸口 IMU / 心率 + LLM + Verifier", fill="#1F2933", font=font_title)
    draw.text((s(MARGIN), s(66)), "原则：视频是主证据；胸口 IMU 主要用于躯干姿态、节奏和片段状态；心率只作弱辅助。", fill="#687385", font=font_label)

    for x, y, w, h, title, bg in LANES:
        draw.rounded_rectangle((s(x), s(y), s(x + w), s(y + h)), radius=s(12), fill=bg)
        draw.text((s(x + 14), s(y + 12)), title, fill="#687385", font=font_lane)

    for src, dst, *label in EDGES:
        start, end = edge_points(src, dst)
        draw.line((s(start[0]), s(start[1]), s(end[0]), s(end[1])), fill="#394150", width=s(2))
        pts = arrowhead_points(start, end, 10)
        draw.polygon([(s(px), s(py)) for px, py in pts], fill="#394150")
        if label:
            mx = (start[0] + end[0]) / 2
            my = (start[1] + end[1]) / 2
            draw.rounded_rectangle((s(mx - 58), s(my - 12), s(mx + 58), s(my + 12)), radius=s(6), fill="white")
            bbox = draw.textbbox((0, 0), label[0], font=font_label)
            draw.text((s(mx) - (bbox[2] - bbox[0]) / 2, s(my) - (bbox[3] - bbox[1]) / 2 - 2), label[0], fill="#687385", font=font_label)

    for x, y, w, h, text, kind in NODES.values():
        fill = f"#{COLORS[kind].hexval()[2:]}"
        draw.rounded_rectangle((s(x), s(y), s(x + w), s(y + h)), radius=s(9), fill=fill, outline="#C7D0DD", width=s(1))
        lines = text.split("\n")
        line_h = 24
        start_y = s(y + (h - len(lines) * 12) / 2 - 6)
        for idx, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font_node)
            draw.text((s(x + w / 2) - (bbox[2] - bbox[0]) / 2, start_y + idx * line_h), line, fill="#1F2933", font=font_node)

    img.save(PNG_PATH)


if __name__ == "__main__":
    draw_pdf()
    draw_png()
    print(PDF_PATH)
    print(PNG_PATH)
