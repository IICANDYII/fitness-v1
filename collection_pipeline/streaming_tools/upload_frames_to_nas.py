from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path


def format_seconds(value: float | None) -> str:
    if value is None or value < 0:
        return "--:--"
    value = int(value)
    hours, rem = divmod(value, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def find_latest_zip(root: Path) -> Path:
    candidates = [p for p in root.glob("*/frames_low.zip") if p.is_file()]
    if not candidates:
        raise FileNotFoundError(f"No completed frames_low.zip under {root}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def detect_owner(card_root: Path) -> str:
    ignored = {"settings.txt", "setting.txt", "readme.txt", "log.txt"}
    markers = [p for p in card_root.glob("*.txt") if p.name.lower() not in ignored and not p.name.startswith(".")]
    if len(markers) != 1:
        raise RuntimeError(f"Expected one owner marker on {card_root}; found {[p.name for p in markers]}")
    return markers[0].stem


def detect_date(video_root: Path) -> str:
    for video in sorted(video_root.iterdir()):
        match = re.search(r"(20\d{6})\d{6}", video.name)
        if match:
            return match.group(1)
    raise RuntimeError(f"Cannot detect capture date from files under {video_root}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Timed, buffered upload of frames_low.zip to NAS.")
    parser.add_argument("--source-root", default=r"E:\_pipeline_scratch\sd_direct_benchmark")
    parser.add_argument("--nas-root", default=r"\\10.10.10.2\collector-data\Processed Videos")
    parser.add_argument("--card-root", default="F:\\")
    parser.add_argument("--chunk-mib", type=int, default=64)
    args = parser.parse_args()

    source = find_latest_zip(Path(args.source_root))
    card_root = Path(args.card_root)
    owner = detect_owner(card_root)
    capture_date = detect_date(card_root / "VIDEO")
    destination_dir = Path(args.nas_root) / owner / capture_date / "processed"
    destination = destination_dir / "frames_low.zip"
    temporary = destination_dir / f"frames_low.zip.uploading.{os.getpid()}"

    total = source.stat().st_size
    started_at = datetime.now()
    started = time.perf_counter()
    copied = 0
    last_update = 0.0

    print("NAS upload benchmark")
    print(f"Source : {source}")
    print(f"Target : {destination}")
    print(f"Size   : {total / (1024 ** 2):.2f} MiB")
    print(f"Start  : {started_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    try:
        destination_dir.mkdir(parents=True, exist_ok=True)
        with open(source, "rb", buffering=0) as src, open(temporary, "wb", buffering=0) as dst:
            while True:
                chunk = src.read(args.chunk_mib * 1024 * 1024)
                if not chunk:
                    break
                dst.write(chunk)
                copied += len(chunk)
                now = time.perf_counter()
                if now - last_update >= 0.5:
                    elapsed = now - started
                    speed = copied / elapsed if elapsed else 0.0
                    eta = (total - copied) / speed if speed else None
                    print(
                        f"\r{copied * 100 / total:6.2f}%  "
                        f"{copied / (1024 ** 2):9.1f}/{total / (1024 ** 2):9.1f} MiB  "
                        f"{speed / (1024 ** 2):7.2f} MiB/s  "
                        f"elapsed={format_seconds(elapsed)}  ETA={format_seconds(eta)}",
                        end="",
                        flush=True,
                    )
                    last_update = now
            dst.flush()
            os.fsync(dst.fileno())
        if temporary.stat().st_size != total:
            raise IOError(f"Size mismatch: local={total}, NAS={temporary.stat().st_size}")
        os.replace(temporary, destination)
    except BaseException:
        print()
        print(f"[ERROR] Upload failed; partial file may remain at: {temporary}")
        raise

    elapsed = time.perf_counter() - started
    ended_at = datetime.now()
    speed_mib = total / elapsed / (1024 ** 2) if elapsed else 0.0
    report = {
        "source": str(source),
        "destination": str(destination),
        "owner": owner,
        "capture_date": capture_date,
        "bytes": total,
        "started_at": started_at.isoformat(timespec="seconds"),
        "ended_at": ended_at.isoformat(timespec="seconds"),
        "elapsed_seconds": round(elapsed, 3),
        "average_mib_per_second": round(speed_mib, 3),
    }
    report_path = source.parent / "upload_benchmark.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy2(report_path, destination_dir / "upload_benchmark.json")

    print("\n")
    print("=" * 78)
    print("UPLOAD FINISHED")
    print(f"Start time    : {started_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"End time      : {ended_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Elapsed       : {format_seconds(elapsed)} ({elapsed:.1f} seconds)")
    print(f"Average speed : {speed_mib:.2f} MiB/s")
    print(f"NAS file      : {destination}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
