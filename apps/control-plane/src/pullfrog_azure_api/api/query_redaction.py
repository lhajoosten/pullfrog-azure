from pullfrog_azure_api.api.auth_cookies import CALLBACK_PATH
from starlette.types import ASGIApp, Receive, Scope, Send


class CallbackQueryRedactionMiddleware:
    """Hide OIDC callback parameters from the server-facing request scope.

    Uvicorn writes its access-log entry after the application starts the response
    and reads the original scope at that point. The application receives a copy
    containing the query so the OIDC flow can still validate ``code`` and ``state``.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] != CALLBACK_PATH or not scope["query_string"]:
            await self._app(scope, receive, send)
            return

        application_scope: Scope = dict(scope)
        scope["query_string"] = b""
        await self._app(application_scope, receive, send)
