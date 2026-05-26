"""
将肌群示意图拆分成独立SVG矢量图
策略：
1. 用颜色分割检测深蓝色肌肉区域
2. 用连通分量找到各个独立肌肉块
3. 根据位置与已知标签匹配
4. 每个肌肉区域输出一个SVG
"""

import cv2
import numpy as np
import svgwrite
import os
from pathlib import Path

IMG_PATH = r"D:\WorkPath\fitness\肌群正反面示意图.png"
OUT_DIR = Path(r"D:\WorkPath\fitness\muscle_svgs")
OUT_DIR.mkdir(exist_ok=True)

# OpenCV 不支持中文路径，用 PIL 中转
from PIL import Image
pil_img = Image.open(IMG_PATH).convert("RGB")
img_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
h, w = img_bgr.shape[:2]

# ── 1. 颜色分割：提取深蓝色肌肉区域 ──────────────────────────────────────
hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

# 深蓝色范围（肌肉填充色）
lower_blue = np.array([95, 60, 30])
upper_blue = np.array([135, 255, 160])
mask = cv2.inRange(hsv, lower_blue, upper_blue)

# 形态学操作：闭运算填补小空洞，开运算去噪点
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel, iterations=1)

# ── 2. 连通分量：分离各个肌肉块 ──────────────────────────────────────────
n_labels, labels_map, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)

# 过滤太小的区域（背景噪点）
MIN_AREA = 400
valid_ids = [i for i in range(1, n_labels) if stats[i, cv2.CC_STAT_AREA] >= MIN_AREA]
print(f"检测到 {len(valid_ids)} 个有效肌肉区域")

# ── 3. 已知标签与位置（根据图片目视估计，像素坐标）───────────────────────
# 格式：(name, side, approx_x, approx_y)
# side: 'front' = 左半图, 'back' = 右半图
# 图片宽约 560px，左半 0~280 为正面，右半 280~560 为背面
HALF = w // 2

LABELS = [
    # 正面
    ("上胸",   "front",  135, 105),
    ("中下胸", "front",  130, 140),
    ("二头",   "front",   75, 195),
    ("腹部",   "front",  140, 235),
    ("股四",   "front",  135, 350),
    ("前束",   "front",  170,  88),
    ("中束",   "front",  170, 108),
    ("小臂",   "front",   70, 255),
    ("小腿",   "front",  130, 430),
    # 背面
    ("斜方",   "back",   365,  95),
    ("后束",   "back",   355, 130),
    ("三头",   "back",   415, 190),
    ("背部",   "back",   375, 200),
    ("臀部",   "back",   370, 300),
    ("腘绳",   "back",   370, 370),
    ("小腿背", "back",   370, 435),
]

# ── 4. 每个 valid_id 找最近标签 ───────────────────────────────────────────
def label_for_component(cid):
    cx, cy = centroids[cid]
    side = "front" if cx < HALF else "back"
    best_name, best_dist = "未知", float("inf")
    for name, s, lx, ly in LABELS:
        if s != side:
            continue
        d = (cx - lx) ** 2 + (cy - ly) ** 2
        if d < best_dist:
            best_dist = d
            best_name = name
    return best_name, side

# 合并同名区域的轮廓
from collections import defaultdict
group_masks = defaultdict(lambda: np.zeros((h, w), dtype=np.uint8))

for cid in valid_ids:
    name, side = label_for_component(cid)
    key = f"{name}_{side}"
    component_mask = (labels_map == cid).astype(np.uint8) * 255
    group_masks[key] = cv2.bitwise_or(group_masks[key], component_mask)

print(f"合并后共 {len(group_masks)} 个肌肉组")

# ── 5. 输出 SVG ────────────────────────────────────────────────────────────
def mask_to_svg_paths(mask_bin, color="#1a3a6b"):
    """从二值 mask 提取轮廓并生成 SVG path 字符串列表"""
    contours, _ = cv2.findContours(mask_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_TC89_KCOS)
    paths = []
    for cnt in contours:
        if cv2.contourArea(cnt) < 200:
            continue
        # Douglas-Peucker 简化，epsilon 越大越平滑
        epsilon = 1.5
        approx = cv2.approxPolyDP(cnt, epsilon, True)
        pts = approx.reshape(-1, 2)
        if len(pts) < 3:
            continue
        d = "M " + " L ".join(f"{x},{y}" for x, y in pts) + " Z"
        paths.append(d)
    return paths

