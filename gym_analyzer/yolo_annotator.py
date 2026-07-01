"""
yolo_annotator.py - YOLO 器材标注 + Roboflow API 手部检测

对帧图片并行运行:
  - 本地 YOLO 模型: 器材识别（绿色框）
  - Roboflow API: 手部分割检测（橙色框）
"""

from __future__ import annotations

import base64
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

_YOLO_DIR = Path(__file__).parent / "yolo"
EQUIP_MODEL_PATH = _YOLO_DIR / "runs" / "detect" / "runs" / "fitness_equipment_test" / "weights" / "best.pt"

ROBOFLOW_API_URL = "https://serverless.roboflow.com"
ROBOFLOW_API_KEY = "93cfYbfIdFrloQ3NmyhU"
ROBOFLOW_WORKSPACE = "boyu-yang-jh3ze"
ROBOFLOW_WORKFLOW_ID = "general-segmentation-api-5"
ROBOFLOW_HAND_CLASSES = "Hand, hand"

_equip_model = None
_rf_client = None
_initialized = False


def _init():
    """懒加载模型和客户端（仅初始化一次）。"""
    global _equip_model, _rf_client, _initialized
    if _initialized:
        return
    from ultralytics import YOLO
    from inference_sdk import InferenceHTTPClient

    if EQUIP_MODEL_PATH.exists():
        _equip_model = YOLO(str(EQUIP_MODEL_PATH))
        print(f"[YOLO] 器材检测模型已加载: {EQUIP_MODEL_PATH}")
    else:
        print(f"[YOLO] 警告: 器材检测模型不存在: {EQUIP_MODEL_PATH}")

    _rf_client = InferenceHTTPClient(
        api_url=ROBOFLOW_API_URL,
        api_key=ROBOFLOW_API_KEY,
    )
    print(f"[YOLO] Roboflow 手部检测 API 已连接")

    _initialized = True


def _run_hand_api(img: np.ndarray, img_path: str | None = None) -> list[dict]:
    """
    调用 Roboflow workflow API 进行手部检测。

    Returns:
        list[dict]，每个 dict 包含 x, y, width, height, confidence
    """
    if _rf_client is None:
        return []

    try:
        if img_path and Path(img_path).exists():
            source = img_path
        else:
            _, tmp = tempfile.mkstemp(suffix=".jpg")
            cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tofile(tmp)
            source = tmp

        result = _rf_client.run_workflow(
            workspace_name=ROBOFLOW_WORKSPACE,
            workflow_id=ROBOFLOW_WORKFLOW_ID,
            images={"image": source},
            parameters={"classes": ROBOFLOW_HAND_CLASSES},
            use_cache=True,
        )

        detections = []
        if result and isinstance(result, list):
            for item in result:
                preds = item.get("predictions", item.get("output", {}))
                if isinstance(preds, dict):
                    preds = preds.get("predictions", [])
                if isinstance(preds, list):
                    for pred in preds:
                        if isinstance(pred, dict) and "x" in pred and "y" in pred:
                            detections.append(pred)
        return detections
    except Exception as e:
        print(f"[YOLO] Roboflow API 调用失败: {e}")
        return []


def _draw_equip_boxes(img: np.ndarray, equip_result) -> None:
    """在图片上绘制器材检测框（绿色）。"""
    if equip_result is None or equip_result.boxes is None:
        return
    for box in equip_result.boxes:
        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
        conf = float(box.conf[0])
        cls_id = int(box.cls[0])
        label = equip_result.names.get(cls_id, str(cls_id))
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        text = f"{label} {conf:.2f}"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
        cv2.rectangle(img, (x1, y1 - th - 4), (x1 + tw, y1), (0, 255, 0), -1)
        cv2.putText(img, text, (x1, y1 - 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1, cv2.LINE_AA)


def _draw_hand_boxes(img: np.ndarray, hand_dets: list[dict]) -> None:
    """在图片上绘制手部检测框（橙色）。"""
    for det in hand_dets:
        cx = det.get("x", 0)
        cy = det.get("y", 0)
        w = det.get("width", 0)
        h = det.get("height", 0)
        conf = det.get("confidence", 0)
        x1 = int(cx - w / 2)
        y1 = int(cy - h / 2)
        x2 = int(cx + w / 2)
        y2 = int(cy + h / 2)
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 165, 255), 2)
        text = f"hand {conf:.2f}"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
        cv2.rectangle(img, (x1, y1 - th - 4), (x1 + tw, y1), (0, 165, 255), -1)
        cv2.putText(img, text, (x1, y1 - 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1, cv2.LINE_AA)


def annotate_frame(img: np.ndarray, img_path: str | None = None) -> np.ndarray:
    """
    对单张图片并行运行器材识别（本地 YOLO）和手部检测（Roboflow API），
    在原图上绘制标注框。

    Args:
        img: BGR 格式的 numpy 数组
        img_path: 图片文件路径（有则直接传给 API，避免临时文件）

    Returns:
        标注后的 BGR 图片
    """
    _init()
    annotated = img.copy()

    def run_equip():
        if _equip_model is None:
            return None
        return _equip_model(img, verbose=False)[0]

    def run_hand():
        return _run_hand_api(img, img_path)

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_equip = pool.submit(run_equip)
        fut_hand = pool.submit(run_hand)
        equip_result = fut_equip.result()
        hand_dets = fut_hand.result()

    _draw_equip_boxes(annotated, equip_result)
    _draw_hand_boxes(annotated, hand_dets)

    return annotated
