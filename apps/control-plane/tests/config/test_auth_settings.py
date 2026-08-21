from uuid import UUID

import pytest
from pullfrog_azure_api.config import DatabaseSettings, Settings
from pydantic import ValidationError

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
CLIENT_ID = UUID("00000000-0000-0000-0000-000000000002")
USER_ID = UUID("00000000-0000-0000-0000-000000000003")
GROUP_ID = UUID("00000000-0000-0000-0000-000000000004")
CLIENT_SECRET = "test-client-secret-not-a-credential"


@pytest.fixture
def database_url() -> str:
    return "postgresql+asyncpg://pullfrog:pullfrog@127.0.0.1:55432/pullfrog"


def build_settings(database_url: str, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": database_url,
        "entra_tenant_id": TENANT_ID,
        "entra_client_id": CLIENT_ID,
        "entra_client_secret": CLIENT_SECRET,
        "public_base_url": "https://pullfrog.example",
        "admin_user_object_ids": (USER_ID,),
    }
    values.update(overrides)
    return Settings(**values)


def test_database_settings_only_require_a_database_url(database_url: str) -> None:
    settings = DatabaseSettings(database_url=database_url)

    assert str(settings.database_url) == database_url


def test_settings_require_a_bootstrap_admin(database_url: str) -> None:
    with pytest.raises(ValidationError, match="bootstrap administrator"):
        Settings(
            database_url=database_url,
            entra_tenant_id=TENANT_ID,
            entra_client_id=CLIENT_ID,
            entra_client_secret=CLIENT_SECRET,
            public_base_url="https://pullfrog.example",
            admin_user_object_ids=(),
            admin_group_object_ids=(),
        )


