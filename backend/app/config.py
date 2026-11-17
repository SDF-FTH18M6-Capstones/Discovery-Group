"""Settings come from environment variables (.env file locally)."""

import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


def database_url(name: str, default: str) -> str:
    url = os.getenv(name, default)
    # Hosting platforms often give postgres://, SQLAlchemy needs postgresql+psycopg://
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return url.replace(prefix, "postgresql+psycopg://", 1)
    return url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-key-change-me-before-deploying")
    SQLALCHEMY_DATABASE_URI = database_url(
        "DATABASE_URL", "postgresql+psycopg://stockpilot:stockpilot@localhost:5432/stockpilot_dev"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ORIGINS = [
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    ]

    # Sign-in (JWT)
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-jwt-key-change-me-before-deploying")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)

    BCRYPT_LOG_ROUNDS = 12  # how slow (and so how hard to crack) each password hash is

    # Hardening
    MAX_CONTENT_LENGTH = 1024 * 1024  # bodies over 1 MB are refused with 413
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    # Sign-in and sign-up attempts per IP address
    LOGIN_RATE_LIMIT = os.getenv("LOGIN_RATE_LIMIT", "10 per minute")
    BEHIND_PROXY = False  # True on hosts like Render, so the real client IP is used

    # Swagger / OpenAPI (flask-smorest). The Authorize button takes the access token.
    API_TITLE = "StockPilot API"
    API_VERSION = "v1"
    OPENAPI_VERSION = "3.0.3"
    OPENAPI_URL_PREFIX = "/api"
    OPENAPI_SWAGGER_UI_PATH = "/docs"
    OPENAPI_SWAGGER_UI_URL = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"
    API_SPEC_OPTIONS = {
        "components": {
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
            }
        },
        "security": [{"bearerAuth": []}],
    }


DEV_KEYS = {
    "dev-only-secret-key-change-me-before-deploying",
    "dev-only-jwt-key-change-me-before-deploying",
}


class ProductionConfig(Config):
    """Used when APP_ENV=production. Refuses to start with the development keys."""

    DEBUG = False
    BEHIND_PROXY = True
    PREFERRED_URL_SCHEME = "https"

    @classmethod
    def check(cls):
        if cls.SECRET_KEY in DEV_KEYS or cls.JWT_SECRET_KEY in DEV_KEYS:
            raise RuntimeError("Set SECRET_KEY and JWT_SECRET_KEY before running in production.")
        if not os.getenv("DATABASE_URL"):
            raise RuntimeError("Set DATABASE_URL before running in production.")
        if not os.getenv("CORS_ORIGINS"):
            raise RuntimeError("Set CORS_ORIGINS to the frontend's address in production.")


def config_for_environment():
    return ProductionConfig if os.getenv("APP_ENV") == "production" else Config


class TestConfig(Config):
    TESTING = True
    RATELIMIT_ENABLED = False  # turned on only in the test that checks it
    SQLALCHEMY_DATABASE_URI = database_url(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://stockpilot:stockpilot@localhost:5432/stockpilot_test",
    )
    BCRYPT_LOG_ROUNDS = 4  # fast hashing so the tests run quickly