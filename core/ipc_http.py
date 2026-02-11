import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from core.events import Event
from core.bus import event_bus

class Handler(BaseHTTPRequestHandler):
    state_machine = None

    def _send(self, code: int, body: dict):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode("utf-8"))

    def do_GET(self):
        if self.path != "/state":
            return self._send(404, {"ok": False, "error": "not_found"})

        if self.state_machine is None:
            return self._send(503, {"error": "state_machine_unavailable"})

        return self._send(200, {"state": self.state_machine.state})

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
