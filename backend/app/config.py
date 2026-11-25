import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


def database_url(name: str, default: str) -> str:
    url = os.getenv(name, default)
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return url.replace(prefix, "postgresql+psycopg://", 1)
    return url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY") or "dev-only-secret-key-change-me-before-deploying"
    SQLALCHEMY_DATABASE_URI = database_url(
        "DATABASE_URL", "postgresql+psycopg://stockpilot:stockpilot@localhost:5432/stockpilot_dev"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ORIGINS = [
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    ]

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY") or "dev-only-jwt-key-change-me-before-deploying"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)

    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")

    MAIL_SERVER = os.getenv("MAIL_SERVER", "")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_FROM = os.getenv("MAIL_FROM", "StockPilot <no-reply@stockpilot.local>")
    BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")

    EMAIL_VERIFICATION_REQUIRED = os.getenv("EMAIL_VERIFICATION_REQUIRED", "true").lower() == "true"
    LOGIN_CODE_REQUIRED = os.getenv("LOGIN_CODE_REQUIRED", "true").lower() == "true"
    LOGIN_CODE_EXEMPT_DOMAINS = [
        d.strip().lower()
        for d in os.getenv("LOGIN_CODE_EXEMPT_DOMAINS", "").split(",")
        if d.strip()
    ]

    MAX_UPLOAD_BYTES = 5 * 1024 * 1024
    IMAGE_MAX_SIDE = 1200

    BCRYPT_LOG_ROUNDS = 12

    MAX_CONTENT_LENGTH = 1024 * 1024
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    LOGIN_RATE_LIMIT = os.getenv("LOGIN_RATE_LIMIT", "10 per minute")
    BEHIND_PROXY = False

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
        if not os.getenv("FRONTEND_URL"):
            raise RuntimeError("Set FRONTEND_URL so emailed links point at the live app.")


def config_for_environment():
    return ProductionConfig if os.getenv("APP_ENV") == "production" else Config


class TestConfig(Config):
    TESTING = True
    RATELIMIT_ENABLED = False
    SQLALCHEMY_DATABASE_URI = database_url(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://stockpilot:stockpilot@localhost:5432/stockpilot_test",
    )
    BCRYPT_LOG_ROUNDS = 4
    EMAIL_VERIFICATION_REQUIRED = False
    LOGIN_CODE_REQUIRED = False
    LOGIN_CODE_EXEMPT_DOMAINS = []
