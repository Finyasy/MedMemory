#!/usr/bin/env python3
"""Prepare a database for local CI/staging use.

Behavior:
- if the database is empty, create the current schema and stamp Alembic to head
- if the database is already versioned, run `alembic upgrade head`
- if the database is non-empty but unversioned, refuse to continue
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.database import engine
from app.models import Base


def _alembic_config() -> Config:
    backend_dir = Path(__file__).resolve().parents[1]
    return Config(str(backend_dir / "alembic.ini"))


async def _list_public_tables() -> list[str]:
    async with engine.begin() as conn:
        return await conn.run_sync(
            lambda sync_conn: sorted(inspect(sync_conn).get_table_names(schema="public"))
        )


async def _create_current_schema() -> None:
    async with engine.begin() as conn:
        await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        await conn.run_sync(Base.metadata.create_all)


async def _prepare_database() -> str:
    tables = await _list_public_tables()

    if not tables:
        await _create_current_schema()
        return "stamp"

    if "alembic_version" in tables:
        return "upgrade"

    raise RuntimeError(
        "Refusing to stamp a non-empty unversioned database. "
        "Reset the database or migrate it manually first."
    )


def main() -> None:
    action = asyncio.run(_prepare_database())
    cfg = _alembic_config()
    if action == "stamp":
        command.stamp(cfg, "head")
        print("Schema created from current models and Alembic stamped to head.")
        return
    command.upgrade(cfg, "head")
    print("Existing versioned schema upgraded to head.")


if __name__ == "__main__":
    main()
