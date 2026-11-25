import importlib
import pkgutil

from flask import Flask, g
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import config_for_environment
from app.errors import register_error_handlers
from app.extensions import api, bcrypt, cors, db, jwt, limiter, migrate
from app.security import add_security_headers


def create_app(config_class=None):
    config_class = config_class or config_for_environment()
    if hasattr(config_class, "check"):
        config_class.check()
    app = Flask(__name__)
    app.config.from_object(config_class)
    if app.config["BEHIND_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})
    api.init_app(app)
    jwt.init_app(app)
    bcrypt.init_app(app)
    limiter.init_app(app)
    add_security_headers(app)

    from app import auth, mail, models, resources, tenancy  # noqa: F401  (imported to register hooks)

    @app.before_request
    def start_outside_any_business():
        g.outer_business_id = tenancy.current_business_id()
        tenancy.clear_business()
        g.pop("business", None)
        db.session.info.pop("emails", None)

    @app.teardown_request
    def leave_business(_exc):
        outer = g.pop("outer_business_id", None)
        tenancy.clear_business()
        g.pop("business", None)
        if outer is not None:
            tenancy.set_business(outer)

    for info in pkgutil.iter_modules(resources.__path__):
        module = importlib.import_module(f"app.resources.{info.name}")
        for blueprint in getattr(module, "blueprints", [getattr(module, "blp", None)]):
            if blueprint is not None:
                api.register_blueprint(blueprint)

    register_error_handlers(app)
    return app
