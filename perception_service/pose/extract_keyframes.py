"""
extract_keyframes.py
--------------------
按固定时间间隔从视频中截取关键帧。

规则：
- 视频目录：VIDEO_DIR
- 间隔：INTERVAL 秒（默认 0.5s，即每秒 2 帧）
- 格式：JPEG，自适应压缩至 MAX_SIZE_KB 以内
- 命名：state{N}_yyyy-mm-dd_hh-mm-ss.jpg
  * 时间戳 = 视频文件的「修改时间」+ N*INTERVAL 偏移
- 输出：FRAMES_DIR / {视频名（不含扩展名）} /

用法：
    python extract_keyframes.py           # 处理 video/ 下所有视频
    python extract_keyframes.py 5_26.mp4  # 只处理指定视频
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

import cv2

# ── 配置 ──────────────────────────────────────────────
SCRIPT_DIR  = Path(__file__).parent
VIDEO_DIR   = Path(r"D:\WorkPath\fitness\video")
FRAMES_DIR  = VIDEO_DIR / "frames"   # 抽帧输出根目录
INTERVAL    = 0.5                    # 截帧间隔（秒），0.5s = 每秒 2 帧
MAX_SIZE_KB = 30                     # 单帧 JPEG 最大体积（KB）
VIDEO_EXTS  = {".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".m4v", ".ts", ".qt"}
# ─────────────────────────────────────────────────────


def get_video_duration(cap: cv2.VideoCapture) -> float:
    """返回视频总时长（秒）"""
    fps         = cap.get(cv2.CAP_PROP_FPS) or 25
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    return frame_count / fps


def encode_jpg(frame, max_kb: int = MAX_SIZE_KB) -> bytes | None:
    """将帧编码为 JPEG，使文件 <= max_kb KB。
    策略：先二分搜索 JPEG 质量（5-95）；若最低质量仍超限，
    则依次缩小分辨率（75% / 50% / 25%）后重试。
    返回字节数据，失败返回 None。
    """
    limit = max_kb * 1024

    for scale in (1.0, 0.75, 0.5, 0.25):
        if scale < 1.0:
            h, w = frame.shape[:2]
            f = cv2.resize(frame, (int(w * scale), int(h * scale)),
                           interpolation=cv2.INTER_AREA)
        else:
            f = frame

        lo, hi = 5, 95
        best_buf = None
        while lo <= hi:
            mid = (lo + hi) // 2
            ok, buf = cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, mid])
            if not ok:
                return None
            if len(buf) <= limit:
                best_buf = buf      # 记录满足条件的最高质量
                lo = mid + 1        # 尝试更高质量
            else:
                hi = mid - 1        # 体积超标，降低质量

        if best_buf is not None:
            return best_buf.tobytes()

    return None  # 极端情况：即使 25% 分辨率 + 最低质量仍超限


def extract_frames(video_path: Path) -> None:
    """对单个视频文件提取关键帧并保存为 JPEG"""
    out_dir = FRAMES_DIR / video_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    # 以视频文件的修改时间作为"起始时刻"
    mtime      = video_path.stat().st_mtime
    start_time = datetime.fromtimestamp(mtime)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"  [错误] 无法打开视频：{video_path.name}")
        return

    duration = get_video_duration(cap)
    fps      = cap.get(cv2.CAP_PROP_FPS) or 25

    print(f"  时长：{duration:.1f}s  |  FPS：{fps:.2f}  |  起始时间：{start_time:%Y-%m-%d %H:%M:%S}")

    frame_num = 1
    t_sec     = 0.0

    while t_sec < duration:
        target_frame = int(t_sec * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)

        ret, frame = cap.read()
        if not ret:
            break

        ts       = start_time + timedelta(seconds=t_sec)
        filename = f"state{frame_num}_{ts:%Y-%m-%d_%H-%M-%S}.jpg"
        out_path = out_dir / filename

        data = encode_jpg(frame)
        if data is None:
            print(f"  [{frame_num:>5}] 编码失败，跳过：{filename}")
        else:
            out_path.write_bytes(data)
            kb = len(data) / 1024
            print(f"  [{frame_num:>5}] {filename}  ({kb:.1f} KB)")

        frame_num += 1
        t_sec     += INTERVAL

    cap.release()
    print(f"  完成，共 {frame_num - 1} 帧 -> {out_dir}")


def main() -> None:
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    if not VIDEO_DIR.exists():
        print(f"[错误] 视频目录不存在：{VIDEO_DIR}")
        sys.exit(1)

    if len(sys.argv) > 1:
        targets = [VIDEO_DIR / name for name in sys.argv[1:]]
    else:
        targets = sorted(
            [f for f in VIDEO_DIR.iterdir() if f.suffix.lower() in VIDEO_EXTS]
        )

    if not targets:
        print("未找到视频文件。")
        sys.exit(0)

    for video_path in targets:
        if not video_path.exists():
            print(f"[跳过] 文件不存在：{video_path}")
            continue
        print(f"\n[处理] {video_path.name}")
        extract_frames(video_path)

    print("\n全部完成！")


if __name__ == "__main__":
    main()
