"""Extract frames from videos at 2fps using OpenCV. Skips videos that already have frames."""

import cv2
import numpy as np
from pathlib import Path

RAW_DIR = Path(r"D:\WorkPath\fitness\video\raw")
FRAMES_DIR = Path(r"D:\WorkPath\fitness\video\frames")
TARGET_FPS = 2


def imwrite_unicode(path: Path, img):
    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    path.write_bytes(buf.tobytes())


def extract_frames(video_path: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"  ERROR: cannot open {video_path.name}")
        return False

    src_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    interval = src_fps / TARGET_FPS
    duration = total_frames / src_fps if src_fps > 0 else 0

    print(f"Extracting: {video_path.name} ({src_fps:.1f}fps, {duration:.1f}s) -> {output_dir.name}/")

    frame_idx = 0
    saved = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx >= saved * interval:
            out_path = output_dir / f"frame_{saved + 1:05d}.jpg"
            imwrite_unicode(out_path, frame)
            saved += 1
        frame_idx += 1

    cap.release()
    print(f"  Done: {saved} frames extracted")
    return True


def main():
    videos = [f for f in RAW_DIR.iterdir() if f.suffix.lower() in (".mp4", ".avi", ".mov", ".mkv", ".webm")]
    if not videos:
        print("No videos found in raw directory.")
        return

    skipped = 0
    processed = 0
    for video in sorted(videos):
        output_dir = FRAMES_DIR / video.stem
        if output_dir.exists() and any(output_dir.glob("frame_*.jpg")):
            print(f"Skipped (already extracted): {video.name}")
            skipped += 1
            continue
        if extract_frames(video, output_dir):
            processed += 1

    print(f"\nSummary: {processed} extracted, {skipped} skipped, {len(videos)} total")


if __name__ == "__main__":
    main()
