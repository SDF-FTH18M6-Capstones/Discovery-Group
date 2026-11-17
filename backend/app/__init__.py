import importlib
import pkgutil

from flask import Flask
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

    from app import auth, models, resources

    for info in pkgutil.iter_modules(resources.__path__):
        module = importlib.import_module(f"app.resources.{info.name}")
        if hasattr(module, "blp"):
            api.register_blueprint(module.blp)

    register_error_handlers(app)
    return app
