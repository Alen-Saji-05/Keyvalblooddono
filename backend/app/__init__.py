"""Application factory.

A factory rather than a module-level ``app`` object so that configuration is chosen at
construction time. Tests build an application pointed at the test database, the CLI
builds one for a command, and neither inherits settings from the other.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

# This runs before any other import in the package, and the ordering is deliberate.
#
# config.py reads os.environ when its classes are *defined*, not when they are
# instantiated, so the environment has to be populated before that module is imported.
# Importing config first and loading the file afterwards leaves every setting at its
# hardcoded default. The `flask` CLI hides this, because Flask loads .env itself before
# importing the application, so the bug only appears when the package is imported
# directly - from a script, a test runner, or a production WSGI server.
#
# Every path into this package executes this line first: importing app.config or any
# other submodule runs the package __init__ before the submodule.
#
# load_dotenv does not override variables already set, so a deployment that provides
# real environment variables is not overridden by a stray file on disk.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from flask import Flask  # noqa: E402

from .config import resolve_config  # noqa: E402
from .extensions import cors, db, jwt, limiter, migrate  # noqa: E402


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(resolve_config(config_name)())

    register_extensions(app)
    register_error_handling(app)
    register_cli(app)
    register_routes(app)

    return app


def register_extensions(app: Flask) -> None:
    db.init_app(app)

    # render_as_batch is off: it exists to work around SQLite's inability to alter a
    # column in place, and this project targets PostgreSQL, where ALTER works properly.
    migrate.init_app(app, db, directory=os.path.join(app.root_path, "..", "migrations"))

    jwt.init_app(app)

    from .security.tokens import register_jwt_callbacks

    register_jwt_callbacks(app)

    limiter.init_app(app)

    # supports_credentials is required for the refresh cookie to be sent from the Vite
    # development server, which is a different origin than the API. It also means the
    # allowed origins must be an explicit list rather than a wildcard, since a browser
    # refuses to send credentials to a wildcard origin.
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        supports_credentials=True,
    )


def register_error_handling(app: Flask) -> None:
    from .api.errors import register_error_handlers

    register_error_handlers(app)


def register_cli(app: Flask) -> None:
    from .cli import register_commands

    register_commands(app)


def register_routes(app: Flask) -> None:
    from .api.auth import bp as auth_bp
    from .api.donors import bp as donors_bp
    from .api.health import bp as health_bp
    from .api.me import bp as me_bp
    from .api.meta import bp as meta_bp
    from .api.notifications import bp as notifications_bp
    from .api.requests import bp as requests_bp
    from .api.summary import bp as summary_bp
    from .api.users import bp as users_bp

    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(meta_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(users_bp, url_prefix="/api/users")
    app.register_blueprint(donors_bp, url_prefix="/api/donors")
    app.register_blueprint(requests_bp, url_prefix="/api/requests")
    app.register_blueprint(notifications_bp, url_prefix="/api/notifications")
    app.register_blueprint(me_bp, url_prefix="/api/me")
    app.register_blueprint(summary_bp, url_prefix="/api/summary")
