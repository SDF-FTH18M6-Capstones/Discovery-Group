import logging

from flask import jsonify
from werkzeug.exceptions import HTTPException


def register_error_handlers(app):
    @app.errorhandler(HTTPException)
    def http_error(exc):
        body = {"code": exc.code, "message": exc.description or exc.name}
        data = getattr(exc, "data", None) or {} 
        if data.get("message"):
            body["message"] = data["message"]
        if data.get("messages"):  
            body["message"] = "Some fields are invalid."
            messages = data["messages"]
            body["details"] = messages.get("json") or messages.get("query") or messages
        return jsonify(error=body), exc.code

    @app.errorhandler(Exception)
    def unexpected_error(exc):
        logging.exception("Unexpected error")
        body = {"code": 500, "message": "Something went wrong. Please try again."}
        return jsonify(error=body), 500
