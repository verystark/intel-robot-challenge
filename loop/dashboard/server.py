"""The dashboard's web server: one page, three camera streams, one event stream, a few commands.

Standard library only (http.server), so it runs in Studio's backend venv with no new packages and
needs no internet. It binds to 127.0.0.1: the dashboard is for the station laptop's own screen.

    GET  /                          the page (static/index.html)
    GET  /static/<file>             style.css, app.js, palette.json
    GET  /stream/<top|wrist|inspection>.mjpg   live camera, MJPEG (~12 fps)
    GET  /api/events                server-sent events: the state as JSON, 5 times a second
    GET  /api/tile/<i>.jpg          the current cycle's stop photos with heatmaps
    GET  /api/img/<cycle>/<file>    saved photos of earlier cycles (history)
    GET  /api/bench                 newest benchmark numbers (device comparison)
    POST /api/stop | /api/resume | /api/pause      same as the keys Esc, R, Space
    POST /api/mark  {"cycle": 3, "ok": true|false|null}   where the brick really landed
"""

from __future__ import annotations

import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import numpy as np

STATIC = Path(__file__).resolve().parent / "static"
PALETTE = Path(__file__).resolve().parent / "palette.json"
REPO = Path(__file__).resolve().parents[2]
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".js": "application/javascript; charset=utf-8", ".json": "application/json"}
CAMERAS = ("top", "wrist", "inspection")
HISTORY_FILE = re.compile(r"^c\d{3}_[0-9]+deg(_heat)?\.jpg$")


def _jpeg(image: np.ndarray, max_width: int = 960, quality: int = 72) -> bytes:
    if image.shape[1] > max_width:
        scale = max_width / image.shape[1]
        image = cv2.resize(image, (max_width, int(image.shape[0] * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes() if ok else b""


def newest_bench() -> dict:
    """The newest Anomalib and policy benchmark rows, for the 'measured placement' table."""
    out: dict = {}
    results = REPO / "bench" / "results"
    for kind in ("anomaly", "policy"):
        files = sorted(results.glob(f"{kind}_*.json"))
        if not files:
            continue
        data = json.loads(files[-1].read_text())
        rows = []
        for r in data.get("rows", []):
            rows.append({"model": r.get("model"), "policy": r.get("policy"), "device": r.get("device"),
                         "median_ms": r.get("median_ms"), "error": bool(r.get("error"))})
        out[kind] = {"time": data.get("time"), "contended": data.get("contended", ""), "rows": rows}
    return out


class DashboardServer:
    def __init__(self, cell, port: int = 8080, host: str = "127.0.0.1") -> None:
        self.cell = cell
        self.host, self.port = host, port
        self.running = True
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, fmt, *args):  # quiet
                pass

            def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):  # noqa: N802
                path = self.path.split("?", 1)[0]
                try:
                    if path in ("/", "/index.html"):
                        return self._file(STATIC / "index.html")
                    if path == "/static/palette.json":
                        return self._file(PALETTE)
                    if path.startswith("/static/"):
                        name = path[len("/static/"):]
                        if "/" in name or name.startswith("."):
                            return self._send(404, b"", "text/plain")
                        return self._file(STATIC / name)
                    if path.startswith("/stream/") and path.endswith(".mjpg"):
                        cam = path[len("/stream/"):-len(".mjpg")]
                        if cam in CAMERAS:
                            return self._mjpeg(cam)
                    if path == "/api/events":
                        return self._events()
                    if path.startswith("/api/tile/") and path.endswith(".jpg"):
                        image = server.cell.telemetry.tile(int(path[len("/api/tile/"):-4]))
                        if image is not None:
                            return self._send(200, _jpeg(image, 480, 85), "image/jpeg")
                        return self._send(404, b"", "text/plain")
                    if path.startswith("/api/img/"):
                        parts = path[len("/api/img/"):].split("/")
                        run_dir = server.cell.run_dir
                        if len(parts) == 2 and HISTORY_FILE.match(parts[1]) and (run_dir / parts[1]).exists():
                            return self._file(run_dir / parts[1], "image/jpeg")
                        return self._send(404, b"", "text/plain")
                    if path == "/api/bench":
                        return self._send(200, json.dumps(newest_bench()).encode(), TYPES[".json"])
                except (BrokenPipeError, ConnectionResetError):
                    return None
                self._send(404, b"not found", "text/plain")

            def do_POST(self):  # noqa: N802
                path = self.path.split("?", 1)[0]
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                if path in ("/api/stop", "/api/resume", "/api/pause"):
                    server.cell.command(path.rsplit("/", 1)[1])
                    return self._send(200, b'{"ok":true}', TYPES[".json"])
                if path == "/api/mark":
                    data = json.loads(body or b"{}")
                    server.cell.telemetry.mark(int(data["cycle"]), data.get("ok"))
                    return self._send(200, b'{"ok":true}', TYPES[".json"])
                self._send(404, b"not found", "text/plain")

            def _file(self, path: Path, ctype: str | None = None) -> None:
                if not path.is_file():
                    return self._send(404, b"not found", "text/plain")
                self._send(200, path.read_bytes(), ctype or TYPES.get(path.suffix, "application/octet-stream"))

            def _mjpeg(self, cam: str) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close")
                self.end_headers()
                last = None
                try:
                    while server.running:
                        image = server.cell.dashboard_frame(cam)
                        if image is not None and image is not last:
                            last = image
                            jpg = _jpeg(image)
                            self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                             + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n")
                        time.sleep(1 / 12)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass

            def _events(self) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close")
                self.end_headers()
                try:
                    while server.running:
                        data = json.dumps(server.cell.dashboard_state(), default=float, separators=(",", ":"))
                        self.wfile.write(f"data: {data}\n\n".encode())
                        self.wfile.flush()
                        time.sleep(0.2)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass

        class Server(ThreadingHTTPServer):
            daemon_threads = True
            allow_reuse_address = True

        self.httpd = Server((host, port), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True, name="dashboard")

    def start(self) -> "DashboardServer":
        self.thread.start()
        return self

    def stop(self) -> None:
        self.running = False
        self.httpd.shutdown()
        self.httpd.server_close()

    @property
    def url(self) -> str:
        return f"http://localhost:{self.port}/"
