import json
import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from core.events import Event
from core.creator_intelligence import (
    CreatorDemandValidator,
    CreatorOfferService,
    CreatorPainClassifier,
    CreatorProductSuggester,
    CreatorLaunchTracker,
)
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
from core.revenue_attribution.store import RevenueAttributionStore
from core.subreddit_performance_store import SubredditPerformanceStore
from core.system_integrity import compute_system_integrity
from core.reddit_intelligence.router import RedditIntelligenceRouter
from core.reddit_public.config import get_config, update_config
from core.http_response import error, ok
from core.logging_config import set_request_id, set_trace_id
from core.version import VERSION
from core.config import API_TOKEN

UI_DIR = Path(__file__).parent.parent / "ui"
logger = logging.getLogger("treta.http")

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

_auth_dev_mode_warned = False


def require_auth(headers) -> bool:
    global _auth_dev_mode_warned
    if API_TOKEN is None:
        if not _auth_dev_mode_warned:
            logger.warning("TRETA running in dev permissive mode (no API token set)")
            _auth_dev_mode_warned = True
        return True

    auth_header = headers.get("Authorization")
    if not auth_header:
        return False

    if not auth_header.startswith("Bearer "):
        return False

    token = auth_header.split(" ", 1)[1]
    return token == API_TOKEN


def _is_protected_endpoint(method: str, path: str) -> bool:
    if method in {"PUT", "DELETE"}:
        return True
    if method != "POST":
        return False
    if path == "/strategy/decide":
        return True
    if path.startswith("/scan/"):
        return True
    if path == "/opportunities/evaluate":
        return True
    if path == "/autonomy/override":
        return True
    return False


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
        self.conversation_core = dependencies.get("conversation_core")
        self.reddit_router = dependencies.get("reddit_router") or RedditIntelligenceRouter()
        self.mutation_lock = threading.Lock()
        self.revenue_attribution_store = dependencies.get("revenue_attribution_store")
        self.subreddit_performance_store = dependencies.get("subreddit_performance_store")
        self.storage = dependencies.get("storage")
        self.integrity_cache_ttl_seconds = 15
        self.integrity_cache = None
        self.operation_timeout_seconds = 8
        self.metrics_lock = threading.Lock()
        self.metrics = {
            "last_integrity_compute_ms": None,
            "last_integrity_at": None,
            "integrity_cache_hit": 0,
            "last_mutation_at": None,
        }

    def update_metrics(self, **updates):
        with self.metrics_lock:
            self.metrics.update(updates)

    def increment_metric(self, metric_name: str):
        with self.metrics_lock:
            current = int(self.metrics.get(metric_name, 0))
            self.metrics[metric_name] = current + 1

    def snapshot_metrics(self) -> dict:
        with self.metrics_lock:
            snapshot = dict(self.metrics)
        if self.bus is not None and hasattr(self.bus, "_q") and hasattr(self.bus._q, "qsize"):
            snapshot["event_queue_depth"] = self.bus._q.qsize()
        return snapshot


