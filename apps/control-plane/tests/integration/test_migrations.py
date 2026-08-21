import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from pullfrog_azure_api.auth.domain import AdminIdentityKind
from pullfrog_azure_api.config import DatabaseSettings
from pullfrog_azure_api.db.database import Database
from pullfrog_azure_api.models.admin_identity import AdminIdentity
from pullfrog_azure_api.models.admin_session import AdminSession
from sqlalchemy import DateTime, String, inspect
from sqlalchemy.engine.interfaces import ReflectedColumn
from sqlalchemy.ext.asyncio import create_async_engine


@dataclass(frozen=True, slots=True)
class ReflectedColumnContract:
    type_name: str
    length: int | None
    timezone: bool | None
    nullable: bool
    default: str | None


async def table_names(database_url: str) -> set[str]:
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        names = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_table_names()
        )
    await engine.dispose()
    return set(names)


def column_contract(column: ReflectedColumn) -> ReflectedColumnContract:
    column_type = column["type"]
    length = column_type.length if isinstance(column_type, String) else None
    timezone = column_type.timezone if isinstance(column_type, DateTime) else None
    return ReflectedColumnContract(
        type_name=type(column_type).__name__,
        length=length,
        timezone=timezone,
        nullable=column["nullable"],
        default=column["default"],
    )


async def column_contracts(
    database_url: str,
    table_name: str,
) -> dict[str, ReflectedColumnContract]:
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        columns = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_columns(table_name)
        )
    await engine.dispose()
    return {column["name"]: column_contract(column) for column in columns}


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


async def check_constraints(database_url: str, table_name: str) -> dict[str, str]:
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        constraints = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_check_constraints(table_name)
        )
    await engine.dispose()
    return {
        constraint["name"]: constraint["sqltext"]
        for constraint in constraints
        if constraint["name"] is not None
    }


async def indexes(
    database_url: str,
    table_name: str,
) -> set[tuple[str | None, tuple[str | None, ...], bool]]:
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        indexes = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_indexes(table_name)
        )
    await engine.dispose()
    return {(index["name"], tuple(index["column_names"]), index["unique"]) for index in indexes}


def assert_kind_check(sqltext: str, column_name: str) -> None:
    normalized_sqltext = re.sub(r"\s+", " ", sqltext).lower()
    assert re.search(rf"\b{re.escape(column_name)}\b", normalized_sqltext) is not None
    assert set(re.findall(r"'([^']+)'", normalized_sqltext)) == {"user", "group"}
    assert "any" in normalized_sqltext or " in " in normalized_sqltext


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

    expected_columns: dict[str, dict[str, ReflectedColumnContract]] = {
        "admin_identity": {
            "id": ReflectedColumnContract("UUID", None, None, False, None),
            "tenant_id": ReflectedColumnContract("UUID", None, None, False, None),
            "kind": ReflectedColumnContract("VARCHAR", 5, None, False, None),
            "entra_object_id": ReflectedColumnContract("UUID", None, None, False, None),
            "created_at": ReflectedColumnContract("TIMESTAMP", None, True, False, "now()"),
        },
        "oidc_login_attempt": {
            "id": ReflectedColumnContract("UUID", None, None, False, None),
            "token_digest": ReflectedColumnContract("BYTEA", None, None, False, None),
            "flow": ReflectedColumnContract("JSONB", None, None, False, None),
            "return_to": ReflectedColumnContract("VARCHAR", 2048, None, False, None),
            "created_at": ReflectedColumnContract("TIMESTAMP", None, True, False, None),
            "expires_at": ReflectedColumnContract("TIMESTAMP", None, True, False, None),
        },
        "admin_session": {
            "id": ReflectedColumnContract("UUID", None, None, False, None),
            "token_digest": ReflectedColumnContract("BYTEA", None, None, False, None),
            "csrf_token_digest": ReflectedColumnContract("BYTEA", None, None, False, None),
            "tenant_id": ReflectedColumnContract("UUID", None, None, False, None),
            "user_object_id": ReflectedColumnContract("UUID", None, None, False, None),
            "authorizing_kind": ReflectedColumnContract("VARCHAR", 5, None, False, None),
            "authorizing_object_id": ReflectedColumnContract("UUID", None, None, False, None),
            "display_name": ReflectedColumnContract("VARCHAR", 256, None, True, None),
            "created_at": ReflectedColumnContract("TIMESTAMP", None, True, False, None),
            "last_seen_at": ReflectedColumnContract("TIMESTAMP", None, True, False, None),
            "idle_expires_at": ReflectedColumnContract(
                "TIMESTAMP",
                None,
                True,
                False,
                None,
            ),
            "absolute_expires_at": ReflectedColumnContract(
                "TIMESTAMP",
                None,
                True,
                False,
                None,
            ),
            "revoked_at": ReflectedColumnContract("TIMESTAMP", None, True, True, None),
        },
    }
    for table_name, columns in expected_columns.items():
        assert asyncio.run(column_contracts(database_url, table_name)) == columns

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
    identity_checks = asyncio.run(check_constraints(database_url, "admin_identity"))
    assert set(identity_checks) == {"ck_admin_identity_kind"}
    assert_kind_check(identity_checks["ck_admin_identity_kind"], "kind")

    session_checks = asyncio.run(check_constraints(database_url, "admin_session"))
    assert set(session_checks) == {"ck_admin_session_authorizing_kind"}
    assert_kind_check(session_checks["ck_admin_session_authorizing_kind"], "authorizing_kind")

    assert (
        "ix_oidc_login_attempt_expires_at",
        ("expires_at",),
        False,
    ) in asyncio.run(indexes(database_url, "oidc_login_attempt"))

    command.downgrade(config, "20260809_0001")
    remaining = asyncio.run(table_names(database_url))
    assert "deployment_settings" in remaining
    assert "admin_identity" not in remaining
    assert "oidc_login_attempt" not in remaining
    assert "admin_session" not in remaining

    command.upgrade(config, "head")


@pytest.mark.integration
async def test_identity_kinds_round_trip_as_domain_enums() -> None:
    config = Config("alembic.ini")
    database_url = str(DatabaseSettings().database_url)
    await asyncio.to_thread(command.upgrade, config, "head")

    now = datetime.now(UTC)
    tenant_id = uuid4()
    identity = AdminIdentity(
        tenant_id=tenant_id,
        kind=AdminIdentityKind.USER,
        entra_object_id=uuid4(),
    )
    admin_session = AdminSession(
        token_digest=uuid4().bytes + uuid4().bytes,
        csrf_token_digest=uuid4().bytes + uuid4().bytes,
        tenant_id=tenant_id,
        user_object_id=uuid4(),
        authorizing_kind=AdminIdentityKind.GROUP,
        authorizing_object_id=uuid4(),
        display_name=None,
        created_at=now,
        last_seen_at=now,
        idle_expires_at=now + timedelta(minutes=30),
        absolute_expires_at=now + timedelta(hours=8),
        revoked_at=None,
    )
    database = Database(database_url)

    try:
        async with database.sessions() as database_session:
            database_session.add_all([identity, admin_session])
            await database_session.commit()

        async with database.sessions() as database_session:
            loaded_identity = await database_session.get(AdminIdentity, identity.id)
            loaded_admin_session = await database_session.get(AdminSession, admin_session.id)

            assert loaded_identity is not None
            assert loaded_identity.kind is AdminIdentityKind.USER
            assert loaded_admin_session is not None
            assert loaded_admin_session.authorizing_kind is AdminIdentityKind.GROUP
    finally:
        await database.close()
