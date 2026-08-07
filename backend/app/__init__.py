"""Application factory.

A factory rather than a module-level ``app`` object so that configuration is chosen at
construction time. Tests build an application pointed at the test database, the CLI
builds one for a command, and neither inherits settings from the other.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from flask import Flask

from .config import resolve_config
from .extensions import db, migrate

# Loaded before the configuration classes are instantiated, since they read the
# environment at that point. Values already present in the real environment win, so a
# deployment that sets variables directly is not overridden by a stray file.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(resolve_config(config_name)())

    register_extensions(app)
    register_cli(app)
    register_routes(app)

    return app


def register_extensions(app: Flask) -> None:
    db.init_app(app)

    # render_as_batch is off: it exists to work around SQLite's inability to alter a
    # column in place, and this project targets PostgreSQL, where ALTER works properly.
    migrate.init_app(app, db, directory=os.path.join(app.root_path, "..", "migrations"))


def register_cli(app: Flask) -> None:
    from .cli import register_commands

    register_commands(app)


def register_routes(app: Flask) -> None:
    from .api.health import bp as health_bp

    app.register_blueprint(health_bp, url_prefix="/api")
