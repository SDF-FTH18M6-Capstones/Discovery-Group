"""Settings come from environment variables (.env file locally)."""

import os

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
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = database_url(
        "DATABASE_URL", "postgresql+psycopg://stockpilot:stockpilot@localhost:5432/stockpilot_dev"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ORIGINS = [
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    ]

    # Swagger / OpenAPI (flask-smorest)
    API_TITLE = "StockPilot API"
    API_VERSION = "v1"
    OPENAPI_VERSION = "3.0.3"
    OPENAPI_URL_PREFIX = "/api"
    OPENAPI_SWAGGER_UI_PATH = "/docs"
    OPENAPI_SWAGGER_UI_URL = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = database_url(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://stockpilot:stockpilot@localhost:5432/stockpilot_test",
    )