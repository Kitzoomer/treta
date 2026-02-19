import json
import threading
import time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from core.events import Event
from core.errors import (
    DependencyError,
    ErrorType,
    InvariantViolationError,
    NotFoundError,
)
from core.bus import EventBus
from core.integrations.gumroad_client import GumroadAPIError, GumroadClient
from core.gumroad_oauth import exchange_code_for_token, get_auth_url, load_token, save_token
from core.services.gumroad_sync_service import GumroadSyncService
from core.system_integrity import compute_system_integrity
from core.reddit_intelligence.router import RedditIntelligenceRouter
from core.reddit_public.config import get_config, update_config
from core.http.response import error as error_response
from core.http.response import success
from core.version import VERSION


class TretaHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address, RequestHandlerClass, *, bus: EventBus, **dependencies):
        super().__init__(server_address, RequestHandlerClass)
        self.bus = bus
        self.state_machine = dependencies.get("state_machine")
        self.opportunity_store = dependencies.get("opportunity_store")
        self.product_proposal_store = dependencies.get("product_proposal_store")
        self.product_plan_store = dependencies.get("product_plan_store")
        self.product_launch_store = dependencies.get("product_launch_store")
        self.performance_engine = dependencies.get("performance_engine")
        self.control = dependencies.get("control")
        self.strategy_engine = dependencies.get("strategy_engine")
        self.strategy_decision_engine = dependencies.get("strategy_decision_engine")
        self.strategy_action_execution_layer = dependencies.get("strategy_action_execution_layer")
        self.autonomy_policy_engine = dependencies.get("autonomy_policy_engine")
        self.daily_loop_engine = dependencies.get("daily_loop_engine")
        self.memory_store = dependencies.get("memory_store")
        self.reddit_router = dependencies.get("reddit_router") or RedditIntelligenceRouter()
        self.mutation_lock = threading.Lock()
        self.integrity_cache_ttl_seconds = 15
        self.integrity_cache = None


