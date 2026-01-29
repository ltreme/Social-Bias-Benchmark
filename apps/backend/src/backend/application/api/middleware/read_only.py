"""Read-only mode middleware."""

import os

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


async def read_only_middleware(request: Request, call_next):
    """
    Middleware to block write operations when READ_ONLY_MODE is enabled.

    When the READ_ONLY_MODE environment variable is set to 'true', '1', or 'yes',
    this middleware will block all POST, PUT, DELETE, and PATCH requests with a 403 error.

    Exception: Export endpoints (containing '/export' in path) are allowed as they are
    read operations that generate files for download.
    """
    read_only = os.getenv("READ_ONLY_MODE", "false").lower() in ("true", "1", "yes")

    if read_only:
        # Allow GET, HEAD, OPTIONS requests
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return await call_next(request)

        # Allow export endpoints (they are read operations that generate downloads)
        if "/export" in request.url.path:
            return await call_next(request)

        # Allow warm-cache endpoint (read operation that pre-computes analytics)
        if "/warm-cache" in request.url.path:
            return await call_next(request)

        # Block all other write operations
        if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Application is in read-only mode. Write operations are disabled.",
                    "read_only_mode": True,
                },
            )

    return await call_next(request)
