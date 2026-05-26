"""
肌群图 → 独立 SVG 矢量图
策略：
- 检测深蓝肌肉区域
- 正背面各自用 Watershed 细分
- 每块保存独立 SVG + 一张总览 SVG

图片: 963x567  前景人体: 正面 x≈119-324, 背面 x≈594-804
"""
import cv2
import numpy as np
import svgwrite
from PIL import Image
from pathlib import Path
from collections import OrderedDict

IMG_PATH = r"D:\WorkPath\fitness\肌群正反面示意图.png"
OUT_DIR  = Path(r"D:\WorkPath\fitness\muscle_svgs")
OUT_DIR.mkdir(exist_ok=True)

# 清空旧文件
for f in OUT_DIR.glob("*.svg"):
    f.unlink()

arr     = np.array(Image.open(IMG_PATH).convert("RGB"))
img_bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
h, w    = arr.shape[:2]

# ── 深蓝肌肉 mask ─────────────────────────────────────────────────────────
def make_muscle_mask(arr):
    m = (
        (arr[:,:,2].astype(int) - arr[:,:,0].astype(int) > 12) &
        (arr[:,:,2].astype(int) - arr[:,:,1].astype(int) > 10) &
        (arr[:,:,2] > 80) & (arr[:,:,0] < 180)
    ).astype(np.uint8) * 255
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k, iterations=2)
    return m

muscle_mask = make_muscle_mask(arr)

# ── Watershed 分割辅助函数 ────────────────────────────────────────────────
def watershed_segment(region_mask, seeds_xy, img_bgr, h, w):
    """
    region_mask: 二值 mask (uint8, 0/255)，仅限该区域
    seeds_xy: list of (name, x, y) 种子点
    返回: dict {name: binary_mask}
    """
    markers = np.zeros((h, w), dtype=np.int32)
    markers[region_mask == 0] = -1        # 背景

    name_list = [n for n, x, y in seeds_xy]
    for idx, (name, x, y) in enumerate(seeds_xy, start=1):
        # 找种子点附近最近的区域内像素
        found = False
        for r in range(0, 40, 3):
            if found:
                break
            for dy in range(-r, r+1, max(1, r)):
                for dx in range(-r, r+1, max(1, r)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and region_mask[ny, nx] > 0:
                        cv2.circle(markers, (nx, ny), 8, idx, -1)
                        found = True
                        break
        if not found:
            # 使用原始坐标
            cv2.circle(markers, (x, y), 8, idx, -1)

    ws_img = img_bgr.copy()
    cv2.watershed(ws_img, markers)

    result = {}
    for idx, name in enumerate(name_list, start=1):
        seg_mask = ((markers == idx) & (region_mask > 0)).astype(np.uint8) * 255
        if seg_mask.sum() > 0:
            result[name] = seg_mask
    return result

# ── 种子点定义（基于组件分析校准）────────────────────────────────────────
# 正面大区域 (bbox: 119-324, 129-267) 内的肌肉
FRONT_UPPER_SEEDS = [
    ("上胸",   220, 138),   # 胸部中上
    ("中下胸", 220, 165),   # 胸部中下
    ("前束",   140, 145),   # 左侧前束（正面左臂）
    ("中束",   305, 145),   # 右侧中束（正面右臂）
    ("二头左", 128, 215),   # 左二头肌
    ("二头右", 315, 215),   # 右二头肌
]

# 正面左下腹/腿 (bbox: 170-216, 266-392)
FRONT_LL_SEEDS = [
    ("腹部左", 193, 295),
    ("股四左", 193, 355),
]

# 正面右下腹/腿 (bbox: 227-272, 265-392)
FRONT_RL_SEEDS = [
    ("腹部右", 249, 295),
    ("股四右", 249, 355),
]

# 背面大区域-上 (bbox: 594-804, 123-265)
BACK_UPPER_SEEDS = [
    ("斜方",   700, 133),   # 斜方肌（上背中央）
    ("后束左", 618, 155),   # 左后束
    ("后束右", 783, 155),   # 右后束
    ("背部",   700, 210),   # 背阔肌/竖脊肌
]

# 背面大区域-下 (bbox: 649-749, 266-408)
BACK_LOWER_SEEDS = [
    ("臀部",   699, 305),
    ("腘绳",   699, 370),
]

# 独立小组件（直接用整个组件）
STANDALONE = [
    # 正面小肩部突起
    ("外侧束", "front", 80,  105, (66,  94, 92, 116)),
    ("中束外", "front", 390, 126, (364, 115, 409, 138)),
    # 正面小腿(文字装饰区域，可能是小腿肌)
    ("小腿",   "front",  43, 489, (20,  479, 67, 501)),
    # 背面右侧三头 / 小腿
    ("三头右", "back",  875, 181, (852, 171, 897, 193)),
    ("臀部右", "back",  875, 322, (851, 312, 897, 335)),
    ("小腿背", "back",  875, 487, (851, 476, 897, 499)),
]

# ── 区域 mask ────────────────────────────────────────────────────────────
def region_mask_from_bbox(base_mask, x0, y0, x1, y1, dilate=5):
    m = np.zeros_like(base_mask)
    m[y0:y1, x0:x1] = base_mask[y0:y1, x0:x1]
    if dilate > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate, dilate))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k, iterations=2)
    return m

