from pullfrog_azure_api.app import create_app


def test_health_paths_are_in_openapi_contract() -> None:
    paths = create_app().openapi()["paths"]

    assert "/api/v1/health/live" in paths
    assert "/api/v1/health/ready" in paths


def test_authentication_paths_and_minimal_session_schema_are_in_openapi_contract() -> None:
    contract = create_app().openapi()
    paths = contract["paths"]

    assert set(paths) >= {
        "/api/v1/auth/login",
        "/api/v1/auth/callback",
        "/api/v1/auth/me",
        "/api/v1/auth/logout",
    }
    assert "302" in paths["/api/v1/auth/login"]["get"]["responses"]
    assert "303" in paths["/api/v1/auth/callback"]["get"]["responses"]
    assert "401" in paths["/api/v1/auth/me"]["get"]["responses"]
    assert "204" in paths["/api/v1/auth/logout"]["post"]["responses"]

    session_schema = contract["components"]["schemas"]["AdminSessionResponse"]
    assert set(session_schema["properties"]) == {
        "display_name",
        "idle_expires_at",
        "absolute_expires_at",
    }
    logout_parameters = paths["/api/v1/auth/logout"]["post"]["parameters"]
    assert {
        "name": "X-Pullfrog-CSRF",
        "in": "header",
        "required": False,
    }.items() <= next(
        parameter for parameter in logout_parameters if parameter["name"] == "X-Pullfrog-CSRF"
    ).items()
