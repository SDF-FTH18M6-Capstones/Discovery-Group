import hmac

from flask import current_app, request
from flask_smorest import Blueprint, abort

from app.summary import send_daily_summaries

blp = Blueprint("tasks", __name__, url_prefix="/api/tasks", description="Scheduled jobs")


@blp.route("/daily-summary", methods=["POST"])
@blp.response(200)
def daily_summary():
    expected = current_app.config["TASK_TOKEN"]
    given = request.headers.get("X-Task-Token", "")
    if not expected or not hmac.compare_digest(given, expected):
        abort(404)
    return {"sent": send_daily_summaries()}
