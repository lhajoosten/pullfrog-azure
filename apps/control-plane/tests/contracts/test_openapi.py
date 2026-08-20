from pullfrog_azure_api.app import create_app


def test_health_paths_are_in_openapi_contract() -> None:
    paths = create_app().openapi()["paths"]

    assert "/api/v1/health/live" in paths
    assert "/api/v1/health/ready" in paths
