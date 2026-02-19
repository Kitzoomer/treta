import json
import threading
import time
import unittest
from urllib.request import Request, urlopen

from core.ipc_http import start_http_server


class _RaceyLaunchStore:
    def __init__(self):
        self._item = {"id": "l1", "sales": 0.0}

    def add_sale(self, launch_id: str, amount: float):
        current = float(self._item["sales"])
        time.sleep(0.05)
        self._item["sales"] = current + amount
        return dict(self._item)


class HttpMutationLockTest(unittest.TestCase):
    def test_parallel_mutations_are_atomic(self):
        store = _RaceyLaunchStore()
        server = start_http_server(host="127.0.0.1", port=0, product_launch_store=store)
        try:
            barrier = threading.Barrier(2)
            responses = []

            def post_sale(amount: float):
                req = Request(
                    f"http://127.0.0.1:{server.server_port}/product_launches/l1/add_sale",
                    data=json.dumps({"amount": amount}).encode("utf-8"),
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                barrier.wait(timeout=2)
                with urlopen(req, timeout=2) as response:
                    responses.append(json.loads(response.read().decode("utf-8")))

            threads = [
                threading.Thread(target=post_sale, args=(1.0,)),
                threading.Thread(target=post_sale, args=(2.0,)),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=3)

            self.assertEqual(len(responses), 2)
            self.assertEqual(store._item["sales"], 3.0)
        finally:
            server.shutdown()
            server.server_close()

    def test_mutation_endpoint_sets_request_id_header(self):
        store = _RaceyLaunchStore()
        server = start_http_server(host="127.0.0.1", port=0, product_launch_store=store)
        try:
            req = Request(
                f"http://127.0.0.1:{server.server_port}/product_launches/l1/add_sale",
                data=json.dumps({"amount": 1.0}).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlopen(req, timeout=2) as response:
                self.assertTrue(response.headers.get("X-Request-Id"))
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
