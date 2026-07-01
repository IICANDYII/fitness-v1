"""
ego_keyframe_sampler.py - 第一人称交互感知关键帧抽样器 (Ego-Interaction Keyframe Sampler)

替代旧的 1fps 均匀抽帧方案，通过 CV 检测 + 信息量评分选出高质量关键帧。

流程：
  1. 密集候选采样 (5-10fps)
  2. 手部/器材/人体检测
  3. 推断 ego hand & active equipment
  4. 噪声过滤
  5. 帧信息量评分
  6. 窗口 Top-K + 端点帧 + 锚点帧 + 去重
  7. 背景抑制 & 标注渲染
  8. 输出 contact sheet + cv_summary.json
"""

from __future__ import annotations

import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml


# ──────────────────────────────────────────────
# 数据类
# ──────────────────────────────────────────────

@dataclass
class HandDetection:
    bbox: list[int]           # [x1, y1, x2, y2]
    confidence: float
    ego_hand_score: float = 0.0
    is_ego_hand: bool = False

@dataclass
class EquipmentDetection:
    label: str
    bbox: list[int]           # [x1, y1, x2, y2]
    confidence: float
    active_equipment_score: float = 0.0
    is_active_equipment: bool = False

@dataclass
class PersonDetection:
    bbox: list[int]           # [x1, y1, x2, y2]
    confidence: float
    area_ratio: float = 0.0   # person bbox area / frame area

@dataclass
class CandidateFrame:
    index: int
    timestamp: float
    image: np.ndarray
    image_path: str | None = None
    hands: list[HandDetection] = field(default_factory=list)
    equipment: list[EquipmentDetection] = field(default_factory=list)
    persons: list[PersonDetection] = field(default_factory=list)
    ego_hand_score: float = 0.0
    active_equipment_score: float = 0.0
    hand_equipment_interaction_score: float = 0.0
    motion_value_score: float = 0.0
    sharpness_score: float = 0.0
    scene_context_score: float = 0.0
    person_noise_score: float = 0.0
    background_equipment_noise_score: float = 0.0
    frame_info_score: float = 0.0
    is_filtered: bool = False
    filter_reason: str = ""
    selection_reason: str = ""


# ──────────────────────────────────────────────
# 配置加载
# ──────────────────────────────────────────────

def load_config(config_path: str | Path | None = None) -> dict:
    if config_path is None:
        config_path = Path(__file__).parent / "keyframe_config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return raw.get("ego_interaction_keyframe_sampler", raw)


# ──────────────────────────────────────────────
# 模型管理（懒加载）
# ──────────────────────────────────────────────

_equip_model = None
_person_model = None
_rf_client = None
_hand_model_local = None
_models_loaded = False

_YOLO_DIR = Path(__file__).parent / "yolo"
EQUIP_MODEL_PATH = _YOLO_DIR / "runs" / "detect" / "runs" / "fitness_equipment_test" / "weights" / "best.pt"
PERSON_MODEL_PATH = _YOLO_DIR / "person-seg" / "yolo12l-person-seg.pt"
HAND_MODEL_LOCAL_PATH = _YOLO_DIR / "runs" / "detect" / "runs" / "hand_detection_test" / "weights" / "best.pt"

ROBOFLOW_API_URL = "https://serverless.roboflow.com"
ROBOFLOW_API_KEY = "93cfYbfIdFrloQ3NmyhU"
ROBOFLOW_WORKSPACE = "boyu-yang-jh3ze"
ROBOFLOW_WORKFLOW_ID = "general-segmentation-api-5"
ROBOFLOW_HAND_CLASSES = "Hand, hand"


def _load_models():
    global _equip_model, _person_model, _rf_client, _hand_model_local, _models_loaded
    if _models_loaded:
        return
    from ultralytics import YOLO

    if EQUIP_MODEL_PATH.exists():
        _equip_model = YOLO(str(EQUIP_MODEL_PATH))
        print(f"[KeyframeSampler] 器材检测模型: {EQUIP_MODEL_PATH.name}")
    else:
        print(f"[KeyframeSampler] 警告: 器材检测模型不存在")

    if PERSON_MODEL_PATH.exists():
        _person_model = YOLO(str(PERSON_MODEL_PATH))
        print(f"[KeyframeSampler] Person 检测模型: {PERSON_MODEL_PATH.name}")
    else:
        print(f"[KeyframeSampler] 警告: Person 检测模型不存在，将跳过 person 检测")

    if HAND_MODEL_LOCAL_PATH.exists():
        _hand_model_local = YOLO(str(HAND_MODEL_LOCAL_PATH))
        print(f"[KeyframeSampler] 本地手部检测模型: {HAND_MODEL_LOCAL_PATH.name}")

    try:
        from inference_sdk import InferenceHTTPClient
        _rf_client = InferenceHTTPClient(
            api_url=ROBOFLOW_API_URL,
            api_key=ROBOFLOW_API_KEY,
        )
        print(f"[KeyframeSampler] Roboflow 手部检测 API 已连接")
    except Exception as e:
        print(f"[KeyframeSampler] Roboflow API 初始化失败: {e}")

    _models_loaded = True


# ──────────────────────────────────────────────
# Step 1: 密集候选采样
# ──────────────────────────────────────────────

def sample_candidate_frames(
    video_path: str | Path,
    start_sec: float,
    end_sec: float,
    fps: int = 5,
    max_frames: int = 300,
    frame_w: int = 640,
    frame_h: int = 360,
) -> list[CandidateFrame]:
    """从视频的 [start_sec, end_sec] 区间按指定 fps 密集采样候选帧。"""
    video_path = Path(video_path)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频: {video_path}")

    video_fps = cap.get(cv2.CAP_PROP_FPS)
    if video_fps <= 0:
        cap.release()
        raise RuntimeError(f"视频 FPS 无效: {video_fps}")

    interval = max(1, round(video_fps / fps))
    start_frame = int(start_sec * video_fps)
    end_frame = int(end_sec * video_fps)

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    candidates = []
    frame_idx = start_frame
    sample_idx = 0

    while frame_idx <= end_frame and len(candidates) < max_frames:
        ret, frame = cap.read()
        if not ret:
            break

        if (frame_idx - start_frame) % interval == 0:
            timestamp = frame_idx / video_fps
            resized = cv2.resize(frame, (frame_w, frame_h), interpolation=cv2.INTER_AREA)
            candidates.append(CandidateFrame(
                index=sample_idx,
                timestamp=round(timestamp, 3),
                image=resized,
            ))
            sample_idx += 1

        frame_idx += 1

    cap.release()
    print(f"[KeyframeSampler] 候选采样: {len(candidates)} 帧 "
          f"({start_sec:.1f}s - {end_sec:.1f}s, {fps}fps)")
    return candidates


# ──────────────────────────────────────────────
# Step 2: CV 检测
# ──────────────────────────────────────────────