# 从组件统计获取正面/背面各大区域的精确 mask
def get_component_mask(full_mask, cx_approx, cy_approx, x_start, x_end):
    """提取在 x_start..x_end 范围内、距 (cx_approx,cy_approx) 最近的最大连通分量"""
    cropped = full_mask.copy()
    cropped[:, :x_start] = 0
    cropped[:, x_end:]   = 0
    n, lm, stats, centroids = cv2.connectedComponentsWithStats(cropped, connectivity=8)
    best_id, best_d = -1, float("inf")
    for i in range(1, n):
        if stats[i, 4] < 200:
            continue
        cx, cy = centroids[i]
        d = (cx - cx_approx)**2 + (cy - cy_approx)**2
        if d < best_d:
            best_d = d
            best_id = i
    if best_id == -1:
        return np.zeros_like(full_mask)
    return (lm == best_id).astype(np.uint8) * 255

front_upper_m = get_component_mask(muscle_mask, 220, 181, 80, 430)
front_ll_m    = get_component_mask(muscle_mask, 193, 332, 80, 430)
front_rl_m    = get_component_mask(muscle_mask, 249, 332, 80, 430)
back_upper_m  = get_component_mask(muscle_mask, 699, 192, 530, 870)
back_lower_m  = get_component_mask(muscle_mask, 698, 328, 530, 870)

# ── 运行 Watershed 分割 ────────────────────────────────────────────────────
print("Running watershed segmentation...")
segments = {}
segments.update(watershed_segment(front_upper_m, FRONT_UPPER_SEEDS, img_bgr, h, w))
segments.update(watershed_segment(front_ll_m,    FRONT_LL_SEEDS,    img_bgr, h, w))
segments.update(watershed_segment(front_rl_m,    FRONT_RL_SEEDS,    img_bgr, h, w))
segments.update(watershed_segment(back_upper_m,  BACK_UPPER_SEEDS,  img_bgr, h, w))
segments.update(watershed_segment(back_lower_m,  BACK_LOWER_SEEDS,  img_bgr, h, w))

# 合并左右对称肌肉
def merge_lr(segments, base_name, left_name, right_name):
    lm = segments.pop(left_name,  None)
    rm = segments.pop(right_name, None)
    if lm is not None and rm is not None:
        segments[base_name] = cv2.bitwise_or(lm, rm)
    elif lm is not None:
        segments[base_name] = lm
    elif rm is not None:
        segments[base_name] = rm

merge_lr(segments, "腹部",   "腹部左",  "腹部右")
merge_lr(segments, "股四",   "股四左",  "股四右")
merge_lr(segments, "前束",   "前束",    "中束")    # 保留各自
merge_lr(segments, "二头",   "二头左",  "二头右")
merge_lr(segments, "后束",   "后束左",  "后束右")

# 加入独立小组件
for name, side, sx, sy, (bx0, by0, bx1, by1) in STANDALONE:
    m = region_mask_from_bbox(muscle_mask, bx0, by0, bx1, by1, dilate=3)
    if m.sum() > 0:
        segments[name] = m

# ── 保存每块 SVG ──────────────────────────────────────────────────────────
SCALE = 2.5
PAD   = 14
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

