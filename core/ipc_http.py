import json
import threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from core.events import Event
from core.bus import event_bus


class Handler(BaseHTTPRequestHandler):
    state_machine = None
    opportunity_store = None
    product_proposal_store = None
    product_plan_store = None
    product_launch_store = None
    control = None
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
        parsed = urlparse(self.path)

        if parsed.path == "/":
            return self._send_static("index.html")

        if parsed.path == "/app.js":
            return self._send_static("app.js")

        if parsed.path == "/style.css":
            return self._send_static("style.css")

        if parsed.path == "/state":
            sm = self.state_machine
            if sm is None:
                return self._send(503, {"error": "state_machine_unavailable"})

            return self._send(200, {"state": str(sm.state)})

        if parsed.path == "/events":
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

        if parsed.path == "/product_proposals":
            if self.product_proposal_store is None:
                return self._send(503, {"error": "product_proposal_store_unavailable"})

            items = self.product_proposal_store.list()[:10]
            return self._send(200, {"items": items})

        if parsed.path.startswith("/product_proposals/"):
            if self.product_proposal_store is None:
                return self._send(503, {"error": "product_proposal_store_unavailable"})

            proposal_id = parsed.path.rsplit("/", 1)[-1]
            item = self.product_proposal_store.get(proposal_id)
            if item is None:
                return self._send(404, {"error": "not_found"})
            return self._send(200, item)

        if parsed.path == "/product_launches":
            if self.product_launch_store is None:
                return self._send(503, {"error": "product_launch_store_unavailable"})
            items = self.product_launch_store.list()[:10]
            return self._send(200, {"items": items})

        if parsed.path.startswith("/product_launches/"):
            if self.product_launch_store is None:
                return self._send(503, {"error": "product_launch_store_unavailable"})
            launch_id = parsed.path.rsplit("/", 1)[-1]
            item = self.product_launch_store.get(launch_id)
            if item is None:
                return self._send(404, {"error": "not_found"})
            return self._send(200, item)

        if parsed.path == "/product_plans":
            if self.product_plan_store is None:
                return self._send(503, {"error": "product_plan_store_unavailable"})
            items = self.product_plan_store.list(limit=10)
            return self._send(200, {"items": items})

        if parsed.path.startswith("/product_plans/"):
            if self.product_plan_store is None:
                return self._send(503, {"error": "product_plan_store_unavailable"})
            plan_id = parsed.path.rsplit("/", 1)[-1]
            item = self.product_plan_store.get(plan_id)
            if item is None:
                return self._send(404, {"error": "not_found"})
            return self._send(200, item)

        if parsed.path == "/opportunities":
            if self.opportunity_store is None:
                return self._send(503, {"error": "opportunity_store_unavailable"})

            query = parse_qs(parsed.query)
            status = query.get("status", [None])[0]
            items = self.opportunity_store.list(status=status)
            return self._send(200, {"items": items})

        return self._send(404, {"error": "not_found"})

    def do_POST(self):
        proposal_transition_paths = {
            "/approve": "ApproveProposal",
            "/reject": "RejectProposal",
            "/start_build": "StartBuildingProposal",
            "/ready": "MarkReadyToLaunch",
            "/launch": "MarkProposalLaunched",
            "/archive": "ArchiveProposal",
        }

        transition_event_type = None
        transition_proposal_id = None
        for suffix, event_type in proposal_transition_paths.items():
            marker = f"/product_proposals/"
            if self.path.startswith(marker) and self.path.endswith(suffix):
                transition_proposal_id = self.path[len(marker):-len(suffix)]
                transition_event_type = event_type
                break

        launch_sale_id = None
        if self.path.startswith("/product_launches/") and self.path.endswith("/add_sale"):
            launch_sale_id = self.path[len("/product_launches/"):-len("/add_sale")]

        launch_status_id = None
        if self.path.startswith("/product_launches/") and self.path.endswith("/status"):
            launch_status_id = self.path[len("/product_launches/"):-len("/status")]

        allowed_paths = {
            "/event",
            "/opportunities/evaluate",
            "/opportunities/dismiss",
            "/scan/infoproduct",
            "/product_plans/build",
            "/product_proposals/execute",
        }
        if self.path not in allowed_paths and transition_event_type is None and launch_sale_id is None and launch_status_id is None:
            return self._send(404, {"ok": False, "error": "not_found"})

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"

        try:
            data = json.loads(raw)

            if transition_event_type is not None:
                if self.control is None:
                    return self._send(503, {"ok": False, "error": "control_unavailable"})
                proposal_id = str(transition_proposal_id or "").strip()
                if not proposal_id:
                    return self._send(400, {"ok": False, "error": "missing_id"})

                transition_event = Event(
                    type=transition_event_type,
                    payload={"proposal_id": proposal_id},
                    source="http",
                )
                event_bus.push(transition_event)
                actions = self.control.consume(transition_event)
                for action in actions:
                    event_bus.push(Event(type=action.type, payload=action.payload, source="control"))
                    if action.type == "ProductProposalStatusChanged":
                        return self._send(200, action.payload["proposal"])

                return self._send(404, {"ok": False, "error": "proposal_not_found"})

            if self.path == "/event":
                ev_type = data.get("type")
                payload = data.get("payload", {})
                source = data.get("source", "openclaw")

                if not ev_type:
                    return self._send(400, {"ok": False, "error": "missing_type"})

                event_bus.push(Event(type=ev_type, payload=payload, source=source))
                return self._send(200, {"ok": True})

            if self.path == "/scan/infoproduct":
                event_bus.push(
                    Event(
                        type="RunInfoproductScan",
                        payload={},
                        source="http",
                    )
                )
                return self._send(200, {"ok": True})

            if self.path == "/product_plans/build":
                proposal_id = str(data.get("proposal_id", "")).strip()
                if not proposal_id:
                    return self._send(400, {"ok": False, "error": "missing_proposal_id"})
                event_bus.push(
                    Event(
                        type="BuildProductPlanRequested",
                        payload={"proposal_id": proposal_id},
                        source="http",
                    )
                )
                return self._send(200, {"ok": True})

            if self.path == "/product_proposals/execute":
                proposal_id = str(data.get("id", "")).strip()
                if not proposal_id:
                    return self._send(400, {"ok": False, "error": "missing_id"})
                if self.control is None:
                    return self._send(503, {"ok": False, "error": "control_unavailable"})

                execute_event = Event(
                    type="ExecuteProductPlanRequested",
                    payload={"proposal_id": proposal_id},
                    source="http",
                )
                event_bus.push(execute_event)
                actions = self.control.consume(execute_event)
                for action in actions:
                    event_bus.push(Event(type=action.type, payload=action.payload, source="control"))
                    if action.type == "ProductPlanExecuted":
                        return self._send(200, action.payload["execution_package"])

                return self._send(404, {"ok": False, "error": "proposal_not_found"})

            if launch_sale_id is not None:
                if self.product_launch_store is None:
                    return self._send(503, {"ok": False, "error": "product_launch_store_unavailable"})
                launch_id = str(launch_sale_id).strip()
                if not launch_id:
                    return self._send(400, {"ok": False, "error": "missing_id"})
                amount = float(data.get("amount", 0))
                updated = self.product_launch_store.add_sale(launch_id, amount)
                return self._send(200, updated)

            if launch_status_id is not None:
                if self.product_launch_store is None:
                    return self._send(503, {"ok": False, "error": "product_launch_store_unavailable"})
                launch_id = str(launch_status_id).strip()
                if not launch_id:
                    return self._send(400, {"ok": False, "error": "missing_id"})
                status = str(data.get("status", "")).strip()
                updated = self.product_launch_store.transition_status(launch_id, status)
                return self._send(200, updated)

            event_id = str(data.get("id", "")).strip()
            if not event_id:
                return self._send(400, {"ok": False, "error": "missing_id"})

            if self.path == "/opportunities/evaluate":
                event_bus.push(
                    Event(
                        type="EvaluateOpportunityById",
                        payload={"id": event_id},
                        source="http",
                    )
                )
                return self._send(200, {"ok": True})

            if self.path == "/opportunities/dismiss":
                event_bus.push(
                    Event(
                        type="OpportunityDismissed",
                        payload={"id": event_id},
                        source="http",
                    )
                )
                return self._send(200, {"ok": True})

            return self._send(404, {"ok": False, "error": "not_found"})
        except Exception as e:
            return self._send(400, {"ok": False, "error": str(e)})


def start_http_server(
    host="0.0.0.0",
    port=7777,
    state_machine=None,
    opportunity_store=None,
    product_proposal_store=None,
    product_plan_store=None,
    product_launch_store=None,
    control=None,
):
    # Thread daemon: se muere si se muere el proceso principal (bien para dev)
    Handler.state_machine = state_machine
    Handler.opportunity_store = opportunity_store
    Handler.product_proposal_store = product_proposal_store
    Handler.product_plan_store = product_plan_store
    Handler.product_launch_store = product_launch_store
    Handler.control = control
    server = HTTPServer((host, port), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server
