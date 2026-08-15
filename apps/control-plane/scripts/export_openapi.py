import json
from pathlib import Path

from pullfrog_azure_api.app import create_app


def main() -> None:
    destination = Path("packages/api-client/openapi.json")
    destination.write_text(
        json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
