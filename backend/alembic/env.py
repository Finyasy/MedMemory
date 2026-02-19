from __future__ import annotations

import asyncio
import importlib
import sys
import types
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.config import settings
from app.models import Base

backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


def _install_pgvector_stub() -> None:
    try:
        importlib.import_module("pgvector.sqlalchemy")

        return
    except Exception:
        pass

    try:
        from sqlalchemy.types import TypeEngine
    except Exception:
        return

    pgvector_pkg = types.ModuleType("pgvector")
    sqlalchemy_mod = types.ModuleType("pgvector.sqlalchemy")

    class Vector(TypeEngine):
        cache_ok = True

        def __init__(self, *_args, **_kwargs):
            super().__init__()

    sqlalchemy_mod.Vector = Vector
    pgvector_pkg.sqlalchemy = sqlalchemy_mod
    sys.modules["pgvector"] = pgvector_pkg
    sys.modules["pgvector.sqlalchemy"] = sqlalchemy_mod


_install_pgvector_stub()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    return settings.database_url


def run_migrations_offline() -> None:
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        {
            "sqlalchemy.url": _get_url(),
        },
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