class Handler(BaseHTTPRequestHandler):
    ui_dir = Path(__file__).resolve().parent.parent / "ui"

    @property
    def bus(self) -> EventBus:
        return self.server.bus

    @property
    def state_machine(self):
        return self.server.state_machine

    @property
    def opportunity_store(self):
        return self.server.opportunity_store

    @property
    def product_proposal_store(self):
        return self.server.product_proposal_store

    @property
    def product_plan_store(self):
        return self.server.product_plan_store

    @property
    def product_launch_store(self):
        return self.server.product_launch_store

    @property
    def performance_engine(self):
        return self.server.performance_engine

    @property
    def control(self):
        return self.server.control

    @property
    def strategy_engine(self):
        return self.server.strategy_engine

    @property
    def strategy_decision_engine(self):
        return self.server.strategy_decision_engine

    @property
    def strategy_action_execution_layer(self):
        return self.server.strategy_action_execution_layer

    @property
    def autonomy_policy_engine(self):
        return self.server.autonomy_policy_engine

    @property
    def daily_loop_engine(self):
        return self.server.daily_loop_engine

    @property
    def memory_store(self):
        return self.server.memory_store

    @property
    def reddit_router(self):
        return self.server.reddit_router


    def _reddit_posts_path(self) -> Path:
        data_dir = Path(__file__).resolve().parent.parent / ".treta_data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "reddit_posts.json"

    def _load_reddit_posts(self) -> list[dict]:
        path = self._reddit_posts_path()
        if not path.exists():
            return []
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(loaded, list):
            return []
        return [item for item in loaded if isinstance(item, dict)]

    def _save_reddit_posts(self, items: list[dict]) -> None:
        path = self._reddit_posts_path()
        path.write_text(json.dumps(items, indent=2), encoding="utf-8")

    def _send(self, code: int, body: dict):
        normalized_body = self._normalize_body(code, body)
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(normalized_body).encode("utf-8"))

    def _send_success(self, code: int, data: dict):
        return self._send(code, success(data))

    def _send_error(self, status_code: int, error_type: str, code: str, message: str, details: dict | None = None, data: dict | None = None):
        body = error_response(error_type, code, message, details=details)
        if data is not None:
            body["data"] = data
        return self._send(status_code, body)

    def _classify_exception(self, exc: Exception) -> tuple[int, str, str]:
        if isinstance(exc, InvariantViolationError):
            return 500, ErrorType.INVARIANT_VIOLATION, "invariant_violation"
        if isinstance(exc, NotFoundError):
            return 404, ErrorType.NOT_FOUND, "not_found"
        if isinstance(exc, GumroadAPIError):
            return 503, ErrorType.DEPENDENCY_ERROR, "gumroad_api_error"
        if isinstance(exc, DependencyError):
            return 503, ErrorType.DEPENDENCY_ERROR, "dependency_error"
        if isinstance(exc, ValueError):
            return 400, ErrorType.CLIENT_ERROR, "validation_error"
        return 500, ErrorType.SERVER_ERROR, "unexpected_error"

    def _error_type_for_status(self, status_code: int) -> str:
        if status_code == 400:
            return ErrorType.CLIENT_ERROR
        if status_code == 404:
            return ErrorType.NOT_FOUND
        if status_code == 503:
            return ErrorType.DEPENDENCY_ERROR
        return ErrorType.SERVER_ERROR

    def _normalize_body(self, status_code: int, body: dict):
        if isinstance(body, dict) and body.get("ok") in {True, False} and isinstance(body.get("error"), dict) == (body.get("ok") is False):
            if body.get("ok") is True and isinstance(body.get("data"), dict):
                return {**body, **body["data"]}
            return body
        if status_code < 400:
            wrapped = success(body)
            if isinstance(body, dict):
                wrapped.update(body)
            return wrapped

        details = {}
        message = "request_failed"
        if isinstance(body, dict):
            raw_error = body.get("error")
            if isinstance(raw_error, str) and raw_error:
                message = raw_error
            details = {key: value for key, value in body.items() if key != "error"}
        return error_response(
            self._error_type_for_status(status_code),
            message,
            message,
            details=details,
        )

    def _send_mapped_exception(self, exc: Exception):
        status_code, error_type, code = self._classify_exception(exc)
        return self._send_error(status_code, error_type, code, str(exc))

    def _send_static(self, file_name: str):
        file_path = self.ui_dir / file_name
        if not file_path.exists() or not file_path.is_file():
            return self._send(404, error_response(ErrorType.NOT_FOUND, ErrorType.NOT_FOUND, ErrorType.NOT_FOUND))

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

        try:
            reddit_response = self.reddit_router.handle_get(parsed.path, parse_qs(parsed.query))
            if reddit_response is not None:
                code, body = reddit_response
                return self._send(code, body)
        except ValueError:
            return self._send_error(400, ErrorType.CLIENT_ERROR, "invalid_limit", "invalid_limit")

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
                for event in self.bus.recent(limit=10)
            ]
            return self._send(200, {"events": events})

        if parsed.path == "/memory":
            if self.memory_store is None:
                return self._send(503, {"error": "memory_store_unavailable"})
            return self._send(200, self.memory_store.snapshot())

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
                return self._send(404, error_response(ErrorType.NOT_FOUND, ErrorType.NOT_FOUND, ErrorType.NOT_FOUND))
            return self._send(200, item)

        if parsed.path == "/product_launches":
            if self.product_launch_store is None:
                return self._send(503, {"error": "product_launch_store_unavailable"})
            items = self.product_launch_store.list()[:10]
            return self._send(200, {"items": items})

        if parsed.path == "/performance/summary":
            if self.performance_engine is None:
                return self._send(503, {"error": "performance_engine_unavailable"})
            return self._send(200, self.performance_engine.generate_insights())

        if parsed.path == "/strategy/recommendations":
            if self.strategy_engine is None:
                return self._send(503, {"error": "strategy_engine_unavailable"})
            return self._send(200, self.strategy_engine.generate_recommendations())

        if parsed.path == "/strategy/decide":
            if self.strategy_decision_engine is None:
                return self._send(503, {"error": "strategy_decision_engine_unavailable"})
            return self._send(200, self.strategy_decision_engine.decide())

        if parsed.path == "/strategy/pending_actions":
            if self.strategy_action_execution_layer is None:
                return self._send(503, {"error": "strategy_action_execution_layer_unavailable"})
            items = self.strategy_action_execution_layer.list_pending_actions()
            return self._send(200, {"items": items})

        if parsed.path == "/autonomy/status":
            if self.autonomy_policy_engine is None:
                return self._send(503, {"error": "autonomy_policy_engine_unavailable"})
            return self._send(200, self.autonomy_policy_engine.status())

        if parsed.path == "/autonomy/adaptive_status":
            if self.autonomy_policy_engine is None:
                return self._send(503, {"error": "autonomy_policy_engine_unavailable"})
            return self._send(200, self.autonomy_policy_engine.adaptive_status())

        if parsed.path == "/daily_loop/status":
            if self.daily_loop_engine is None:
                return self._send(503, {"error": "daily_loop_engine_unavailable"})
            loop_state = self.daily_loop_engine.get_loop_state()
            loop_state["timestamp"] = time.time()
            return self._send(200, loop_state)

        if parsed.path == "/health/live":
            return self._send_success(200, {"status": "live"})

        if parsed.path == "/health/ready":
            checks = {
                "stores_loadable": all([
                    self.product_proposal_store is not None,
                    self.product_plan_store is not None,
                    self.product_launch_store is not None,
                ]),
                "control_wired": self.control is not None,
                "bus_present": self.bus is not None,
            }
            if all(checks.values()):
                return self._send_success(200, {"status": "ready", "checks": checks})
            return self._send_error(
                503,
                ErrorType.DEPENDENCY_ERROR,
                "not_ready",
                "not_ready",
                details={"checks": checks},
            )

        if parsed.path == "/system/integrity":
            if self.product_proposal_store is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "product_proposal_store_unavailable", "product_proposal_store_unavailable")
            if self.product_plan_store is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "product_plan_store_unavailable", "product_plan_store_unavailable")
            if self.product_launch_store is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "product_launch_store_unavailable", "product_launch_store_unavailable")

            data_errors: list[str] = []

            try:
                proposals = self.product_proposal_store.list()
            except Exception as exc:
                proposals = []
                data_errors.append(f"proposals_load_failed: {exc}")

            try:
                plans = self.product_plan_store.list(limit=10000)
            except TypeError:
                try:
                    plans = self.product_plan_store.list()
                except Exception as exc:
                    plans = []
                    data_errors.append(f"plans_load_failed: {exc}")
            except Exception as exc:
                plans = []
                data_errors.append(f"plans_load_failed: {exc}")

            try:
                launches = self.product_launch_store.list()
            except Exception as exc:
                launches = []
                data_errors.append(f"launches_load_failed: {exc}")

            if data_errors:
                return self._send_error(
                    503,
                    ErrorType.DEPENDENCY_ERROR,
                    "integrity_data_unavailable",
                    "integrity_data_unavailable",
                    details={"data_errors": data_errors},
                    data={"error": "integrity_data_unavailable", "details": data_errors},
                )

            cache_entry = self.server.integrity_cache
            now = time.time()
            if cache_entry is not None and now - cache_entry["computed_at"] < self.server.integrity_cache_ttl_seconds:
                return self._send_success(200, cache_entry["snapshot"])

            try:
                report = compute_system_integrity(
                    proposals=proposals,
                    plans=plans,
                    launches=launches,
                )
                report["version"] = VERSION
                report["stale"] = False
                report["recompute_failed"] = False
                self.server.integrity_cache = {
                    "snapshot": report,
                    "computed_at": now,
                }
                return self._send_success(200, report)
            except Exception:
                if cache_entry is None:
                    raise
                stale_report = dict(cache_entry["snapshot"])
                stale_report["stale"] = True
                stale_report["recompute_failed"] = True
                return self._send_success(200, stale_report)

        if parsed.path.startswith("/product_launches/"):
            if self.product_launch_store is None:
                return self._send(503, {"error": "product_launch_store_unavailable"})
            launch_id = parsed.path.rsplit("/", 1)[-1]
            item = self.product_launch_store.get(launch_id)
            if item is None:
                return self._send(404, error_response(ErrorType.NOT_FOUND, ErrorType.NOT_FOUND, ErrorType.NOT_FOUND))
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
                return self._send(404, error_response(ErrorType.NOT_FOUND, ErrorType.NOT_FOUND, ErrorType.NOT_FOUND))
            return self._send(200, item)

        if parsed.path == "/opportunities":
            if self.opportunity_store is None:
                return self._send(503, {"error": "opportunity_store_unavailable"})

            query = parse_qs(parsed.query)
            status = query.get("status", [None])[0]
            items = self.opportunity_store.list(status=status)
            return self._send(200, {"items": items})

        if parsed.path == "/gumroad/auth":
            try:
                auth_url = get_auth_url()
            except ValueError as e:
                return self._send(400, {"ok": False, "error": str(e)})

            self.send_response(302)
            self.send_header("Location", auth_url)
            self.end_headers()
            return

        if parsed.path == "/gumroad/callback":
            query = parse_qs(parsed.query)
            code = str(query.get("code", [""])[0]).strip()
            if not code:
                return self._send(400, {"ok": False, "error": "missing_code"})
            try:
                token = exchange_code_for_token(code)
                save_token(token)
            except ValueError as e:
                return self._send(400, {"ok": False, "error": str(e)})
            except Exception as e:
                return self._send(503, {"ok": False, "error": f"oauth_exchange_failed: {e}"})
            return self._send(200, {"status": "connected"})

        if parsed.path == "/reddit/config":
            return self._send_success(200, get_config())

        if parsed.path == "/reddit/last_scan":
            if self.control is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "control_unavailable", "control_unavailable")
            return self._send_success(
                200,
                self.control.get_last_reddit_scan() or {"message": "No scan executed yet."},
            )

        if parsed.path == "/reddit/posts":
            posts = self._load_reddit_posts()
            return self._send_success(200, {"items": list(reversed(posts))})

        return self._send(404, error_response(ErrorType.NOT_FOUND, ErrorType.NOT_FOUND, ErrorType.NOT_FOUND))

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

        launch_link_gumroad_id = None
        if self.path.startswith("/product_launches/") and self.path.endswith("/link_gumroad"):
            launch_link_gumroad_id = self.path[len("/product_launches/"):-len("/link_gumroad")]

        strategy_execute_id = None
        if self.path.startswith("/strategy/execute_action/"):
            strategy_execute_id = self.path[len("/strategy/execute_action/"):]

        strategy_reject_id = None
        if self.path.startswith("/strategy/reject_action/"):
            strategy_reject_id = self.path[len("/strategy/reject_action/"):]

        allowed_paths = {
            "/event",
            "/opportunities/evaluate",
            "/opportunities/dismiss",
            "/scan/infoproduct",
            "/product_plans/build",
            "/product_proposals/execute",
            "/gumroad/sync_sales",
            "/reddit/signals",
            "/reddit/config",
            "/reddit/run_scan",
            "/reddit/mark_posted",
        }
        if self.path not in allowed_paths and transition_event_type is None and launch_sale_id is None and launch_status_id is None and launch_link_gumroad_id is None and strategy_execute_id is None and strategy_reject_id is None:
            return self._send(404, error_response(ErrorType.NOT_FOUND, ErrorType.NOT_FOUND, ErrorType.NOT_FOUND))

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"

        try:
            data = json.loads(raw)

            with self.server.mutation_lock:
                reddit_post_response = self.reddit_router.handle_post(self.path, data)
                if reddit_post_response is not None:
                    code, body = reddit_post_response
                    return self._send(code, body)

                if transition_event_type is not None:
                    if self.control is None:
                        return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "control_unavailable", "control_unavailable")
                    proposal_id = str(transition_proposal_id or "").strip()
                    if not proposal_id:
                        return self._send_error(400, ErrorType.CLIENT_ERROR, "missing_id", "missing_id")

                    transition_event = Event(
                        type=transition_event_type,
                        payload={"proposal_id": proposal_id},
                        source="http",
                    )
                    self.bus.push(transition_event)
                    actions = self.control.consume(transition_event)
                    for action in actions:
                        self.bus.push(Event(type=action.type, payload=action.payload, source="control"))
                        if action.type == "ProductProposalStatusChanged":
                            return self._send_success(200, action.payload["proposal"])

                    return self._send_error(404, ErrorType.NOT_FOUND, "proposal_not_found", "proposal_not_found")

                if self.path == "/event":
                    ev_type = data.get("type")
                    payload = data.get("payload", {})
                    source = data.get("source", "openclaw")

                    if not ev_type:
                        return self._send(400, {"ok": False, "error": "missing_type"})

                    self.bus.push(Event(type=ev_type, payload=payload, source=source))
                    return self._send(200, {"ok": True})

                if self.path == "/scan/infoproduct":
                    self.bus.push(
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
                    self.bus.push(
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
                        return self._send_error(400, ErrorType.CLIENT_ERROR, "missing_id", "missing_id")
                    if self.control is None:
                        return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "control_unavailable", "control_unavailable")

                    execute_event = Event(
                        type="ExecuteProductPlanRequested",
                        payload={"proposal_id": proposal_id},
                        source="http",
                    )
                    self.bus.push(execute_event)
                    actions = self.control.consume(execute_event)
                    for action in actions:
                        self.bus.push(Event(type=action.type, payload=action.payload, source="control"))
                        if action.type == "ProductPlanExecuted":
                            return self._send_success(200, action.payload["execution_package"])

                    return self._send_error(404, ErrorType.NOT_FOUND, "proposal_not_found", "proposal_not_found")

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

                if launch_link_gumroad_id is not None:
                    if self.control is None:
                        return self._send(503, {"ok": False, "error": "control_unavailable"})
                    launch_id = str(launch_link_gumroad_id).strip()
                    if not launch_id:
                        return self._send(400, {"ok": False, "error": "missing_id"})
                    gumroad_product_id = str(data.get("gumroad_product_id", "")).strip()
                    if not gumroad_product_id:
                        return self._send(400, {"ok": False, "error": "missing_gumroad_product_id"})
                    updated = self.control.link_launch_gumroad(launch_id, gumroad_product_id)
                    return self._send(200, updated)

                if self.path == "/gumroad/sync_sales":
                    if self.product_launch_store is None:
                        return self._send(503, {"ok": False, "error": "product_launch_store_unavailable"})
                    access_token = load_token()
                    if not access_token:
                        return self._send(400, {"ok": False, "error": "Gumroad not connected. Visit /gumroad/auth first."})
                    gumroad_client = GumroadClient(access_token)
                    service = GumroadSyncService(self.product_launch_store, gumroad_client)
                    summary = service.sync_sales()
                    return self._send(200, summary)

                if self.path == "/reddit/config":
                    editable_fields = {
                        "subreddits",
                        "pain_threshold",
                        "pain_keywords",
                        "commercial_keywords",
                        "enable_engagement_boost",
                    }
                    payload = {key: value for key, value in data.items() if key in editable_fields}
                    if "subreddits" in payload:
                        raw_subreddits = payload["subreddits"]
                        if isinstance(raw_subreddits, str):
                            raw_subreddits = raw_subreddits.split(",")
                        payload["subreddits"] = [str(item).strip() for item in raw_subreddits if str(item).strip()]
                    if "pain_threshold" in payload:
                        payload["pain_threshold"] = int(payload["pain_threshold"])
                    if "pain_keywords" in payload:
                        raw_pain_keywords = payload["pain_keywords"]
                        if isinstance(raw_pain_keywords, str):
                            raw_pain_keywords = raw_pain_keywords.split(",")
                        payload["pain_keywords"] = [str(item).strip().lower() for item in raw_pain_keywords if str(item).strip()]
                    if "commercial_keywords" in payload:
                        raw_commercial_keywords = payload["commercial_keywords"]
                        if isinstance(raw_commercial_keywords, str):
                            raw_commercial_keywords = raw_commercial_keywords.split(",")
                        payload["commercial_keywords"] = [str(item).strip().lower() for item in raw_commercial_keywords if str(item).strip()]
                    if "enable_engagement_boost" in payload:
                        payload["enable_engagement_boost"] = bool(payload["enable_engagement_boost"])
                    updated = update_config(payload)
                    return self._send_success(200, updated)

                if self.path == "/reddit/run_scan":
                    if self.control is None:
                        return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "control_unavailable", "control_unavailable")
                    return self._send_success(200, self.control.run_reddit_public_scan())

                if self.path == "/reddit/mark_posted":
                    proposal_id = str(data.get("proposal_id", "")).strip()
                    subreddit = str(data.get("subreddit", "")).strip()
                    post_url = str(data.get("post_url", "")).strip()
                    post_id = str(data.get("post_id", "")).strip()
                    if not post_id and post_url:
                        path_parts = [part for part in urlparse(post_url).path.split("/") if part]
                        if "comments" in path_parts:
                            comments_index = path_parts.index("comments")
                            if comments_index + 1 < len(path_parts):
                                post_id = str(path_parts[comments_index + 1]).strip()
                    if not proposal_id:
                        return self._send_error(400, ErrorType.CLIENT_ERROR, "missing_proposal_id", "missing_proposal_id")
                    if not subreddit:
                        return self._send_error(400, ErrorType.CLIENT_ERROR, "missing_subreddit", "missing_subreddit")
                    if not post_url:
                        return self._send_error(400, ErrorType.CLIENT_ERROR, "missing_post_url", "missing_post_url")

                    product_name = ""
                    if self.product_proposal_store is not None:
                        proposal = self.product_proposal_store.get(proposal_id)
                        if proposal:
                            product_name = str(proposal.get("product_name", "")).strip()

                    upvotes = data.get("upvotes", 0)
                    comments = data.get("comments", 0)
                    try:
                        upvotes = int(upvotes)
                    except (TypeError, ValueError):
                        upvotes = 0
                    try:
                        comments = int(comments)
                    except (TypeError, ValueError):
                        comments = 0

                    entry = {
                        "id": f"reddit_post_{int(time.time() * 1000)}",
                        "post_id": post_id,
                        "proposal_id": proposal_id,
                        "product_name": product_name,
                        "subreddit": subreddit,
                        "post_url": post_url,
                        "upvotes": upvotes,
                        "comments": comments,
                        "status": "open",
                        "date": time.strftime("%Y-%m-%d"),
                        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    }
                    posts = self._load_reddit_posts()
                    posts.append(entry)
                    self._save_reddit_posts(posts)
                    return self._send_success(200, {"item": entry})

                if strategy_execute_id is not None:
                    if self.strategy_action_execution_layer is None:
                        return self._send(503, {"ok": False, "error": "strategy_action_execution_layer_unavailable"})
                    action_id = str(strategy_execute_id).strip()
                    if not action_id:
                        return self._send(400, {"ok": False, "error": "missing_id"})
                    updated = self.strategy_action_execution_layer.execute_action(action_id)
                    return self._send(200, updated)

                if strategy_reject_id is not None:
                    if self.strategy_action_execution_layer is None:
                        return self._send(503, {"ok": False, "error": "strategy_action_execution_layer_unavailable"})
                    action_id = str(strategy_reject_id).strip()
                    if not action_id:
                        return self._send(400, {"ok": False, "error": "missing_id"})
                    updated = self.strategy_action_execution_layer.reject_action(action_id)
                    return self._send(200, updated)

                event_id = str(data.get("id", "")).strip()
                if not event_id:
                    return self._send(400, {"ok": False, "error": "missing_id"})

                if self.path == "/opportunities/evaluate":
                    self.bus.push(
                        Event(
                            type="EvaluateOpportunityById",
                            payload={"id": event_id},
                            source="http",
                        )
                    )
                    return self._send(200, {"ok": True})

                if self.path == "/opportunities/dismiss":
                    self.bus.push(
                        Event(
                            type="OpportunityDismissed",
                            payload={"id": event_id},
                            source="http",
                        )
                    )
                    return self._send(200, {"ok": True})

            return self._send(404, error_response(ErrorType.NOT_FOUND, ErrorType.NOT_FOUND, ErrorType.NOT_FOUND))
        except Exception as e:
            return self._send_mapped_exception(e)

    def do_PATCH(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"

        try:
            data = json.loads(raw)
        except Exception as e:
            return self._send_mapped_exception(ValueError(str(e)))

        with self.server.mutation_lock:
            patch_response = self.reddit_router.handle_patch(self.path, data)
            if patch_response is None:
                return self._send(404, error_response(ErrorType.NOT_FOUND, ErrorType.NOT_FOUND, ErrorType.NOT_FOUND))

            code, body = patch_response
            return self._send(code, body)


def start_http_server(
    host="0.0.0.0",
    port=7777,
    bus: EventBus | None = None,
    state_machine=None,
    opportunity_store=None,
    product_proposal_store=None,
    product_plan_store=None,
    product_launch_store=None,
    performance_engine=None,
    control=None,
    strategy_engine=None,
    strategy_decision_engine=None,
    strategy_action_execution_layer=None,
    autonomy_policy_engine=None,
    daily_loop_engine=None,
    memory_store=None,
):
    # Thread daemon: se muere si se muere el proceso principal (bien para dev)
    resolved_bus = bus or EventBus()
    server = TretaHTTPServer(
        (host, port),
        Handler,
        bus=resolved_bus,
        state_machine=state_machine,
        opportunity_store=opportunity_store,
        product_proposal_store=product_proposal_store,
        product_plan_store=product_plan_store,
        product_launch_store=product_launch_store,
        performance_engine=performance_engine,
        control=control,
        strategy_engine=strategy_engine,
        strategy_decision_engine=strategy_decision_engine,
        strategy_action_execution_layer=strategy_action_execution_layer,
        autonomy_policy_engine=autonomy_policy_engine,
        daily_loop_engine=daily_loop_engine,
        memory_store=memory_store,
        reddit_router=RedditIntelligenceRouter(),
    )
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server
