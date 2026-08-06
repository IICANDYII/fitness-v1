"""
prepare.py — 转码 NAS 上的双机位 avi → 本地 mp4，并生成同步清单 manifest.json

- 直接从 NAS 读 avi，用 ffmpeg 转 H.264 mp4 到本地（本地 mp4 = 可标注副本）
- 从文件名时间戳 A09999_YYYYMMDDHHMMSS_XXXX.avi 解析每段的墙钟起点
- 会话 t0 = 所有段里最早的墙钟起点；每段 wall_start = 起点 - t0（秒）
  → 两机位的 32s 偏移天然编码进 wall_start，前端按同一条时间轴对齐
- Apple Silicon 用 h264_videotoolbox 硬件编码，转码远快于实时

用法:
    python prepare.py            # 全部机位全部段
    python prepare.py --only-first  # 每机位只转第一段(联调用)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

NAS_BASE = Path("/Volumes/homes/max/视角对比/fitness")
OUT_DIR = Path.home() / "Downloads" / "fitness_annotation" / "videos"
CAMERAS = ["normal", "45"]  # normal 早 32s，作会话基准
TS_RE = re.compile(r"_(\d{14})_")


def parse_wall(fname: str) -> datetime:
    m = TS_RE.search(fname)
    if not m:
        raise ValueError(f"文件名无时间戳: {fname}")
    return datetime.strptime(m.group(1), "%Y%m%d%H%M%S")


def ffprobe_duration(path: Path) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ], text=True)
    return float(out.strip())


def transcode(src: Path, dst: Path) -> None:
    """MJPG avi → H.264 mp4（硬件编码，faststart 便于浏览器 seek）。"""
    if dst.exists() and dst.stat().st_size > 0:
        print(f"[skip] 已存在 {dst.name}")
        return
    print(f"[转码] {src.name} → {dst.name}")
    subprocess.run([
        "ffmpeg", "-y", "-i", str(src),
        "-c:v", "h264_videotoolbox", "-b:v", "6M",
        "-c:a", "aac", "-movflags", "+faststart",
        str(dst),
    ], check=True, stdin=subprocess.DEVNULL)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-first", action="store_true")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 收集所有段 + 墙钟
    segs: list[dict] = []
    for cam in CAMERAS:
        cam_dir = NAS_BASE / cam
        files = sorted(cam_dir.glob("*.avi"))
        if args.only_first:
            files = files[:1]
        for i, f in enumerate(files):
            segs.append({"cam": cam, "idx": i, "src": f, "wall": parse_wall(f.name)})

    if not segs:
        raise SystemExit("未找到任何 avi")

    # 每台相机各自的录制起点做基准 → 两路都从 local 0 同步起播。
    # 两机时钟差 32s，因此同一 master 位置 normal 显示的真实时刻比 45 早约 32s。
    cam_t0 = {c: min(s["wall"] for s in segs if s["cam"] == c) for c in CAMERAS}
    for c in CAMERAS:
        print(f"{c} 起点 = {cam_t0[c].isoformat()}")

    cameras: dict[str, list] = {c: [] for c in CAMERAS}
    total = 0.0
    for s in segs:
        dst = OUT_DIR / f'{s["cam"]}_{s["idx"]}.mp4'
        transcode(s["src"], dst)
        dur = ffprobe_duration(dst)
        wall_start = (s["wall"] - cam_t0[s["cam"]]).total_seconds()
        cameras[s["cam"]].append({
            "file": dst.name,
            "wall_start": round(wall_start, 3),
            "duration": round(dur, 3),
            "src_name": s["src"].name,
        })
        total = max(total, wall_start + dur)
        print(f"       {dst.name}  wall_start={wall_start:.1f}s  dur={dur:.1f}s")

    manifest = {
        "session_start_iso": cam_t0["normal"].isoformat(),
        "duration_sec": round(total, 3),
        "cameras": cameras,
        "note": "两路各自从 local 0 同步起播；两机时钟差约32s，故同一 master 位置 normal 真实时刻比 45 早约32s。GT offset 以 normal 时间轴为准。",
    }
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n清单 → {OUT_DIR / 'manifest.json'}")
    print(f"会话总时长 ≈ {total/60:.1f} min")


if __name__ == "__main__":
    main()