def _detect_hands_roboflow(img: np.ndarray) -> list[HandDetection]:
    """调用 Roboflow API 检测手部。"""
    if _rf_client is None:
        return []
    import tempfile
    try:
        _, tmp = tempfile.mkstemp(suffix=".jpg")
        cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tofile(tmp)
        result = _rf_client.run_workflow(
            workspace_name=ROBOFLOW_WORKSPACE,
            workflow_id=ROBOFLOW_WORKFLOW_ID,
            images={"image": tmp},
            parameters={"classes": ROBOFLOW_HAND_CLASSES},
            use_cache=True,
        )
        Path(tmp).unlink(missing_ok=True)

        hands = []
        if result and isinstance(result, list):
            for item in result:
                preds = item.get("predictions", item.get("output", {}))
                if isinstance(preds, dict):
                    preds = preds.get("predictions", [])
                if isinstance(preds, list):
                    for pred in preds:
                        if isinstance(pred, dict) and "x" in pred:
                            cx, cy = pred["x"], pred["y"]
                            w, h = pred.get("width", 0), pred.get("height", 0)
                            hands.append(HandDetection(
                                bbox=[int(cx - w/2), int(cy - h/2),
                                      int(cx + w/2), int(cy + h/2)],
                                confidence=pred.get("confidence", 0.5),
                            ))
        return hands
    except Exception as e:
        Path(tmp).unlink(missing_ok=True)
        return []


def _detect_hands_local(img: np.ndarray) -> list[HandDetection]:
    """使用本地 YOLO 模型检测手部。"""
    if _hand_model_local is None:
        return []
    try:
        results = _hand_model_local(img, verbose=False)[0]
        hands = []
        if results.boxes is not None:
            for box in results.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                conf = float(box.conf[0])
                hands.append(HandDetection(
                    bbox=[int(x1), int(y1), int(x2), int(y2)],
                    confidence=conf,
                ))
        return hands
    except Exception:
        return []


def _detect_equipment(img: np.ndarray) -> list[EquipmentDetection]:
    """使用本地 YOLO 模型检测器材。"""
    if _equip_model is None:
        return []
    try:
        results = _equip_model(img, verbose=False)[0]
        equipment = []
        if results.boxes is not None:
            for box in results.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                label = results.names.get(cls_id, str(cls_id))
                if label.lower() == "person":
                    continue
                equipment.append(EquipmentDetection(
                    label=label,
                    bbox=[int(x1), int(y1), int(x2), int(y2)],
                    confidence=conf,
                ))
        return equipment
    except Exception:
        return []


def _detect_persons(img: np.ndarray) -> list[PersonDetection]:
    """使用 YOLO person-seg 模型检测人体。"""
    if _person_model is None:
        return []
    try:
        results = _person_model(img, classes=0, conf=0.4, verbose=False)[0]
        persons = []
        h, w = img.shape[:2]
        frame_area = h * w
        if results.boxes is not None:
            for box in results.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                conf = float(box.conf[0])
                box_area = (x2 - x1) * (y2 - y1)
                persons.append(PersonDetection(
                    bbox=[int(x1), int(y1), int(x2), int(y2)],
                    confidence=conf,
                    area_ratio=box_area / frame_area if frame_area > 0 else 0,
                ))
        return persons
    except Exception:
        return []


def run_cv_detection(
    candidates: list[CandidateFrame],
    use_roboflow: bool = True,
    batch_size: int = 4,
) -> None:
    """对所有候选帧执行三类 CV 检测（并行）。"""
    _load_models()
    total = len(candidates)
    print(f"[KeyframeSampler] CV 检测: {total} 帧...")
    t0 = time.time()

    def detect_one(cf: CandidateFrame):
        img = cf.image
        if use_roboflow and _rf_client is not None:
            cf.hands = _detect_hands_roboflow(img)
        else:
            cf.hands = _detect_hands_local(img)
        cf.equipment = _detect_equipment(img)
        cf.persons = _detect_persons(img)

    with ThreadPoolExecutor(max_workers=batch_size) as pool:
        futures = {pool.submit(detect_one, cf): i for i, cf in enumerate(candidates)}
        done = 0
        for fut in as_completed(futures):
            done += 1
            if done % 20 == 0 or done == total:
                print(f"  [{done}/{total}] 检测完成")
            fut.result()

    elapsed = time.time() - t0
    print(f"[KeyframeSampler] CV 检测完成: {elapsed:.1f}s")


# ──────────────────────────────────────────────
# Step 3: Ego Hand 推断
# ──────────────────────────────────────────────

def _bbox_center(bbox: list[int]) -> tuple[float, float]:
    return (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2

def _bbox_area(bbox: list[int]) -> float:
    return max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1])

def _bbox_iou(a: list[int], b: list[int]) -> float:
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area_a = _bbox_area(a)
    area_b = _bbox_area(b)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0

def _bbox_distance(a: list[int], b: list[int]) -> float:
    ca = _bbox_center(a)
    cb = _bbox_center(b)
    return math.sqrt((ca[0] - cb[0])**2 + (ca[1] - cb[1])**2)

