"""Generate exercise interval mosaic images from phase1 period segmentation results."""

import json
import math
import cv2
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

RESULT_DIR = Path(r"D:\WorkPath\fitness_new\recognize\visualize\result\v10")
RAW_DIR = Path(r"D:\WorkPath\fitness_new\recognize\visualize\raw")
OUTPUT_DIR = Path(r"D:\WorkPath\fitness_new\recognize\visualize\graph")

SAMPLE_INTERVAL = 2  # sample one frame every N seconds within exercise interval
THUMB_WIDTH = 320
THUMB_HEIGHT = 180
MAX_COLS = 8


def imwrite_unicode(path: Path, img):
    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    path.write_bytes(buf.tobytes())


def extract_frame_at(cap, timestamp_sec, fps):
    frame_no = int(timestamp_sec * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
    ret, frame = cap.read()
    if not ret:
        return None
    return cv2.resize(frame, (THUMB_WIDTH, THUMB_HEIGHT))


def get_cjk_font(size=28):
    for name in ["msyh.ttc", "msyhbd.ttc", "simhei.ttf", "simsun.ttc"]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


CJK_FONT = get_cjk_font(28)


def create_mosaic(frames, title, start_time, end_time):
    n = len(frames)
    if n == 0:
        return None

    cols = min(n, MAX_COLS)
    rows = math.ceil(n / cols)

    header_h = 50
    canvas_w = cols * THUMB_WIDTH
    canvas_h = header_h + rows * THUMB_HEIGHT

    canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
    canvas[:header_h, :] = (40, 40, 40)

    for i, frame in enumerate(frames):
        r, c = divmod(i, cols)
        y = header_h + r * THUMB_HEIGHT
        x = c * THUMB_WIDTH
        canvas[y:y + THUMB_HEIGHT, x:x + THUMB_WIDTH] = frame

    pil_img = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)
    label = f"{title}  [{start_time} - {end_time}]  ({n} frames)"
    draw.text((10, 8), label, font=CJK_FONT, fill=(255, 255, 255))
    canvas = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    return canvas


def process_video(video_name):
    result_dir = RESULT_DIR / video_name
    period_path = result_dir / "period_result.json"
    if not period_path.exists():
        print(f"  SKIP: no period_result.json for {video_name}")
        return

    video_path = RAW_DIR / f"{video_name}.mp4"
    if not video_path.exists():
        print(f"  SKIP: no video file for {video_name}")
        return

    with open(period_path, encoding="utf-8") as f:
        data = json.load(f)

    exercises = [s for s in data["segments"] if s["state"] == "EXERCISE"]
    if not exercises:
        print(f"  SKIP: no EXERCISE segments for {video_name}")
        return

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"  ERROR: cannot open {video_path}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    out_dir = OUTPUT_DIR / video_name
    out_dir.mkdir(parents=True, exist_ok=True)

    for idx, ex in enumerate(exercises, 1):
        start_sec = ex["start_sec"]
        end_sec = ex["end_sec"]
        duration = end_sec - start_sec

        interval = max(1, int(duration / 40)) if duration > 40 else SAMPLE_INTERVAL
        if duration > 200:
            interval = max(1, int(duration / 32))

        timestamps = list(np.arange(start_sec, end_sec + 0.5, interval))
        frames = []
        for ts in timestamps:
            frame = extract_frame_at(cap, ts, fps)
            if frame is not None:
                frames.append(frame)

        if not frames:
            continue

        mosaic = create_mosaic(frames, f"动作{idx}", ex["start_time"], ex["end_time"])
        if mosaic is not None:
            out_path = out_dir / f"动作{idx}.jpg"
            imwrite_unicode(out_path, mosaic)
            print(f"  Saved: {video_name}/动作{idx}.jpg ({len(frames)} frames, interval={interval}s)")

    cap.release()


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    video_names = sorted([
        d.name for d in RESULT_DIR.iterdir()
        if d.is_dir() and (d / "period_result.json").exists()
    ])

    print(f"Found {len(video_names)} videos to process\n")

    for name in video_names:
        print(f"Processing: {name}")
        process_video(name)
        print()

    print("Done!")


if __name__ == "__main__":
    main()
