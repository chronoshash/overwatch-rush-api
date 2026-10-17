"""ASGI middleware that answers HEAD requests exactly like GET.

Starlette/FastAPI does not register HEAD for GET routes (unlike Flask), so a
plain FastAPI app returns 405 on HEAD. Preview proxies and uptime checks often
probe with HEAD first, and a 405 makes the preview look broken.

This middleware rewrites HEAD to GET internally and drops the body while
keeping the original headers (including content-length, as RFC 9110 requires).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


class HeadAsGetMiddleware:
    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        if scope.get("type") != "http" or scope.get("method") != "HEAD":
            await self.app(scope, receive, send)
            return

        get_scope = dict(scope)
        get_scope["method"] = "GET"

        async def send_without_body(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.body":
                message = {**message, "body": b"", "more_body": False}
            await send(message)

        await self.app(get_scope, receive, send_without_body)
