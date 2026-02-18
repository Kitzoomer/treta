import json
import threading
import time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from core.events import Event
from core.bus import event_bus
from core.integrations.gumroad_client import GumroadAPIError, GumroadClient
from core.gumroad_oauth import exchange_code_for_token, get_auth_url, load_token, save_token
from core.services.gumroad_sync_service import GumroadSyncService
from core.system_integrity import compute_system_integrity
from core.reddit_intelligence.router import RedditIntelligenceRouter
from core.reddit_public.config import get_config, update_config


class Handler(BaseHTTPRequestHandler):
    state_machine = None
    opportunity_store = None
    product_proposal_store = None
    product_plan_store = None
    product_launch_store = None
    performance_engine = None
    control = None
    strategy_engine = None
    strategy_decision_engine = None
    strategy_action_execution_layer = None
    autonomy_policy_engine = None
    daily_loop_engine = None
    memory_store = None
    reddit_router = None
    ui_dir = Path(__file__).resolve().parent.parent / "ui"

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

        try:
            if self.reddit_router is None:
                self.reddit_router = RedditIntelligenceRouter()
            reddit_response = self.reddit_router.handle_get(parsed.path, parse_qs(parsed.query))
            if reddit_response is not None:
                code, body = reddit_response
                return self._send(code, body)
        except ValueError:
            return self._send(400, {"ok": False, "error": "invalid_limit"})

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
                return self._send(404, {"error": "not_found"})
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

        if parsed.path == "/system/integrity":
            if self.product_proposal_store is None:
                return self._send(503, {"error": "product_proposal_store_unavailable"})
            if self.product_plan_store is None:
                return self._send(503, {"error": "product_plan_store_unavailable"})
            if self.product_launch_store is None:
                return self._send(503, {"error": "product_launch_store_unavailable"})

            try:
                proposals = self.product_proposal_store.list()
            except Exception:
                proposals = []

            try:
                plans = self.product_plan_store.list(limit=10000)
            except TypeError:
                try:
                    plans = self.product_plan_store.list()
                except Exception:
                    plans = []
            except Exception:
                plans = []

            try:
                launches = self.product_launch_store.list()
            except Exception:
                launches = []

            report = compute_system_integrity(
                proposals=proposals,
                plans=plans,
                launches=launches,
            )
            return self._send(200, report)

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
                return self._send(502, {"ok": False, "error": f"oauth_exchange_failed: {e}"})
            return self._send(200, {"status": "connected"})

        if parsed.path == "/reddit/config":
            return self._send(200, get_config())

        if parsed.path == "/reddit/last_scan":
            if self.control is None:
                return self._send(503, {"ok": False, "error": "control_unavailable"})
            return self._send(
                200,
                self.control.get_last_reddit_scan() or {"message": "No scan executed yet."},
            )

        if parsed.path == "/reddit/posts":
            posts = self._load_reddit_posts()
            return self._send(200, {"items": list(reversed(posts))})

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
            return self._send(404, {"ok": False, "error": "not_found"})

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"

        try:
            data = json.loads(raw)

            if self.reddit_router is None:
                self.reddit_router = RedditIntelligenceRouter()
            reddit_post_response = self.reddit_router.handle_post(self.path, data)
            if reddit_post_response is not None:
                code, body = reddit_post_response
                return self._send(code, body)

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
                return self._send(200, updated)

            if self.path == "/reddit/run_scan":
                if self.control is None:
                    return self._send(503, {"ok": False, "error": "control_unavailable"})
                return self._send(200, self.control.run_reddit_public_scan())

            if self.path == "/reddit/mark_posted":
                proposal_id = str(data.get("proposal_id", "")).strip()
                subreddit = str(data.get("subreddit", "")).strip()
                post_url = str(data.get("post_url", "")).strip()
                if not proposal_id:
                    return self._send(400, {"ok": False, "error": "missing_proposal_id"})
                if not subreddit:
                    return self._send(400, {"ok": False, "error": "missing_subreddit"})
                if not post_url:
                    return self._send(400, {"ok": False, "error": "missing_post_url"})

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
                return self._send(200, {"ok": True, "item": entry})

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
        except GumroadAPIError as e:
            return self._send(502, {"ok": False, "error": str(e)})
        except ValueError as e:
            if "Missing Gumroad credentials" in str(e):
                return self._send(400, {"ok": False, "error": str(e)})
            return self._send(400, {"ok": False, "error": str(e)})
        except Exception as e:
            return self._send(400, {"ok": False, "error": str(e)})

    def do_PATCH(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"

        try:
            data = json.loads(raw)
        except Exception as e:
            return self._send(400, {"ok": False, "error": str(e)})

        if self.reddit_router is None:
            self.reddit_router = RedditIntelligenceRouter()
        patch_response = self.reddit_router.handle_patch(self.path, data)
        if patch_response is None:
            return self._send(404, {"ok": False, "error": "not_found"})

        code, body = patch_response
        return self._send(code, body)


def start_http_server(
    host="0.0.0.0",
    port=7777,
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
    Handler.state_machine = state_machine
    Handler.opportunity_store = opportunity_store
    Handler.product_proposal_store = product_proposal_store
    Handler.product_plan_store = product_plan_store
    Handler.product_launch_store = product_launch_store
    Handler.performance_engine = performance_engine
    Handler.control = control
    Handler.strategy_engine = strategy_engine
    Handler.strategy_decision_engine = strategy_decision_engine
    Handler.strategy_action_execution_layer = strategy_action_execution_layer
    Handler.autonomy_policy_engine = autonomy_policy_engine
    Handler.daily_loop_engine = daily_loop_engine
    Handler.memory_store = memory_store
    Handler.reddit_router = RedditIntelligenceRouter()
    server = HTTPServer((host, port), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server