# 整体尺寸（与原图等比）
SCALE = 2.0  # 放大倍数，让SVG更清晰

for key, m in group_masks.items():
    name = key.rsplit("_", 1)[0]
    # 裁剪到有内容的边界框并加一点 padding
    ys, xs = np.where(m > 0)
    if len(xs) == 0:
        continue
    pad = 10
    x0 = max(0, xs.min() - pad)
    y0 = max(0, ys.min() - pad)
    x1 = min(w, xs.max() + pad)
    y1 = min(h, ys.max() + pad)
    crop_w = x1 - x0
    crop_h = y1 - y0

    # 裁剪 mask 并重新找轮廓
    crop_mask = m[y0:y1, x0:x1]
    contours, _ = cv2.findContours(crop_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_TC89_KCOS)

    svg_w = crop_w * SCALE
    svg_h = crop_h * SCALE

    dwg = svgwrite.Drawing(
        str(OUT_DIR / f"{key}.svg"),
        size=(f"{svg_w}px", f"{svg_h}px"),
        viewBox=f"0 0 {svg_w} {svg_h}",
    )
    # 背景透明（默认）
    dwg.add(dwg.rect(insert=(0, 0), size=("100%", "100%"), fill="none"))

    has_path = False
    for cnt in contours:
        if cv2.contourArea(cnt) < 150:
            continue
        epsilon = 1.2
        approx = cv2.approxPolyDP(cnt, epsilon, True)
        pts = approx.reshape(-1, 2) * SCALE
        if len(pts) < 3:
            continue
        d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z"
        dwg.add(dwg.path(d=d, fill="#1e3a6e", stroke="#0a1f40", stroke_width=1.0, fill_opacity=0.92))
        has_path = True

    if has_path:
        # 添加标签文字
        dwg.add(dwg.text(
            name,
            insert=(svg_w / 2, svg_h - 4),
            text_anchor="middle",
            font_size="13px",
            font_family="Microsoft YaHei, SimHei, sans-serif",
            fill="#1e3a6e",
            font_weight="bold",
        ))
        dwg.save()
        print(f"  已保存: {key}.svg  ({crop_w}x{crop_h}px 原始, {int(svg_w)}x{int(svg_h)} SVG)")
    else:
        print(f"  跳过(无有效轮廓): {key}")

# ── 6. 同时输出一张总览 SVG（正反面合图）───────────────────────────────────
dwg_all = svgwrite.Drawing(
    str(OUT_DIR / "_总览.svg"),
    size=(f"{w * SCALE}px", f"{h * SCALE}px"),
    viewBox=f"0 0 {w * SCALE} {h * SCALE}",
)
dwg_all.add(dwg_all.rect(insert=(0, 0), size=("100%", "100%"), fill="#f5f5f5"))

COLORS = [
    "#1e3a6e", "#2a5298", "#1565c0", "#0d47a1", "#1976d2",
    "#283593", "#3949ab", "#303f9f", "#1a237e", "#0288d1",
    "#01579b", "#006064", "#004d40", "#1b5e20", "#33691e",
]

for idx, (key, m) in enumerate(group_masks.items()):
    name = key.rsplit("_", 1)[0]
    ys, xs = np.where(m > 0)
    if len(xs) == 0:
        continue
    contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_TC89_KCOS)
    color = COLORS[idx % len(COLORS)]
    for cnt in contours:
        if cv2.contourArea(cnt) < 150:
            continue
        approx = cv2.approxPolyDP(cnt, 1.2, True)
        pts = approx.reshape(-1, 2) * SCALE
        if len(pts) < 3:
            continue
        d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z"
        dwg_all.add(dwg_all.path(d=d, fill=color, stroke="#000", stroke_width=0.5, fill_opacity=0.8))
    # 标签
    cx = int(xs.mean() * SCALE)
    cy = int(ys.mean() * SCALE)
    dwg_all.add(dwg_all.text(
        name, insert=(cx, cy),
        text_anchor="middle", dominant_baseline="middle",
        font_size="9px", font_family="Microsoft YaHei, SimHei, sans-serif",
        fill="white", font_weight="bold",
    ))

dwg_all.save()
print("\n总览 SVG 已保存: _总览.svg")
print(f"\n所有文件在: {OUT_DIR}")
