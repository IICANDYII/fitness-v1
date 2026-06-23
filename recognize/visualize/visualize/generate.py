"""扫描 result 目录下所有版本的样本，生成可交互的 HTML 可视化页面（支持版本切换）。"""
from __future__ import annotations

import json
import re
import os
from pathlib import Path

RESULT_DIR = Path(r"D:\WorkPath\fitness_new\recognize\visualize\result")
OUT_HTML = Path(__file__).parent / "index.html"

def _load_version_labels() -> dict[str, str]:
    """从 VERSION_INFO.md 读取版本说明，回退为空 dict。"""
    path = RESULT_DIR / "VERSION_INFO.md"
    labels: dict[str, str] = {}
    if not path.exists():
        return labels
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")]
        # parts: ['', col1, col2, '']
        if len(parts) < 4:
            continue
        ver, desc = parts[1], parts[2]
        if ver in ("版本", "------", "---"):
            continue
        if re.match(r"^-+$", ver) or re.match(r"^-+$", desc):
            continue
        labels[ver] = f"{ver}: {desc}"
    return labels

VERSION_LABELS = _load_version_labels()

EQUIPMENT_COLORS = {
    "跑步机": "#EF4444", "跑步": "#EF4444",
    "史密斯机": "#1D4ED8", "史密斯架": "#1D4ED8", "Smith Machine": "#1D4ED8",
    "引体向上架": "#10B981", "引体向上": "#10B981", "Pull Up Bar": "#10B981",
    "龙门架": "#F59E0B",
    "杠铃": "#8B5CF6",
    "高位下拉": "#06B6D4", "高位下拉机": "#06B6D4",
    "坐姿划船": "#EC4899",
    "悍马机": "#F97316",
}
STATE_COLORS = {
    "EXERCISE": "#EF4444",
    "REST": "#3B82F6",
    "TRANSITION": "#9CA3AF",
}
TRANSITION_COLOR = "#9CA3AF"

GT_TYPE_COLORS = {
    "exercise": "#EF4444",
    "transition": TRANSITION_COLOR,
    "rest": "#3B82F6",
}


def _parse_ground_truth(path: Path) -> list[dict] | None:
    """Parse ground_truth.json which may contain Python variables like TOTAL, TRANSITION_COLOR."""
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return None

    if not text.startswith("["):
        text = "[" + text + "]"
    text = re.sub(r",\s*]", "]", text)
    text = text.replace("TRANSITION_COLOR", f'"{TRANSITION_COLOR}"')
    text = re.sub(r'\bTOTAL\b', "99999", text)

    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        return None

    segments = []
    for item in raw:
        label = item.get("label", "")
        # Infer type from label when not explicitly provided
        if "type" in item:
            seg_type = item["type"]
        else:
            label_lower = label.lower()
            if label_lower in ("过渡", "transition", ""):
                seg_type = "transition"
            elif label_lower in ("休息", "rest"):
                seg_type = "rest"
            else:
                seg_type = "exercise"
        seg = {
            "start": item.get("start", 0),
            "end": item.get("end", 0),
            "label": label,
            "type": seg_type,
        }
        if "color" in item:
            seg["color"] = item["color"]
        else:
            seg["color"] = GT_TYPE_COLORS.get(seg["type"], TRANSITION_COLOR)
            if seg["type"] == "exercise" and "equipment" in item:
                seg["color"] = EQUIPMENT_COLORS.get(item["equipment"], "#EF4444")
        segments.append(seg)
    return segments


def _build_model_bars(period: dict, exercise: dict) -> list[dict]:
    """Combine period segments with exercise recognition results."""
    segments = period.get("segments", [])
    ex_map = {r["segmentId"]: r for r in exercise.get("results", [])}

    ex_idx = 0
    bars = []
    for seg in segments:
        s = seg.get("start_sec", 0.0)
        e = seg.get("end_sec", 0.0)
        state = seg.get("state", "TRANSITION").upper()
        label = state
        color = STATE_COLORS.get(state, TRANSITION_COLOR)
        seg_id = seg.get("segmentId", "")

        total_sets = 0
        total_reps = 0
        equip = ""

        if state == "EXERCISE":
            if not seg_id:
                ex_idx += 1
                seg_id = f"exercise_{ex_idx:03d}"
            if seg_id in ex_map:
                res = ex_map[seg_id].get("result", {})
                equip = res.get("equipment", "")
                action = res.get("exercise", "")
                sets = res.get("sets", [])
                total_sets = res.get("total_sets", len(sets))
                total_reps = res.get("total_reps", sum(st.get("reps", 0) for st in sets if isinstance(st, dict)))
                label = action or equip or "EXERCISE"
                color = EQUIPMENT_COLORS.get(equip, "#EF4444")

        bars.append({
            "start": s, "end": e, "label": label, "color": color,
            "state": state, "confidence": seg.get("confidence", 0),
            "reason": seg.get("reason", ""),
            "equipment": equip,
            "total_sets": total_sets,
            "total_reps": total_reps,
        })
    return bars


def _load_optical_flow(sample_name: str) -> list[dict] | None:
    """Load optical flow from shared directory."""
    path = RESULT_DIR / "shared" / sample_name / "optical_flow.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    flow_list = data.get("flow", [])
    return [{"t": f["time_sec"], "v": round(f["avg_flow"], 2)} for f in flow_list]


