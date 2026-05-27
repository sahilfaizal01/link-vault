from __future__ import annotations

from fastapi import HTTPException, Request
from starlette.status import HTTP_401_UNAUTHORIZED

from .config import API_KEY

PUBLIC_API_PATHS = {
    "/api/health",
}


def _read_key(request: Request) -> str | None:
    return request.headers.get("X-Link-Vault-Key") or request.headers.get(
        "Authorization", ""
    ).removeprefix("Bearer ").strip() or None


async def require_api_key(request: Request) -> None:
    if not API_KEY:
        return
    if request.method == "OPTIONS":
        return
    path = request.url.path
    if path in PUBLIC_API_PATHS:
        return
    if not path.startswith("/api/"):
        return
    if _read_key(request) != API_KEY:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key (X-Link-Vault-Key header).",
        )
