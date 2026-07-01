import http.server
import json
import os
import socketserver
import urllib.parse

RAW_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'gym_analyzer', 'input'))
SHARED_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'result', 'shared'))
PREPROCESS_DIR = os.path.dirname(__file__)

VIDEO_EXTS = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.qt'}


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PREPROCESS_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == '/api/videos':
            self._serve_video_list()
        elif path == '/api/ground_truth':
            self._serve_ground_truth(parsed.query)
        elif path == '/api/imu':
            self._serve_imu(parsed.query)
        elif path == '/api/imu_sessions':
            self._serve_imu_sessions()
        elif path.startswith('/raw/'):
            self._serve_raw_file(path[5:])
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/ground_truth':
            self._save_ground_truth(parsed.query)
        else:
            self.send_error(404)

    def _video_to_folder(self, video_name):
        return os.path.splitext(video_name)[0]

    def _serve_ground_truth(self, query_string):
        params = urllib.parse.parse_qs(query_string)
        video = params.get('video', [''])[0]
        if not video:
            self.send_error(400, 'Missing video parameter')
            return
        folder = self._video_to_folder(video)
        gt_path = os.path.normpath(os.path.join(SHARED_DIR, folder, 'ground_truth.json'))
        if not gt_path.startswith(SHARED_DIR):
            self.send_error(403)
            return
        if not os.path.isfile(gt_path):
            data = json.dumps({"found": False}).encode('utf-8')
        else:
            with open(gt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                import re
                cleaned = re.sub(r':\s*([A-Z_]+)', ': null', content)
                cleaned = re.sub(r',\s*]', ']', cleaned)
                try:
                    parsed = json.loads(cleaned)
                except json.JSONDecodeError:
                    parsed = None
            if parsed is not None:
                data = json.dumps({"found": True, "data": parsed, "folder": folder}).encode('utf-8')
            else:
                data = json.dumps({"found": False, "error": "invalid JSON"}).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)

    def _save_ground_truth(self, query_string):
        params = urllib.parse.parse_qs(query_string)
        video = params.get('video', [''])[0]
        if not video:
            self.send_error(400, 'Missing video parameter')
            return
        folder = self._video_to_folder(video)
        folder_path = os.path.normpath(os.path.join(SHARED_DIR, folder))
        if not folder_path.startswith(SHARED_DIR):
            self.send_error(403)
            return
        os.makedirs(folder_path, exist_ok=True)
        gt_path = os.path.join(folder_path, 'ground_truth.json')
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        payload = json.loads(body.decode('utf-8'))
        with open(gt_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        resp = json.dumps({"status": "ok", "folder": folder}).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(resp))
        self.end_headers()
        self.wfile.write(resp)

    def _serve_imu_sessions(self):
        sessions = []
        if os.path.isdir(SHARED_DIR):
            for folder in sorted(os.listdir(SHARED_DIR)):
                imu_path = os.path.join(SHARED_DIR, folder, 'IMU.txt')
                if os.path.isfile(imu_path):
                    has_gt = os.path.isfile(os.path.join(SHARED_DIR, folder, 'ground_truth.json'))
                    sessions.append({"folder": folder, "has_gt": has_gt})
        data = json.dumps(sessions, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)

    def _serve_imu(self, query_string):
        params = urllib.parse.parse_qs(query_string)
        folder = params.get('folder', [''])[0]
        if not folder:
            self.send_error(400, 'Missing folder parameter')
            return
        imu_path = os.path.normpath(os.path.join(SHARED_DIR, folder, 'IMU.txt'))
        if not imu_path.startswith(SHARED_DIR):
            self.send_error(403)
            return
        if not os.path.isfile(imu_path):
            data = json.dumps({"found": False}).encode('utf-8')
        else:
            rows = []
            with open(imu_path, 'r', encoding='utf-8') as f:
                header = f.readline().strip().split('\t')
                for line in f:
                    parts = line.strip().split('\t')
                    if len(parts) >= 11:
                        rows.append({
                            "time": parts[0],
                            "ax": float(parts[2]) if parts[2] != 'null' else None,
                            "ay": float(parts[3]) if parts[3] != 'null' else None,
                            "az": float(parts[4]) if parts[4] != 'null' else None,
                            "gx": float(parts[5]) if parts[5] != 'null' else None,
                            "gy": float(parts[6]) if parts[6] != 'null' else None,
                            "gz": float(parts[7]) if parts[7] != 'null' else None,
                            "rx": float(parts[8]) if parts[8] != 'null' else None,
                            "ry": float(parts[9]) if parts[9] != 'null' else None,
                            "rz": float(parts[10]) if parts[10] != 'null' else None,
                        })
            gt_path = os.path.join(SHARED_DIR, folder, 'ground_truth.json')
            gt = None
            if os.path.isfile(gt_path):
                with open(gt_path, 'r', encoding='utf-8') as f:
                    gt = json.load(f)
            data = json.dumps({"found": True, "data": rows, "gt": gt}, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)

    def _serve_video_list(self):
        files = []
        if os.path.isdir(RAW_DIR):
            for f in sorted(os.listdir(RAW_DIR)):
                ext = os.path.splitext(f)[1].lower()
                if ext in VIDEO_EXTS:
                    files.append(f)
        data = json.dumps(files, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)

    def _serve_raw_file(self, filename):
        filename = urllib.parse.unquote(filename)
        filepath = os.path.normpath(os.path.join(RAW_DIR, filename))
        if not filepath.startswith(RAW_DIR):
            self.send_error(403)
            return
        if not os.path.isfile(filepath):
            self.send_error(404)
            return

        ext = os.path.splitext(filename)[1].lower()
        content_types = {
            '.mp4': 'video/mp4', '.webm': 'video/webm', '.mov': 'video/quicktime',
            '.avi': 'video/x-msvideo', '.mkv': 'video/x-matroska', '.qt': 'video/quicktime',
            '.flv': 'video/x-flv', '.wmv': 'video/x-ms-wmv',
        }
        content_type = content_types.get(ext, 'application/octet-stream')
        file_size = os.path.getsize(filepath)

        range_header = self.headers.get('Range')
        if range_header:
            range_val = range_header.strip().split('=')[1]
            parts = range_val.split('-')
            start = int(parts[0])
            end = int(parts[1]) if parts[1] else file_size - 1
            length = end - start + 1
            self.send_response(206)
            self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
            self.send_header('Content-Length', length)
            self.send_header('Content-Type', content_type)
            self.send_header('Accept-Ranges', 'bytes')
            self.end_headers()
            with open(filepath, 'rb') as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        else:
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', file_size)
            self.send_header('Accept-Ranges', 'bytes')
            self.end_headers()
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == '__main__':
    PORT = 8765
    print(f'Serving on http://localhost:{PORT}')
    print(f'Raw video dir: {RAW_DIR}')
    server = ThreadedHTTPServer(('0.0.0.0', PORT), Handler)
    server.serve_forever()