def _process_sample(sample_dir: Path, version: str, sample_name: str) -> dict | None:
    period_path = sample_dir / "period_result.json"
    exercise_path = sample_dir / "exercise_result.json"
    adjusted_path = sample_dir / "period_result_adjusted.json"
    shared_dir = RESULT_DIR / "shared" / sample_name
    gt_path = shared_dir / "ground_truth.json"
    if not gt_path.exists():
        gt_path = shared_dir / "ground_truth.txt"
    if not gt_path.exists():
        gt_path = sample_dir / "ground_truth.json"
    if not gt_path.exists():
        gt_path = sample_dir / "ground_truth.txt"

    if not period_path.exists():
        return None

    period = json.loads(period_path.read_text(encoding="utf-8"))
    exercise = json.loads(exercise_path.read_text(encoding="utf-8")) if exercise_path.exists() else {"results": []}
    adjusted = json.loads(adjusted_path.read_text(encoding="utf-8")) if adjusted_path.exists() else None

    gt_segments = _parse_ground_truth(gt_path)

    combined_bars = _build_model_bars(adjusted or period, exercise)

    all_ends = [b["end"] for b in combined_bars]
    if gt_segments:
        all_ends += [s["end"] for s in gt_segments]
    total = max(all_ends) if all_ends else 0
    if total >= 99999 and gt_segments:
        real_ends = [e for e in all_ends if e < 99999]
        total = max(real_ends) if real_ends else 600
        for s in gt_segments:
            if s["end"] >= 99999:
                s["end"] = total

    optical = _load_optical_flow(sample_name)

    exercise_details = []
    for r in exercise.get("results", []):
        res = r.get("result", {})
        sets = res.get("sets", [])
        total_sets = res.get("total_sets", len(sets))
        total_reps = res.get("total_reps", sum(s.get("reps", 0) for s in sets if isinstance(s, dict)))
        detail = {
            "segmentId": r.get("segmentId", ""),
            "start": r.get("startTime", 0),
            "end": r.get("endTime", 0),
            "equipment": res.get("equipment", ""),
            "exercise": res.get("exercise", ""),
            "confidence": res.get("confidence", 0),
            "sets": sets,
            "total_sets": total_sets,
            "total_reps": total_reps,
        }
        exercise_details.append(detail)

    video_name = sample_name + ".mp4"

    return {
        "name": sample_name,
        "version": version,
        "version_label": VERSION_LABELS.get(version, version),
        "total": total,
        "ground_truth": gt_segments,
        "combined_bars": combined_bars,
        "optical_flow": optical,
        "exercise_details": exercise_details,
        "model": period.get("model", ""),
        "prompt_version": period.get("version", ""),
        "phase2_prompt": exercise.get("phase2_prompt", ""),
        "video": video_name,
    }


def main():
    # Discover versions
    versions = sorted([
        d.name for d in RESULT_DIR.iterdir()
        if d.is_dir() and d.name.startswith("v") and d.name != "shared"
    ])

    if not versions:
        print("No version directories found (expected result/v1/, result/v2/, ...)")
        return

    print(f"Found versions: {versions}")

    all_data = {}  # {version: [samples]}
    for ver in versions:
        ver_dir = RESULT_DIR / ver
        samples = []
        for d in sorted(ver_dir.iterdir()):
            if d.is_dir():
                result = _process_sample(d, ver, d.name)
                if result:
                    samples.append(result)
                    print(f"  [{ver}] processed: {d.name}")
        all_data[ver] = samples

    html = _generate_html(all_data, versions)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"\nGenerated: {OUT_HTML}")
    for ver in versions:
        label = VERSION_LABELS.get(ver, ver)
        print(f"  {ver}: {len(all_data[ver])} samples — {label}")


def _generate_html(all_data: dict, versions: list[str]) -> str:
    data_json = json.dumps(all_data, ensure_ascii=False, indent=None)
    versions_json = json.dumps(versions, ensure_ascii=False)
    labels_json = json.dumps(VERSION_LABELS, ensure_ascii=False)
    html = HTML_TEMPLATE.replace("__DATA_PLACEHOLDER__", data_json)
    html = html.replace("__VERSIONS_PLACEHOLDER__", versions_json)
    html = html.replace("__VERSION_LABELS_PLACEHOLDER__", labels_json)
    return html


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>训练视频识别结果 — 多版本对比</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, "Microsoft YaHei", "PingFang SC", sans-serif;
  background: #f8fafc; color: #1e293b;
}
.header {
  background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
  color: white; padding: 20px 32px;
  display: flex; align-items: center; justify-content: space-between;
}
.header h1 { font-size: 20px; font-weight: 600; }

