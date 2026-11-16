"""Creates the Flask app: settings, database, CORS, Swagger, routes, errors."""

import importlib
import pkgutil

from flask import Flask

from app.config import Config
from app.errors import register_error_handlers
from app.extensions import api, bcrypt, cors, db, jwt, migrate


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})
    api.init_app(app)
    jwt.init_app(app)
    bcrypt.init_app(app)

    # `models` is imported so migrations see every table; `auth` sets up the JWT checks.
    # Every file in app/resources/ that defines `blp` is registered automatically,
    # so adding a new resource never means editing this file.
    from app import auth, models, resources  # noqa: F401

    for info in pkgutil.iter_modules(resources.__path__):
        module = importlib.import_module(f"app.resources.{info.name}")
        if hasattr(module, "blp"):
            api.register_blueprint(module.blp)

    register_error_handlers(app)
    return app