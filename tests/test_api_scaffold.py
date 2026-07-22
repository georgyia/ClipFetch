from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from clipfetch.api.app import create_app  # noqa: E402
from clipfetch.api.errors import ApiException  # noqa: E402


def _client() -> TestClient:
    app = create_app()

    @app.get("/api/v1/_boom")
    def _boom() -> dict[str, str]:
        raise ApiException(418, "teapot", "no coffee here", recovery_actions=("brew_tea",))

    @app.get("/api/v1/_validate")
    def _validate(n: int) -> dict[str, int]:
        return {"n": n}

    @app.get("/api/v1/_crash")
    def _crash() -> dict[str, str]:
        raise ValueError("secret internal detail")

    return TestClient(app, raise_server_exceptions=False)


def test_health_endpoints():
    client = _client()
    live = client.get("/health/live")
    assert live.status_code == 200
    assert live.json() == {"status": "ok"}
    assert client.get("/health/ready").status_code == 200


def test_request_id_is_generated_and_echoed():
    client = _client()
    generated = client.get("/health/live")
    assert generated.headers["X-Request-ID"]
    assert generated.headers["X-Content-Type-Options"] == "nosniff"

    echoed = client.get("/health/live", headers={"X-Request-ID": "req_test_123"})
    assert echoed.headers["X-Request-ID"] == "req_test_123"


def test_capabilities_matrix_shape():
    body = _client().get("/api/v1/capabilities").json()
    caps = body["capabilities"]
    assert set(caps) == {
        "semantic_search",
        "transcription",
        "duplicate_analysis",
        "cookie_import",
    }
    for entry in caps.values():
        assert isinstance(entry["available"], bool)


def test_api_exception_renders_envelope():
    resp = _client().get("/api/v1/_boom")
    assert resp.status_code == 418
    error = resp.json()["error"]
    assert error["code"] == "teapot"
    assert error["message"] == "no coffee here"
    assert error["request_id"]
    assert error["details"]["recovery_actions"] == ["brew_tea"]


def test_validation_error_is_envelope():
    resp = _client().get("/api/v1/_validate", params={"n": "not-an-int"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_request"


def test_not_found_is_envelope():
    resp = _client().get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_unexpected_error_does_not_leak():
    resp = _client().get("/api/v1/_crash")
    assert resp.status_code == 500
    error = resp.json()["error"]
    assert error["code"] == "internal_error"
    assert "secret internal detail" not in resp.text
    assert "ValueError" not in resp.text
