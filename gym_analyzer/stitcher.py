"""
stitcher.py - 关键帧拼图模块

将 list[FrameMeta] 按 frames_per_grid 张一组拼成网格大图。
每帧左下角叠加 MM:SS 时间戳。
画布宽高均不超过 max_dim（默认 3028）。

布局：
  每 cell = 280×158
  max_cols = floor(3028 / 280) = 10 (实际固定 7 列)
  60帧 → 7列×9行 → 1960×1422
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np

from .extractor import FrameMeta


# ──────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────

CELL_W = 280
CELL_H = 158
FRAMES_PER_GRID = 60
MAX_DIM = 3028
JPEG_QUALITY = 60

# 时间戳文字样式
FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 0.45
FONT_THICKNESS = 1
OUTLINE_THICKNESS = 3
TEXT_COLOR = (255, 255, 255)      # 白色
OUTLINE_COLOR = (0, 0, 0)         # 黑色描边

# 固定列数
GRID_COLS = 7


# ──────────────────────────────────────────────
# 数据类
# ──────────────────────────────────────────────

@dataclass
class GridMeta:
    grid_index: int       # 第几张拼图（0-based）
    path: str             # 拼图文件路径（相对于 output_dir）
    time_start: float     # 该拼图第一帧时间戳（秒）
    time_end: float       # 该拼图最后一帧时间戳（秒）
    frame_indices: list   # 包含的 FrameMeta.index 列表
    cols: int = 0         # 实际列数
    rows: int = 0         # 实际行数


# ──────────────────────────────────────────────
# 工具函数（对外导出）
# ──────────────────────────────────────────────

def sec_to_mmss(sec: float) -> str:
    """将秒数转为 MM:SS 字符串。"""
    s = int(sec)
    return f"{s // 60:02d}:{s % 60:02d}"


def sec_to_hhmmss(sec: float) -> str:
    """将秒数转为 HH:MM:SS 字符串。"""
    s = int(sec)
    h, rem = divmod(s, 3600)
    m, sec_part = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec_part:02d}"


def mmss_to_sec(t: str) -> float:
    """MM:SS 或 HH:MM:SS → 秒数。"""
    parts = t.strip().split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(parts[0])


# ──────────────────────────────────────────────
# 内部工具
# ──────────────────────────────────────────────

def _compute_layout(n: int, cols: int = GRID_COLS) -> tuple[int, int]:
    """计算 (cols, rows)。列数固定，行数自动。"""
    cols = min(cols, n)
    rows = math.ceil(n / cols)
    return cols, rows


def _imread_unicode(path: str) -> np.ndarray | None:
    buf = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def _imwrite_unicode(path: str, img: np.ndarray, quality: int = JPEG_QUALITY) -> None:
    encode_param = [cv2.IMWRITE_JPEG_QUALITY, quality]
    ok, buf = cv2.imencode(".jpg", img, encode_param)
    if ok:
        buf.tofile(path)


def _draw_timestamp(cell: np.ndarray, text: str) -> np.ndarray:
    """在 cell 左下角绘制带黑色描边的白色时间戳。"""
    h, w = cell.shape[:2]
    x = 4
    y = h - 6
    cv2.putText(cell, text, (x, y), FONT, FONT_SCALE,
                OUTLINE_COLOR, OUTLINE_THICKNESS, cv2.LINE_AA)
    cv2.putText(cell, text, (x, y), FONT, FONT_SCALE,
                TEXT_COLOR, FONT_THICKNESS, cv2.LINE_AA)
    return cell


def _resolve_frame_path(fm: FrameMeta, frames_dir: Path, output_dir: Path) -> Path:
    """尝试多种路径解析策略找到帧图片。"""
    # 尝试直接从 frames_dir
    name = Path(fm.path).name
    p = frames_dir / name
    if p.exists():
        return p
    # 尝试去掉 frames/ 前缀
    clean = fm.path.replace("frames/", "").replace("frames\\", "")
    p = frames_dir / clean
    if p.exists():
        return p
    # 尝试 output_dir / path
    p = output_dir / fm.path
    if p.exists():
        return p
    return frames_dir / name   # 返回最可能的路径，让后续报错


# ──────────────────────────────────────────────
# 核心函数：构建单张网格（返回 bytes）
# ──────────────────────────────────────────────

def build_grid_bytes(
    metas: list[FrameMeta],
    frames_dir: Path,
    output_dir: Path | None = None,
    cols: int = GRID_COLS,
) -> tuple[bytes, int, int]:
    """
    将帧列表拼成一张网格大图，返回 (JPEG bytes, cols, rows)。
    不保存文件，用于直接发送给 LLM。
    """
    if not metas:
        raise ValueError("metas 为空")

    if output_dir is None:
        output_dir = frames_dir.parent

    n = len(metas)
    cols, rows = _compute_layout(n, cols)
    canvas_w = cols * CELL_W
    canvas_h = rows * CELL_H
    canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)

    for i, fm in enumerate(metas):
        row, col = divmod(i, cols)
        x0, y0 = col * CELL_W, row * CELL_H

        img_path = _resolve_frame_path(fm, frames_dir, output_dir)
        cell = _imread_unicode(str(img_path))

        if cell is None:
            cell = np.full((CELL_H, CELL_W, 3), 80, dtype=np.uint8)
        else:
            cell = cv2.resize(cell, (CELL_W, CELL_H), interpolation=cv2.INTER_AREA)

        label = sec_to_mmss(fm.timestamp)
        _draw_timestamp(cell, label)

        canvas[y0:y0 + CELL_H, x0:x0 + CELL_W] = cell

    encode_param = [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
    ok, buf = cv2.imencode(".jpg", canvas, encode_param)
    if not ok:
        raise RuntimeError("JPEG 编码失败")

    return bytes(buf), cols, rows


# ──────────────────────────────────────────────
# Phase 1 用：按窗口拼图并保存
# ──────────────────────────────────────────────

def stitch_phase1_grids(
    metas: list[FrameMeta],
    output_dir: str | Path,
    frames_dir: str | Path | None = None,
    window_sec: int = FRAMES_PER_GRID,
    overwrite: bool = False,
) -> list[dict]:
    """
    将帧按 window_sec 秒分窗口，每窗口一张拼图保存到 mid_result/。

    Returns:
        list[dict]，每个 dict：
          grid_index, path, jpeg_bytes, time_start, time_end,
          frame_count, cols, rows
    """
    output_dir = Path(output_dir)
    frames_dir = Path(frames_dir) if frames_dir else output_dir / "frames"
    mid_dir = output_dir / "mid_result"
    mid_dir.mkdir(parents=True, exist_ok=True)

    # 按 window_sec 分窗口（1fps 所以帧数 == 秒数）
    windows = [metas[i:i + window_sec]
               for i in range(0, len(metas), window_sec)]

    print(f"[stitcher] Phase1 拼图：{len(metas)} 帧 → {len(windows)} 个窗口"
          f"（每窗 {window_sec}s，{GRID_COLS} 列）")

    results: list[dict] = []
    for g_idx, batch in enumerate(windows):
        jpeg_bytes, cols, rows = build_grid_bytes(
            batch, frames_dir, output_dir, cols=GRID_COLS)

        fname = f"phase1_window_{g_idx + 1:03d}.jpg"
        fpath = mid_dir / fname
        fpath.write_bytes(jpeg_bytes)

        gm = {
            "grid_index": g_idx,
            "path": str(fpath),
            "jpeg_bytes": jpeg_bytes,
            "time_start": batch[0].timestamp,
            "time_end": batch[-1].timestamp,
            "frame_count": len(batch),
            "cols": cols,
            "rows": rows,
        }
        results.append(gm)

        print(f"[stitcher]   窗口 {g_idx + 1:03d}  "
              f"{sec_to_mmss(gm['time_start'])} → {sec_to_mmss(gm['time_end'])}  "
              f"({len(batch)} 帧)  {cols}×{rows}  "
              f"{len(jpeg_bytes) / 1024:.0f} KB")

    return results


# ──────────────────────────────────────────────
# Phase 2 用：对指定时间窗口拼图
# ──────────────────────────────────────────────

def stitch_exercise_grid(
    metas: list[FrameMeta],
    frames_dir: Path,
    output_dir: Path,
    start_sec: float,
    end_sec: float,
    seg_id: str = "",
) -> tuple[bytes, int, int, int] | None:
    """
    截取 [start_sec, end_sec] 范围内的帧并拼图。

    Returns:
        (jpeg_bytes, cols, rows, frame_count)  或 None
    """
    window_metas = [fm for fm in metas if start_sec - 0.5 <= fm.timestamp <= end_sec + 0.5]
    if not window_metas:
        print(f"[stitcher] 警告：窗口 {sec_to_mmss(start_sec)}→{sec_to_mmss(end_sec)} 内无帧")
        return None

    jpeg_bytes, cols, rows = build_grid_bytes(
        window_metas, frames_dir, output_dir, cols=GRID_COLS)

    print(f"    [{seg_id}] 拼图: {len(window_metas)} 帧, "
          f"{cols}×{rows}, {len(jpeg_bytes) / 1024:.0f} KB")

    return jpeg_bytes, cols, rows, len(window_metas)


# ──────────────────────────────────────────────
# Phase 2 YOLO 对比实验：YOLO 标注后拼图
# ──────────────────────────────────────────────

def stitch_exercise_grid_yolo(
    metas: list[FrameMeta],
    frames_dir: Path,
    output_dir: Path,
    start_sec: float,
    end_sec: float,
    seg_id: str = "",
    save_dir: Path | None = None,
) -> tuple[bytes, int, int, int, float] | None:
    """
    截取 [start_sec, end_sec] 范围帧，经 YOLO 手部+器材标注后拼图。

    Args:
        save_dir: 保存标注拼图的目录（graph_yolo）

    Returns:
        (jpeg_bytes, cols, rows, frame_count, yolo_elapsed_sec) 或 None
    """
    import time as _time
    from .yolo_annotator import annotate_frame

    window_metas = [fm for fm in metas if start_sec - 0.5 <= fm.timestamp <= end_sec + 0.5]
    if not window_metas:
        print(f"[stitcher-yolo] 警告：窗口 {sec_to_mmss(start_sec)}→{sec_to_mmss(end_sec)} 内无帧")
        return None

    n = len(window_metas)
    cols, rows = _compute_layout(n, GRID_COLS)
    canvas_w = cols * CELL_W
    canvas_h = rows * CELL_H
    canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)

    yolo_start = _time.time()

    for i, fm in enumerate(window_metas):
        row, col = divmod(i, cols)
        x0, y0 = col * CELL_W, row * CELL_H

        img_path = _resolve_frame_path(fm, frames_dir, output_dir)
        cell = _imread_unicode(str(img_path))

        if cell is None:
            cell = np.full((CELL_H, CELL_W, 3), 80, dtype=np.uint8)
        else:
            cell = annotate_frame(cell, img_path=str(img_path))
            cell = cv2.resize(cell, (CELL_W, CELL_H), interpolation=cv2.INTER_AREA)

        label = sec_to_mmss(fm.timestamp)
        _draw_timestamp(cell, label)
        canvas[y0:y0 + CELL_H, x0:x0 + CELL_W] = cell

    yolo_elapsed = _time.time() - yolo_start

    encode_param = [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
    ok, buf = cv2.imencode(".jpg", canvas, encode_param)
    if not ok:
        raise RuntimeError("JPEG 编码失败")
    jpeg_bytes = bytes(buf)

    if save_dir is not None:
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        fname = f"yolo_{seg_id}.jpg" if seg_id else "yolo_grid.jpg"
        save_path = save_dir / fname
        save_path.write_bytes(jpeg_bytes)
        print(f"    [{seg_id}] YOLO 拼图已保存: {save_path}")

    print(f"    [{seg_id}] YOLO 拼图: {n} 帧, "
          f"{cols}×{rows}, {len(jpeg_bytes) / 1024:.0f} KB, "
          f"YOLO 耗时 {yolo_elapsed:.1f}s")

    return jpeg_bytes, cols, rows, n, yolo_elapsed
