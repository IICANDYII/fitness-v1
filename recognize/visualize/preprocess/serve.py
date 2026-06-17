import http.server
import json
import os
import urllib.parse

RAW_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'raw'))
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
        elif path.startswith('/raw/'):
            self._serve_raw_file(path[5:])
        else:
            super().do_GET()

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
                self.wfile.write(f.read(length))
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


if __name__ == '__main__':
    PORT = 8765
    print(f'Serving on http://localhost:{PORT}')
    print(f'Raw video dir: {RAW_DIR}')
    server = http.server.HTTPServer(('0.0.0.0', PORT), Handler)
    server.serve_forever()
