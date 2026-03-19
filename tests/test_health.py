from __future__ import annotations

import json
import os
import subprocess
import time
from urllib.request import urlopen


def test_health_endpoint() -> None:
    env = dict(os.environ)
    env["TRETA_DEV_MODE"] = "1"
    proc = subprocess.Popen(["python", "main.py"], env=env)
    try:
        deadline = time.time() + 10
        payload = None
        while time.time() < deadline:
            try:
                with urlopen("http://127.0.0.1:7777/health", timeout=1) as response:
                    assert response.status == 200
                    payload = json.loads(response.read().decode("utf-8"))
                    break
            except Exception:
                time.sleep(0.2)

        assert payload is not None, "health endpoint did not become available within 10s"
        assert payload["data"]["status"] == "ok"
    finally:
        proc.terminate()
        proc.wait(timeout=5)
