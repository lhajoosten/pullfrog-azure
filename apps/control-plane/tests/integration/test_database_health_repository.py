import pytest
from pullfrog_azure_api.config import DatabaseSettings
from pullfrog_azure_api.db.database import Database
from pullfrog_azure_api.repositories.database_health import (
    DatabaseHealthRepository,
    DatabaseUnavailableError,
)
from sqlalchemy.engine import make_url


@pytest.mark.integration
async def test_database_health_repository_pings_postgresql() -> None:
    database = Database(str(DatabaseSettings().database_url))
    repository = DatabaseHealthRepository(database.sessions)

    try:
        await repository.ping()
    finally:
        await database.close()


@pytest.mark.integration
async def test_database_health_repository_translates_connection_refusal() -> None:
    unavailable_url = make_url(str(DatabaseSettings().database_url)).set(
        host="127.0.0.1",
        port=1,
    )
    database = Database(unavailable_url.render_as_string(hide_password=False))
    repository = DatabaseHealthRepository(database.sessions)

    try:
        with pytest.raises(DatabaseUnavailableError) as error:
            await repository.ping()
    finally:
        await database.close()

    assert str(error.value) == "Database is unavailable"
