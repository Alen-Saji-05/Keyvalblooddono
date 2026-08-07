"""Alembic environment, wired to the Flask application.

The connection URL is read from the running application's configuration rather than
from alembic.ini, so ``flask db upgrade`` cannot be pointed at a different database than
the one the application uses.
"""

from __future__ import annotations

import logging
from logging.config import fileConfig

from alembic import context
from flask import current_app

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")


def get_engine():
    return current_app.extensions["migrate"].db.engine


def get_engine_url() -> str:
    # The percent signs are doubled because the value is written into a ConfigParser
    # option, where a bare percent begins an interpolation. A password containing one
    # would otherwise break the URL.
    return get_engine().url.render_as_string(hide_password=False).replace("%", "%%")


config.set_main_option("sqlalchemy.url", get_engine_url())
target_db = current_app.extensions["migrate"].db


def get_metadata():
    if hasattr(target_db, "metadatas"):
        return target_db.metadatas[None]
    return target_db.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=get_metadata(),
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    def process_revision_directives(context_, revision, directives):
        # Prevents an empty revision file being written when nothing has changed, which
        # otherwise accumulates as no-op migrations in the history.
        if getattr(config.cmd_opts, "autogenerate", False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info("No schema changes detected.")

    connectable = get_engine()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            process_revision_directives=process_revision_directives,
            # Without this, a change to a column type is not detected and the migration
            # silently omits it.
            compare_type=True,
            compare_server_default=True,
            **current_app.extensions["migrate"].configure_args,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
