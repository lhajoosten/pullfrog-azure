import asyncio

import pytest
from alembic import command
from alembic.config import Config
from pullfrog_azure_api.config import DatabaseSettings
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


async def column_names(database_url: str, table_name: str) -> set[str]:
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        columns = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_columns(table_name)
        )
    await engine.dispose()
    return {column["name"] for column in columns}


async def unique_constraints(
    database_url: str,
    table_name: str,
) -> set[tuple[str | None, tuple[str, ...]]]:
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        constraints = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_unique_constraints(table_name)
        )
    await engine.dispose()
    return {(constraint["name"], tuple(constraint["column_names"])) for constraint in constraints}


async def check_constraint_names(database_url: str, table_name: str) -> set[str]:
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        constraints = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_check_constraints(table_name)
        )
    await engine.dispose()
    return {constraint["name"] for constraint in constraints if constraint["name"] is not None}


async def index_names(database_url: str, table_name: str) -> set[str]:
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        indexes = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_indexes(table_name)
        )
    await engine.dispose()
    return {index["name"] for index in indexes if index["name"] is not None}


@pytest.mark.integration
def test_admin_identity_session_migration_round_trip() -> None:
    config = Config("alembic.ini")
    database_url = str(DatabaseSettings().database_url)

    command.upgrade(config, "head")
    expected_tables = {
        "deployment_settings",
        "admin_identity",
        "oidc_login_attempt",
        "admin_session",
    }
    assert expected_tables <= asyncio.run(table_names(database_url))

    expected_columns = {
        "admin_identity": {
            "id",
            "tenant_id",
            "kind",
            "entra_object_id",
            "created_at",
        },
        "oidc_login_attempt": {
            "id",
            "token_digest",
            "flow",
            "return_to",
            "created_at",
            "expires_at",
        },
        "admin_session": {
            "id",
            "token_digest",
            "csrf_token_digest",
            "tenant_id",
            "user_object_id",
            "authorizing_kind",
            "authorizing_object_id",
            "display_name",
            "created_at",
            "last_seen_at",
            "idle_expires_at",
            "absolute_expires_at",
            "revoked_at",
        },
    }
    for table_name, columns in expected_columns.items():
        assert columns <= asyncio.run(column_names(database_url, table_name))

    assert (
        "uq_admin_identity_tenant_id_kind_entra_object_id",
        ("tenant_id", "kind", "entra_object_id"),
    ) in asyncio.run(unique_constraints(database_url, "admin_identity"))
    assert (
        "uq_oidc_login_attempt_token_digest",
        ("token_digest",),
    ) in asyncio.run(unique_constraints(database_url, "oidc_login_attempt"))
    assert (
        "uq_admin_session_token_digest",
        ("token_digest",),
    ) in asyncio.run(unique_constraints(database_url, "admin_session"))
    assert "ck_admin_identity_kind" in asyncio.run(
        check_constraint_names(database_url, "admin_identity")
    )
    assert "ck_admin_session_authorizing_kind" in asyncio.run(
        check_constraint_names(database_url, "admin_session")
    )
    assert "ix_oidc_login_attempt_expires_at" in asyncio.run(
        index_names(database_url, "oidc_login_attempt")
    )

    command.downgrade(config, "20260809_0001")
    remaining = asyncio.run(table_names(database_url))
    assert "deployment_settings" in remaining
    assert "admin_identity" not in remaining
    assert "oidc_login_attempt" not in remaining
    assert "admin_session" not in remaining

    command.upgrade(config, "head")
