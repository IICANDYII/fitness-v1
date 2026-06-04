"""Thread-safe per-video progress tracker shared between agent and API."""

from __future__ import annotations
import threading
from datetime import datetime

_lock  = threading.Lock()
_store: dict[str, dict] = {}

STEPS = {
    0: "排队中",
    1: "提取视频帧",
    2: "加载训练计划",
    3: "Gemini 视觉分析",
    4: "计算仪表盘数据",
    5: "写入数据库",
    6: "保存备份",
    7: "完成",
}


def update(key: str, step: int, detail: str = "") -> None:
    with _lock:
        prev = _store.get(key, {})
        _store[key] = {
            "step":      step,
            "total":     len(STEPS) - 1,
            "label":     STEPS.get(step, ""),
            "detail":    detail,
            "status":    "running",
            "error":     None,
            "started_at": prev.get("started_at") or datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }


def mark_done(key: str) -> None:
    with _lock:
        entry = _store.get(key, {})
        entry.update({"step": 7, "label": STEPS[7], "status": "done",
                      "detail": "", "updated_at": datetime.now().isoformat()})
        _store[key] = entry


def mark_error(key: str, msg: str) -> None:
    with _lock:
        entry = _store.get(key, {})
        entry.update({"status": "error", "error": msg,
                      "updated_at": datetime.now().isoformat()})
        _store[key] = entry


def get(key: str) -> dict:
    with _lock:
        return dict(_store.get(key, {"status": "unknown"}))


def get_all() -> dict:
    with _lock:
        return {k: dict(v) for k, v in _store.items()}
