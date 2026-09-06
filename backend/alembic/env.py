import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.core.paths import get_sqlite_path

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The application runner injects an explicit database URL for isolated tests
# and per-user desktop data.  Only fall back to the configured Kuantra data
# directory when Alembic is invoked without one; silently overwriting an
# explicit URL would migrate the wrong database.
configured_url = config.get_main_option("sqlalchemy.url")
if not configured_url or configured_url == "sqlite:///../data/kuantra_trades.db":
    config.set_main_option("sqlalchemy.url", f"sqlite:///{get_sqlite_path()}")

target_metadata = None

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