saved = []
for name, seg_mask in segments.items():
    seg_mask = cv2.morphologyEx(seg_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    ys, xs = np.where(seg_mask > 0)
    if len(xs) == 0:
        print(f"  [skip-empty] {name}")
        continue

    x0 = max(0, int(xs.min()) - PAD)
    y0 = max(0, int(ys.min()) - PAD)
    x1 = min(w, int(xs.max()) + PAD)
    y1 = min(h, int(ys.max()) + PAD)
    crop_w, crop_h = x1 - x0, y1 - y0

    crop = seg_mask[y0:y1, x0:x1]
    contours, _ = cv2.findContours(crop, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_TC89_KCOS)

    svg_w, svg_h = crop_w * SCALE, crop_h * SCALE
    fname = f"{name}.svg"
    dwg = svgwrite.Drawing(
        str(OUT_DIR / fname),
        size=(f"{svg_w:.0f}px", f"{svg_h:.0f}px"),
        viewBox=f"0 0 {svg_w:.0f} {svg_h:.0f}",
    )
    dwg.add(dwg.rect(insert=(0,0), size=("100%","100%"), fill="none"))

    has_path = False
    for cnt in contours:
        if cv2.contourArea(cnt) < 80:
            continue
        approx = cv2.approxPolyDP(cnt, 1.2, True)
        pts = approx.reshape(-1, 2) * SCALE
        if len(pts) < 3:
            continue
        d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z"
        dwg.add(dwg.path(
            d=d, fill="#1e3a6e", stroke="#0a1f40",
            stroke_width=1.5, fill_opacity=0.9,
        ))
        has_path = True

    if has_path:
        dwg.add(dwg.text(
            name,
            insert=(svg_w / 2, svg_h - 4),
            text_anchor="middle",
            font_size="15px",
            font_family="Microsoft YaHei, SimHei, sans-serif",
            fill="#1e3a6e", font_weight="bold",
        ))
        dwg.save()
        area = int(seg_mask.sum() / 255)
        print(f"  Saved: {fname}  ({crop_w}x{crop_h}px  area={area})")
        saved.append((name, seg_mask, x0, y0, x1, y1))
    else:
        print(f"  [no-contour] {name}")

# ── 总览 SVG ──────────────────────────────────────────────────────────────
OVERVIEW_COLORS = [
    "#e74c3c","#3498db","#2ecc71","#f39c12","#9b59b6",
    "#1abc9c","#e67e22","#2980b9","#c0392b","#16a085",
    "#8e44ad","#27ae60","#d35400","#2c3e50","#7f8c8d",
    "#f1c40f","#95a5a6","#34495e",
]

dwg_all = svgwrite.Drawing(
    str(OUT_DIR / "_总览.svg"),
    size=(f"{w*2}px", f"{h*2}px"),
    viewBox=f"0 0 {w*2} {h*2}",
)
dwg_all.add(dwg_all.rect(insert=(0,0), size=("100%","100%"), fill="#f0f4f8"))

for idx, (name, seg_mask, *_) in enumerate(saved):
    seg_mask_c = cv2.morphologyEx(seg_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(seg_mask_c, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_TC89_KCOS)
    color = OVERVIEW_COLORS[idx % len(OVERVIEW_COLORS)]
    all_pts = []
    for cnt in contours:
        if cv2.contourArea(cnt) < 80:
            continue
        approx = cv2.approxPolyDP(cnt, 1.2, True)
        pts = approx.reshape(-1, 2) * 2
        if len(pts) < 3:
            continue
        d = "M " + " L ".join(f"{x:.0f},{y:.0f}" for x, y in pts) + " Z"
        dwg_all.add(dwg_all.path(d=d, fill=color, stroke="#333",
                                  stroke_width=1.0, fill_opacity=0.8))
        all_pts.extend(pts.tolist())
    if all_pts:
        pts_arr = np.array(all_pts)
        cx = int(pts_arr[:,0].mean())
        cy = int(pts_arr[:,1].mean())
        dwg_all.add(dwg_all.text(name, insert=(cx, cy),
            text_anchor="middle", dominant_baseline="middle",
            font_size="11px", font_family="Microsoft YaHei, SimHei, sans-serif",
            fill="white", font_weight="bold",
            style="text-shadow: 1px 1px 2px #000;"))

dwg_all.save()
print(f"\n{'='*50}")
print(f"Total saved: {len(saved)} muscle SVGs")
print(f"Output: {OUT_DIR}")
print(f"  + _总览.svg (overview)")
