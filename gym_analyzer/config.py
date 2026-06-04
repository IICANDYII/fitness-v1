from __future__ import annotations
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

# ── Agent / LLM ──────────────────────────────────────────────────────────────
AGENT_MODEL   = "gemini-3-flash-preview"
VISION_MODEL  = "gemini-3-flash-preview"

_base = (os.getenv("NEXTROUTER_BASE_URL") or os.getenv("BASE_URL", "")).rstrip("/")
GATEWAY_URL   = _base if _base.endswith("/v1") else _base + "/v1"
GATEWAY_KEY   = os.getenv("NEXTROUTER_API_KEY") or os.getenv("API_KEY", "")

# ── Video sampling ────────────────────────────────────────────────────────────
FPS           = 1          # frames per second to extract
FRAME_QUALITY = 70         # JPEG quality 0-100
BATCH_FRAMES  = 60         # frames per Gemini call (1 min) — keep grid small

# ── Bigcell grid ──────────────────────────────────────────────────────────────
# Fixed cell size so AI can clearly see each frame regardless of total count
CELL_W             = 220   # pixels per cell width
CELL_H             = 123   # pixels per cell height (≈ 16:9)
GEMINI_MAX_DIM     = 3072  # Gemini max canvas dimension per side
GEMINI_MAX_IMAGES  = 16    # Gemini max images per API call

# Derived constants
MAX_FRAMES_PER_GRID = (GEMINI_MAX_DIM // CELL_W) * (GEMINI_MAX_DIM // CELL_H)  # 13×24 = 312

# ── Storage ───────────────────────────────────────────────────────────────────
RESULTS_DIR   = Path(__file__).parent / "results"
FRAMES_DIR    = Path(__file__).parent / "frames"
INPUT_DIR     = Path(__file__).parent / "input"
RESULTS_DIR.mkdir(exist_ok=True)
FRAMES_DIR.mkdir(exist_ok=True)
INPUT_DIR.mkdir(exist_ok=True)

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv"}
HR_EXTS    = {".csv", ".xlsx"}

# ── API server ────────────────────────────────────────────────────────────────
API_PORT         = 8002
DEFAULT_USER_ID  = os.getenv("FITNESS_USER_ID", "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11")

# ── Muscle → SVG ID mapping ───────────────────────────────────────────────────
# Maps Chinese exercise names to SVG muscle IDs used by the frontend
EXERCISE_MUSCLES: dict[str, dict[str, list[str]]] = {
    "平板卧推":   {"primary": ["chest"],                       "secondary": ["front-shoulders", "triceps"]},
    "上斜卧推":   {"primary": ["chest"],                       "secondary": ["front-shoulders", "triceps"]},
    "下斜卧推":   {"primary": ["chest"],                       "secondary": ["triceps"]},
    "哑铃卧推":   {"primary": ["chest"],                       "secondary": ["front-shoulders", "triceps"]},
    "哑铃飞鸟":   {"primary": ["chest"],                       "secondary": ["front-shoulders"]},
    "夹胸":       {"primary": ["chest"],                       "secondary": []},
    "绳索夹胸":   {"primary": ["chest"],                       "secondary": []},
    "俯卧撑":     {"primary": ["chest", "triceps"],            "secondary": ["front-shoulders"]},
    "高位下拉":   {"primary": ["lats"],                        "secondary": ["biceps", "rear-shoulders"]},
    "引体向上":   {"primary": ["lats"],                        "secondary": ["biceps", "rear-shoulders"]},
    "坐姿划船":   {"primary": ["lats", "traps-middle"],        "secondary": ["biceps", "rear-shoulders"]},
    "杠铃划船":   {"primary": ["lats", "traps-middle"],        "secondary": ["biceps", "lowerback"]},
    "哑铃划船":   {"primary": ["lats"],                        "secondary": ["biceps", "rear-shoulders"]},
    "绳索划船":   {"primary": ["lats", "traps-middle"],        "secondary": ["biceps"]},
    "面拉":       {"primary": ["rear-shoulders", "traps-middle"], "secondary": []},
    "硬拉":       {"primary": ["hamstrings", "lowerback"],     "secondary": ["glutes", "traps", "lats"]},
    "罗马尼亚硬拉": {"primary": ["hamstrings", "glutes"],      "secondary": ["lowerback"]},
    "深蹲":       {"primary": ["quads", "glutes"],             "secondary": ["hamstrings", "lowerback"]},
    "腿举":       {"primary": ["quads", "glutes"],             "secondary": ["hamstrings"]},
    "箭步蹲":     {"primary": ["quads", "glutes"],             "secondary": ["hamstrings"]},
    "腿弯举":     {"primary": ["hamstrings"],                  "secondary": []},
    "腿伸展":     {"primary": ["quads"],                       "secondary": []},
    "提踵":       {"primary": ["calves"],                      "secondary": []},
    "杠铃推举":   {"primary": ["front-shoulders"],             "secondary": ["triceps", "traps"]},
    "哑铃推举":   {"primary": ["front-shoulders"],             "secondary": ["triceps", "traps"]},
    "哑铃侧平举": {"primary": ["front-shoulders"],             "secondary": ["rear-shoulders"]},
    "杠铃弯举":   {"primary": ["biceps"],                      "secondary": ["forearms"]},
    "哑铃弯举":   {"primary": ["biceps"],                      "secondary": ["forearms"]},
    "绳索弯举":   {"primary": ["biceps"],                      "secondary": ["forearms"]},
    "绳索下压":   {"primary": ["triceps"],                     "secondary": []},
    "卷腹":       {"primary": ["abdominals"],                  "secondary": ["obliques"]},
    "平板支撑":   {"primary": ["abdominals", "obliques"],      "secondary": ["lowerback"]},
    "悬垂举腿":   {"primary": ["abdominals"],                  "secondary": ["obliques"]},
    "跑步":       {"primary": ["quads", "hamstrings", "calves"], "secondary": ["glutes"]},
    "椭圆机":     {"primary": ["quads", "hamstrings"],         "secondary": ["glutes", "calves"]},
}

# Muscle group → Chinese display name (for /api/daily muscle_distribution)
MUSCLE_GROUP_DISPLAY: dict[str, str] = {
    "chest":           "胸",
    "lats":            "背",
    "traps":           "背",
    "traps-middle":    "背",
    "lowerback":       "背",
    "front-shoulders": "肩",
    "rear-shoulders":  "肩",
    "quads":           "腿",
    "hamstrings":      "腿",
    "glutes":          "腿",
    "calves":          "腿",
    "biceps":          "二头",
    "triceps":         "三头",
    "abdominals":      "腹",
    "obliques":        "腹",
    "forearms":        "二头",
}

# MET values for calorie estimation
EXERCISE_MET: dict[str, float] = {
    "跑步": 8.3, "椭圆机": 5.0, "动感单车": 6.8,
    "深蹲": 6.0, "硬拉": 6.0, "卧推": 5.5, "平板卧推": 5.5,
    "引体向上": 8.0, "俯卧撑": 3.8,
    "default": 5.0,
}
