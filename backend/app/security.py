"""Response headers that stop browsers from misusing what the API sends back."""


def add_security_headers(app):
    @app.after_request
    def secure(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if not request_is_docs():
            # The API only ever returns JSON: nothing in a response may load or run anything.
            response.headers.setdefault(
                "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
            )
        if app.config.get("BEHIND_PROXY"):
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


def request_is_docs():
    from flask import request

    return request.path.startswith("/api/docs")