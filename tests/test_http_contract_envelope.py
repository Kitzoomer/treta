import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from core.control import Control
from core.errors import DependencyError, InvariantViolationError, NotFoundError
from core.ipc_http import start_http_server


class _OkStore:
    def __init__(self, items):
        self._items = items

    def list(self, *args, **kwargs):
        return self._items


class _BoomStore:
    def list(self, *args, **kwargs):
        raise RuntimeError("boom")


class _CrashControl(Control):
    def consume(self, _event):
        raise RuntimeError("unexpected boom")




class _InvariantCrashControl(Control):
    def consume(self, _event):
        raise InvariantViolationError("invariant broken")


class _NotFoundCrashControl(Control):
    def consume(self, _event):
        raise NotFoundError("proposal_not_found")


class _DependencyCrashControl(Control):
    def consume(self, _event):
        raise DependencyError("storage unavailable")


class _ValidationCrashControl(Control):
    def consume(self, _event):
        raise ValueError("invalid input")

class HttpContractEnvelopeTest(unittest.TestCase):
    def test_success_response_contains_ok_true_and_data(self):
        server = start_http_server(
            host="127.0.0.1",
            port=0,
            product_proposal_store=_OkStore([]),
            product_plan_store=_OkStore([]),
            product_launch_store=_OkStore([]),
        )
        try:
            with urlopen(f"http://127.0.0.1:{server.server_port}/system/integrity", timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))

            self.assertTrue(payload["ok"])
            self.assertIn("data", payload)
        finally:
            server.shutdown()
            server.server_close()

    def test_concurrent_get_requests_return_200(self):
        server = start_http_server(host="127.0.0.1", port=0)
        try:
            statuses = [None, None]
            errors = []
            start = threading.Barrier(2)

            def fire_get(index):
                try:
                    start.wait(timeout=2)
                    with urlopen(f"http://127.0.0.1:{server.server_port}/events", timeout=2) as response:
                        statuses[index] = response.status
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)

            threads = [threading.Thread(target=fire_get, args=(idx,)) for idx in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=3)

            self.assertEqual(errors, [])
            self.assertEqual(statuses, [200, 200])
        finally:
            server.shutdown()
            server.server_close()

    def test_missing_entity_returns_not_found_type(self):
        server = start_http_server(host="127.0.0.1", port=0, control=Control())
        try:
            req = Request(
                f"http://127.0.0.1:{server.server_port}/product_proposals/abc/approve",
                data=b"{}",
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with self.assertRaises(HTTPError) as ctx:
                urlopen(req, timeout=2)

            self.assertEqual(ctx.exception.code, 404)
            payload = json.loads(ctx.exception.read().decode("utf-8"))
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error"]["type"], "not_found")
        finally:
            server.shutdown()
            server.server_close()

    def test_unexpected_exception_returns_500_server_error(self):
        server = start_http_server(host="127.0.0.1", port=0, control=_CrashControl())
        try:
            req = Request(
                f"http://127.0.0.1:{server.server_port}/product_proposals/abc/approve",
                data=b"{}",
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with self.assertRaises(HTTPError) as ctx:
                urlopen(req, timeout=2)

            self.assertEqual(ctx.exception.code, 500)
            payload = json.loads(ctx.exception.read().decode("utf-8"))
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error"]["type"], "server_error")
        finally:
            server.shutdown()
            server.server_close()

    def test_store_failure_returns_503_dependency_error(self):
        server = start_http_server(
            host="127.0.0.1",
            port=0,
            product_proposal_store=_BoomStore(),
            product_plan_store=_BoomStore(),
            product_launch_store=_BoomStore(),
        )
        try:
            with self.assertRaises(HTTPError) as ctx:
                urlopen(f"http://127.0.0.1:{server.server_port}/system/integrity", timeout=2)

            self.assertEqual(ctx.exception.code, 503)
            payload = json.loads(ctx.exception.read().decode("utf-8"))
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error"]["type"], "dependency_error")
        finally:
            server.shutdown()
            server.server_close()

    def test_invariant_exception_is_classified_as_invariant_violation(self):
        server = start_http_server(host="127.0.0.1", port=0, control=_InvariantCrashControl())
        try:
            req = Request(
                f"http://127.0.0.1:{server.server_port}/product_proposals/abc/approve",
                data=b"{}",
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with self.assertRaises(HTTPError) as ctx:
                urlopen(req, timeout=2)

            self.assertEqual(ctx.exception.code, 500)
            payload = json.loads(ctx.exception.read().decode("utf-8"))
            self.assertEqual(payload["error"]["type"], "invariant_violation")
        finally:
            server.shutdown()
            server.server_close()

    def test_not_found_exception_is_classified_as_not_found(self):
        server = start_http_server(host="127.0.0.1", port=0, control=_NotFoundCrashControl())
        try:
            req = Request(
                f"http://127.0.0.1:{server.server_port}/product_proposals/abc/approve",
                data=b"{}",
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with self.assertRaises(HTTPError) as ctx:
                urlopen(req, timeout=2)

            self.assertEqual(ctx.exception.code, 404)
            payload = json.loads(ctx.exception.read().decode("utf-8"))
            self.assertEqual(payload["error"]["type"], "not_found")
        finally:
            server.shutdown()
            server.server_close()

    def test_dependency_exception_is_classified_as_dependency_error(self):
        server = start_http_server(host="127.0.0.1", port=0, control=_DependencyCrashControl())
        try:
            req = Request(
                f"http://127.0.0.1:{server.server_port}/product_proposals/abc/approve",
                data=b"{}",
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with self.assertRaises(HTTPError) as ctx:
                urlopen(req, timeout=2)

            self.assertEqual(ctx.exception.code, 503)
            payload = json.loads(ctx.exception.read().decode("utf-8"))
            self.assertEqual(payload["error"]["type"], "dependency_error")
        finally:
            server.shutdown()
            server.server_close()

    def test_validation_exception_is_classified_as_client_error(self):
        server = start_http_server(host="127.0.0.1", port=0, control=_ValidationCrashControl())
        try:
            req = Request(
                f"http://127.0.0.1:{server.server_port}/product_proposals/abc/approve",
                data=b"{}",
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with self.assertRaises(HTTPError) as ctx:
                urlopen(req, timeout=2)

            self.assertEqual(ctx.exception.code, 400)
            payload = json.loads(ctx.exception.read().decode("utf-8"))
            self.assertEqual(payload["error"]["type"], "client_error")
        finally:
            server.shutdown()
            server.server_close()

    def test_representative_endpoints_use_standard_envelope(self):
        server = start_http_server(host="127.0.0.1", port=0)
        try:
            # system
            with self.assertRaises(HTTPError) as state_err:
                urlopen(f"http://127.0.0.1:{server.server_port}/state", timeout=2)
            self.assertEqual(state_err.exception.code, 503)
            state_payload = json.loads(state_err.exception.read().decode("utf-8"))
            self.assertFalse(state_payload["ok"])
            self.assertEqual(state_payload["error"]["type"], "dependency_error")

            # proposals
            with self.assertRaises(HTTPError) as proposals_err:
                urlopen(f"http://127.0.0.1:{server.server_port}/product_proposals", timeout=2)
            self.assertEqual(proposals_err.exception.code, 503)
            proposals_payload = json.loads(proposals_err.exception.read().decode("utf-8"))
            self.assertEqual(proposals_payload["error"]["type"], "dependency_error")

            # plans
            with self.assertRaises(HTTPError) as plans_err:
                urlopen(f"http://127.0.0.1:{server.server_port}/product_plans", timeout=2)
            self.assertEqual(plans_err.exception.code, 503)

            # launches
            with self.assertRaises(HTTPError) as launches_err:
                urlopen(f"http://127.0.0.1:{server.server_port}/product_launches", timeout=2)
            self.assertEqual(launches_err.exception.code, 503)

            # strategy
            with self.assertRaises(HTTPError) as strategy_err:
                urlopen(f"http://127.0.0.1:{server.server_port}/strategy/recommendations", timeout=2)
            self.assertEqual(strategy_err.exception.code, 503)

            # reddit
            with urlopen(f"http://127.0.0.1:{server.server_port}/reddit/config", timeout=2) as response:
                reddit_payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(reddit_payload["ok"])

            # gumroad
            with self.assertRaises(HTTPError) as gumroad_err:
                urlopen(f"http://127.0.0.1:{server.server_port}/gumroad/callback", timeout=2)
            self.assertEqual(gumroad_err.exception.code, 400)
            gumroad_payload = json.loads(gumroad_err.exception.read().decode("utf-8"))
            self.assertEqual(gumroad_payload["error"]["type"], "client_error")

            # memory
            with self.assertRaises(HTTPError) as memory_err:
                urlopen(f"http://127.0.0.1:{server.server_port}/memory", timeout=2)
            self.assertEqual(memory_err.exception.code, 503)

            # not found matrix
            with self.assertRaises(HTTPError) as not_found_err:
                urlopen(f"http://127.0.0.1:{server.server_port}/does-not-exist", timeout=2)
            self.assertEqual(not_found_err.exception.code, 404)
            not_found_payload = json.loads(not_found_err.exception.read().decode("utf-8"))
            self.assertEqual(not_found_payload["error"]["type"], "not_found")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