def test_settings_parse_auth_values_from_environment(
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PULLFROG_DATABASE_URL", database_url)
    monkeypatch.setenv("PULLFROG_ENTRA_TENANT_ID", str(TENANT_ID))
    monkeypatch.setenv("PULLFROG_ENTRA_CLIENT_ID", str(CLIENT_ID))
    monkeypatch.setenv("PULLFROG_ENTRA_CLIENT_SECRET", CLIENT_SECRET)
    monkeypatch.setenv("PULLFROG_PUBLIC_BASE_URL", "https://pullfrog.example")
    monkeypatch.setenv("PULLFROG_ADMIN_USER_OBJECT_IDS", f"{USER_ID},{GROUP_ID}")
    monkeypatch.setenv("PULLFROG_ADMIN_GROUP_OBJECT_IDS", str(GROUP_ID))

    settings = Settings()

    assert settings.admin_user_object_ids == (USER_ID, GROUP_ID)
    assert settings.admin_group_object_ids == (GROUP_ID,)
    assert settings.callback_url == "https://pullfrog.example/api/v1/auth/callback"
    assert settings.secure_cookies is True


@pytest.mark.parametrize("user_object_ids", (None, ""))
def test_settings_accept_group_only_bootstrap_from_environment(
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
    user_object_ids: str | None,
) -> None:
    monkeypatch.setenv("PULLFROG_DATABASE_URL", database_url)
    monkeypatch.setenv("PULLFROG_ENTRA_TENANT_ID", str(TENANT_ID))
    monkeypatch.setenv("PULLFROG_ENTRA_CLIENT_ID", str(CLIENT_ID))
    monkeypatch.setenv("PULLFROG_ENTRA_CLIENT_SECRET", CLIENT_SECRET)
    monkeypatch.setenv("PULLFROG_PUBLIC_BASE_URL", "https://pullfrog.example")
    monkeypatch.setenv("PULLFROG_ADMIN_GROUP_OBJECT_IDS", str(GROUP_ID))
    if user_object_ids is None:
        monkeypatch.delenv("PULLFROG_ADMIN_USER_OBJECT_IDS", raising=False)
    else:
        monkeypatch.setenv("PULLFROG_ADMIN_USER_OBJECT_IDS", user_object_ids)

    settings = Settings()

    assert settings.admin_user_object_ids == ()
    assert settings.admin_group_object_ids == (GROUP_ID,)


def test_http_origin_is_allowed_only_for_explicit_loopback_development(
    database_url: str,
) -> None:
    settings = Settings(
        database_url=database_url,
        entra_tenant_id=TENANT_ID,
        entra_client_id=CLIENT_ID,
        entra_client_secret=CLIENT_SECRET,
        public_base_url="http://127.0.0.1:8000",
        admin_user_object_ids=(USER_ID,),
        allow_insecure_local_cookies=True,
    )

    assert settings.secure_cookies is False
    assert settings.callback_url == "http://127.0.0.1:8000/api/v1/auth/callback"


def test_loopback_http_requires_the_explicit_insecure_cookie_switch(
    database_url: str,
) -> None:
    with pytest.raises(ValidationError):
        build_settings(database_url, public_base_url="http://localhost:8000")


@pytest.mark.parametrize(
    "public_base_url",
    (
        "http://pullfrog.example",
        "http://192.0.2.1",
        "http://[2001:db8::1]",
    ),
)
def test_http_origin_rejects_non_loopback_hosts(
    database_url: str,
    public_base_url: str,
) -> None:
    with pytest.raises(ValidationError):
        build_settings(
            database_url,
            public_base_url=public_base_url,
            allow_insecure_local_cookies=True,
        )


@pytest.mark.parametrize(
    "public_base_url",
    (
        "https://operator:credential@pullfrog.example",
        "https://pullfrog.example?return_to=/settings",
        "https://pullfrog.example#settings",
        "https://pullfrog.example/settings",
    ),
)
def test_public_base_url_must_be_an_origin(
    database_url: str,
    public_base_url: str,
) -> None:
    with pytest.raises(ValidationError):
        build_settings(database_url, public_base_url=public_base_url)


@pytest.mark.parametrize(
    "public_base_url",
    ("https://pullfrog.example?", "https://pullfrog.example#"),
)
def test_public_base_url_rejects_empty_query_or_fragment_delimiters(
    database_url: str,
    public_base_url: str,
) -> None:
    with pytest.raises(ValidationError):
        build_settings(database_url, public_base_url=public_base_url)


@pytest.mark.parametrize(
    "admin_user_object_ids",
    (
        "not-a-uuid",
        f"{USER_ID},",
        f"{USER_ID},{USER_ID}",
    ),
)
def test_settings_reject_malformed_or_ambiguous_user_identity_lists(
    database_url: str,
    admin_user_object_ids: str,
) -> None:
    with pytest.raises(ValidationError):
        build_settings(database_url, admin_user_object_ids=admin_user_object_ids)


@pytest.mark.parametrize("idle_minutes", (9, 1_441))
def test_settings_reject_idle_expiry_outside_the_allowed_range(
    database_url: str,
    idle_minutes: int,
) -> None:
    with pytest.raises(ValidationError):
        build_settings(database_url, admin_session_idle_minutes=idle_minutes)


@pytest.mark.parametrize("absolute_hours", (0, 169))
def test_settings_reject_absolute_expiry_outside_the_allowed_range(
    database_url: str,
    absolute_hours: int,
) -> None:
    with pytest.raises(ValidationError):
        build_settings(database_url, admin_session_absolute_hours=absolute_hours)


@pytest.mark.parametrize(
    ("idle_minutes", "absolute_hours"),
    ((60, 1), (61, 1)),
)
def test_settings_require_absolute_expiry_to_exceed_idle_expiry(
    database_url: str,
    idle_minutes: int,
    absolute_hours: int,
) -> None:
    with pytest.raises(ValidationError, match="absolute"):
        build_settings(
            database_url,
            admin_session_idle_minutes=idle_minutes,
            admin_session_absolute_hours=absolute_hours,
        )


@pytest.mark.parametrize("attempt_minutes", (0, 11))
def test_settings_reject_login_attempt_expiry_outside_the_allowed_range(
    database_url: str,
    attempt_minutes: int,
) -> None:
    with pytest.raises(ValidationError):
        build_settings(database_url, oidc_login_attempt_minutes=attempt_minutes)


def test_settings_representation_redacts_the_client_secret(database_url: str) -> None:
    settings = build_settings(database_url)

    assert CLIENT_SECRET not in repr(settings)
