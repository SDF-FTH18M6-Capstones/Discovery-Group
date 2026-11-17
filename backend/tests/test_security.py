import pytest

from app import create_app
from app.config import ProductionConfig, TestConfig

FRONTEND = "http://localhost:5173"


def test_api_responses_carry_security_headers(client):
    response = client.get("/api/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert (
        response.headers["Content-Security-Policy"] == "default-src 'none'; frame-ancestors 'none'"
    )


def test_a_body_over_one_megabyte_is_refused_as_json(client):
    response = client.post(
        "/api/auth/login", data="x" * (1024 * 1024 + 1), content_type="application/json"
    )

    assert response.status_code == 413
    assert response.json["error"]["code"] == 413


def test_html_is_stored_and_returned_as_plain_text(admin):
    created = admin.post("/api/categories/", json={"name": "<script>alert(1)</script>"})

    assert created.status_code == 201
    assert created.headers["Content-Type"].startswith("application/json")
    assert created.json["name"] == "<script>alert(1)</script>"  # data, never run by the API


def test_text_is_trimmed_and_spaces_alone_count_as_empty(admin):
    assert admin.post("/api/categories/", json={"name": "  Snacks  "}).json["name"] == "Snacks"
    blank = admin.post("/api/categories/", json={"name": "   "})
    assert blank.status_code == 422
    assert "name" in blank.json["error"]["details"]


class LimitedConfig(TestConfig):
    RATELIMIT_ENABLED = True
    LOGIN_RATE_LIMIT = "3 per minute"


def test_sign_in_is_rate_limited_per_address(_schema):
    client = create_app(LimitedConfig).test_client()
    body = {"email": "nobody@test.com", "password": "Wrong1234"}

    answers = [client.post("/api/auth/login", json=body).status_code for _ in range(4)]

    assert answers == [401, 401, 401, 429]
    blocked = client.post("/api/auth/login", json=body)
    assert blocked.json["error"]["message"] == "Too many attempts. Wait a minute and try again."


def test_cors_allows_the_frontend_only(client):
    allowed = client.options(
        "/api/products/",
        headers={"Origin": FRONTEND, "Access-Control-Request-Method": "GET"},
    )
    other = client.options(
        "/api/products/",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )

    assert allowed.headers.get("Access-Control-Allow-Origin") == FRONTEND
    assert "Access-Control-Allow-Origin" not in other.headers


def test_production_refuses_development_keys(monkeypatch):
    monkeypatch.setattr(
        ProductionConfig, "SECRET_KEY", "dev-only-secret-key-change-me-before-deploying"
    )

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(ProductionConfig)


def test_production_needs_database_and_frontend_addresses(monkeypatch):
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "x" * 64)
    monkeypatch.setattr(ProductionConfig, "JWT_SECRET_KEY", "y" * 64)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        create_app(ProductionConfig)

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db/x")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        create_app(ProductionConfig)


def test_production_sends_hsts(monkeypatch):
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "x" * 64)
    monkeypatch.setattr(ProductionConfig, "JWT_SECRET_KEY", "y" * 64)
    monkeypatch.setattr(
        ProductionConfig, "SQLALCHEMY_DATABASE_URI", TestConfig.SQLALCHEMY_DATABASE_URI
    )
    monkeypatch.setenv("DATABASE_URL", "set")
    monkeypatch.setenv("CORS_ORIGINS", FRONTEND)

    response = create_app(ProductionConfig).test_client().get("/api/health")

    assert response.headers["Strict-Transport-Security"].startswith("max-age=")