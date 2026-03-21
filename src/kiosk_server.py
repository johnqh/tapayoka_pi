"""Simple HTTP server for the kiosk display page."""

from __future__ import annotations

import json
import os
import threading
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler

KIOSK_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Tapayoka</title>
  <!-- QR code is now served as a server-generated PNG -->
  <style>
    *, *:before, *:after { padding: 0; margin: 0; box-sizing: border-box; }
    html { cursor: none; }
    body {
      background-color: #080710;
      cursor: none;
      font-family: 'Helvetica Neue', Arial, sans-serif;
      color: #ffffff;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
    }
    .card {
      background-color: rgba(217, 205, 205, 0.13);
      border-radius: 16px;
      backdrop-filter: blur(10px);
      border: 2px solid rgba(255,255,255,0.1);
      box-shadow: 0 0 40px rgba(8,7,16,0.6);
      padding: 40px;
      text-align: center;
      max-width: 420px;
      width: 90%;
    }
    h3 {
      font-size: 28px;
      font-weight: 500;
      margin-bottom: 24px;
    }
    #qrcode {
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 200px;
    }
    #qrcode img { border-radius: 8px; width: 256px; height: 256px; }
    #status {
      display: none;
      flex-direction: column;
      align-items: center;
    }
    #countdown {
      font-size: 72px;
      font-weight: 300;
      margin: 16px 0;
    }
    #status-text {
      font-size: 18px;
      opacity: 0.8;
    }
    .bg-shape {
      position: fixed;
      width: 200px;
      height: 200px;
      border-radius: 50%;
      z-index: -1;
    }
    .bg-shape.top-left {
      background: linear-gradient(#1845ad, #23a2f6);
      left: -60px;
      top: -60px;
    }
    .bg-shape.bottom-right {
      background: linear-gradient(to right, #ff512f, #f09819);
      right: -60px;
      bottom: -60px;
    }
  </style>
</head>
<body>
  <div class="bg-shape top-left"></div>
  <div class="bg-shape bottom-right"></div>
  <div class="card">
    <h3 id="heading">Loading...</h3>
    <div id="qrcode"></div>
    <div id="status">
      <div id="countdown">00:00</div>
      <p id="status-text">Service Active</p>
    </div>
  </div>
  <script>
    let lastTimestamp = 0;
    let lastQrUrl = null;
    let countdownInterval = null;

    function updateState() {
      fetch('/state.json')
        .then(r => r.json())
        .then(data => {
          if (data.timestamp <= lastTimestamp) return;
          lastTimestamp = data.timestamp;

          const qrBox = document.getElementById('qrcode');
          const statusBox = document.getElementById('status');
          const heading = document.getElementById('heading');

          if (data.status === 'RUNNING') {
            qrBox.style.display = 'none';
            statusBox.style.display = 'flex';
            heading.textContent = 'Service Active';

            if (countdownInterval) clearInterval(countdownInterval);

            const startTime = data.started_at;
            const duration = data.duration_seconds;

            countdownInterval = setInterval(() => {
              const now = Math.floor(Date.now() / 1000);
              const remaining = Math.max(0, duration - (now - startTime));
              const m = Math.floor(remaining / 60);
              const s = remaining % 60;
              document.getElementById('countdown').textContent =
                String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
              if (remaining === 0) {
                clearInterval(countdownInterval);
                countdownInterval = null;
              }
            }, 1000);

          } else if (data.status === 'CONNECTED') {
            qrBox.style.display = 'none';
            statusBox.style.display = 'none';
            if (countdownInterval) { clearInterval(countdownInterval); countdownInterval = null; }
            heading.textContent = 'Connected';

          } else if (data.status === 'QR' && data.qr_url) {
            statusBox.style.display = 'none';
            qrBox.style.display = 'flex';
            qrBox.innerHTML = '';
            if (countdownInterval) { clearInterval(countdownInterval); countdownInterval = null; }
            lastQrUrl = data.qr_url;
            heading.textContent = data.message || 'Scan QR Code';
            var img = document.createElement('img');
            img.src = '/qr.png?t=' + data.timestamp;
            qrBox.appendChild(img);

          } else if (data.message) {
            statusBox.style.display = 'none';
            if (lastQrUrl) {
              qrBox.style.display = 'flex';
              qrBox.innerHTML = '';
              heading.textContent = 'Scan QR Code';
              var img2 = document.createElement('img');
              img2.src = '/qr.png?t=' + data.timestamp;
              qrBox.appendChild(img2);
            } else {
              qrBox.style.display = 'none';
              heading.textContent = data.message;
            }
          }
        })
        .catch(() => {});
    }

    setInterval(updateState, 1000);
    updateState();
  </script>
</body>
</html>
"""

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


class KioskHandler(SimpleHTTPRequestHandler):
    """Serves the kiosk HTML page and state.json from a directory."""

    def __init__(self, *args, state_dir: str, **kwargs) -> None:  # type: ignore[no-untyped-def]
        self._state_dir = state_dir
        super().__init__(*args, directory=state_dir, **kwargs)

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        if path == "/" or path == "/index.html":
            self._serve_string(KIOSK_HTML, "text/html")
        elif path == "/state.json":
            state_file = os.path.join(self._state_dir, "state.json")
            if os.path.exists(state_file):
                with open(state_file) as f:
                    content = f.read()
                self._serve_string(content, "application/json")
            else:
                self._serve_string(json.dumps({"status": "IDLE", "timestamp": 0}), "application/json")
        elif path == "/qr.png":
            qr_path = os.path.join(self._state_dir, "qr.png")
            if os.path.exists(qr_path):
                self._serve_binary(qr_path, "image/png")
            else:
                self.send_error(404)
        elif self.path == "/qrcode.min.js":
            js_path = os.path.join(STATIC_DIR, "qrcode.min.js")
            if os.path.exists(js_path):
                with open(js_path) as f:
                    self._serve_string(f.read(), "application/javascript")
            else:
                self.send_error(404)
        else:
            self.send_error(404)

    def _serve_string(self, content: str, content_type: str) -> None:
        data = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _serve_binary(self, path: str, content_type: str) -> None:
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:
        # Silence request logs
        pass


def start_kiosk_server(state_dir: str, port: int = 8080) -> HTTPServer:
    """Start the kiosk HTTP server in a background thread. Returns the server instance."""
    os.makedirs(state_dir, exist_ok=True)

    handler = partial(KioskHandler, state_dir=state_dir)
    server = HTTPServer(("0.0.0.0", port), handler)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[Kiosk] HTTP server started on http://0.0.0.0:{port}")
    return server
