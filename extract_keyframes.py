"""
extract_keyframes.py
--------------------
按固定时间间隔从视频中截取关键帧。

规则：
- 视频目录：VIDEO_DIR（脚本同级的 video/ 文件夹）
- 间隔：INTERVAL 秒（默认 10s）
- 命名：state{N}_yyyy-mm-dd_hh-mm-ss.png
  * 时间戳 = 视频文件的「修改时间」+ N*INTERVAL 偏移
- 输出：VIDEO_DIR / {视频名（不含扩展名）} /

用法：
    python extract_keyframes.py           # 处理 video/ 下所有视频
    python extract_keyframes.py 卷饼.mp4  # 只处理指定视频
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

import cv2

# ── 配置 ──────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
VIDEO_DIR  = SCRIPT_DIR / "video"
INTERVAL   = 3           # 截帧间隔（秒），约 0.33fps
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".m4v", ".ts"}
# ─────────────────────────────────────────────────────


def get_video_duration(cap: cv2.VideoCapture) -> float:
    """返回视频总时长（秒）"""
    fps        = cap.get(cv2.CAP_PROP_FPS) or 25
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    return frame_count / fps


def extract_frames(video_path: Path) -> None:
    """对单个视频文件提取关键帧"""
    # 输出目录：video/{视频名}/
    out_dir = VIDEO_DIR / video_path.stem
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
    t_sec     = 0.0          # 当前截帧位置（秒）

    while t_sec < duration:
        # 跳转到目标帧
        target_frame = int(t_sec * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)

        ret, frame = cap.read()
        if not ret:
            break

        # 计算该帧对应的"现实时间戳"
        ts       = start_time + timedelta(seconds=t_sec)
        filename = f"state{frame_num}_{ts:%Y-%m-%d_%H-%M-%S}.png"
        out_path = out_dir / filename

        # cv2.imwrite 在 Windows 上不支持中文路径，改用 imencode + write_bytes
        ok, buf = cv2.imencode('.png', frame)
        if not ok:
            print(f"  [{frame_num:>4}] 编码失败，跳过：{filename}")
        else:
            out_path.write_bytes(buf.tobytes())
            print(f"  [{frame_num:>4}] {filename}")

        frame_num += 1
        t_sec     += INTERVAL

    cap.release()
    print(f"  完成，共 {frame_num - 1} 帧 → {out_dir}")


def main() -> None:
    if not VIDEO_DIR.exists():
        print(f"[错误] 视频目录不存在：{VIDEO_DIR}")
        sys.exit(1)

    # 支持命令行指定单个/多个文件名
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
        print(f"\n▶ 处理：{video_path.name}")
        extract_frames(video_path)

    print("\n全部完成！")


if __name__ == "__main__":
    main()
