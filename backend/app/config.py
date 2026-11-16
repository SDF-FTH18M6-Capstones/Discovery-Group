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


def flag(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in ("1", "true", "yes")


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

    # 2-step sign-in code
    OTP_MINUTES = 5
    OTP_MAX_ATTEMPTS = 5
    # Local development only: also return the code in the login response, so you can sign in
    # without email set up. Never set this on the deployed backend.
    DEV_SHOW_OTP = flag("DEV_SHOW_OTP")

    # Email. Gmail (SMTP) is used when SMTP_HOST is set, otherwise SendGrid when its key is set,
    # otherwise emails are printed in the terminal instead of being sent.
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").replace(" ", "")  # Gmail shows it in 4 groups
    SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
    MAIL_FROM = os.getenv("MAIL_FROM") or SMTP_USERNAME or "no-reply@stockpilot.test"
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    EMAIL_TOKEN_HOURS = 24

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


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = database_url(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://stockpilot:stockpilot@localhost:5432/stockpilot_test",
    )
    SMTP_HOST = ""  # tests read emails from the outbox, never send them
    SENDGRID_API_KEY = ""
    BCRYPT_LOG_ROUNDS = 4  # fast hashing so the tests run quickly
    DEV_SHOW_OTP = False