.sample-tabs {
  display: flex; gap: 8px; padding: 16px 32px; background: white;
  border-bottom: 1px solid #e2e8f0; overflow-x: auto; flex-wrap: wrap;
  align-items: center;
}
.sample-tabs-label {
  font-size: 13px; font-weight: 600; color: #475569; margin-right: 8px;
}
.sample-tab {
  padding: 8px 20px; border-radius: 8px; cursor: pointer;
  font-size: 14px; font-weight: 500; border: 2px solid #e2e8f0;
  background: white; transition: all 0.2s;
}
.sample-tab:hover { border-color: #94a3b8; }
.sample-tab.active {
  background: #1e293b; color: white; border-color: #1e293b;
}

.version-bar {
  display: flex; gap: 8px; padding: 12px 32px; background: #fefce8;
  border-bottom: 1px solid #fde68a; align-items: center; flex-wrap: wrap;
}
.version-bar-label {
  font-size: 13px; font-weight: 600; color: #92400e; margin-right: 8px;
}
.version-check {
  display: flex; align-items: center; gap: 5px; padding: 6px 14px;
  border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 500;
  border: 2px solid #fde68a; background: white; transition: all 0.2s; color: #92400e;
  user-select: none;
}
.version-check:hover { border-color: #f59e0b; }
.version-check.active { background: #f59e0b; color: white; border-color: #f59e0b; }
.version-check input { display: none; }
.version-check-icon {
  width: 16px; height: 16px; border-radius: 3px; border: 2px solid #d97706;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  transition: all 0.2s; background: white;
}
.version-check.active .version-check-icon {
  background: white; border-color: white;
}
.version-check-icon svg { display: none; width: 10px; height: 10px; }
.version-check.active .version-check-icon svg { display: block; }
.select-all-btn {
  padding: 4px 12px; border-radius: 4px; cursor: pointer;
  font-size: 12px; border: 1px solid #fde68a; background: white;
  color: #92400e; margin-left: 4px; transition: all 0.2s;
}
.select-all-btn:hover { background: #fef3c7; }

.content { padding: 24px 32px; }
.card {
  background: white; border-radius: 12px; padding: 24px;
  margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.card-title {
  font-size: 16px; font-weight: 600; margin-bottom: 16px;
  display: flex; align-items: center; gap: 8px;
}
.card-title .badge {
  font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 500;
}
.badge-model { background: #dbeafe; color: #1e40af; }
.badge-version { background: #dcfce7; color: #166534; }

.video-panel { margin-bottom: 20px; }
.video-row { display: flex; gap: 16px; align-items: flex-start; }
.video-row video { max-width: 640px; width: 100%; border-radius: 8px; background: #000; }
.video-side { flex: 1; min-width: 200px; display: flex; flex-direction: column; gap: 8px; }
.video-time-display { display: flex; align-items: baseline; gap: 8px; font-size: 13px; color: #64748b; }
.video-time-current { font-size: 28px; font-weight: 700; color: #1e293b; font-variant-numeric: tabular-nums; }
.video-segment-info {
  padding: 8px 12px; border-radius: 6px;
  background: #f8fafc; font-size: 12px; color: #475569;
  min-height: 36px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.video-segment-info .seg-badge {
  padding: 2px 8px; border-radius: 4px; color: white;
  font-weight: 600; font-size: 11px; white-space: nowrap;
}
.speed-control { display: flex; align-items: center; gap: 6px; margin-top: 8px; }
.speed-btn {
  padding: 3px 10px; border-radius: 4px; border: 1px solid #e2e8f0;
  background: white; cursor: pointer; font-size: 12px; color: #475569;
}
.speed-btn.active { background: #1e293b; color: white; border-color: #1e293b; }
.info-row { display: flex; gap: 24px; margin-bottom: 16px; font-size: 13px; color: #64748b; }
.info-row .info-item { display: flex; align-items: center; gap: 6px; }
.info-row .info-value { font-weight: 600; color: #1e293b; }

.timeline-panel { min-width: 0; }
.timeline-container { position: relative; }
.timeline-row { display: flex; align-items: center; margin-bottom: 6px; min-height: 40px; }
.timeline-label {
  width: 160px; flex-shrink: 0; font-size: 12px;
  font-weight: 600; text-align: right; padding-right: 12px; color: #475569;
  line-height: 1.3;
}
.timeline-label .ver-tag {
  display: inline-block; font-size: 10px; padding: 1px 6px; border-radius: 3px;
  color: white; margin-right: 4px; vertical-align: middle;
}
.timeline-bar-area {
  flex: 1; position: relative; height: 36px;
  background: #f1f5f9; border-radius: 6px; overflow: visible; cursor: pointer;
}
.timeline-segment {
  position: absolute; top: 0; height: 100%;
  display: flex; align-items: center; justify-content: center;
  overflow: hidden; cursor: pointer; transition: opacity 0.15s;
  border-right: 1px solid rgba(255,255,255,0.3);
}
.timeline-segment:hover { opacity: 0.85; }
.timeline-segment span {
  color: white; font-size: 11px; font-weight: 600;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  padding: 0 4px; text-shadow: 0 1px 2px rgba(0,0,0,0.3);
}
.playhead {
  position: absolute; top: -4px; bottom: -4px; width: 2px;
  background: #ef4444; z-index: 10; pointer-events: none;
  transition: left 0.1s linear;
}
.playhead::after {
  content: ''; position: absolute; top: -3px; left: -4px;
  width: 10px; height: 10px; background: #ef4444;
  border-radius: 50%; border: 2px solid white;
  box-shadow: 0 1px 3px rgba(0,0,0,0.3);
}
.timeline-divider {
  height: 1px; background: #e2e8f0; margin: 8px 0 8px 160px;
}
.time-axis { display: flex; align-items: flex-start; margin-top: 2px; }
.time-axis-label { width: 160px; flex-shrink: 0; }
.time-axis-area { flex: 1; position: relative; height: 24px; border-top: 1px solid #cbd5e1; }
.time-tick { position: absolute; top: 0; font-size: 10px; color: #94a3b8; transform: translateX(-50%); }
.time-tick::before {
  content: ''; position: absolute; top: -4px; left: 50%;
  width: 1px; height: 4px; background: #cbd5e1;
}
.legend {
  display: flex; flex-wrap: wrap; gap: 12px;
  margin-top: 16px; padding-top: 12px; border-top: 1px solid #f1f5f9;
}
.legend-item { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #64748b; }
.legend-color { width: 14px; height: 14px; border-radius: 3px; flex-shrink: 0; }
.flow-chart-wrap { position: relative; }
.flow-chart { width: 100%; height: 120px; }
.flow-playhead {
  position: absolute; top: 0; bottom: 24px; width: 2px;
  background: #ef4444; z-index: 10; pointer-events: none;
  transition: left 0.1s linear;
}
.tooltip {
  position: fixed; pointer-events: none;
  background: #1e293b; color: white;
  padding: 10px 14px; border-radius: 8px;
  font-size: 12px; line-height: 1.6;
  max-width: 320px; z-index: 1000;
  box-shadow: 0 4px 12px rgba(0,0,0,0.2); display: none;
}

/* IoU comparison table */
.iou-compare-table {
  width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 12px;
}
.iou-compare-table th {
  text-align: center; padding: 8px 12px; background: #f0fdf4;
  border-bottom: 2px solid #bbf7d0; font-weight: 600; color: #166534; font-size: 12px;
}
.iou-compare-table th:first-child { text-align: left; width: 160px; }
.iou-compare-table td {
  text-align: center; padding: 6px 12px; border-bottom: 1px solid #f1f5f9;
}
.iou-compare-table td:first-child { text-align: left; font-weight: 500; color: #475569; }
.iou-compare-table tr:hover td { background: #f0fdf4; }
.iou-compare-table .best-cell { font-weight: 700; }
.iou-score { font-weight: 700; font-variant-numeric: tabular-nums; }
.iou-score.high { color: #16a34a; }
.iou-score.mid { color: #d97706; }
.iou-score.low { color: #dc2626; }

/* Exercise details tabs */
.ex-tabs { display: flex; gap: 4px; margin-bottom: 12px; flex-wrap: wrap; }
.ex-tab {
  padding: 5px 14px; border-radius: 6px 6px 0 0; cursor: pointer;
  font-size: 12px; font-weight: 500; border: 1px solid #e2e8f0;
  border-bottom: none; background: #f8fafc; color: #64748b; transition: all 0.2s;
}
.ex-tab.active { background: white; color: #1e293b; font-weight: 600; border-color: #cbd5e1; }
.ex-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.ex-table th {
  text-align: left; padding: 8px 12px; background: #f8fafc;
  border-bottom: 2px solid #e2e8f0; font-weight: 600; color: #475569;
}
.ex-table td { padding: 8px 12px; border-bottom: 1px solid #f1f5f9; }
.ex-table tr:hover td { background: #f8fafc; }

.no-data-hint {
  padding: 20px; text-align: center; color: #94a3b8; font-size: 14px;
}

@media (max-width: 700px) {
  .video-row { flex-direction: column; }
  .video-row video { max-width: 100%; }
}
</style>
</head>
<body>

<div class="header">
  <h1>训练视频识别结果 — 多版本对比</h1>
  <span id="sample-count" style="font-size:13px;opacity:0.7"></span>
</div>

<div class="sample-tabs" id="tabs"></div>
<div class="version-bar" id="versionBar"></div>
<div class="content" id="content"></div>
<div class="tooltip" id="tooltip"></div>

<script>
const ALL_DATA = __DATA_PLACEHOLDER__;
const VERSIONS = __VERSIONS_PLACEHOLDER__;
const VERSION_LABELS = __VERSION_LABELS_PLACEHOLDER__;

const VERSION_COLORS = ['#f59e0b','#3b82f6','#10b981','#8b5cf6','#ef4444','#ec4899','#06b6d4','#f97316'];

let currentSample = '';
let selectedVersions = new Set(VERSIONS);
let videoEl = null;
let animFrameId = null;
let tipData = {};
const tooltip = document.getElementById('tooltip');

function allSampleNames() {
  const names = new Set();
  VERSIONS.forEach(ver => { (ALL_DATA[ver] || []).forEach(s => names.add(s.name)); });
  return Array.from(names).sort();
}

function getSampleForVersion(sampleName, ver) {
  return (ALL_DATA[ver] || []).find(s => s.name === sampleName) || null;
}

function getFirstAvailableSample(sampleName) {
  for (const ver of VERSIONS) {
    const s = getSampleForVersion(sampleName, ver);
    if (s) return s;
  }
  return null;
}

function videoSrc(filename) {
  if (location.protocol === 'file:') return '../raw/' + filename;
  return '/video/' + encodeURIComponent(filename);
}
function fmtTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return m + ':' + String(s).padStart(2, '0');
}
function fmtTimePrecise(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return m + ':' + String(s).padStart(2, '0');
}
function verColor(ver) {
  const idx = VERSIONS.indexOf(ver);
  return VERSION_COLORS[idx % VERSION_COLORS.length];
}

function init() {
  buildSampleTabs();
  buildVersionBar();
  const samples = allSampleNames();
  if (samples.length > 0) {
    currentSample = samples[0];
    renderComparison();
  }
}

function buildSampleTabs() {
  const samples = allSampleNames();
  document.getElementById('sample-count').textContent = samples.length + ' 个样本';
  const tabs = document.getElementById('tabs');
  tabs.innerHTML = '<span class="sample-tabs-label">样本:</span>';
  samples.forEach((name, i) => {
    const tab = document.createElement('div');
    tab.className = 'sample-tab' + (i === 0 ? ' active' : '');
    tab.textContent = name;
    tab.onclick = () => selectSample(name);
    tabs.appendChild(tab);
  });
}

function buildVersionBar() {
  const vbar = document.getElementById('versionBar');
  vbar.innerHTML = '<span class="version-bar-label">对比版本:</span>';
  VERSIONS.forEach((ver, i) => {
    const label = document.createElement('label');
    label.className = 'version-check active';
    label.dataset.ver = ver;
    label.innerHTML = `<span class="version-check-icon" style="border-color:${verColor(ver)}"><svg viewBox="0 0 12 12" fill="${verColor(ver)}"><path d="M10 3L4.5 8.5 2 6" stroke="${verColor(ver)}" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg></span>${VERSION_LABELS[ver] || ver}`;
    label.onclick = () => toggleVersion(ver, label);
    vbar.appendChild(label);
  });
  const allBtn = document.createElement('button');
  allBtn.className = 'select-all-btn';
  allBtn.textContent = '全选/反选';
  allBtn.onclick = toggleAllVersions;
  vbar.appendChild(allBtn);
}

function toggleVersion(ver, label) {
  if (selectedVersions.has(ver)) {
    if (selectedVersions.size <= 1) return;
    selectedVersions.delete(ver);
    label.classList.remove('active');
  } else {
    selectedVersions.add(ver);
    label.classList.add('active');
  }
  renderComparison();
}

function toggleAllVersions() {
  const allSelected = selectedVersions.size === VERSIONS.length;
  if (allSelected) {
    selectedVersions = new Set([VERSIONS[0]]);
  } else {
    selectedVersions = new Set(VERSIONS);
  }
  document.querySelectorAll('.version-check').forEach(el => {
    el.classList.toggle('active', selectedVersions.has(el.dataset.ver));
  });
  renderComparison();
}

function selectSample(name) {
  if (animFrameId) { cancelAnimationFrame(animFrameId); animFrameId = null; }
  currentSample = name;
  document.querySelectorAll('.sample-tab').forEach(t => {
    t.classList.toggle('active', t.textContent === name);
  });
  renderComparison();
}

function renderComparison() {
  const content = document.getElementById('content');
  const activeVersions = VERSIONS.filter(v => selectedVersions.has(v));
  const ref = getFirstAvailableSample(currentSample);
  if (!ref) {
    content.innerHTML = '<div class="card no-data-hint">该样本无数据</div>';
    return;
  }

  tipData = {};
  let html = '';

  // Video card
  html += '<div class="card">';
  html += '<div class="card-title">原始视频</div>';
  html += '<div class="video-panel"><div class="video-row">';
  html += `<video id="videoPlayer" controls preload="metadata" src="${videoSrc(ref.video)}"></video>`;
  html += '<div class="video-side">';
  html += '<div class="video-time-display">';
  html += '<span class="video-time-current" id="videoTimeDisplay">0:00</span>';
  html += `<span>/ ${fmtTime(ref.total)}</span>`;
  html += '</div>';
  html += '<div class="video-segment-info" id="segmentInfo">加载中...</div>';
  html += '<div class="speed-control">';
  html += '<span style="font-size:12px;color:#94a3b8">倍速:</span>';
  [0.5, 1, 1.5, 2, 4].forEach(sp => {
    html += `<div class="speed-btn${sp === 1 ? ' active' : ''}" onclick="setSpeed(${sp}, this)">${sp}x</div>`;
  });
  html += '</div>';
  html += '<div class="info-row" style="margin-top:8px;margin-bottom:0">';
  html += `<div class="info-item">样本: <span class="info-value">${currentSample}</span></div>`;
  html += '</div>';
  html += '</div></div></div></div>';

  // Timeline comparison card
  const total = ref.total;
  html += '<div class="card">';
  html += '<div class="card-title">时间线多版本对比</div>';
  html += '<div class="timeline-panel"><div class="timeline-container" id="timelineContainer">';

  if (ref.ground_truth) {
    const tipKey = 'gt';
    tipData[tipKey] = ref.ground_truth;
    html += renderTimelineRow('Ground Truth', ref.ground_truth, total, tipKey);
    html += '<div class="timeline-divider"></div>';
  }

  activeVersions.forEach((ver, vi) => {
    const s = getSampleForVersion(currentSample, ver);
    if (!s) {
      html += `<div class="timeline-row"><div class="timeline-label"><span class="ver-tag" style="background:${verColor(ver)}">${ver}</span></div><div class="timeline-bar-area" style="display:flex;align-items:center;justify-content:center;color:#94a3b8;font-size:12px">无数据</div></div>`;
    } else {
      const tipKey = 'v_' + ver;
      tipData[tipKey] = s.combined_bars;
      const labelHtml = `<span class="ver-tag" style="background:${verColor(ver)}">${ver}</span>`;
      html += renderTimelineRow(labelHtml, s.combined_bars, total, tipKey);
    }
    if (vi < activeVersions.length - 1) {
      html += '<div class="timeline-divider"></div>';
    }
  });

  html += renderTimeAxis(total);
  html += renderCombinedLegend(ref, activeVersions);
  html += '</div></div>';

  // IoU comparison table
  if (ref.ground_truth) {
    html += renderIouCompareTable(ref.ground_truth, activeVersions, total);
  }
  html += '</div>';

  // Optical flow
  if (ref.optical_flow && ref.optical_flow.length > 0) {
    html += '<div class="card">';
    html += '<div class="card-title">光流强度 (Optical Flow)</div>';
    html += '<div class="flow-chart-wrap" id="flowChartWrap">';
    html += '<canvas class="flow-chart" id="flowChart"></canvas>';
    html += '<div class="flow-playhead" id="flowPlayhead" style="display:none"></div>';
    html += '</div></div>';
  }

  // Exercise details with tabs per version
  const versionsWithDetails = activeVersions.filter(ver => {
    const s = getSampleForVersion(currentSample, ver);
    return s && s.exercise_details && s.exercise_details.length > 0;
  });
  if (versionsWithDetails.length > 0) {
    html += '<div class="card">';
    html += '<div class="card-title">动作识别详情 (Phase 2)</div>';
    if (versionsWithDetails.length > 1) {
      html += '<div class="ex-tabs" id="exTabs">';
      versionsWithDetails.forEach((ver, i) => {
        html += `<div class="ex-tab${i === 0 ? ' active' : ''}" onclick="switchExTab('${ver}', this)" style="border-left:3px solid ${verColor(ver)}">${VERSION_LABELS[ver] || ver}</div>`;
      });
      html += '</div>';
    }
    versionsWithDetails.forEach((ver, i) => {
      const s = getSampleForVersion(currentSample, ver);
      html += `<div class="ex-content" id="exContent_${ver}" style="display:${i === 0 ? 'block' : 'none'}">`;
      html += '<table class="ex-table"><thead><tr>';
      html += '<th>片段</th><th>时间范围</th><th>器械</th><th>动作</th><th>置信度</th><th>组数</th><th>总次数</th><th>组次详情</th>';
      html += '</tr></thead><tbody>';
      s.exercise_details.forEach(d => {
        const setsDetail = (d.sets || []).map(st =>
          `${st.start_time || ''}-${st.end_time || ''} ×${st.reps || '?'}`
        ).join('; ');
        const totalSets = d.total_sets || (d.sets || []).length || '-';
        const totalReps = d.total_reps || '-';
        html += `<tr class="ex-row" data-start="${d.start}" data-end="${d.end}" style="cursor:pointer">
          <td>${d.segmentId}</td>
          <td>${fmtTime(d.start)} - ${fmtTime(d.end)}</td>
          <td>${d.equipment}</td>
          <td><strong>${d.exercise}</strong></td>
          <td>${(d.confidence * 100).toFixed(0)}%</td>
          <td style="text-align:center;font-weight:bold">${totalSets}</td>
          <td style="text-align:center;font-weight:bold">${totalReps}</td>
          <td style="font-size:0.85em">${setsDetail || '-'}</td>
        </tr>`;
      });
      html += '</tbody></table></div>';
    });
    html += '</div>';
  }

  content.innerHTML = html;

  videoEl = document.getElementById('videoPlayer');
  if (videoEl) {
    videoEl.addEventListener('timeupdate', onVideoTimeUpdate);
    videoEl.addEventListener('seeked', onVideoTimeUpdate);
    document.querySelectorAll('.ex-row').forEach(row => {
      row.onclick = () => {
        const t = parseFloat(row.dataset.start);
        if (videoEl && !isNaN(t)) { videoEl.currentTime = t; videoEl.play(); }
      };
    });
    startPlayheadLoop();
  }

  if (ref.optical_flow && ref.optical_flow.length > 0) {
    requestAnimationFrame(() => drawFlowChart(ref));
  }
}

function switchExTab(ver, btn) {
  document.querySelectorAll('.ex-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.ex-content').forEach(c => c.style.display = 'none');
  const el = document.getElementById('exContent_' + ver);
  if (el) el.style.display = 'block';
}

function setSpeed(speed, btn) {
  if (videoEl) videoEl.playbackRate = speed;
  document.querySelectorAll('.speed-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
}

function startPlayheadLoop() {
  if (animFrameId) cancelAnimationFrame(animFrameId);
  function tick() {
    if (!videoEl) return;
    updatePlayheads(videoEl.currentTime);
    animFrameId = requestAnimationFrame(tick);
  }
  animFrameId = requestAnimationFrame(tick);
}

function onVideoTimeUpdate() {
  if (!videoEl) return;
  updatePlayheads(videoEl.currentTime);
}

function updatePlayheads(currentTime) {
  const ref = getFirstAvailableSample(currentSample);
  if (!ref) return;
  const pct = (currentTime / ref.total * 100);
  const disp = document.getElementById('videoTimeDisplay');
  if (disp) disp.textContent = fmtTimePrecise(currentTime);
  document.querySelectorAll('.playhead').forEach(ph => { ph.style.left = pct + '%'; });
  const flowPh = document.getElementById('flowPlayhead');
  if (flowPh) {
    const canvas = document.getElementById('flowChart');
    if (canvas) {
      const padL = 160, padR = 20;
      const w = canvas.width - padL - padR;
      const x = padL + (currentTime / ref.total) * w;
      flowPh.style.left = x + 'px';
      flowPh.style.display = 'block';
    }
  }
  updateSegmentInfo(currentTime);
}

function updateSegmentInfo(t) {
  const info = document.getElementById('segmentInfo');
  if (!info) return;
  let html = '';
  const ref = getFirstAvailableSample(currentSample);
  if (ref && ref.ground_truth) {
    const gtSeg = ref.ground_truth.find(seg => t >= seg.start && t < seg.end);
    if (gtSeg) html += `<span class="seg-badge" style="background:${gtSeg.color}">GT: ${gtSeg.label}</span>`;
  }
  const activeVersions = VERSIONS.filter(v => selectedVersions.has(v));
  activeVersions.forEach(ver => {
    const s = getSampleForVersion(currentSample, ver);
    if (!s) return;
    const seg = s.combined_bars.find(seg => t >= seg.start && t < seg.end);
    if (seg) html += `<span class="seg-badge" style="background:${verColor(ver)}">${ver}: ${seg.label}</span>`;
  });
  if (!html) html = '<span style="color:#94a3b8">—</span>';
  info.innerHTML = html;
}

function seekToTime(e, total) {
  if (!videoEl) return;
  const bar = e.currentTarget;
  const rect = bar.getBoundingClientRect();
  const x = e.clientX - rect.left;
  videoEl.currentTime = (x / rect.width) * total;
}

function renderTimelineRow(label, bars, total, tipKey) {
  let html = '<div class="timeline-row">';
  html += `<div class="timeline-label">${label}</div>`;
  html += `<div class="timeline-bar-area" onclick="seekToTime(event, ${total})">`;
  html += '<div class="playhead" style="left:0%"></div>';
  bars.forEach((b, i) => {
    const left = (b.start / total * 100).toFixed(4);
    const width = ((b.end - b.start) / total * 100).toFixed(4);
    const minWidth = Math.max(parseFloat(width), 0.3);
    html += `<div class="timeline-segment" data-tipkey="${tipKey}" data-idx="${i}"
      style="left:${left}%;width:${minWidth}%;background:${b.color}"
      onmouseenter="showTip(event,'${tipKey}',${i})"
      onmousemove="moveTip(event)"
      onmouseleave="hideTip()">`;
    if (parseFloat(width) > 4) {
      let lbl = b.label;
      if (b.total_reps) lbl += ' ×' + b.total_reps;
      html += `<span>${lbl}</span>`;
    }
    html += '</div>';
  });
  html += '</div></div>';
  return html;
}

function renderTimeAxis(total) {
  let html = '<div class="time-axis"><div class="time-axis-label"></div><div class="time-axis-area">';
  const step = total <= 120 ? 15 : total <= 300 ? 30 : 60;
  for (let t = 0; t <= total; t += step) {
    const pct = (t / total * 100).toFixed(2);
    html += `<div class="time-tick" style="left:${pct}%">${fmtTime(t)}</div>`;
  }
  html += '</div></div>';
  return html;
}

function renderCombinedLegend(ref, activeVersions) {
  const seen = new Map();
  const addBars = (bars) => { bars.forEach(b => { if (!seen.has(b.label) && b.label !== 'TRANSITION') seen.set(b.label, b.color); }); };
  if (ref.ground_truth) addBars(ref.ground_truth);
  activeVersions.forEach(ver => {
    const s = getSampleForVersion(currentSample, ver);
    if (s) addBars(s.combined_bars);
  });
  seen.set('过渡/TRANSITION', '#9CA3AF');
  seen.set('REST', '#3B82F6');
  let html = '<div class="legend">';
  seen.forEach((color, label) => {
    html += `<div class="legend-item"><div class="legend-color" style="background:${color}"></div>${label}</div>`;
  });
  html += '</div>';
  return html;
}

function showTip(e, tipKey, idx) {
  const bars = tipData[tipKey];
  if (!bars) return;
  const b = bars[idx];
  let verLabel = tipKey === 'gt' ? 'Ground Truth' : tipKey.replace('v_', '');
  let html = `<strong>[${verLabel}] ${b.label}</strong><br>`;
  html += `${fmtTime(b.start)} → ${fmtTime(b.end)} (${(b.end - b.start).toFixed(1)}s)`;
  if (b.state) html += `<br>状态: ${b.state}`;
  if (b.confidence) html += ` | 置信度: ${(b.confidence * 100).toFixed(0)}%`;
  if (b.reason) html += `<br>${b.reason}`;
  if (b.equipment) html += `<br>器械: ${b.equipment}`;
  if (b.total_sets) html += `<br>组数: ${b.total_sets}`;
  if (b.total_reps) html += `<br>总次数: ${b.total_reps}`;
  if (b.type) html += `<br>类型: ${b.type}`;
  html += `<br><em style="opacity:0.6">点击时间线可跳转视频</em>`;
  tooltip.innerHTML = html;
  tooltip.style.display = 'block';
  moveTip(e);
}
function moveTip(e) {
  tooltip.style.left = Math.min(e.clientX + 12, window.innerWidth - 340) + 'px';
  tooltip.style.top = Math.min(e.clientY + 12, window.innerHeight - 100) + 'px';
}
function hideTip() { tooltip.style.display = 'none'; }

function drawFlowChart(ref) {
  const canvas = document.getElementById('flowChart');
  if (!canvas) return;
  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width;
  canvas.height = 120;
  const ctx = canvas.getContext('2d');
  const flow = ref.optical_flow;
  const total = ref.total;
  const padL = 160, padR = 20, padT = 10, padB = 24;
  const w = canvas.width - padL - padR;
  const h = canvas.height - padT - padB;

  canvas.onclick = (e) => {
    if (!videoEl) return;
    const cr = canvas.getBoundingClientRect();
    const x = e.clientX - cr.left - padL;
    if (x < 0 || x > w) return;
    videoEl.currentTime = (x / w) * total;
  };
  canvas.style.cursor = 'pointer';

  ref.combined_bars.forEach(b => {
    const x0 = padL + (b.start / total) * w;
    const x1 = padL + (b.end / total) * w;
    ctx.fillStyle = b.color + '18';
    ctx.fillRect(x0, padT, x1 - x0, h);
  });

  let maxV = 0;
  flow.forEach(f => { if (f.v > maxV) maxV = f.v; });
  maxV = maxV * 1.1 || 1;

  ctx.beginPath();
  ctx.strokeStyle = '#6366f1';
  ctx.lineWidth = 1.5;
  flow.forEach((f, i) => {
    const x = padL + (f.t / total) * w;
    const y = padT + h - (f.v / maxV) * h;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();

  const lastF = flow[flow.length - 1];
  ctx.lineTo(padL + (lastF.t / total) * w, padT + h);
  ctx.lineTo(padL + (flow[0].t / total) * w, padT + h);
  ctx.closePath();
  ctx.fillStyle = 'rgba(99,102,241,0.1)';
  ctx.fill();

  ctx.fillStyle = '#94a3b8';
  ctx.font = '10px sans-serif';
  ctx.textAlign = 'center';
  const step = total <= 120 ? 15 : total <= 300 ? 30 : 60;
  for (let t = 0; t <= total; t += step) {
    const x = padL + (t / total) * w;
    ctx.fillText(fmtTime(t), x, canvas.height - 4);
    ctx.beginPath(); ctx.strokeStyle = '#e2e8f0'; ctx.lineWidth = 0.5;
    ctx.moveTo(x, padT); ctx.lineTo(x, padT + h); ctx.stroke();
  }

  ctx.fillStyle = '#94a3b8';
  ctx.font = '10px sans-serif';
  ctx.textAlign = 'right';
  ctx.fillText(maxV.toFixed(1), padL - 4, padT + 10);
  ctx.fillText('0', padL - 4, padT + h);
}

function classifyGt(seg) {
  if (seg.type) {
    const t = seg.type.toLowerCase();
    if (t === 'exercise') return 'exercise';
    if (t === 'rest') return 'rest';
    return 'transition';
  }
  const l = (seg.label || '').toLowerCase();
  if (l === '过渡' || l === 'transition' || l === '') return 'transition';
  if (l === '休息' || l === 'rest') return 'rest';
  return 'exercise';
}

function classifyModel(bar) {
  const st = (bar.state || '').toUpperCase();
  if (st === 'EXERCISE') return 'exercise';
  if (st === 'REST') return 'rest';
  return 'transition';
}

function computeIou(gtBars, modelBars, total) {
  const step = 0.5;
  const classes = ['exercise', 'rest', 'transition'];
  const counts = {};
  classes.forEach(c => { counts[c] = {inter: 0, union: 0}; });
  let totalCorrect = 0, totalSteps = 0;

  for (let t = 0; t < total; t += step) {
    let gtClass = 'transition';
    for (const seg of gtBars) {
      if (t >= seg.start && t < seg.end) { gtClass = classifyGt(seg); break; }
    }
    let mdClass = 'transition';
    for (const bar of modelBars) {
      if (t >= bar.start && t < bar.end) { mdClass = classifyModel(bar); break; }
    }
    classes.forEach(c => {
      const inGt = gtClass === c;
      const inMd = mdClass === c;
      if (inGt && inMd) counts[c].inter++;
      if (inGt || inMd) counts[c].union++;
    });
    if (gtClass === mdClass) totalCorrect++;
    totalSteps++;
  }

  const result = {};
  classes.forEach(c => {
    result[c] = counts[c].union > 0 ? counts[c].inter / counts[c].union : null;
  });
  result.accuracy = totalSteps > 0 ? totalCorrect / totalSteps : 0;

  let sumIou = 0, n = 0;
  classes.forEach(c => { if (result[c] !== null) { sumIou += result[c]; n++; } });
  result.mIoU = n > 0 ? sumIou / n : 0;
  return result;
}

function iouClass(v) { return v >= 0.7 ? 'high' : v >= 0.4 ? 'mid' : 'low'; }

function renderIouCompareTable(gtBars, activeVersions, total) {
  const metrics = ['mIoU', 'Accuracy', 'Exercise IoU', 'Rest IoU', 'Transition IoU'];
  const keys = ['mIoU', 'accuracy', 'exercise', 'rest', 'transition'];
  const ious = {};
  activeVersions.forEach(ver => {
    const s = getSampleForVersion(currentSample, ver);
    if (s) ious[ver] = computeIou(gtBars, s.combined_bars, total);
  });

  let html = '<div style="margin-top:16px;padding-top:12px;border-top:1px solid #f1f5f9">';
  html += '<div style="font-size:13px;font-weight:600;color:#166534;margin-bottom:8px">IoU 指标对比</div>';
  html += '<table class="iou-compare-table"><thead><tr><th>指标</th>';
  activeVersions.forEach(ver => {
    html += `<th><span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${verColor(ver)};margin-right:4px;vertical-align:middle"></span>${VERSION_LABELS[ver] || ver}</th>`;
  });
  html += '</tr></thead><tbody>';

  metrics.forEach((label, mi) => {
    const k = keys[mi];
    let best = -1;
    activeVersions.forEach(ver => {
      const v = ious[ver] ? ious[ver][k] : null;
      if (v !== null && v > best) best = v;
    });
    html += `<tr><td>${label}</td>`;
    activeVersions.forEach(ver => {
      const v = ious[ver] ? ious[ver][k] : null;
      if (v === null || v === undefined) {
        html += '<td>-</td>';
      } else {
        const pct = (v * 100).toFixed(1);
        const cls = iouClass(v);
        const isBest = activeVersions.length > 1 && v === best && activeVersions.filter(vv => ious[vv] && ious[vv][k] === best).length === 1;
        html += `<td class="${isBest ? 'best-cell' : ''}"><span class="iou-score ${cls}">${pct}%</span></td>`;
      }
    });
    html += '</tr>';
  });
  html += '</tbody></table></div>';
  return html;
}

init();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
