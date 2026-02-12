import json
import threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

from core.events import Event
from core.bus import event_bus


class Handler(BaseHTTPRequestHandler):
    state_machine = None
    ui_dir = Path(__file__).resolve().parent.parent / "ui"

    def _send(self, code: int, body: dict):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode("utf-8"))

    def _send_static(self, file_name: str):
        file_path = self.ui_dir / file_name
        if not file_path.exists() or not file_path.is_file():
            return self._send(404, {"error": "not_found"})

        content_type = "text/plain; charset=utf-8"
        if file_name.endswith(".html"):
            content_type = "text/html; charset=utf-8"
        elif file_name.endswith(".js"):
            content_type = "application/javascript; charset=utf-8"
        elif file_name.endswith(".css"):
            content_type = "text/css; charset=utf-8"

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(file_path.read_bytes())

    def do_GET(self):
        if self.path == "/":
            return self._send_static("index.html")

        if self.path == "/app.js":
            return self._send_static("app.js")

        if self.path == "/style.css":
            return self._send_static("style.css")

        if self.path == "/state":
            sm = self.state_machine
            if sm is None:
                return self._send(503, {"error": "state_machine_unavailable"})

            return self._send(200, {"state": str(sm.state)})

        if self.path == "/events":
            events = [
                {
                    "type": event.type,
                    "payload": event.payload,
                    "source": event.source,
                    "trace_id": event.trace_id,
                    "timestamp": event.timestamp,
                }
                for event in event_bus.recent(limit=10)
            ]
            return self._send(200, {"events": events})

        return self._send(404, {"error": "not_found"})

    def do_POST(self):
        if self.path != "/event":
            return self._send(404, {"ok": False, "error": "not_found"})

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"

        try:
            data = json.loads(raw)
            ev_type = data.get("type")
            payload = data.get("payload", {})
            source = data.get("source", "openclaw")

            if not ev_type:
                return self._send(400, {"ok": False, "error": "missing_type"})

            event_bus.push(Event(type=ev_type, payload=payload, source=source))
            return self._send(200, {"ok": True})
        except Exception as e:
            return self._send(400, {"ok": False, "error": str(e)})


def start_http_server(host="0.0.0.0", port=7777, state_machine=None):
    # Thread daemon: se muere si se muere el proceso principal (bien para dev)
    Handler.state_machine = state_machine
    server = HTTPServer((host, port), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server
