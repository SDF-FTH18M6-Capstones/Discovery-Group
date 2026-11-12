"""GET /api/health — is the API up and can it reach the database?"""

from datetime import UTC, datetime

from flask_smorest import Blueprint
from sqlalchemy import text

from app.extensions import db

blp = Blueprint("health", __name__, url_prefix="/api", description="Service health")


@blp.route("/health")
def health():
    """Returns 200 when the database answers, 503 when it does not."""
    try:
        db.session.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        db.session.rollback()
        database = "unavailable"
    body = {
        "status": "ok" if database == "ok" else "degraded",
        "database": database,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    return body, 200 if database == "ok" else 503