class Handler(BaseHTTPRequestHandler):
    ui_dir = UI_DIR

    def _ensure_request_id(self) -> str:
        if not hasattr(self, "request_id"):
            incoming_request_id = str(self.headers.get("X-Request-Id", "")).strip()
            self.request_id = incoming_request_id or str(uuid.uuid4())
            set_request_id(self.request_id)
        return self.request_id

    def _ensure_trace_id(self) -> str:
        if not hasattr(self, "trace_id"):
            incoming_trace_id = str(self.headers.get("X-Trace-Id", "")).strip()
            self.trace_id = incoming_trace_id or str(uuid.uuid4())
            set_trace_id(self.trace_id)
        return self.trace_id

    def _ensure_event_id(self) -> str:
        if not hasattr(self, "event_id"):
            incoming_event_id = str(self.headers.get("X-Event-Id", "")).strip()
            self.event_id = incoming_event_id or str(uuid.uuid4())
        return self.event_id

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
    def conversation_core(self):
        return self.server.conversation_core

    @property
    def reddit_router(self):
        return self.server.reddit_router

    @property
    def revenue_attribution_store(self):
        return self.server.revenue_attribution_store

    @property
    def subreddit_performance_store(self):
        return self.server.subreddit_performance_store

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
        self.send_header("X-Request-Id", self._ensure_request_id())
        self.end_headers()
        self.wfile.write(json.dumps(normalized_body).encode("utf-8"))

    def _send_success(self, code: int, data: dict):
        return self._send(code, ok(data, self._ensure_request_id()))

    def _send_bytes(self, code: int, body: bytes, content_type: str):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("X-Request-Id", self._ensure_request_id())
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status_code: int, error_type: str, code: str, message: str, details: dict | None = None, data: dict | None = None):
        merged_details = dict(details or {})
        if error_type:
            merged_details.setdefault("type", error_type)
        if data is not None:
            merged_details.setdefault("data", data)
        return self._send(status_code, error(code, message, merged_details, self._ensure_request_id()))


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

    def _handle_exception(self, exc: Exception):
        status_code, error_type, code = self._classify_exception(exc)
        if code == "unexpected_error":
            return self._send_internal_error(exc)
        return self._send_error(status_code, error_type, code, str(exc))

    def _normalize_body(self, status_code: int, body: dict):
        request_id = self._ensure_request_id()
        if isinstance(body, dict) and body.get("ok") in {True, False} and "data" in body and "error" in body:
            if body.get("ok") is True:
                return ok(body.get("data"), request_id)
            raw_error = body.get("error") if isinstance(body.get("error"), dict) else {}
            return error(
                str(raw_error.get("code", "request_failed")),
                str(raw_error.get("message", "request_failed")),
                raw_error.get("details") if isinstance(raw_error.get("details"), dict) else {},
                request_id,
            )

        if status_code < 400:
            wrapped = ok(body, request_id)
            if isinstance(body, dict):
                wrapped.update(body)
            return wrapped

        message = "request_failed"
        details = {}
        if isinstance(body, dict):
            raw_error = body.get("error")
            if isinstance(raw_error, str) and raw_error:
                message = raw_error
            elif isinstance(raw_error, dict):
                message = str(raw_error.get("message") or raw_error.get("code") or message)
                details = raw_error.get("details") if isinstance(raw_error.get("details"), dict) else {}
            details = details or {key: value for key, value in body.items() if key != "error"}
        return error(message, message, details, request_id)

    def _check_auth_or_401(self, method: str, path: str) -> bool:
        if not _is_protected_endpoint(method, path):
            return True
        if require_auth(self.headers):
            return True
        logger.warning("request_id=%s unauthorized endpoint=%s", self._ensure_request_id(), path)
        self._send(401, {"error": "unauthorized"})
        return False

    def _send_internal_error(self, exc: Exception):
        request_id = self._ensure_request_id()
        logger.exception("request_id=%s Unexpected server error", request_id, exc_info=exc)
        return self._send(500, error("internal_error", "Unexpected server error", None, request_id))

    def _send_timeout_error(self, operation_name: str):
        request_id = self._ensure_request_id()
        self.log_error("request_id=%s timeout operation=%s", request_id, operation_name)
        return self._send_error(
            500,
            ErrorType.SERVER_ERROR,
            "server_error",
            f"{operation_name}_timeout",
            details={"request_id": request_id, "operation": operation_name},
        )

    def _run_with_timeout(self, operation_name: str, func):
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"treta-{operation_name}")
        future = executor.submit(func)
        try:
            return True, future.result(timeout=self.server.operation_timeout_seconds)
        except TimeoutError:
            future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            return False, None
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _resolve_static_path(self, request_path: str) -> Path | None:
        if request_path == "/":
            relative_path = "index.html"
        else:
            relative_path = request_path.lstrip("/")

        if not relative_path:
            return None

        candidate = (self.ui_dir / relative_path).resolve()
        ui_root = self.ui_dir.resolve()
        if ui_root not in candidate.parents and candidate != ui_root:
            return None
        return candidate

    def _send_static(self, request_path: str):
        file_path = self._resolve_static_path(request_path)
        if file_path is None or not file_path.exists() or not file_path.is_file():
            return self._send_error(404, ErrorType.NOT_FOUND, "not_found", "not_found")

        content_type = "application/octet-stream"
        suffix = file_path.suffix.lower()
        if suffix == ".html":
            content_type = "text/html; charset=utf-8"
        elif suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        elif suffix == ".css":
            content_type = "text/css; charset=utf-8"

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("X-Request-Id", self._ensure_request_id())
        self.end_headers()
        self.wfile.write(file_path.read_bytes())

    def do_GET(self):
        try:
            return self._do_get()
        except Exception as e:
            return self._handle_exception(e)

    def _do_get(self):
        self._ensure_request_id()
        self._ensure_trace_id()
        parsed = urlparse(self.path)

        try:
            reddit_response = self.reddit_router.handle_get(parsed.path, parse_qs(parsed.query))
            if reddit_response is not None:
                code, body = reddit_response
                return self._send(code, body)
        except ValueError:
            return self._send_error(400, ErrorType.CLIENT_ERROR, "invalid_limit", "invalid_limit")

        static_path = self._resolve_static_path(parsed.path)
        if static_path is not None and static_path.exists() and static_path.is_file():
            return self._send_static(parsed.path)

        if parsed.path == "/state":
            sm = self.state_machine
            if sm is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "state_machine_unavailable", "state_machine_unavailable")

            return self._send(200, {"state": str(sm.state)})

        if parsed.path == "/events":
            events = [
                {
                    "type": event.type,
                    "payload": event.payload,
                    "source": event.source,
                    "request_id": event.request_id,
                    "trace_id": event.trace_id,
                    "timestamp": event.timestamp,
                    "event_id": event.event_id,
                }
                for event in self.bus.recent(limit=10)
            ]
            return self._send(200, {"events": events})

        if parsed.path == "/memory":
            if self.memory_store is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "memory_store_unavailable", "memory_store_unavailable")
            return self._send(200, self.memory_store.snapshot())

        if parsed.path == "/product_proposals":
            if self.product_proposal_store is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "product_proposal_store_unavailable", "product_proposal_store_unavailable")

            items = self.product_proposal_store.list()[:10]
            return self._send(200, {"items": items})

        if parsed.path.startswith("/product_proposals/"):
            if self.product_proposal_store is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "product_proposal_store_unavailable", "product_proposal_store_unavailable")

            proposal_id = parsed.path.rsplit("/", 1)[-1]
            item = self.product_proposal_store.get(proposal_id)
            if item is None:
                return self._send_error(404, ErrorType.NOT_FOUND, "not_found", "not_found")
            return self._send(200, item)

        if parsed.path == "/product_launches":
            if self.product_launch_store is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "product_launch_store_unavailable", "product_launch_store_unavailable")
            items = self.product_launch_store.list()[:10]
            return self._send(200, {"items": items})

        if parsed.path == "/performance/summary":
            if self.performance_engine is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "performance_engine_unavailable", "performance_engine_unavailable")
            return self._send(200, self.performance_engine.generate_insights())

        if parsed.path == "/revenue/summary":
            if self.revenue_attribution_store is None:
                return self._send_success(200, {"totals": {"sales": 0, "revenue": 0.0}, "by_product": {}, "by_channel": {}, "by_subreddit": {}, "sales": []})
            return self._send_success(200, self.revenue_attribution_store.summary())

        if parsed.path == "/revenue/subreddits":
            if self.subreddit_performance_store is None:
                return self._send_success(200, {"subreddits": []})

            summary = self.subreddit_performance_store.get_summary()
            revenue_summary = self.revenue_attribution_store.summary() if self.revenue_attribution_store is not None else {}
            by_subreddit = revenue_summary.get("by_subreddit", {}) if isinstance(revenue_summary, dict) else {}
            subreddits = []
            for item in summary.get("subreddits", []):
                name = str(item.get("name", ""))
                posts_attempted = int(item.get("posts_attempted", 0) or 0)
                revenue_item = by_subreddit.get(name, {}) if isinstance(by_subreddit, dict) else {}
                sales = int(revenue_item.get("sales", item.get("sales", 0)) or 0)
                conversion_rate = (sales / posts_attempted) if posts_attempted > 0 else 0.0
                subreddits.append(
                    {
                        "name": name,
                        "posts_attempted": posts_attempted,
                        "plans_executed": int(item.get("plans_executed", 0) or 0),
                        "sales": sales,
                        "conversion_rate": round(conversion_rate, 4),
                    }
                )
            return self._send_success(200, {"subreddits": subreddits})

        if parsed.path == "/revenue/roi":
            if self.subreddit_performance_store is None:
                return self._send_success(200, {"subreddits": []})

            summary = self.subreddit_performance_store.get_summary()
            revenue_summary = self.revenue_attribution_store.summary() if self.revenue_attribution_store is not None else {}
            by_subreddit = revenue_summary.get("by_subreddit", {}) if isinstance(revenue_summary, dict) else {}
            subreddits = []
            for item in summary.get("subreddits", []):
                name = str(item.get("name", ""))
                posts_attempted = int(item.get("posts_attempted", 0) or 0)
                revenue_item = by_subreddit.get(name, {}) if isinstance(by_subreddit, dict) else {}
                sales = int(revenue_item.get("sales", item.get("sales", 0)) or 0)
                roi = (sales / posts_attempted) if posts_attempted > 0 else 0.0
                subreddits.append(
                    {
                        "name": name,
                        "roi": round(roi, 4),
                        "posts_attempted": posts_attempted,
                        "sales": sales,
                    }
                )
            return self._send_success(200, {"subreddits": subreddits})

        if parsed.path == "/revenue/dominant":
            if self.control is None:
                return self._send_success(200, {"dominant_subreddits": [], "total_tracked": 0})
            return self._send_success(200, self.control.get_dominant_subreddits(limit=2))

        if parsed.path == "/metrics/strategic/summary":
            if self.server.storage is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "storage_unavailable", "storage_unavailable")
            return self._send_success(200, self.server.storage.get_strategic_metrics_summary())

        if parsed.path == "/strategy/recommendations":
            if self.strategy_engine is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "strategy_engine_unavailable", "strategy_engine_unavailable")
            return self._send(200, self.strategy_engine.generate_recommendations())

        if parsed.path == "/strategy/decide":
            if not self._check_auth_or_401("POST", parsed.path):
                return
            if self.strategy_decision_engine is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "strategy_decision_engine_unavailable", "strategy_decision_engine_unavailable")
            if self.control is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "control_unavailable", "control_unavailable")
            request_id = self._ensure_request_id()
            trace_id = self._ensure_trace_id()
            event_id = self._ensure_event_id()
            event = Event(
                type="RunStrategyDecision",
                payload={
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "event_id": event_id,
                },
                source="http",
                request_id=request_id,
                trace_id=trace_id,
                event_id=event_id,
            )
            actions = self.control.consume(event)
            result = actions[0].payload if actions else {"status": "executed", "cooldown_active": False}
            if result.get("status") == "skipped":
                return self._send_success(
                    200,
                    {
                        "status": "skipped",
                        "reason": "cooldown_active",
                        "cooldown_remaining_minutes": float(result.get("cooldown_remaining_minutes", 0.0) or 0.0),
                    },
                )
            return self._send_success(
                200,
                {
                    "status": "executed",
                    "cooldown_active": False,
                },
            )

        if parsed.path == "/debug/events/recent":
            if self.server.storage is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "storage_unavailable", "storage_unavailable")
            query = parse_qs(parsed.query)
            limit_raw = query.get("limit", ["50"])[0]
            try:
                limit = int(limit_raw)
            except (TypeError, ValueError):
                return self._send_error(400, ErrorType.CLIENT_ERROR, "invalid_limit", "invalid_limit")
            items = self.server.storage.list_recent_processed_events(limit=limit)
            return self._send_success(200, {"items": items})

        if parsed.path in {"/system/decision_logs", "/decision-logs"}:
            if self.server.storage is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "storage_unavailable", "storage_unavailable")
            query = parse_qs(parsed.query)
            limit_raw = query.get("limit", ["50"])[0]
            decision_type = str(query.get("decision_type", [""])[0] or "").strip() or None
            try:
                limit = int(limit_raw)
            except (TypeError, ValueError):
                return self._send_error(400, ErrorType.CLIENT_ERROR, "invalid_limit", "invalid_limit")
            items = self.server.storage.list_recent_decision_logs(limit=limit, decision_type=decision_type)
            return self._send_success(200, items)

        if parsed.path == "/decision-logs/entity":
            if self.server.storage is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "storage_unavailable", "storage_unavailable")
            query = parse_qs(parsed.query)
            entity_type = str(query.get("entity_type", [""])[0] or "").strip()
            entity_id = str(query.get("entity_id", [""])[0] or "").strip()
            limit_raw = query.get("limit", ["50"])[0]
            if not entity_type or not entity_id:
                return self._send_error(400, ErrorType.CLIENT_ERROR, "missing_entity", "missing_entity")
            try:
                limit = int(limit_raw)
            except (TypeError, ValueError):
                return self._send_error(400, ErrorType.CLIENT_ERROR, "invalid_limit", "invalid_limit")
            items = self.server.storage.get_decision_logs_for_entity(entity_type=entity_type, entity_id=entity_id, limit=limit)
            return self._send_success(200, items)

        if parsed.path == "/strategy/pending_actions":
            if self.strategy_action_execution_layer is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "strategy_action_execution_layer_unavailable", "strategy_action_execution_layer_unavailable")
            items = self.strategy_action_execution_layer.list_pending_actions()
            return self._send(200, {"items": items})

        if parsed.path == "/autonomy/status":
            if self.autonomy_policy_engine is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "autonomy_policy_engine_unavailable", "autonomy_policy_engine_unavailable")
            return self._send(200, self.autonomy_policy_engine.status())

        if parsed.path == "/autonomy/adaptive_status":
            if self.autonomy_policy_engine is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "autonomy_policy_engine_unavailable", "autonomy_policy_engine_unavailable")
            return self._send(200, self.autonomy_policy_engine.adaptive_status())

        if parsed.path == "/daily_loop/status":
            if self.daily_loop_engine is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "daily_loop_engine_unavailable", "daily_loop_engine_unavailable")
            loop_state = self.daily_loop_engine.get_loop_state()
            loop_state["timestamp"] = time.time()
            return self._send(200, loop_state)

        if parsed.path == "/health/live":
            return self._send_success(200, {"status": "live"})

        if parsed.path == "/health":
            return self._send_success(
                200,
                {
                    "status": "ok",
                    "timestamp": time.time(),
                    "version": VERSION,
                },
            )

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
                return self._send_success(200, {"status": "ready", "checks": checks, "metrics": self.server.snapshot_metrics()})
            return self._send_error(
                503,
                ErrorType.DEPENDENCY_ERROR,
                "not_ready",
                "not_ready",
                details={"checks": checks},
            )

        if parsed.path == "/ready":
            if self.server.storage is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "storage_unavailable", "storage_unavailable")
            try:
                self.server.storage.conn.execute("SELECT 1").fetchone()
                return self._send_success(200, {"status": "ready", "timestamp": time.time(), "version": VERSION})
            except Exception as exc:
                return self._send_error(
                    503,
                    ErrorType.DEPENDENCY_ERROR,
                    "db_not_ready",
                    "db_not_ready",
                    details={"error": str(exc)},
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
                self.server.increment_metric("integrity_cache_hit")
                cached_snapshot = dict(cache_entry["snapshot"])
                cached_snapshot["metrics"] = self.server.snapshot_metrics()
                return self._send_success(200, cached_snapshot)

            try:
                started_at = time.perf_counter()

                ok, report = self._run_with_timeout(
                    "integrity_recompute",
                    lambda: compute_system_integrity(
                        proposals=proposals,
                        plans=plans,
                        launches=launches,
                    ),
                )
                if not ok:
                    return self._send_timeout_error("integrity_recompute")

                finished_at = time.time()
                compute_ms = round((time.perf_counter() - started_at) * 1000, 2)
                self.server.update_metrics(
                    last_integrity_compute_ms=compute_ms,
                    last_integrity_at=finished_at,
                )
                report["version"] = VERSION
                report["stale"] = False
                report["recompute_failed"] = False
                report["metrics"] = self.server.snapshot_metrics()
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
                stale_report["metrics"] = self.server.snapshot_metrics()
                return self._send_success(200, stale_report)

        if parsed.path.startswith("/product_launches/"):
            if self.product_launch_store is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "product_launch_store_unavailable", "product_launch_store_unavailable")
            launch_id = parsed.path.rsplit("/", 1)[-1]
            item = self.product_launch_store.get(launch_id)
            if item is None:
                return self._send_error(404, ErrorType.NOT_FOUND, "not_found", "not_found")
            return self._send(200, item)

        if parsed.path == "/product_plans":
            if self.product_plan_store is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "product_plan_store_unavailable", "product_plan_store_unavailable")
            items = self.product_plan_store.list(limit=10)
            return self._send(200, {"items": items})

        if parsed.path.startswith("/product_plans/"):
            if self.product_plan_store is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "product_plan_store_unavailable", "product_plan_store_unavailable")
            plan_id = parsed.path.rsplit("/", 1)[-1]
            item = self.product_plan_store.get(plan_id)
            if item is None:
                return self._send_error(404, ErrorType.NOT_FOUND, "not_found", "not_found")
            return self._send(200, item)

        if parsed.path == "/opportunities":
            if self.opportunity_store is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "opportunity_store_unavailable", "opportunity_store_unavailable")

            query = parse_qs(parsed.query)
            status = query.get("status", [None])[0]
            items = self.opportunity_store.list(status=status)
            return self._send(200, {"items": items})

        if parsed.path == "/gumroad/auth":
            try:
                auth_url = get_auth_url()
            except ValueError as e:
                return self._send_error(400, ErrorType.CLIENT_ERROR, "validation_error", str(e))

            self.send_response(302)
            self.send_header("Location", auth_url)
            self.send_header("X-Request-Id", self._ensure_request_id())
            self.end_headers()
            return

        if parsed.path == "/gumroad/callback":
            query = parse_qs(parsed.query)
            code = str(query.get("code", [""])[0]).strip()
            if not code:
                return self._send_error(400, ErrorType.CLIENT_ERROR, "missing_code", "missing_code")
            try:
                token = exchange_code_for_token(code)
                save_token(token)
            except ValueError as e:
                return self._send_error(400, ErrorType.CLIENT_ERROR, "validation_error", str(e))
            except Exception as e:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "oauth_exchange_failed", f"oauth_exchange_failed: {e}")
            return self._send(200, {"status": "connected"})

        if parsed.path == "/creator/pains":
            if self.server.storage is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "storage_unavailable", "storage_unavailable")
            classifier = CreatorPainClassifier(storage=self.server.storage)
            items = classifier.list_recent_analysis(limit=50)
            return self._send(200, {"ok": True, "data": items, "error": None})

        if parsed.path == "/creator/product_suggestions":
            if self.server.storage is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "storage_unavailable", "storage_unavailable")
            suggester = CreatorProductSuggester(storage=self.server.storage)
            items = suggester.list_recent_suggestions(limit=20)
            return self._send_success(200, {"items": items})

        if parsed.path == "/creator/offers":
            if self.server.storage is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "storage_unavailable", "storage_unavailable")
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["20"])[0])
            except (TypeError, ValueError):
                return self._send_error(400, ErrorType.CLIENT_ERROR, "invalid_limit", "invalid_limit")
            service = CreatorOfferService(storage=self.server.storage)
            items = service.list_offer_drafts(limit=limit)
            return self._send_success(200, {"items": items})

        if parsed.path.startswith("/creator/offers/"):
            if self.server.storage is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "storage_unavailable", "storage_unavailable")
            offer_id = parsed.path.rsplit("/", 1)[-1]
            service = CreatorOfferService(storage=self.server.storage)
            item = service.get_offer_draft(offer_id)
            if item is None:
                return self._send_error(404, ErrorType.NOT_FOUND, "not_found", "not_found")
            return self._send_success(200, item)

        if parsed.path == "/creator/launches":
            if self.server.storage is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "storage_unavailable", "storage_unavailable")
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["50"])[0])
            except (TypeError, ValueError):
                return self._send_error(400, ErrorType.CLIENT_ERROR, "invalid_limit", "invalid_limit")
            tracker = CreatorLaunchTracker(storage=self.server.storage)
            items = tracker.list_launches(limit=limit)
            return self._send_success(200, {"items": items})

        if parsed.path == "/creator/launches/summary":
            if self.server.storage is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "storage_unavailable", "storage_unavailable")
            tracker = CreatorLaunchTracker(storage=self.server.storage)
            return self._send_success(200, tracker.get_performance_summary())

        if parsed.path == "/creator/demand":
            if self.server.storage is None:
                return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "storage_unavailable", "storage_unavailable")
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["20"])[0])
            except (TypeError, ValueError):
                return self._send_error(400, ErrorType.CLIENT_ERROR, "invalid_limit", "invalid_limit")
            validator = CreatorDemandValidator(storage=self.server.storage)
            items = validator.list_recent_validations(limit=limit)
            return self._send_success(200, {"items": items})

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

        return self._send_error(404, ErrorType.NOT_FOUND, "not_found", "not_found")
    def do_POST(self):
        self._ensure_request_id()
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

        creator_launch_sale_id = None
        if self.path.startswith("/creator/launches/") and self.path.endswith("/sale"):
            creator_launch_sale_id = self.path[len("/creator/launches/"):-len("/sale")]


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
            "/conversation/message",
            "/voice/tts",
            "/creator/offers/generate",
            "/creator/demand/validate",
            "/creator/launches/register",
            "/autonomy/override",
        }
        if self.path not in allowed_paths and transition_event_type is None and launch_sale_id is None and launch_status_id is None and launch_link_gumroad_id is None and strategy_execute_id is None and strategy_reject_id is None and creator_launch_sale_id is None:
            return self._send_error(404, ErrorType.NOT_FOUND, "not_found", "not_found")

        if not self._check_auth_or_401("POST", self.path):
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"

        try:
            data = json.loads(raw)

            with self.server.mutation_lock:
                self.server.update_metrics(last_mutation_at=time.time())
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
                        payload={"proposal_id": proposal_id, "request_id": self._ensure_request_id()},
                        source="http",
                        request_id=self._ensure_request_id(),
                    )
                    self.bus.push(transition_event)
                    actions = self.control.consume(transition_event)
                    for action in actions:
                        self.bus.push(Event(type=action.type, payload=action.payload, source="control", request_id=self._ensure_request_id()))
                        if action.type == "ProductProposalStatusChanged":
                            return self._send_success(200, action.payload["proposal"])

                    return self._send_error(404, ErrorType.NOT_FOUND, "proposal_not_found", "proposal_not_found")

                if self.path == "/event":
                    ev_type = data.get("type")
                    payload = data.get("payload", {})
                    source = data.get("source", "openclaw")

                    if not ev_type:
                        return self._send_error(400, ErrorType.CLIENT_ERROR, "missing_type", "missing_type")

                    self.bus.push(Event(type=ev_type, payload={**payload, "request_id": self._ensure_request_id(), "trace_id": self._ensure_trace_id()}, source=source, request_id=self._ensure_request_id(), trace_id=self._ensure_trace_id()))
                    return self._send_success(200, {"status": "ok"})

                if self.path == "/scan/infoproduct":
                    self.bus.push(
                        Event(
                            type="RunInfoproductScan",
                            payload={"request_id": self._ensure_request_id()},
                            source="http",
                            request_id=self._ensure_request_id(),
                            trace_id=self._ensure_trace_id(),
                        )
                    )
                    return self._send_success(200, {"status": "ok"})

                if self.path == "/product_plans/build":
                    proposal_id = str(data.get("proposal_id", "")).strip()
                    if not proposal_id:
                        return self._send_error(400, ErrorType.CLIENT_ERROR, "missing_proposal_id", "missing_proposal_id")
                    self.bus.push(
                        Event(
                            type="BuildProductPlanRequested",
                            payload={"proposal_id": proposal_id, "request_id": self._ensure_request_id()},
                            source="http",
                            request_id=self._ensure_request_id(),
                            trace_id=self._ensure_trace_id(),
                        )
                    )
                    return self._send_success(200, {"status": "ok"})

                if self.path == "/product_proposals/execute":
                    proposal_id = str(data.get("id", "")).strip()
                    if not proposal_id:
                        return self._send_error(400, ErrorType.CLIENT_ERROR, "missing_id", "missing_id")
                    if self.control is None:
                        return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "control_unavailable", "control_unavailable")

                    execute_event = Event(
                        type="ExecuteProductPlanRequested",
                        payload={"proposal_id": proposal_id, "request_id": self._ensure_request_id()},
                        source="http",
                        request_id=self._ensure_request_id(),
                    )
                    self.bus.push(execute_event)
                    actions = self.control.consume(execute_event)
                    for action in actions:
                        self.bus.push(Event(type=action.type, payload=action.payload, source="control", request_id=self._ensure_request_id()))
                        if action.type == "ProductPlanExecuted":
                            return self._send_success(200, action.payload["execution_package"])

                    return self._send_error(404, ErrorType.NOT_FOUND, "proposal_not_found", "proposal_not_found")

                if self.path == "/conversation/message":
                    if self.conversation_core is None:
                        return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "conversation_core_unavailable", "conversation_core_unavailable")
                    text = str(data.get("text", "")).strip()
                    source = str(data.get("source", "ui")).strip() or "ui"
                    if not text:
                        return self._send_error(400, ErrorType.CLIENT_ERROR, "missing_text", "missing_text")
                    reply_text = self.conversation_core.reply(text, source=source)
                    return self._send_success(200, {"reply_text": reply_text})

                if self.path == "/autonomy/override":
                    if self.autonomy_policy_engine is None:
                        return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "autonomy_policy_engine_unavailable", "autonomy_policy_engine_unavailable")
                    requested_mode = str(data.get("mode", "")).strip().lower()
                    if requested_mode not in {"manual", "partial", "disabled"}:
                        return self._send_error(400, ErrorType.CLIENT_ERROR, "invalid_mode", "invalid_mode")
                    effective_mode = self.autonomy_policy_engine.set_runtime_mode_override(requested_mode)
                    return self._send_success(200, {"mode": effective_mode, "status": self.autonomy_policy_engine.status()})

                if self.path == "/voice/tts":
                    text = str(data.get("text", "")).strip()
                    if not text:
                        return self._send_error(400, ErrorType.CLIENT_ERROR, "missing_text", "missing_text")

                    api_key = os.getenv("OPENAI_API_KEY", "").strip()
                    if not api_key or OpenAI is None:
                        return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "gpt_not_configured", "gpt_not_configured")

                    client = OpenAI()
                    response = client.audio.speech.create(
                        model="gpt-4o-mini-tts",
                        voice="sol",
                        input=text,
                    )
                    return self._send_bytes(200, response.read(), "audio/mpeg")

                if launch_sale_id is not None:
                    if self.product_launch_store is None:
                        return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "product_launch_store_unavailable", "product_launch_store_unavailable")
                    launch_id = str(launch_sale_id).strip()
                    if not launch_id:
                        return self._send_error(400, ErrorType.CLIENT_ERROR, "missing_id", "missing_id")
                    amount = float(data.get("amount", 0))
                    updated = self.product_launch_store.add_sale(launch_id, amount)
                    return self._send(200, updated)

                if launch_status_id is not None:
                    if self.product_launch_store is None:
                        return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "product_launch_store_unavailable", "product_launch_store_unavailable")
                    launch_id = str(launch_status_id).strip()
                    if not launch_id:
                        return self._send_error(400, ErrorType.CLIENT_ERROR, "missing_id", "missing_id")
                    status = str(data.get("status", "")).strip()
                    updated = self.product_launch_store.transition_status(launch_id, status)
                    return self._send(200, updated)

                if launch_link_gumroad_id is not None:
                    if self.control is None:
                        return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "control_unavailable", "control_unavailable")
                    launch_id = str(launch_link_gumroad_id).strip()
                    if not launch_id:
                        return self._send_error(400, ErrorType.CLIENT_ERROR, "missing_id", "missing_id")
                    gumroad_product_id = str(data.get("gumroad_product_id", "")).strip()
                    if not gumroad_product_id:
                        return self._send_error(400, ErrorType.CLIENT_ERROR, "missing_gumroad_product_id", "missing_gumroad_product_id")
                    updated = self.control.link_launch_gumroad(launch_id, gumroad_product_id)
                    return self._send(200, updated)

                if self.path == "/gumroad/sync_sales":
                    if self.product_launch_store is None:
                        return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "product_launch_store_unavailable", "product_launch_store_unavailable")
                    access_token = load_token()
                    if not access_token:
                        return self._send_error(400, ErrorType.CLIENT_ERROR, "gumroad_not_connected", "Gumroad not connected. Visit /gumroad/auth first.")
                    gumroad_client = GumroadClient(access_token)
                    service = GumroadSyncService(
                        self.product_launch_store,
                        gumroad_client,
                        self.revenue_attribution_store,
                    )
                    ok, summary = self._run_with_timeout("gumroad_sync", service.sync_sales)
                    if not ok:
                        return self._send_timeout_error("gumroad_sync")
                    return self._send(200, summary)

                if self.path == "/creator/offers/generate":
                    if self.server.storage is None:
                        return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "storage_unavailable", "storage_unavailable")
                    suggestion_id = str(data.get("suggestion_id", "")).strip()
                    if not suggestion_id:
                        return self._send_error(400, ErrorType.CLIENT_ERROR, "missing_suggestion_id", "missing_suggestion_id")
                    service = CreatorOfferService(storage=self.server.storage)
                    try:
                        draft = service.generate_offer_draft(suggestion_id=suggestion_id)
                    except ValueError as exc:
                        if str(exc) == "suggestion_not_found":
                            return self._send_error(404, ErrorType.NOT_FOUND, "suggestion_not_found", "suggestion_not_found")
                        raise
                    return self._send_success(200, draft)

                if self.path == "/creator/launches/register":
                    if self.server.storage is None:
                        return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "storage_unavailable", "storage_unavailable")
                    offer_id = str(data.get("offer_id", "")).strip()
                    if not offer_id:
                        return self._send_error(400, ErrorType.CLIENT_ERROR, "missing_offer_id", "missing_offer_id")
                    try:
                        price = float(data.get("price"))
                    except (TypeError, ValueError):
                        return self._send_error(400, ErrorType.CLIENT_ERROR, "invalid_price", "invalid_price")
                    notes = str(data.get("notes", ""))
                    tracker = CreatorLaunchTracker(storage=self.server.storage)
                    try:
                        launch = tracker.register_launch(offer_id=offer_id, price=price, notes=notes)
                    except ValueError as exc:
                        if str(exc) == "offer_not_found":
                            return self._send_error(404, ErrorType.NOT_FOUND, "offer_not_found", "offer_not_found")
                        raise
                    return self._send_success(200, launch)

                if self.path.startswith("/creator/launches/") and self.path.endswith("/sale"):
                    if self.server.storage is None:
                        return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "storage_unavailable", "storage_unavailable")
                    launch_id = self.path[len("/creator/launches/") : -len("/sale")].strip("/")
                    if not launch_id:
                        return self._send_error(400, ErrorType.CLIENT_ERROR, "missing_launch_id", "missing_launch_id")
                    try:
                        quantity = int(data.get("quantity", 1))
                    except (TypeError, ValueError):
                        return self._send_error(400, ErrorType.CLIENT_ERROR, "invalid_quantity", "invalid_quantity")
                    tracker = CreatorLaunchTracker(storage=self.server.storage)
                    try:
                        launch = tracker.record_sale(launch_id=launch_id, quantity=quantity)
                    except ValueError as exc:
                        if str(exc) == "launch_not_found":
                            return self._send_error(404, ErrorType.NOT_FOUND, "launch_not_found", "launch_not_found")
                        if str(exc) == "invalid_quantity":
                            return self._send_error(400, ErrorType.CLIENT_ERROR, "invalid_quantity", "invalid_quantity")
                        raise
                    return self._send_success(200, launch)

                if self.path == "/creator/demand/validate":
                    if self.server.storage is None:
                        return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "storage_unavailable", "storage_unavailable")
                    validator = CreatorDemandValidator(storage=self.server.storage)
                    items = validator.validate()
                    return self._send_success(200, {"items": items})

                if self.path == "/reddit/config":
                    editable_fields = {
                        "subreddits",
                        "pain_threshold",
                        "pain_keywords",
                        "commercial_keywords",
                        "enable_engagement_boost",
                        "source",
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
                    if "source" in payload:
                        source_value = str(payload["source"]).strip().lower()
                        if source_value not in {"reddit_public", "openclaw"}:
                            return self._send_error(
                                400,
                                ErrorType.CLIENT_ERROR,
                                "invalid_source",
                                "source must be one of: reddit_public, openclaw",
                            )
                        payload["source"] = source_value
                    updated = update_config(payload)
                    return self._send_success(200, updated)

                if self.path == "/reddit/run_scan":
                    if self.control is None:
                        return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "control_unavailable", "control_unavailable")
                    ok, result = self._run_with_timeout("reddit_scan", self.control.run_reddit_scan)
                    if not ok:
                        return self._send_timeout_error("reddit_scan")
                    return self._send_success(200, result)

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
                        return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "strategy_action_execution_layer_unavailable", "strategy_action_execution_layer_unavailable")
                    action_id = str(strategy_execute_id).strip()
                    if not action_id:
                        return self._send_error(400, ErrorType.CLIENT_ERROR, "missing_id", "missing_id")
                    updated = self.strategy_action_execution_layer.execute_action(action_id)
                    return self._send(200, updated)

                if strategy_reject_id is not None:
                    if self.strategy_action_execution_layer is None:
                        return self._send_error(503, ErrorType.DEPENDENCY_ERROR, "strategy_action_execution_layer_unavailable", "strategy_action_execution_layer_unavailable")
                    action_id = str(strategy_reject_id).strip()
                    if not action_id:
                        return self._send_error(400, ErrorType.CLIENT_ERROR, "missing_id", "missing_id")
                    updated = self.strategy_action_execution_layer.reject_action(action_id)
                    return self._send(200, updated)

                event_id = str(data.get("id", "")).strip()
                if not event_id:
                    return self._send_error(400, ErrorType.CLIENT_ERROR, "missing_id", "missing_id")

                if self.path == "/opportunities/evaluate":
                    self.bus.push(
                        Event(
                            type="EvaluateOpportunityById",
                            payload={"id": event_id, "request_id": self._ensure_request_id()},
                            source="http",
                            request_id=self._ensure_request_id(),
                            trace_id=self._ensure_trace_id(),
                        )
                    )
                    return self._send_success(200, {"status": "ok"})

                if self.path == "/opportunities/dismiss":
                    self.bus.push(
                        Event(
                            type="OpportunityDismissed",
                            payload={"id": event_id, "request_id": self._ensure_request_id()},
                            source="http",
                            request_id=self._ensure_request_id(),
                            trace_id=self._ensure_trace_id(),
                        )
                    )
                    return self._send_success(200, {"status": "ok"})

            return self._send_error(404, ErrorType.NOT_FOUND, "not_found", "not_found")
        except Exception as e:
            return self._handle_exception(e)

    def do_PATCH(self):
        try:
            self._ensure_request_id()
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"

            try:
                data = json.loads(raw)
            except Exception as e:
                return self._send_error(400, ErrorType.CLIENT_ERROR, "invalid_json", str(e))

            with self.server.mutation_lock:
                self.server.update_metrics(last_mutation_at=time.time())
                patch_response = self.reddit_router.handle_patch(self.path, data)
                if patch_response is None:
                    return self._send_error(404, ErrorType.NOT_FOUND, "not_found", "not_found")

                code, body = patch_response
                return self._send(code, body)
        except Exception as e:
            return self._handle_exception(e)


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
    conversation_core=None,
    revenue_attribution_store: RevenueAttributionStore | None = None,
    subreddit_performance_store: SubredditPerformanceStore | None = None,
    storage=None,
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
        conversation_core=conversation_core,
        revenue_attribution_store=revenue_attribution_store,
        subreddit_performance_store=subreddit_performance_store,
        storage=storage,
        reddit_router=RedditIntelligenceRouter(),
    )
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server
