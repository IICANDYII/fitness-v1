"""
Watershed + 种子点方法分割肌肉区域 → 每块输出 SVG
图片尺寸: 963x567
"""
import cv2
import numpy as np
import svgwrite
from PIL import Image
from pathlib import Path

IMG_PATH = r"D:\WorkPath\fitness\肌群正反面示意图.png"
OUT_DIR = Path(r"D:\WorkPath\fitness\muscle_svgs")
OUT_DIR.mkdir(exist_ok=True)

pil_img = Image.open(IMG_PATH).convert("RGB")
arr = np.array(pil_img)
img_bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
h, w = arr.shape[:2]

# ── 1. 体型轮廓 mask（去掉纯白背景和黑色文字）─────────────────────────────
bg_mask  = (arr[:,:,0] > 248) & (arr[:,:,1] > 248) & (arr[:,:,2] > 248)
txt_mask = (arr[:,:,0] <  80) & (arr[:,:,1] <  80) & (arr[:,:,2] <  80)
body_mask = (~bg_mask & ~txt_mask).astype(np.uint8) * 255

kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
body_mask = cv2.morphologyEx(body_mask, cv2.MORPH_CLOSE, kernel, iterations=3)
body_mask = cv2.morphologyEx(body_mask, cv2.MORPH_OPEN,  kernel, iterations=1)

# ── 2. 深蓝肌肉 mask（用于最终 SVG 输出）──────────────────────────────────
muscle_mask = (
    (arr[:,:,2].astype(int) - arr[:,:,0].astype(int) > 12) &
    (arr[:,:,2].astype(int) - arr[:,:,1].astype(int) > 10) &
    (arr[:,:,2] > 80) & (arr[:,:,0] < 180)
).astype(np.uint8) * 255
muscle_mask = cv2.morphologyEx(muscle_mask, cv2.MORPH_CLOSE, kernel, iterations=2)

# ── 3. 种子点定义（在 963x567 图中的像素坐标）────────────────────────────
# 根据图片实际位置校准（正面人体中心≈x240，背面人体中心≈x700）
MUSCLES = [
    # --- 正面 ---
    ("上胸",   "front",  228, 112),
    ("中下胸", "front",  235, 158),
    ("前束",   "front",  152, 108),
    ("中束",   "front",  300,  95),  # 三角肌中束（正面右侧）
    ("二头",   "front",  128, 198),
    ("小臂",   "front",  122, 268),
    ("腹部",   "front",  235, 260),
    ("股四",   "front",  228, 390),
    ("小腿",   "front",  225, 490),
    # --- 背面 ---
    ("斜方",   "back",   700,  90),
    ("后束",   "back",   668, 145),
    ("三头",   "back",   618, 210),
    ("背部",   "back",   700, 238),
    ("臀部",   "back",   700, 330),
    ("腘绳",   "back",   700, 415),
    ("小腿背", "back",   700, 490),
]

# ── 4. Watershed 分割 ──────────────────────────────────────────────────────
markers = np.zeros((h, w), dtype=np.int32)
markers[body_mask == 0] = -1          # 背景标记为 -1（不参与 watershed）

for idx, (name, side, x, y) in enumerate(MUSCLES, start=1):
    if 0 <= y < h and 0 <= x < w:
        cv2.circle(markers, (x, y), 10, idx, -1)

img_ws = img_bgr.copy()
cv2.watershed(img_ws, markers)

# watershed 边界处 markers == -1（被覆盖），还原为背景
# 原始背景已经是 -1，watershed 的边界也是 -1，用 body_mask 区分
segment_map = markers.copy()

# ── 5. 调试：保存分割示意图 ────────────────────────────────────────────────
palette = [
    (31,119,180),(255,127,14),(44,160,44),(214,39,40),(148,103,189),
    (140,86,75),(227,119,194),(127,127,127),(188,189,34),(23,190,207),
    (174,199,232),(255,187,120),(152,223,138),(255,152,150),(197,176,213),
    (196,156,148),(247,182,210),(199,199,199),(219,219,141),(158,218,229),
]
debug = np.ones((h, w, 3), dtype=np.uint8) * 240
for idx, (name, side, x, y) in enumerate(MUSCLES, start=1):
    color = palette[(idx-1) % len(palette)]
    region = (segment_map == idx)
    debug[region] = color
    if region.any():
        ys, xs = np.where(region)
        cx, cy = int(xs.mean()), int(ys.mean())
        cv2.putText(debug, name, (cx-20, cy), cv2.FONT_HERSHEY_SIMPLEX,
                    0.4, (0,0,0), 1, cv2.LINE_AA)
cv2.imwrite(str(OUT_DIR / "_debug_watershed.png"), debug)
print(f"Watershed debug saved")

# ── 6. 每块肌肉：只用深蓝 mask 与 watershed region 取交集 → SVG ───────────
SCALE = 2.0
PAD = 12