def _is_inside(inner: list[int], outer: list[int], threshold: float = 0.6) -> bool:
    """判断 inner bbox 是否大部分在 outer bbox 内部。"""
    x1 = max(inner[0], outer[0])
    y1 = max(inner[1], outer[1])
    x2 = min(inner[2], outer[2])
    y2 = min(inner[3], outer[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    inner_area = _bbox_area(inner)
    return (inter / inner_area) >= threshold if inner_area > 0 else False


def compute_ego_hand_score(
    hand: HandDetection,
    equipment: list[EquipmentDetection],
    persons: list[PersonDetection],
    frame_h: int,
    frame_w: int,
) -> float:
    """计算单个手部候选的 ego_hand_score。"""
    cx, cy = _bbox_center(hand.bbox)
    hand_area = _bbox_area(hand.bbox)
    frame_area = frame_h * frame_w

    # position_prior: 偏向画面下半区和边缘
    y_ratio = cy / frame_h
    position_prior = max(0, min(1, (y_ratio - 0.3) / 0.5))

    # size_prior: 偏向较大的手（近景）
    size_ratio = hand_area / frame_area if frame_area > 0 else 0
    size_prior = min(1.0, size_ratio / 0.05)

    # equipment_proximity: 与最近器材的接近度
    equipment_proximity = 0.0
    if equipment:
        min_dist = min(_bbox_distance(hand.bbox, eq.bbox) for eq in equipment)
        max_dist = math.sqrt(frame_w**2 + frame_h**2)
        equipment_proximity = max(0, 1 - min_dist / (max_dist * 0.3))

    # temporal_persistence: 在单帧中无法计算，设为中值
    temporal_persistence = 0.5

    # edge_origin_prior: 手部从画面边缘进入
    margin = 0.1
    from_left = cx / frame_w < margin
    from_right = cx / frame_w > (1 - margin)
    from_bottom = cy / frame_h > (1 - margin)
    edge_origin_prior = 0.8 if (from_left or from_right or from_bottom) else 0.3

    # motion_consistency: 单帧无法计算
    motion_consistency = 0.5

    # inside_person_penalty: 手部在 person bbox 内部
    inside_person = 0.0
    for p in persons:
        if _is_inside(hand.bbox, p.bbox, threshold=0.5):
            inside_person = 1.0
            break

    score = (
        0.25 * position_prior
        + 0.20 * size_prior
        + 0.20 * equipment_proximity
        + 0.15 * temporal_persistence
        + 0.10 * edge_origin_prior
        + 0.10 * motion_consistency
        - 0.30 * inside_person
    )
    return max(0.0, min(1.0, score))


def infer_ego_hands(candidates: list[CandidateFrame], threshold: float = 0.55) -> None:
    """推断所有候选帧中哪些手部属于当前用户。"""
    # 先做单帧推断
    for cf in candidates:
        h, w = cf.image.shape[:2]
        for hand in cf.hands:
            score = compute_ego_hand_score(
                hand, cf.equipment, cf.persons, h, w
            )
            hand.ego_hand_score = score
            hand.is_ego_hand = score > threshold

    # 时序一致性增强：连续帧中在相似位置出现的手部提升得分
    for i in range(1, len(candidates) - 1):
        cf = candidates[i]
        for hand in cf.hands:
            if hand.is_ego_hand:
                continue
            prev_ego = [h for h in candidates[i-1].hands if h.is_ego_hand]
            next_ego = [h for h in candidates[i+1].hands if h.is_ego_hand]
            if prev_ego or next_ego:
                ref_hands = prev_ego + next_ego
                for rh in ref_hands:
                    dist = _bbox_distance(hand.bbox, rh.bbox)
                    h_frame = cf.image.shape[0]
                    if dist < h_frame * 0.2:
                        hand.ego_hand_score = min(1.0, hand.ego_hand_score + 0.15)
                        hand.is_ego_hand = hand.ego_hand_score > threshold
                        break

    # 汇总每帧最高 ego_hand_score
    for cf in candidates:
        ego_scores = [h.ego_hand_score for h in cf.hands if h.is_ego_hand]
        cf.ego_hand_score = max(ego_scores) if ego_scores else 0.0


# ──────────────────────────────────────────────
# Step 4: Active Equipment 推断
# ──────────────────────────────────────────────

def compute_active_equipment_score(
    equip: EquipmentDetection,
    ego_hands: list[HandDetection],
    frame_h: int,
    frame_w: int,
) -> float:
    """计算单个器材候选的 active_equipment_score。"""
    detection_confidence = equip.confidence

    # ego_hand_proximity
    ego_hand_proximity = 0.0
    if ego_hands:
        min_dist = min(_bbox_distance(equip.bbox, h.bbox) for h in ego_hands)
        max_dist = math.sqrt(frame_w**2 + frame_h**2)
        ego_hand_proximity = max(0, 1 - min_dist / (max_dist * 0.25))

    # motion_sync: 单帧无法计算
    motion_sync = 0.5

    # temporal_persistence: 单帧无法计算
    temporal_persistence = 0.5

    # center_relevance: 偏向画面中心
    cx, cy = _bbox_center(equip.bbox)
    dx = abs(cx / frame_w - 0.5) * 2
    dy = abs(cy / frame_h - 0.5) * 2
    center_relevance = max(0, 1 - (dx + dy) / 2)

    # background_penalty: 小面积远处器材
    equip_area = _bbox_area(equip.bbox)
    frame_area = frame_h * frame_w
    area_ratio = equip_area / frame_area if frame_area > 0 else 0
    background_penalty = max(0, 1 - area_ratio / 0.02) if area_ratio < 0.02 else 0

    score = (
        0.30 * detection_confidence
        + 0.25 * ego_hand_proximity
        + 0.20 * motion_sync
        + 0.15 * temporal_persistence
        + 0.10 * center_relevance
        - 0.20 * background_penalty
    )
    return max(0.0, min(1.0, score))


def infer_active_equipment(candidates: list[CandidateFrame], threshold: float = 0.55) -> None:
    """推断所有候选帧中哪些器材是当前用户正在交互的。"""
    # 统计器材标签在整个区间的出现频率
    label_count: dict[str, int] = {}
    for cf in candidates:
        for eq in cf.equipment:
            label_count[eq.label] = label_count.get(eq.label, 0) + 1

    total = len(candidates)
    for cf in candidates:
        h, w = cf.image.shape[:2]
        ego_hands = [hd for hd in cf.hands if hd.is_ego_hand]

        for eq in cf.equipment:
            base_score = compute_active_equipment_score(eq, ego_hands, h, w)

            # 时序稳定性加成：频繁出现的器材更可能是交互器材
            freq = label_count.get(eq.label, 0) / total if total > 0 else 0
            temporal_bonus = min(0.15, freq * 0.2)
            eq.active_equipment_score = min(1.0, base_score + temporal_bonus)
            eq.is_active_equipment = eq.active_equipment_score > threshold

    # 汇总每帧最高 active_equipment_score
    for cf in candidates:
        active_scores = [eq.active_equipment_score for eq in cf.equipment if eq.is_active_equipment]
        cf.active_equipment_score = max(active_scores) if active_scores else 0.0


# ──────────────────────────────────────────────
# Step 5: 噪声过滤
# ──────────────────────────────────────────────

def filter_low_value_frames(candidates: list[CandidateFrame], config: dict) -> None:
    """标记不适合进入 Phase2 的低价值帧。"""
    rules = config.get("filter_rules", {})
    person_dominant_ratio = rules.get("person_dominant_area_ratio", 0.25)
    hard_person_ratio = rules.get("hard_person_area_ratio", 0.45)
    min_ego_for_person = rules.get("min_ego_hand_score_for_person_frame", 0.30)
    min_active_for_person = rules.get("min_active_equipment_score_for_person_frame", 0.30)

    for cf in candidates:
        max_person_area = max((p.area_ratio for p in cf.persons), default=0)

        # Hard filter: person-dominant + no ego evidence
        if (max_person_area > hard_person_ratio
                and cf.ego_hand_score < 0.20):
            cf.is_filtered = True
            cf.filter_reason = "person_dominant_hard"
            continue

        # Soft filter: person-dominant
        if (max_person_area > person_dominant_ratio
                and cf.ego_hand_score < min_ego_for_person
                and cf.active_equipment_score < min_active_for_person):
            cf.is_filtered = True
            cf.filter_reason = "person_dominant_soft"
            continue

        # Coach demo filter
        if (max_person_area > person_dominant_ratio
                and cf.ego_hand_score < 0.1
                and cf.active_equipment_score < 0.1):
            cf.is_filtered = True
            cf.filter_reason = "coach_demo"
            continue

        # Blur filter
        if cf.sharpness_score < 0.15:
            cf.is_filtered = True
            cf.filter_reason = "blur"
            continue


# ──────────────────────────────────────────────
# Step 6: 每帧信息量评分
# ──────────────────────────────────────────────

def compute_sharpness(image: np.ndarray) -> float:
    """使用 Laplacian 方差评估图像清晰度。"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    return min(1.0, lap_var / 500.0)


def compute_interaction_score(cf: CandidateFrame) -> float:
    """计算手-器材交互分数。"""
    ego_hands = [h for h in cf.hands if h.is_ego_hand]
    active_equip = [eq for eq in cf.equipment if eq.is_active_equipment]

    if not ego_hands or not active_equip:
        return 0.0

    h, w = cf.image.shape[:2]
    max_dist = math.sqrt(w**2 + h**2)
    min_dist = float('inf')

    for hand in ego_hands:
        for eq in active_equip:
            d = _bbox_distance(hand.bbox, eq.bbox)
            min_dist = min(min_dist, d)

    if min_dist == float('inf'):
        return 0.0

    # 接触或重叠 -> 高分
    for hand in ego_hands:
        for eq in active_equip:
            if _bbox_iou(hand.bbox, eq.bbox) > 0.01:
                return 1.0

    proximity = max(0, 1 - min_dist / (max_dist * 0.2))
    return proximity


def compute_motion_value(cf: CandidateFrame, prev_cf: CandidateFrame | None) -> float:
    """通过与前一帧的差异估算运动价值。"""
    if prev_cf is None:
        return 0.5
    diff = cv2.absdiff(
        cv2.cvtColor(cf.image, cv2.COLOR_BGR2GRAY),
        cv2.cvtColor(prev_cf.image, cv2.COLOR_BGR2GRAY),
    )
    motion = diff.mean() / 255.0
    return min(1.0, motion / 0.1)


def compute_person_noise(cf: CandidateFrame) -> float:
    """计算 person 噪声分数。"""
    if not cf.persons:
        return 0.0
    max_area = max(p.area_ratio for p in cf.persons)
    if cf.ego_hand_score > 0.5:
        return max_area * 0.3
    return max_area


def compute_background_equipment_noise(cf: CandidateFrame) -> float:
    """计算背景器材噪声分数。"""
    bg_equips = [eq for eq in cf.equipment if not eq.is_active_equipment]
    if not bg_equips:
        return 0.0
    total_equip = len(cf.equipment)
    bg_ratio = len(bg_equips) / total_equip if total_equip > 0 else 0
    if cf.active_equipment_score > 0.5:
        return bg_ratio * 0.3
    return bg_ratio


def compute_frame_info_scores(candidates: list[CandidateFrame]) -> None:
    """计算所有候选帧的信息量分数。"""
    for i, cf in enumerate(candidates):
        cf.sharpness_score = compute_sharpness(cf.image)
        cf.hand_equipment_interaction_score = compute_interaction_score(cf)

        prev_cf = candidates[i - 1] if i > 0 else None
        cf.motion_value_score = compute_motion_value(cf, prev_cf)

        cf.scene_context_score = 0.5
        cf.person_noise_score = compute_person_noise(cf)
        cf.background_equipment_noise_score = compute_background_equipment_noise(cf)

        cf.frame_info_score = max(0.0, min(1.0,
            0.30 * cf.ego_hand_score
            + 0.25 * cf.active_equipment_score
            + 0.20 * cf.hand_equipment_interaction_score
            + 0.10 * cf.motion_value_score
            + 0.10 * cf.sharpness_score
            + 0.05 * cf.scene_context_score
            - 0.25 * cf.person_noise_score
            - 0.15 * cf.background_equipment_noise_score
        ))


# ──────────────────────────────────────────────
# Step 7: 关键帧选择
# ──────────────────────────────────────────────

def select_topk_by_window(
    candidates: list[CandidateFrame],
    window_sec: float = 2.0,
    top_k: int = 2,
) -> list[CandidateFrame]:
    """按时间窗口选择 Top-K 高分帧。"""
    valid = [cf for cf in candidates if not cf.is_filtered]
    if not valid:
        return []

    t_start = valid[0].timestamp
    t_end = valid[-1].timestamp
    selected = []

    t = t_start
    while t <= t_end:
        window_end = t + window_sec
        window_frames = [cf for cf in valid if t <= cf.timestamp < window_end]
        window_frames.sort(key=lambda x: x.frame_info_score, reverse=True)
        for cf in window_frames[:top_k]:
            cf.selection_reason = "window_topk"
            selected.append(cf)
        t += window_sec

    return selected


def select_endpoint_frames(
    candidates: list[CandidateFrame],
    config: dict,
) -> list[CandidateFrame]:
    """选择动作端点帧（手部/器材 y 坐标极值点）。"""
    ep_cfg = config.get("endpoint_selection", {})
    if not ep_cfg.get("enable", True):
        return []

    valid = [cf for cf in candidates if not cf.is_filtered]
    if not valid:
        return []

    endpoints = []

    # 收集 ego hand 的 y 坐标序列
    hand_y_series = []
    for cf in valid:
        ego_hands = [h for h in cf.hands if h.is_ego_hand]
        if ego_hands:
            avg_y = sum(_bbox_center(h.bbox)[1] for h in ego_hands) / len(ego_hands)
            hand_y_series.append((cf, avg_y))

    if hand_y_series and ep_cfg.get("include_hand_y_max", True):
        max_cf = max(hand_y_series, key=lambda x: x[1])[0]
        max_cf.selection_reason = "hand_y_max_endpoint"
        endpoints.append(max_cf)
    if hand_y_series and ep_cfg.get("include_hand_y_min", True):
        min_cf = min(hand_y_series, key=lambda x: x[1])[0]
        min_cf.selection_reason = "hand_y_min_endpoint"
        endpoints.append(min_cf)

    # 收集 active equipment 的 y 坐标序列
    equip_y_series = []
    for cf in valid:
        active_equips = [eq for eq in cf.equipment if eq.is_active_equipment]
        if active_equips:
            avg_y = sum(_bbox_center(eq.bbox)[1] for eq in active_equips) / len(active_equips)
            equip_y_series.append((cf, avg_y))

    if equip_y_series and ep_cfg.get("include_equipment_y_max", True):
        max_cf = max(equip_y_series, key=lambda x: x[1])[0]
        max_cf.selection_reason = "equipment_y_max_endpoint"
        endpoints.append(max_cf)
    if equip_y_series and ep_cfg.get("include_equipment_y_min", True):
        min_cf = min(equip_y_series, key=lambda x: x[1])[0]
        min_cf.selection_reason = "equipment_y_min_endpoint"
        endpoints.append(min_cf)

    # 双手距离极值
    hand_dist_series = []
    for cf in valid:
        ego_hands = [h for h in cf.hands if h.is_ego_hand]
        if len(ego_hands) >= 2:
            c0 = _bbox_center(ego_hands[0].bbox)
            c1 = _bbox_center(ego_hands[1].bbox)
            dist = math.sqrt((c0[0] - c1[0])**2 + (c0[1] - c1[1])**2)
            hand_dist_series.append((cf, dist))

    if hand_dist_series and ep_cfg.get("include_hand_distance_max", True):
        max_cf = max(hand_dist_series, key=lambda x: x[1])[0]
        max_cf.selection_reason = "hand_distance_max_endpoint"
        endpoints.append(max_cf)
    if hand_dist_series and ep_cfg.get("include_hand_distance_min", True):
        min_cf = min(hand_dist_series, key=lambda x: x[1])[0]
        min_cf.selection_reason = "hand_distance_min_endpoint"
        endpoints.append(min_cf)

    return endpoints


def select_anchor_frames(
    candidates: list[CandidateFrame],
    config: dict,
) -> list[CandidateFrame]:
    """选择时间锚点帧。"""
    anchor_cfg = config.get("anchor_frames", {})
    if not anchor_cfg.get("enable", True):
        return []

    valid = [cf for cf in candidates if not cf.is_filtered]
    if not valid:
        return []

    positions = anchor_cfg.get("positions", [0.0, 0.25, 0.5, 0.75, 1.0])
    t_start = valid[0].timestamp
    t_end = valid[-1].timestamp
    duration = t_end - t_start

    anchors = []
    for pos in positions:
        target_t = t_start + duration * pos
        closest = min(valid, key=lambda cf: abs(cf.timestamp - target_t))
        closest.selection_reason = f"anchor_{pos:.0%}"
        anchors.append(closest)

    return anchors


def _compute_phash(image: np.ndarray, hash_size: int = 8) -> int:
    """计算感知哈希。"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
    diff = resized[:, 1:] > resized[:, :-1]
    return int(np.packbits(diff.flatten()).tobytes().hex(), 16)


def _hamming_distance(h1: int, h2: int) -> int:
    return bin(h1 ^ h2).count('1')


def deduplicate_frames(
    selected: list[CandidateFrame],
    config: dict,
) -> list[CandidateFrame]:
    """多样性去重：基于 pHash 和最小时间间隔。"""
    div_cfg = config.get("diversity", {})
    if not div_cfg.get("enable", True):
        return selected

    min_gap = div_cfg.get("min_time_gap_sec", 0.3)
    phash_threshold = div_cfg.get("phash_duplicate_threshold", 6)

    # 按时间排序
    selected.sort(key=lambda cf: cf.timestamp)

    # 计算哈希
    hashes = {}
    for cf in selected:
        hashes[cf.index] = _compute_phash(cf.image)

    deduped = []
    for cf in selected:
        is_dup = False
        for kept in deduped:
            if abs(cf.timestamp - kept.timestamp) < min_gap:
                is_dup = True
                break
            if _hamming_distance(hashes[cf.index], hashes[kept.index]) < phash_threshold:
                is_dup = True
                break
        if not is_dup:
            deduped.append(cf)

    print(f"[KeyframeSampler] 去重: {len(selected)} → {len(deduped)} 帧")
    return deduped


# ──────────────────────────────────────────────
# Step 8: 背景抑制 & 标注渲染
# ──────────────────────────────────────────────

def _apply_background_suppression(
    image: np.ndarray,
    cf: CandidateFrame,
    config: dict,
) -> np.ndarray:
    """对关键帧应用背景抑制。"""
    bg_cfg = config.get("background_suppression", {})
    if not bg_cfg.get("enabled", True):
        return image.copy()

    result = image.copy()
    h, w = result.shape[:2]
    blur_kernel = bg_cfg.get("blur_kernel", 31)

    # 创建保留区域的 mask
    keep_mask = np.zeros((h, w), dtype=np.uint8)

    # 保留 ego hand 区域
    if bg_cfg.get("keep_ego_hand", True):
        for hand in cf.hands:
            if hand.is_ego_hand:
                x1, y1, x2, y2 = hand.bbox
                pad = 15
                x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
                x2, y2 = min(w, x2 + pad), min(h, y2 + pad)
                keep_mask[y1:y2, x1:x2] = 255

    # 保留 active equipment 区域
    if bg_cfg.get("keep_active_equipment", True):
        for eq in cf.equipment:
            if eq.is_active_equipment:
                x1, y1, x2, y2 = eq.bbox
                pad = 10
                x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
                x2, y2 = min(w, x2 + pad), min(h, y2 + pad)
                keep_mask[y1:y2, x1:x2] = 255

    # 保留 context equipment（非 active 但在附近）
    if bg_cfg.get("keep_context_equipment", True):
        for eq in cf.equipment:
            if not eq.is_active_equipment and eq.active_equipment_score > 0.3:
                x1, y1, x2, y2 = eq.bbox
                keep_mask[y1:y2, x1:x2] = 255

    # 模糊背景
    blurred = cv2.GaussianBlur(result, (blur_kernel, blur_kernel), 0)
    keep_mask_3ch = cv2.merge([keep_mask, keep_mask, keep_mask])
    result = np.where(keep_mask_3ch > 0, result, blurred)

    # Person 抑制（马赛克）
    if bg_cfg.get("suppress_person", True):
        for person in cf.persons:
            # 不抑制与 ego hand 重叠的 person
            skip = False
            for hand in cf.hands:
                if hand.is_ego_hand and _bbox_iou(hand.bbox, person.bbox) > 0.1:
                    skip = True
                    break
            if skip:
                continue

            x1, y1, x2, y2 = person.bbox
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            if bg_cfg.get("person_mode", "mosaic") == "mosaic":
                roi = result[y1:y2, x1:x2]
                if roi.size > 0:
                    block_size = 15
                    small = cv2.resize(roi, (max(1, (x2-x1)//block_size),
                                             max(1, (y2-y1)//block_size)),
                                       interpolation=cv2.INTER_LINEAR)
                    mosaic = cv2.resize(small, (x2-x1, y2-y1),
                                        interpolation=cv2.INTER_NEAREST)
                    result[y1:y2, x1:x2] = mosaic
            else:
                roi = result[y1:y2, x1:x2]
                if roi.size > 0:
                    result[y1:y2, x1:x2] = cv2.GaussianBlur(
                        roi, (blur_kernel, blur_kernel), 0
                    )

    return result


def _draw_annotations(image: np.ndarray, cf: CandidateFrame) -> np.ndarray:
    """在图片上绘制 CV 标注。"""
    result = image.copy()

    # ego hand: 绿色粗框
    for hand in cf.hands:
        if hand.is_ego_hand:
            x1, y1, x2, y2 = hand.bbox
            cv2.rectangle(result, (x1, y1), (x2, y2), (0, 255, 0), 3)
            text = f"EGO {hand.ego_hand_score:.2f}"
            cv2.putText(result, text, (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1, cv2.LINE_AA)

    # active equipment: 黄色粗框
    for eq in cf.equipment:
        if eq.is_active_equipment:
            x1, y1, x2, y2 = eq.bbox
            cv2.rectangle(result, (x1, y1), (x2, y2), (0, 255, 255), 3)
            text = f"{eq.label} {eq.active_equipment_score:.2f}"
            cv2.putText(result, text, (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1, cv2.LINE_AA)
        elif eq.active_equipment_score > 0.3:
            # context equipment: 蓝色细框
            x1, y1, x2, y2 = eq.bbox
            cv2.rectangle(result, (x1, y1), (x2, y2), (255, 180, 0), 1)
            text = f"{eq.label}"
            cv2.putText(result, text, (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 180, 0), 1, cv2.LINE_AA)

    # 时间戳
    ts_text = _sec_to_mmss(cf.timestamp)
    cv2.putText(result, ts_text, (5, result.shape[0] - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(result, ts_text, (5, result.shape[0] - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)

    return result


def _sec_to_mmss(sec: float) -> str:
    m = int(sec) // 60
    s = int(sec) % 60
    return f"{m:02d}:{s:02d}"


def render_contact_sheet(
    frames: list[CandidateFrame],
    config: dict,
    output_path: str | Path,
    cols: int = 6,
    cell_w: int = 320,
    cell_h: int = 180,
    apply_suppression: bool = True,
) -> bytes:
    """将选中的关键帧渲染为带标注的 contact sheet。"""
    if not frames:
        return b""

    rows = math.ceil(len(frames) / cols)
    canvas_w = cols * cell_w
    canvas_h = rows * cell_h
    canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)

    for i, cf in enumerate(frames):
        row, col = divmod(i, cols)

        if apply_suppression:
            processed = _apply_background_suppression(cf.image, cf, config)
        else:
            processed = cf.image.copy()

        annotated = _draw_annotations(processed, cf)
        cell = cv2.resize(annotated, (cell_w, cell_h), interpolation=cv2.INTER_AREA)

        y1 = row * cell_h
        x1 = col * cell_w
        canvas[y1:y1 + cell_h, x1:x1 + cell_w] = cell

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".jpg", canvas, [cv2.IMWRITE_JPEG_QUALITY, 75])
    if ok:
        buf.tofile(str(output_path))
    return buf.tobytes() if ok else b""


def render_interaction_roi_sheet(
    frames: list[CandidateFrame],
    output_path: str | Path,
    cols: int = 6,
    roi_size: int = 200,
) -> bytes:
    """渲染交互区域放大图的 contact sheet。"""
    if not frames:
        return b""

    rois = []
    for cf in frames:
        ego_hands = [h for h in cf.hands if h.is_ego_hand]
        active_equips = [eq for eq in cf.equipment if eq.is_active_equipment]
        all_hands = cf.hands
        all_equips = cf.equipment

        # 优先级: ego hand + active equip > ego hand only > any hand > any equip > 画面中心
        roi_bboxes: list[list[int]] = []
        if ego_hands or active_equips:
            roi_bboxes = [h.bbox for h in ego_hands] + [eq.bbox for eq in active_equips]
        elif all_hands:
            roi_bboxes = [h.bbox for h in all_hands]
        elif all_equips:
            roi_bboxes = [eq.bbox for eq in all_equips]

        fh, fw = cf.image.shape[:2]

        if roi_bboxes:
            x1 = min(b[0] for b in roi_bboxes)
            y1 = min(b[1] for b in roi_bboxes)
            x2 = max(b[2] for b in roi_bboxes)
            y2 = max(b[3] for b in roi_bboxes)

            pad = 30
            x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
            x2, y2 = min(fw, x2 + pad), min(fh, y2 + pad)

            roi = cf.image[y1:y2, x1:x2].copy()

            for hand in ego_hands:
                bx1, by1, bx2, by2 = hand.bbox
                cv2.rectangle(roi,
                              (bx1 - x1, by1 - y1), (bx2 - x1, by2 - y1),
                              (0, 255, 0), 2)
            for hand in all_hands:
                if not hand.is_ego_hand:
                    bx1, by1, bx2, by2 = hand.bbox
                    cv2.rectangle(roi,
                                  (bx1 - x1, by1 - y1), (bx2 - x1, by2 - y1),
                                  (0, 165, 255), 1)
            for eq in active_equips:
                bx1, by1, bx2, by2 = eq.bbox
                cv2.rectangle(roi,
                              (bx1 - x1, by1 - y1), (bx2 - x1, by2 - y1),
                              (0, 255, 255), 2)
            for eq in all_equips:
                if not eq.is_active_equipment:
                    bx1, by1, bx2, by2 = eq.bbox
                    cv2.rectangle(roi,
                                  (bx1 - x1, by1 - y1), (bx2 - x1, by2 - y1),
                                  (255, 180, 0), 1)

            roi = cv2.resize(roi, (roi_size, roi_size), interpolation=cv2.INTER_AREA)
        else:
            # 无任何检测结果 → 裁剪画面下半部中心区域（第一人称最可能的交互区域）
            cx, cy = fw // 2, fh * 2 // 3
            half = min(fw, fh) // 3
            x1 = max(0, cx - half)
            y1 = max(0, cy - half)
            x2 = min(fw, cx + half)
            y2 = min(fh, cy + half)
            roi = cf.image[y1:y2, x1:x2].copy()
            roi = cv2.resize(roi, (roi_size, roi_size), interpolation=cv2.INTER_AREA)

        # 加时间戳
        ts = _sec_to_mmss(cf.timestamp)
        cv2.putText(roi, ts, (3, roi_size - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
        rois.append(roi)

    rows = math.ceil(len(rois) / cols)
    canvas = np.zeros((rows * roi_size, cols * roi_size, 3), dtype=np.uint8)
    for i, roi in enumerate(rois):
        r, c = divmod(i, cols)
        canvas[r*roi_size:(r+1)*roi_size, c*roi_size:(c+1)*roi_size] = roi

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".jpg", canvas, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if ok:
        buf.tofile(str(output_path))
    return buf.tobytes() if ok else b""


# ──────────────────────────────────────────────
# Step 9: CV Summary 输出
# ──────────────────────────────────────────────

def export_cv_summary(
    selected: list[CandidateFrame],
    all_candidates: list[CandidateFrame],
    segment: dict,
    output_path: str | Path,
) -> dict:
    """输出结构化 CV 摘要。"""
    total = len(all_candidates)
    ego_visible = sum(1 for cf in all_candidates if cf.ego_hand_score > 0.3)
    both_visible = sum(1 for cf in all_candidates
                       if len([h for h in cf.hands if h.is_ego_hand]) >= 2)

    # Active equipment 统计
    equip_stats: dict[str, dict] = {}
    bg_equip_reasons: list[dict] = []
    for cf in all_candidates:
        for eq in cf.equipment:
            if eq.label not in equip_stats:
                equip_stats[eq.label] = {"count": 0, "active_count": 0, "scores": []}
            equip_stats[eq.label]["count"] += 1
            equip_stats[eq.label]["scores"].append(eq.active_equipment_score)
            if eq.is_active_equipment:
                equip_stats[eq.label]["active_count"] += 1

    active_equips = []
    bg_equips = []
    for label, stats in equip_stats.items():
        mean_score = sum(stats["scores"]) / len(stats["scores"]) if stats["scores"] else 0
        visible_ratio = stats["count"] / total if total > 0 else 0
        if stats["active_count"] > 0:
            active_equips.append({
                "label": label,
                "visible_ratio": round(visible_ratio, 2),
                "mean_active_score": round(mean_score, 2),
            })
        else:
            bg_equips.append({
                "label": label,
                "reason": "远离 ego hand，未与手部同步运动",
            })

    # 噪声统计
    person_removed = sum(1 for cf in all_candidates
                         if cf.is_filtered and "person" in cf.filter_reason)
    bg_downweighted = sum(1 for cf in all_candidates
                          if cf.background_equipment_noise_score > 0.5)
    walking_removed = sum(1 for cf in all_candidates
                          if cf.is_filtered and "walking" in cf.filter_reason)

    # 动作摘要
    hand_y_values = []
    for cf in all_candidates:
        ego_hands = [h for h in cf.hands if h.is_ego_hand]
        if ego_hands:
            avg_y = sum(_bbox_center(h.bbox)[1] for h in ego_hands) / len(ego_hands)
            hand_y_values.append(avg_y)

    hand_motion_axis = "unknown"
    if hand_y_values:
        y_range = max(hand_y_values) - min(hand_y_values)
        hand_motion_axis = "vertical" if y_range > 50 else "horizontal"

    seg_start = _parse_segment_time(segment, "start")
    seg_end = _parse_segment_time(segment, "end")

    summary = {
        "segment": {
            "segment_id": segment.get("segment_id", segment.get("segmentId", "")),
            "start": seg_start,
            "end": seg_end,
            "duration": round(seg_end - seg_start, 1),
            "candidate_fps": 5,
            "selected_frame_count": len(selected),
        },
        "ego_hand_summary": {
            "ego_hand_visible_ratio": round(ego_visible / total, 2) if total > 0 else 0,
            "both_ego_hands_visible_ratio": round(both_visible / total, 2) if total > 0 else 0,
            "mean_ego_hand_score": round(
                sum(cf.ego_hand_score for cf in all_candidates) / total, 2
            ) if total > 0 else 0,
            "low_hand_visibility": ego_visible / total < 0.2 if total > 0 else True,
        },
        "active_equipment_summary": {
            "active_equipment": active_equips,
            "background_equipment": bg_equips,
        },
        "noise_summary": {
            "person_dominant_frames_removed": person_removed,
            "background_equipment_frames_downweighted": bg_downweighted,
            "walking_transition_frames_removed": walking_removed,
        },
        "motion_summary": {
            "hand_motion_dominant_axis": hand_motion_axis,
        },
        "selected_keyframe_reasons": [
            {
                "timestamp": cf.timestamp,
                "reason": cf.selection_reason or "window_topk",
                "frame_info_score": round(cf.frame_info_score, 3),
            }
            for cf in selected
        ],
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"[KeyframeSampler] CV summary → {output_path}")
    return summary


# ──────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────

def extract_keyframes(
    video_path: str | Path,
    segment: dict,
    output_dir: str | Path,
    config: dict | None = None,
    use_roboflow: bool = True,
    seg_id: str = "",
) -> dict:
    """
    对单个 Exercise 区间执行完整的关键帧提取流程。

    Args:
        video_path:   视频文件路径
        segment:      Phase1 输出的 Exercise 区间 dict
                      需包含 start/end 或 start_time/end_time 字段
        output_dir:   输出目录
        config:       配置 dict（如为 None 则加载默认配置）
        use_roboflow: 是否使用 Roboflow API 检测手部
        seg_id:       segment ID 用于命名输出文件

    Returns:
        dict 包含 selected_frames, cv_summary, contact_sheet_path 等
    """
    t0 = time.time()
    if config is None:
        config = load_config()

    video_path = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sampling_cfg = config.get("candidate_sampling", {})
    output_cfg = config.get("output", {})
    window_cfg = config.get("window_selection", {})

    # 解析区间时间（支持多种字段名和格式）
    start_sec = _parse_segment_time(segment, "start")
    end_sec = _parse_segment_time(segment, "end")

    prefix = f"{seg_id}_" if seg_id else ""

    print(f"\n{'─' * 50}")
    print(f"[KeyframeSampler] Exercise: {start_sec:.1f}s → {end_sec:.1f}s "
          f"(duration={end_sec - start_sec:.1f}s)")

    # 1. 密集候选采样
    candidates = sample_candidate_frames(
        video_path=video_path,
        start_sec=start_sec,
        end_sec=end_sec,
        fps=sampling_cfg.get("default_fps", 5),
        max_frames=sampling_cfg.get("max_candidate_frames_per_segment", 300),
    )

    if not candidates:
        print("[KeyframeSampler] 没有候选帧，跳过")
        return {"selected_frames": [], "cv_summary": {}}

    # 2. CV 检测
    run_cv_detection(candidates, use_roboflow=use_roboflow)

    # 3. 检查手部出现率，必要时升采样
    hand_visible = sum(1 for cf in candidates if cf.hands)
    hand_ratio = hand_visible / len(candidates) if candidates else 0
    threshold = sampling_cfg.get("low_hand_visible_ratio_threshold", 0.2)

    if hand_ratio < threshold:
        fallback_fps = sampling_cfg.get("fallback_fps_if_low_hand_ratio", 10)
        print(f"[KeyframeSampler] 手部出现率 {hand_ratio:.2f} < {threshold}，"
              f"升采样至 {fallback_fps}fps")
        candidates = sample_candidate_frames(
            video_path=video_path,
            start_sec=start_sec,
            end_sec=end_sec,
            fps=fallback_fps,
            max_frames=sampling_cfg.get("max_candidate_frames_per_segment", 300),
        )
        run_cv_detection(candidates, use_roboflow=use_roboflow)

    # 4. 推断 ego hand
    infer_ego_hands(candidates)

    # 5. 推断 active equipment
    infer_active_equipment(candidates)

    # 6. 计算信息量分数
    compute_frame_info_scores(candidates)

    # 7. 噪声过滤
    filter_low_value_frames(candidates, config)

    # 8. 关键帧选择
    selected = select_topk_by_window(
        candidates,
        window_sec=window_cfg.get("window_sec", 2.0),
        top_k=window_cfg.get("top_k_per_window", 2),
    )

    endpoint_frames = select_endpoint_frames(candidates, config)
    selected.extend(endpoint_frames)

    anchor_frames = select_anchor_frames(candidates, config)
    selected.extend(anchor_frames)

    # 9. 去重
    selected = deduplicate_frames(selected, config)

    # 10. 限制数量
    max_frames = output_cfg.get("max_frames", 36)
    min_frames = output_cfg.get("min_frames", 12)

    if len(selected) > max_frames:
        selected.sort(key=lambda cf: cf.frame_info_score, reverse=True)
        selected = selected[:max_frames]
        selected.sort(key=lambda cf: cf.timestamp)

    if len(selected) < min_frames:
        # 补充低分帧填充
        remaining = [cf for cf in candidates
                     if not cf.is_filtered and cf not in selected]
        remaining.sort(key=lambda cf: cf.frame_info_score, reverse=True)
        for cf in remaining:
            if len(selected) >= min_frames:
                break
            selected.append(cf)
            cf.selection_reason = "fill"
        selected.sort(key=lambda cf: cf.timestamp)

    print(f"[KeyframeSampler] 最终选择: {len(selected)} 帧")

    # 11. 渲染 contact sheet
    overlay_path = output_dir / f"{prefix}masked_overlay_contact_sheet.jpg"
    render_contact_sheet(selected, config, overlay_path, apply_suppression=True)

    roi_path = output_dir / f"{prefix}interaction_roi_contact_sheet.jpg"
    render_interaction_roi_sheet(selected, roi_path)

    # 12. 输出 CV summary
    summary_path = output_dir / f"{prefix}cv_summary.json"
    cv_summary = export_cv_summary(selected, candidates, segment, summary_path)

    # 13. Debug JSON
    debug_path = output_dir / f"{prefix}keyframe_debug.json"
    debug_info = {
        "total_candidates": len(candidates),
        "filtered_count": sum(1 for cf in candidates if cf.is_filtered),
        "selected_count": len(selected),
        "hand_visible_ratio": round(hand_ratio, 3),
        "frames": [
            {
                "index": cf.index,
                "timestamp": cf.timestamp,
                "ego_hand_score": round(cf.ego_hand_score, 3),
                "active_equipment_score": round(cf.active_equipment_score, 3),
                "interaction_score": round(cf.hand_equipment_interaction_score, 3),
                "frame_info_score": round(cf.frame_info_score, 3),
                "selection_reason": cf.selection_reason,
                "hands_count": len(cf.hands),
                "ego_hands_count": len([h for h in cf.hands if h.is_ego_hand]),
                "equipment": [eq.label for eq in cf.equipment if eq.is_active_equipment],
            }
            for cf in selected
        ],
    }
    with open(debug_path, "w", encoding="utf-8") as f:
        json.dump(debug_info, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - t0
    print(f"[KeyframeSampler] 完成: {elapsed:.1f}s")
    print(f"  → {overlay_path.name}")
    print(f"  → {roi_path.name}")
    print(f"  → {summary_path.name}")
    print(f"{'─' * 50}\n")

    return {
        "selected_frames": selected,
        "cv_summary": cv_summary,
        "overlay_contact_sheet": str(overlay_path),
        "roi_contact_sheet": str(roi_path),
        "cv_summary_path": str(summary_path),
        "debug_path": str(debug_path),
    }


def _mmss_to_sec(t: str) -> float:
    """将 MM:SS 或 HH:MM:SS 格式转为秒数。"""
    parts = t.strip().split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(t)


def _parse_segment_time(segment: dict, which: str) -> float:
    """从 segment dict 中解析起止时间，支持多种字段名和格式。"""
    # 优先用 _sec 后缀的 float 字段
    sec_key = f"{which}_sec"
    if sec_key in segment and isinstance(segment[sec_key], (int, float)):
        return float(segment[sec_key])

    # 尝试 start/end 直接字段
    val = segment.get(which, None)
    if val is not None:
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            return _mmss_to_sec(val)

    # 尝试 start_time/end_time
    time_key = f"{which}_time"
    val = segment.get(time_key, None)
    if val is not None:
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            return _mmss_to_sec(val)

    return 0.0


# ──────────────────────────────────────────────
# 批量处理入口
# ──────────────────────────────────────────────

def process_video_segments(
    video_path: str | Path,
    segments: list[dict],
    output_dir: str | Path,
    config: dict | None = None,
    use_roboflow: bool = True,
) -> list[dict]:
    """
    对一个视频的所有 Exercise 区间批量执行关键帧提取。

    Args:
        video_path:  视频路径
        segments:    Phase1 输出的 segments 列表
        output_dir:  输出目录
        config:      配置
        use_roboflow: 是否用 Roboflow API

    Returns:
        每个 segment 的结果 list[dict]
    """
    if config is None:
        config = load_config()

    exercise_segments = [
        s for s in segments
        if s.get("state", "").upper() == "EXERCISE"
    ]

    print(f"\n{'=' * 60}")
    print(f"[KeyframeSampler] 批量处理: {len(exercise_segments)} 个 Exercise 区间")
    print(f"[KeyframeSampler] 视频: {video_path}")
    print(f"{'=' * 60}\n")

    results = []
    for i, seg in enumerate(exercise_segments):
        seg_id = seg.get("segment_id", f"exercise_{i+1:03d}")
        result = extract_keyframes(
            video_path=video_path,
            segment=seg,
            output_dir=output_dir,
            config=config,
            use_roboflow=use_roboflow,
            seg_id=seg_id,
        )
        results.append(result)

    return results


# ──────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Ego-Interaction Keyframe Sampler")
    parser.add_argument(
        "video_path",
        help="视频文件路径")
    parser.add_argument(
        "--start", type=float, required=True,
        help="Exercise 起始时间（秒）")
    parser.add_argument(
        "--end", type=float, required=True,
        help="Exercise 结束时间（秒）")
    parser.add_argument(
        "--output", "-o", default=None,
        help="输出目录（默认：视频同目录/keyframes/）")
    parser.add_argument(
        "--no-roboflow", action="store_true",
        help="不使用 Roboflow API，用本地模型检测手部")
    parser.add_argument(
        "--config", default=None,
        help="配置文件路径")
    args = parser.parse_args()

    vpath = Path(args.video_path)
    out = Path(args.output) if args.output else vpath.parent / vpath.stem / "keyframes"

    segment = {"start": args.start, "end": args.end}
    cfg = load_config(args.config) if args.config else load_config()

    extract_keyframes(
        video_path=vpath,
        segment=segment,
        output_dir=out,
        config=cfg,
        use_roboflow=not args.no_roboflow,
    )
