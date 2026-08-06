"""
server.py — 双机位标注工具本地服务

- GET  /                 标注前端 index.html
- GET  /manifest.json    视频清单（prepare.py 生成）
- GET  /videos/<file>    转码后的 mp4，支持 Range（浏览器 seek 必需）
- GET  /ground_truth     读取已保存的标注（无则空数组）
- POST /save             保存标注 JSON 到本地 ground_truth.json

用法: python server.py   (默认 :8090)
"""
from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = 8090
HERE = Path(__file__).parent
VIDEO_DIR = Path.home() / "Downloads" / "fitness_annotation" / "videos"
GT_PATH = Path.home() / "Downloads" / "fitness_annotation" / "ground_truth.json"
HTML_PATH = HERE / "index.html"


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body: bytes, ctype: str, extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._send(200, HTML_PATH.read_bytes(), "text/html; charset=utf-8")
        elif path == "/manifest.json":
            p = VIDEO_DIR / "manifest.json"
            if p.exists():
                self._send(200, p.read_bytes(), "application/json; charset=utf-8")
            else:
                self._send(404, b'{"error":"no manifest, run prepare.py"}', "application/json")
        elif path == "/ground_truth":
            body = GT_PATH.read_bytes() if GT_PATH.exists() else b"[]"
            self._send(200, body, "application/json; charset=utf-8")
        elif path.startswith("/videos/"):
            self._serve_video(VIDEO_DIR / path[len("/videos/"):])
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if self.path.split("?", 1)[0] == "/save":
            n = int(self.headers.get("Content-Length", 0))
            data = self.rfile.read(n)
            try:
                parsed = json.loads(data)  # validate
                GT_PATH.write_text(
                    json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
                self._send(200, b'{"status":"ok"}', "application/json")
                print(f"[save] {len(parsed)} 个片段 → {GT_PATH}")
            except Exception as e:
                self._send(400, json.dumps({"error": str(e)}).encode(), "application/json")
        else:
            self._send(404, b"not found", "text/plain")

    def _serve_video(self, path: Path):
        if not path.exists() or path.suffix != ".mp4":
            self._send(404, b"no video", "text/plain")
            return
        size = path.stat().st_size
        rng = self.headers.get("Range")
        if rng and (m := re.match(r"bytes=(\d+)-(\d*)", rng)):
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else size - 1
            end = min(end, size - 1)
            length = end - start + 1
            self.send_response(206)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(length))
            self.end_headers()
            try:
                with open(path, "rb") as f:
                    f.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk = f.read(min(1 << 16, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass          # 浏览器 seek 时中断连接，正常
        else:
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(size))
            self.end_headers()
            try:
                with open(path, "rb") as f:
                    while chunk := f.read(1 << 16):
                        self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"标注工具: http://localhost:{PORT}")
    print(f"视频目录: {VIDEO_DIR}")
    print(f"标注保存: {GT_PATH}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