saved = 0
for idx, (name, side, sx, sy) in enumerate(MUSCLES, start=1):
    # 该肌肉的 watershed 区域
    ws_region = (segment_map == idx).astype(np.uint8)

    # 与深蓝肌肉 mask 取交集，突出显示实际肌肉形状
    combined = cv2.bitwise_and(ws_region * 255, muscle_mask)

    # 若交集太小，直接用 watershed 区域（有些肌肉颜色较浅）
    if combined.sum() < 3000:
        combined = ws_region * 255

    # 形态学平滑
    combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel, iterations=2)

    ys, xs = np.where(combined > 0)
    if len(xs) == 0:
        print(f"  Skip (empty): {name}")
        continue

    x0 = max(0, int(xs.min()) - PAD)
    y0 = max(0, int(ys.min()) - PAD)
    x1 = min(w, int(xs.max()) + PAD)
    y1 = min(h, int(ys.max()) + PAD)
    crop_w, crop_h = x1 - x0, y1 - y0

    crop_mask = combined[y0:y1, x0:x1]
    contours, _ = cv2.findContours(crop_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_TC89_KCOS)

    svg_w, svg_h = crop_w * SCALE, crop_h * SCALE
    fname = f"{side}_{idx:02d}_{name}.svg"
    dwg = svgwrite.Drawing(str(OUT_DIR / fname),
                           size=(f"{svg_w}px", f"{svg_h}px"),
                           viewBox=f"0 0 {svg_w} {svg_h}")
    dwg.add(dwg.rect(insert=(0,0), size=("100%","100%"), fill="none"))

    has_path = False
    for cnt in contours:
        if cv2.contourArea(cnt) < 100:
            continue
        approx = cv2.approxPolyDP(cnt, 1.5, True)
        pts = approx.reshape(-1, 2) * SCALE
        if len(pts) < 3:
            continue
        d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x,y in pts) + " Z"
        dwg.add(dwg.path(d=d, fill="#1e3a6e", stroke="#0a1f40",
                         stroke_width=1.5, fill_opacity=0.9))
        has_path = True

    if has_path:
        # 标签文字
        dwg.add(dwg.text(name,
            insert=(svg_w/2, svg_h - 5),
            text_anchor="middle",
            font_size="14px",
            font_family="Microsoft YaHei, SimHei, sans-serif",
            fill="#1e3a6e", font_weight="bold"))
        dwg.save()
        area_px = int(combined.sum() / 255)
        print(f"  Saved: {fname}  ({crop_w}x{crop_h}px, area={area_px}px)")
        saved += 1
    else:
        print(f"  No contour: {name}")

# ── 7. 总览 SVG（正反面合并）──────────────────────────────────────────────
dwg_all = svgwrite.Drawing(str(OUT_DIR / "_总览.svg"),
    size=(f"{w*SCALE}px", f"{h*SCALE}px"),
    viewBox=f"0 0 {w*SCALE} {h*SCALE}")
dwg_all.add(dwg_all.rect(insert=(0,0), size=("100%","100%"), fill="#f8f8f8"))

COLORS_SVG = ["#1e3a6e","#2a5298","#c0392b","#16a085","#8e44ad",
               "#e67e22","#2980b9","#27ae60","#d35400","#7f8c8d",
               "#1abc9c","#e74c3c","#3498db","#f39c12","#9b59b6","#2ecc71"]

for idx, (name, side, sx, sy) in enumerate(MUSCLES, start=1):
    ws_region = (segment_map == idx).astype(np.uint8)
    combined = cv2.bitwise_and(ws_region * 255, muscle_mask)
    if combined.sum() < 3000:
        combined = ws_region * 255
    combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel, iterations=2)

    ys, xs = np.where(combined > 0)
    if len(xs) == 0:
        continue

    contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_TC89_KCOS)
    color = COLORS_SVG[(idx-1) % len(COLORS_SVG)]
    for cnt in contours:
        if cv2.contourArea(cnt) < 100:
            continue
        approx = cv2.approxPolyDP(cnt, 1.5, True)
        pts = approx.reshape(-1, 2) * SCALE
        if len(pts) < 3:
            continue
        d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x,y in pts) + " Z"
        dwg_all.add(dwg_all.path(d=d, fill=color, stroke="#000",
                                  stroke_width=0.8, fill_opacity=0.75))

    cx = int(xs.mean() * SCALE)
    cy = int(ys.mean() * SCALE)
    dwg_all.add(dwg_all.text(name, insert=(cx, cy),
        text_anchor="middle", dominant_baseline="middle",
        font_size="11px", font_family="Microsoft YaHei, SimHei, sans-serif",
        fill="white", font_weight="bold"))

dwg_all.save()
print(f"\nTotal SVGs saved: {saved}")
print(f"Overview SVG: _总览.svg")
print(f"Output dir: {OUT_DIR}")
