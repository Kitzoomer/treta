import os

import pytest

import core.ipc_http as ipc_http


os.environ.setdefault("TRETA_DEV_MODE", "1")
os.environ.setdefault("TRETA_REQUIRE_TOKEN", "0")


@pytest.fixture(autouse=True)
def _enforce_auth_defaults_for_http_auth_tests(request, monkeypatch):
    if request.module.__name__.endswith("test_http_auth"):
        monkeypatch.setattr(ipc_http, "TRETA_DEV_MODE", False)
        monkeypatch.setattr(ipc_http, "TRETA_REQUIRE_TOKEN", True)
