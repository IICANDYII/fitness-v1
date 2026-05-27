"""心率 CSV 加载与解析。

支持的 CSV 列：
  必须：bpm（整数）
  时间戳列名（按优先级匹配）：
    - timestamp_sec        相对视频开头的秒数（用户样本采用此格式，无需偏移）
    - timestamp            Unix 毫秒，或 ISO 字符串
  可选：source            数据源标识（apple_watch / garmin / simulated 等）

如果只有 Unix 毫秒时间戳，需要额外传入 video_start_unix_ms 做对齐。
本 MVP 优先识别 timestamp_sec，省去对齐工作。

未来扩展（v2 之后）：FIT / TCX 二进制格式解析。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from .models import HeartRateData


def load_heart_rate_csv(
    csv_path: Path,
    video_start_unix_ms: Optional[int] = None,
) -> tuple[list[HeartRateData], float]:
    """加载心率 CSV，返回 (标准化数据点列表, 同步偏移秒数)。

    标准化后：所有数据点的 timestamp 字段都是"相对视频开头的秒数"。

    返回的 sync_offset 含义：
      - 心率数据起始时间 - 视频起始时间
      - 正数 = 心率比视频晚
      - 负数 = 心率比视频早

    Raises:
        FileNotFoundError: CSV 不存在
        ValueError: CSV 缺少必需列或格式无法解析
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"心率文件不存在：{csv_path}")

    df = pd.read_csv(csv_path)
    if "bpm" not in df.columns:
        raise ValueError(f"CSV 缺少 bpm 列：{csv_path}")

    # 解析时间戳列
    if "timestamp_sec" in df.columns:
        seconds = df["timestamp_sec"].astype(float).tolist()
        sync_offset = 0.0
    elif "timestamp" in df.columns:
        # 尝试 Unix 毫秒整数
        first = df["timestamp"].iloc[0]
        if isinstance(first, (int, float)) and first > 1_000_000_000_000:
            if video_start_unix_ms is None:
                raise ValueError(
                    "心率数据是 Unix 毫秒时间戳，但未提供 video_start_unix_ms 对齐基准"
                )
            seconds = [(int(t) - video_start_unix_ms) / 1000.0 for t in df["timestamp"]]
            sync_offset = round(seconds[0], 2) if seconds else 0.0
        else:
            # 尝试 ISO 字符串
            try:
                parsed = pd.to_datetime(df["timestamp"])
            except Exception as e:
                raise ValueError(f"无法解析 timestamp 列：{e}") from e
            if video_start_unix_ms is None:
                # 把第一个时间点视为视频开头
                base = parsed.iloc[0]
                seconds = [(t - base).total_seconds() for t in parsed]
                sync_offset = 0.0
            else:
                base = datetime.fromtimestamp(video_start_unix_ms / 1000.0)
                seconds = [(t - base).total_seconds() for t in parsed]
                sync_offset = round(seconds[0], 2) if seconds else 0.0
    else:
        raise ValueError(
            f"CSV 缺少时间戳列（需要 timestamp_sec 或 timestamp）：{csv_path}"
        )

    bpms = df["bpm"].astype(int).tolist()
    sources = df["source"].astype(str).tolist() if "source" in df.columns else ["unknown"] * len(bpms)

    data = [
        HeartRateData(timestamp=round(s, 2), bpm=b, source=src)
        for s, b, src in zip(seconds, bpms, sources)
    ]
    # 按时间排序兜底
    data.sort(key=lambda x: x.timestamp)
    return data, sync_offset


def slice_by_time(
    data: list[HeartRateData],
    start_s: float,
    end_s: float,
) -> list[HeartRateData]:
    """返回 [start_s, end_s) 范围内的心率数据点。"""
    return [d for d in data if start_s <= d.timestamp < end_s]


def average_bpm(points: list[HeartRateData]) -> Optional[float]:
    """计算平均 bpm；空列表返回 None。"""
    if not points:
        return None
    return sum(p.bpm for p in points) / len(points)


def peak_bpm(points: list[HeartRateData]) -> Optional[int]:
    """峰值 bpm；空列表返回 None。"""
    if not points:
        return None
    return max(p.bpm for p in points)
