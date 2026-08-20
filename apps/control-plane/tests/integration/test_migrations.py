import asyncio

import pytest
from alembic import command
from alembic.config import Config
from pullfrog_azure_api.config import Settings
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine


async def table_names(database_url: str) -> set[str]:
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        names = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_table_names()
        )
    await engine.dispose()
    return set(names)


@pytest.mark.integration
def test_initial_migration_round_trip() -> None:
    config = Config("alembic.ini")
    database_url = str(Settings().database_url)

    command.upgrade(config, "head")
    assert "deployment_settings" in asyncio.run(table_names(database_url))

    command.downgrade(config, "base")
    assert "deployment_settings" not in asyncio.run(table_names(database_url))

    command.upgrade(config, "head")
