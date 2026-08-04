from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path


VIDEO_EXTENSIONS = {".avi", ".mp4", ".mov", ".mkv", ".mts", ".m4v", ".insv"}
DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


def format_seconds(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "--:--"
    value = max(0, int(value))
    hours, rem = divmod(value, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def probe_duration(ffmpeg: str, video: Path) -> float:
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(video)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    match = DURATION_RE.search(proc.stderr or "")
    if not match:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def iter_jpegs(stream):
    buffer = bytearray()
    soi = b"\xff\xd8"
    eoi = b"\xff\xd9"
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        buffer.extend(chunk)
        while True:
            start = buffer.find(soi)
            if start < 0:
                if len(buffer) > 1:
                    del buffer[:-1]
                break
            if start:
                del buffer[:start]
            end = buffer.find(eoi, 2)
            if end < 0:
                break
            end += 2
            yield bytes(buffer[:end])
            del buffer[:end]


def main() -> int:
    parser = argparse.ArgumentParser(description="Stream SD-card video frames directly into one ZIP.")
    parser.add_argument("--source", default=r"F:\VIDEO")
    parser.add_argument("--output-root", default=r"E:\_pipeline_scratch\sd_direct_benchmark")
    parser.add_argument("--fps", type=float, default=2.0)
    parser.add_argument("--max-edge", type=int, default=1280)
    parser.add_argument("--jpeg-quality", type=int, default=4)
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    dependency_dir = script_dir.parent / "work" / "pydeps"
    sys.path.insert(0, str(dependency_dir))
    import imageio_ffmpeg  # type: ignore

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    source = Path(args.source)
    if not source.is_dir():
        print(f"[ERROR] Source folder not found: {source}")
        return 2

    videos = sorted(
        (p for p in source.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS),
        key=lambda p: p.name.lower(),
    )
    if not videos:
        print(f"[ERROR] No videos found under: {source}")
        return 2

    print("[1/3] Reading video metadata from F: ...")
    durations = [probe_duration(ffmpeg, video) for video in videos]
    total_duration = sum(durations)
    expected_frames = max(1, round(total_duration * args.fps))
    total_bytes = sum(video.stat().st_size for video in videos)

    run_started_at = datetime.now()
    stamp = run_started_at.strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_root) / stamp
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / "frames_low.zip"
    partial_path = output_dir / "frames_low.zip.partial"
    report_path = output_dir / "benchmark.json"

    print(f"[2/3] Videos : {len(videos)}")
    print(f"      Input  : {total_bytes / (1024 ** 3):.2f} GiB")
    print(f"      Length : {format_seconds(total_duration)}")
    print(f"      Target : about {expected_frames:,} frames at {args.fps:g} fps")
    print(f"      Output : {zip_path}")
    print(f"      Start  : {run_started_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print("[3/3] Streaming decode -> memory -> ZIP_STORED (no loose JPEG files)")
    print()

    started = time.perf_counter()
    last_update = 0.0
    total_frames = 0
    failures: list[dict[str, str | int | float]] = []
    video_results: list[dict[str, str | int | float]] = []

    try:
        with open(partial_path, "wb", buffering=64 * 1024 * 1024) as raw_output:
            with zipfile.ZipFile(raw_output, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
                for video_index, (video, duration) in enumerate(zip(videos, durations), start=1):
                    video_started = time.perf_counter()
                    video_frames = 0
                    filter_graph = (
                        f"fps={args.fps:g},"
                        f"scale={args.max_edge}:{args.max_edge}:"
                        "force_original_aspect_ratio=decrease:force_divisible_by=2"
                    )
                    command = [
                        ffmpeg,
                        "-hide_banner", "-loglevel", "error", "-nostdin",
                        "-i", str(video),
                        "-an", "-vf", filter_graph,
                        "-q:v", str(args.jpeg_quality),
                        "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1",
                    ]
                    proc = subprocess.Popen(
                        command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                    assert proc.stdout is not None
                    for jpeg in iter_jpegs(proc.stdout):
                        video_frames += 1
                        total_frames += 1
                        member = f"frames/{video.stem}_f{video_frames:06d}.jpg"
                        archive.writestr(member, jpeg)
                        now = time.perf_counter()
                        if now - last_update >= 0.5:
                            elapsed = now - started
                            speed = total_frames / elapsed if elapsed else 0.0
                            progress = min(100.0, total_frames * 100.0 / expected_frames)
                            eta = (expected_frames - total_frames) / speed if speed > 0 else None
                            line = (
                                f"\r[{video_index:02d}/{len(videos):02d}] {video.name[:34]:34} "
                                f"frames={total_frames:7,d}/{expected_frames:7,d} "
                                f"{progress:6.2f}%  {speed:6.1f} fps  "
                                f"elapsed={format_seconds(elapsed)}  ETA={format_seconds(eta)}"
                            )
                            print(line, end="", flush=True)
                            last_update = now
                    proc.stdout.close()
                    stderr = (proc.stderr.read() if proc.stderr else b"").decode("utf-8", "replace").strip()
                    return_code = proc.wait()
                    video_elapsed = time.perf_counter() - video_started
                    result = {
                        "file": video.name,
                        "duration_seconds": round(duration, 3),
                        "frames": video_frames,
                        "elapsed_seconds": round(video_elapsed, 3),
                        "return_code": return_code,
                    }
                    video_results.append(result)
                    print("\r" + (" " * 170) + "\r", end="")
                    print(
                        f"[DONE {video_index:02d}/{len(videos):02d}] {video.name}  "
                        f"frames={video_frames:,}  time={format_seconds(video_elapsed)}"
                    )
                    if return_code != 0:
                        failures.append({**result, "error": stderr[-1000:]})
        os.replace(partial_path, zip_path)
    except KeyboardInterrupt:
        print("\n[CANCELLED] Partial ZIP kept for inspection:", partial_path)
        return 130

    elapsed = time.perf_counter() - started
    run_ended_at = datetime.now()
    report = {
        "source": str(source),
        "output": str(zip_path),
        "started_at": run_started_at.isoformat(timespec="seconds"),
        "ended_at": run_ended_at.isoformat(timespec="seconds"),
        "video_count": len(videos),
        "input_bytes": total_bytes,
        "video_duration_seconds": round(total_duration, 3),
        "fps_setting": args.fps,
        "max_edge": args.max_edge,
        "frames_written": total_frames,
        "elapsed_seconds": round(elapsed, 3),
        "processing_frames_per_second": round(total_frames / elapsed, 3) if elapsed else 0,
        "zip_bytes": zip_path.stat().st_size,
        "failures": failures,
        "videos": video_results,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n")
    print("=" * 78)
    print("FINISHED")
    print(f"Start time    : {run_started_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"End time      : {run_ended_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Elapsed       : {format_seconds(elapsed)} ({elapsed:.1f} seconds)")
    print(f"Frames        : {total_frames:,}")
    print(f"Average speed : {total_frames / elapsed:.2f} frames/s" if elapsed else "Average speed : --")
    print(f"ZIP size      : {zip_path.stat().st_size / (1024 ** 3):.2f} GiB")
    print(f"ZIP file      : {zip_path}")
    print(f"Report        : {report_path}")
    print(f"Failed videos : {len(failures)}")
    print("=" * 78)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
