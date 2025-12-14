import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# ВАЖНО: внутри контейнера пакет называется просто "app"
from app.database import Base

import app.models # noqa: F401      # чтобы Alembic увидел таблицы

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise RuntimeError("DATABASE_URL is not set")

config.set_main_option("sqlalchemy.url", DB_URL)
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    context.configure(
        url=DB_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = create_engine(DB_URL, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
