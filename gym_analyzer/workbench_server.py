"""
workbench_server.py - 可视化工作台后端

提供 API：
  - GET  /api/prompts          列出所有 prompt 版本
  - GET  /api/samples          列出所有视频样本
  - POST /api/siglip            SigLIP 抽帧
  - POST /api/run               一键运行 pipeline
  - GET  /api/task/<id>         查询任务状态
"""

from __future__ import annotations

import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
import uuid
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).parent
PROMPTS_DIR = BASE_DIR / "prompts"
INPUT_DIR = BASE_DIR / "input"
WORKBENCH_DIR = BASE_DIR

VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv", ".qt"}

_tasks: dict[str, dict] = {}


def _scan_prompts() -> dict:
    phase1 = []
    phase2 = []
    for f in sorted(PROMPTS_DIR.glob("*.yaml")):
        name_lower = f.name.lower()
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            version = str(data.get("version", "0"))
            desc = data.get("description", "")
            if isinstance(desc, str) and len(desc) > 120:
                desc = desc[:120] + "..."
            name = data.get("name", f.stem)
        except Exception:
            import re
            m = re.search(r"version:\s*['\"]?([^'\"\n]+)", f.read_text(encoding="utf-8")[:500])
            version = m.group(1).strip() if m else "?"
            desc = "(YAML 解析失败，但仍可选用)"
            name = f.stem

        entry = {
            "filename": f.name,
            "version": version,
            "name": name,
            "description": desc,
        }
        if "phase1" in name_lower:
            phase1.append(entry)
        elif "phase2" in name_lower:
            phase2.append(entry)

    def _ver_key(v):
        parts = v.lstrip("vV").replace("-", ".").split(".")
        result = []
        for p in parts:
            try:
                result.append((0, int(p)))
            except ValueError:
                result.append((1, p))
        return result

    phase1.sort(key=lambda x: _ver_key(x["version"]), reverse=True)
    phase2.sort(key=lambda x: _ver_key(x["version"]), reverse=True)
    return {"phase1": phase1, "phase2": phase2}


def _scan_samples() -> list[dict]:
    samples = []
    if not INPUT_DIR.is_dir():
        return samples
    for d in sorted(INPUT_DIR.iterdir()):
        if not d.is_dir():
            continue
        videos = [f.name for f in d.iterdir() if f.suffix.lower() in VIDEO_EXTS]
        has_frames = (d / "frames_meta.json").exists()
        has_siglip = (d / "frames-siglip").is_dir() or (d / "keyframes").is_dir()
        has_period = (d / "period_result.json").exists()
        has_exercise = (d / "exercise_result.json").exists()
        frame_count = 0
        if has_frames:
            try:
                with open(d / "frames_meta.json", "r", encoding="utf-8") as f:
                    frame_count = len(json.load(f))
            except Exception:
                pass

        samples.append({
            "name": d.name,
            "path": str(d),
            "videos": videos,
            "has_frames": has_frames,
            "frame_count": frame_count,
            "has_siglip": has_siglip,
            "has_period_result": has_period,
            "has_exercise_result": has_exercise,
        })
    return samples


def _run_task_in_background(task_id: str, cmd: list[str], cwd: str):
    task = _tasks[task_id]
    task["status"] = "running"
    task["started_at"] = time.time()
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        task["pid"] = proc.pid
        lines = []
        for line in proc.stdout:
            lines.append(line)
            if len(lines) > 2000:
                lines = lines[-1000:]
        proc.wait()
        task["exit_code"] = proc.returncode
        task["output"] = "".join(lines[-500:])
        task["status"] = "success" if proc.returncode == 0 else "failed"
    except Exception as e:
        task["status"] = "failed"
        task["error"] = traceback.format_exc()
        task["output"] = str(e)
    task["finished_at"] = time.time()


class WorkbenchHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WORKBENCH_DIR), **kwargs)

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/":
            self.path = "/workbench.html"
            return super().do_GET()
        elif path == "/api/prompts":
            self._json_response(_scan_prompts())
        elif path == "/api/samples":
            self._json_response(_scan_samples())
        elif path.startswith("/api/task/"):
            task_id = path.split("/")[-1]
            task = _tasks.get(task_id)
            if task:
                self._json_response(task)
            else:
                self._json_response({"error": "task not found"}, 404)
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_body()

        if path == "/api/siglip":
            self._handle_siglip(body)
        elif path == "/api/run":
            self._handle_run(body)
        else:
            self._json_response({"error": "not found"}, 404)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _json_response(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _handle_siglip(self, body: dict):
        samples = body.get("samples", [])
        output_dir = body.get("output_dir", "")
        if not samples:
            self._json_response({"error": "no samples selected"}, 400)
            return

        task_id = str(uuid.uuid4())[:8]
        project_root = str(BASE_DIR.parent)

        cmds = []
        for sample_name in samples:
            sample_dir = INPUT_DIR / sample_name
            videos = [f for f in sample_dir.iterdir() if f.suffix.lower() in VIDEO_EXTS]
            if not videos:
                continue
            video_path = str(videos[0])

            period_result = sample_dir / "period_result.json"
            if period_result.exists():
                with open(period_result, "r", encoding="utf-8") as f:
                    pr = json.load(f)
                segments = [s for s in pr.get("segments", []) if s.get("state", "").upper() == "EXERCISE"]
            else:
                segments = [{"start_time": "00:00:00", "end_time": "99:59:59"}]

            out = output_dir if output_dir else str(sample_dir / "keyframes")
            for i, seg in enumerate(segments):
                start_str = seg.get("start_time", "00:00:00")
                end_str = seg.get("end_time", "00:01:00")
                parts_s = start_str.split(":")
                parts_e = end_str.split(":")
                start_sec = int(parts_s[0]) * 3600 + int(parts_s[1]) * 60 + int(parts_s[2])
                end_sec = int(parts_e[0]) * 3600 + int(parts_e[1]) * 60 + int(parts_e[2])

                cmd = [
                    sys.executable,
                    str(BASE_DIR / "ego_keyframe_sampler.py"),
                    video_path,
                    "--start", str(start_sec),
                    "--end", str(end_sec),
                    "--output", out,
                    "--no-roboflow",
                ]
                cmds.append(cmd)

        if not cmds:
            self._json_response({"error": "no videos found in selected samples"}, 400)
            return

        shell_cmds = []
        for cmd in cmds:
            shell_cmds.append(" ".join(f'"{c}"' if " " in c else c for c in cmd))
        combined = " && ".join(shell_cmds)

        _tasks[task_id] = {
            "id": task_id,
            "type": "siglip",
            "samples": samples,
            "status": "pending",
            "output": "",
            "cmd_count": len(cmds),
        }

        cmd_flat = [sys.executable, "-c",
                     f"import subprocess, sys; " +
                     "; ".join(
                         f"subprocess.check_call({cmd!r})"
                         for cmd in cmds
                     )]

        t = threading.Thread(
            target=_run_task_in_background,
            args=(task_id, cmds[0] if len(cmds) == 1 else cmd_flat, project_root),
            daemon=True,
        )
        t.start()
        self._json_response({"task_id": task_id, "cmd_count": len(cmds)})

    def _handle_run(self, body: dict):
        samples = body.get("samples", [])
        phase1_prompt = body.get("phase1_prompt", "")
        phase2_prompt = body.get("phase2_prompt", "")
        overwrite = body.get("overwrite", False)
        workers = body.get("workers", 4)
        output_base = body.get("output_dir", "")
        use_yolo = body.get("use_yolo", False)

        if not samples:
            self._json_response({"error": "no samples selected"}, 400)
            return
        if not phase1_prompt or not phase2_prompt:
            self._json_response({"error": "must select both phase1 and phase2 prompt"}, 400)
            return

        task_id = str(uuid.uuid4())[:8]
        project_root = str(BASE_DIR.parent)

        p1_path = PROMPTS_DIR / phase1_prompt
        p2_path = PROMPTS_DIR / phase2_prompt
        if not p1_path.exists() or not p2_path.exists():
            self._json_response({"error": "prompt file not found"}, 400)
            return

        temp_prompts_dir = BASE_DIR / f"_temp_prompts_{task_id}"
        temp_prompts_dir.mkdir(exist_ok=True)

        import shutil
        shutil.copy2(p1_path, temp_prompts_dir / p1_path.name)
        shutil.copy2(p2_path, temp_prompts_dir / p2_path.name)

        cmds = []
        for sample_name in samples:
            sample_dir = INPUT_DIR / sample_name
            if not sample_dir.is_dir():
                continue

            out = output_base if output_base else str(sample_dir)
            cmd = [
                sys.executable, "-m", "gym_analyzer.pipeline",
                str(sample_dir),
                "--prompts", str(temp_prompts_dir),
                "--workers", str(workers),
                "--output", out,
            ]
            if overwrite:
                cmd.append("--overwrite")
            if use_yolo:
                cmd.append("--use-yolo")
            cmds.append(cmd)

        if not cmds:
            self._json_response({"error": "no valid samples"}, 400)
            return

        _tasks[task_id] = {
            "id": task_id,
            "type": "pipeline",
            "samples": samples,
            "phase1_prompt": phase1_prompt,
            "phase2_prompt": phase2_prompt,
            "status": "pending",
            "output": "",
            "cmd_count": len(cmds),
            "temp_prompts": str(temp_prompts_dir),
        }

        def run_all():
            task = _tasks[task_id]
            task["status"] = "running"
            task["started_at"] = time.time()
            all_output = []
            failed = False
            for i, cmd in enumerate(cmds):
                task["current_sample"] = samples[i]
                task["progress"] = f"{i+1}/{len(cmds)}"
                try:
                    proc = subprocess.Popen(
                        cmd,
                        cwd=project_root,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                    )
                    lines = []
                    for line in proc.stdout:
                        lines.append(line)
                        if len(lines) > 500:
                            lines = lines[-300:]
                    proc.wait()
                    output_text = "".join(lines[-200:])
                    all_output.append(f"=== {samples[i]} (exit={proc.returncode}) ===\n{output_text}\n")
                    if proc.returncode != 0:
                        failed = True
                except Exception as e:
                    all_output.append(f"=== {samples[i]} ERROR ===\n{traceback.format_exc()}\n")
                    failed = True

            task["output"] = "\n".join(all_output)
            task["status"] = "failed" if failed else "success"
            task["finished_at"] = time.time()

            import shutil
            try:
                shutil.rmtree(temp_prompts_dir)
            except Exception:
                pass

        t = threading.Thread(target=run_all, daemon=True)
        t.start()
        self._json_response({"task_id": task_id, "cmd_count": len(cmds)})


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    PORT = 8769
    print(f"Workbench serving on http://localhost:{PORT}")
    print(f"Prompts dir: {PROMPTS_DIR}")
    print(f"Input dir:   {INPUT_DIR}")
    server = ThreadedHTTPServer(("0.0.0.0", PORT), WorkbenchHandler)
    server.serve_forever()
