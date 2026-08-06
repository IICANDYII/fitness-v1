"""Gym Analyzer Agent.

Orchestrates the video analysis pipeline via tool calls.
The agent (Gemini Flash) decides which tools to call and in what order.
"""

from __future__ import annotations

import json
import time as time_module
from datetime import date
from pathlib import Path
from typing import Any

import requests

from . import config, progress
from .tools import TOOL_SCHEMAS, TOOL_REGISTRY

_DEFAULT_USER_ID = config.DEFAULT_USER_ID

# Map tool name → (step number, label suffix)
_TOOL_STEP: dict[str, tuple[int, str]] = {
    "extract_frames":      (1, ""),
    "load_training_plan":  (2, ""),
    "analyze_frame_batch": (3, ""),
    "compute_dashboard":   (4, ""),
    "save_to_db":          (5, ""),
    "save_result":         (6, ""),
}


class GymAnalyzerAgent:
    """Agent that analyzes workout videos by calling tools via an LLM."""

    def __init__(self, model: str = config.AGENT_MODEL):
        if not config.GATEWAY_KEY:
            raise EnvironmentError(
                "未设置 NEXTROUTER_API_KEY 或 API_KEY，无法调用视频分析 LLM。"
            )
        self.model = model
        self.url = f"{config.GATEWAY_URL}/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {config.GATEWAY_KEY}",
            "Content-Type": "application/json",
        }
        self._session = requests.Session()
        self._session.trust_env = False

    def _chat(self, messages: list[dict], tools: list[dict] | None = None,
              max_retries: int = 5) -> dict:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        for attempt in range(1, max_retries + 1):
            try:
                resp = self._session.post(self.url, headers=self.headers, json=payload, timeout=600)
            except (requests.exceptions.SSLError,
                    requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout) as e:
                wait = min(30 * attempt, 180)
                print(f"  [Agent 网络错误] {type(e).__name__}: {e}")
                if attempt < max_retries:
                    print(f"  等待 {wait}s 后重试（{attempt}/{max_retries}）...")
                    time_module.sleep(wait)
                    continue
                raise

            if resp.status_code == 429:
                wait = 60 * attempt
                print(f"  [Agent 429] 等待 {wait}s 后重试（{attempt}/{max_retries}）...")
                time_module.sleep(wait)
                continue
            if resp.status_code >= 500:
                wait = min(30 * attempt, 180)
                print(f"  [Agent HTTP {resp.status_code}] 服务端错误，等待 {wait}s 后重试（{attempt}/{max_retries}）...")
                if attempt < max_retries:
                    time_module.sleep(wait)
                    continue
            resp.raise_for_status()
            return resp.json()

        raise RuntimeError("Agent: 超过最大重试次数")

    def _dispatch(self, tool_name: str, args: dict, video_key: str) -> str:
        fn = TOOL_REGISTRY.get(tool_name)
        if fn is None:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        # Report progress before calling the tool
        if tool_name in _TOOL_STEP:
            step, _ = _TOOL_STEP[tool_name]
            detail = ""
            if tool_name == "analyze_frame_batch":
                n = len(args.get("frames", []))
                detail = f"共 {n} 帧"
            elif tool_name == "save_to_db":
                detail = "写入 workout_session + exercise_execution"
            progress.update(video_key, step, detail)

        try:
            result = fn(**args)
            # Post-call detail enrichment
            if tool_name == "extract_frames" and isinstance(result, dict):
                n = result.get("total_frames_extracted", "?")
                dur = result.get("duration_sec", "?")
                progress.update(video_key, 1, f"已提取 {n} 帧 / 时长 {dur}s")
            elif tool_name == "load_training_plan" and isinstance(result, dict):
                if result.get("found"):
                    fname = Path(result.get("_path", "")).name or "已加载"
                    progress.update(video_key, 2, f"已加载：{fname}")
                else:
                    progress.update(video_key, 2, "未找到训练计划，跳过")
            elif tool_name == "analyze_frame_batch" and isinstance(result, dict):
                n_seg = len(result.get("segments", []))
                progress.update(video_key, 3, f"识别出 {n_seg} 个时间段")
            elif tool_name == "save_to_db" and isinstance(result, dict):
                if result.get("status") == "ok":
                    progress.update(video_key, 5,
                        f"session_id: {result.get('session_id','')[:8]}…  "
                        f"动作 {result.get('exercises_written',0)} 条  "
                        f"心率 {result.get('hr_points',0)} 点")
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            progress.mark_error(video_key, str(e))
            return json.dumps({"error": str(e)})

    def run(self, video_path: str, workout_date: str | None = None, weight_kg: float = 65.0,
            gender: str = "female", age: int = 25, hr_csv_path: str | None = None,
            user_id: str | None = None) -> dict:
        """Analyze a workout video end-to-end."""
        if workout_date is None:
            workout_date = date.today().isoformat()

        progress.update(video_path, 0, "Agent 启动中")

        system = (
            "你是一个健身视频分析 Agent。用户给你一个视频路径，请按顺序调用工具完成分析：\n"
            "1. extract_frames      — 提取视频帧（1fps）\n"
            "2. load_training_plan  — 加载训练计划 JSON（同目录）；若返回 found=false 则跳过\n"
            "3. analyze_frame_batch — 全量上下文模式：把所有帧合成一张大网格图，一次 Gemini 调用"
            "完成完整时间线划分和器械/动作识别；若第2步找到计划，必须把 training_plan 传入此工具\n"
            "4. compute_dashboard   — 把原始结果转换为前端仪表盘格式\n"
            "5. generate_charts     — 生成时间线和汇总图表 PNG，保存到 results 文件夹\n"
            "6. save_to_db          — 把结果写入 PostgreSQL\n"
            "7. save_result         — 保存 JSON 备份到磁盘\n"
            "完成后把 compute_dashboard 返回的 JSON 原样输出，不要添加任何说明文字。"
        )
        messages: list[dict] = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    f"请分析这个健身视频：{video_path}\n"
                    f"日期：{workout_date}，性别：{gender}，年龄：{age}岁，体重：{weight_kg} kg"
                    + (f"\n心率 CSV 路径：{hr_csv_path}" if hr_csv_path else "\n无心率数据")
                ),
            },
        ]

        max_turns = 15
        dashboard: dict = {}

        for _ in range(max_turns):
            resp = self._chat(messages, tools=TOOL_SCHEMAS)
            choice = resp["choices"][0]
            msg = choice["message"]
            messages.append(msg)

            if choice.get("finish_reason") == "tool_calls" or msg.get("tool_calls"):
                for tc in msg.get("tool_calls", []):
                    name = tc["function"]["name"]
                    args = json.loads(tc["function"]["arguments"] or "{}")

                    if name == "load_training_plan":
                        args.setdefault("workout_date", workout_date)
                    if name == "analyze_frame_batch":
                        args.setdefault("video_key", video_path)
                    if name == "generate_charts":
                        args.setdefault("date_str", workout_date)
                    if name == "compute_dashboard":
                        args.setdefault("weight_kg", weight_kg)
                        args.setdefault("gender",    gender)
                        args.setdefault("age",       age)
                        args.setdefault("date_str",  workout_date)
                    if name == "save_to_db":
                        if hr_csv_path and "hr_csv_path" not in args:
                            args["hr_csv_path"] = hr_csv_path
                        args["user_id"] = user_id or _DEFAULT_USER_ID
                    if name == "save_result":
                        args.setdefault("date_str", workout_date)
                        if hr_csv_path and "hr_csv_path" not in args:
                            args["hr_csv_path"] = hr_csv_path
                        args["user_id"] = user_id or _DEFAULT_USER_ID

                    result_str = self._dispatch(name, args, video_path)

                    if name == "compute_dashboard":
                        try:
                            dashboard = json.loads(result_str)
                        except Exception:
                            pass

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result_str,
                    })
                continue

            if choice.get("finish_reason") == "stop":
                if not dashboard:
                    try:
                        dashboard = json.loads(msg.get("content", "{}"))
                    except Exception:
                        pass
                break

        progress.mark_done(video_path)
        return dashboard
