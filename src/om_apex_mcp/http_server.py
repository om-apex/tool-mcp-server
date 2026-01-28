"""
Om Apex MCP HTTP Server

Streamable HTTP transport for remote access to the Om Apex MCP server.
Supports authenticated access (API key) and demo mode (read-only).

Author: Nishad Tambe
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from .auth import AuthMiddleware
from .server import create_server
from .storage import GoogleDriveStorage, LocalStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("om-apex-mcp")


def _create_storage_backend():
    """Create storage backend based on environment.

    Priority:
    1. Google Drive API (GOOGLE_SERVICE_ACCOUNT_FILE set)
    2. Local filesystem (default — for local dev or if Google Drive Desktop is available)
    """
    if os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE"):
        logger.info("Using GoogleDriveStorage backend")
        return GoogleDriveStorage()

    # Check for demo-only mode with bundled data
    demo_data_dir = Path(__file__).parent.parent.parent / "data" / "demo"
    if os.environ.get("OM_APEX_USE_DEMO_DATA") and demo_data_dir.exists():
        logger.info(f"Using LocalStorage with demo data: {demo_data_dir}")
        return LocalStorage(data_dir=demo_data_dir, shared_drive_root=demo_data_dir.parent)

    logger.info("Using LocalStorage backend (default)")
    return LocalStorage()


def create_app() -> Starlette:
    """Create the Starlette ASGI application."""
    backend = _create_storage_backend()
    server = create_server(backend)
    session_manager = StreamableHTTPSessionManager(app=server, stateless=True)

    @asynccontextmanager
    async def lifespan(app):
        """Application lifespan — startup/shutdown."""
        logger.info("Om Apex MCP HTTP Server starting...")
        async with session_manager.run():
            yield
        logger.info("Om Apex MCP HTTP Server shut down.")

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "server": "om-apex-mcp"})

    routes = [
        Route("/health", health, methods=["GET"]),
        Mount("/mcp", app=session_manager.handle_request),
    ]

    middleware = [
        Middleware(AuthMiddleware),
    ]

    app = Starlette(
        routes=routes,
        middleware=middleware,
        lifespan=lifespan,
    )

    return app


def main():
    """Main entry point for HTTP server."""
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))

    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
