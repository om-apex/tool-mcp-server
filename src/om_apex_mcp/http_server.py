"""
Om Apex MCP HTTP Server

Streamable HTTP transport for remote access to the Om Apex MCP server.
Supports authenticated access (API key) and demo mode (read-only).

Author: Nishad Tambe
"""

import logging
import os
import time
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from typing import Optional

import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from .auth import AuthMiddleware
from .server import SERVER_GROUPS, create_server
from .storage import GoogleDriveStorage, LocalStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("om-apex-mcp")

# Global reference to storage backend for health checks
_storage_backend: Optional[LocalStorage | GoogleDriveStorage] = None


def _create_storage_backend():
    """Create storage backend based on environment.

    Priority:
    1. Google Drive API (GOOGLE_SERVICE_ACCOUNT_FILE set)
    2. Local filesystem (default — for local dev or if Google Drive Desktop is available)
    """
    global _storage_backend

    if os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE"):
        logger.info("Using GoogleDriveStorage backend")
        _storage_backend = GoogleDriveStorage()
        return _storage_backend

    # Check for demo-only mode with bundled data
    demo_data_dir = Path(__file__).parent.parent.parent / "data" / "demo"
    if os.environ.get("OM_APEX_USE_DEMO_DATA") and demo_data_dir.exists():
        logger.info(f"Using LocalStorage with demo data: {demo_data_dir}")
        _storage_backend = LocalStorage(data_dir=demo_data_dir, shared_drive_root=demo_data_dir.parent)
        return _storage_backend

    logger.info("Using LocalStorage backend (default)")
    _storage_backend = LocalStorage()
    return _storage_backend


def _check_supabase_health() -> dict:
    """Check Supabase connectivity and return status."""
    try:
        from .supabase_client import get_supabase_client, is_supabase_available

        if not is_supabase_available():
            return {"status": "not_configured", "message": "Supabase not configured, using JSON fallback"}

        start = time.time()
        client = get_supabase_client()
        client.table("tasks").select("id").limit(1).execute()
        latency_ms = int((time.time() - start) * 1000)

        return {"status": "ok", "latency_ms": latency_ms}
    except ImportError:
        return {"status": "not_configured", "message": "Supabase client not installed"}
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {str(e)}"}


def _check_storage_health() -> dict:
    """Check storage backend health."""
    global _storage_backend

    if _storage_backend is None:
        return {"status": "not_initialized", "backend": "unknown"}

    backend_type = type(_storage_backend).__name__

    try:
        # Try to load a known file to verify storage works
        start = time.time()
        data = _storage_backend.load_json("company_structure.json")
        latency_ms = int((time.time() - start) * 1000)

        if data:
            return {"status": "ok", "backend": backend_type, "latency_ms": latency_ms}
        else:
            return {"status": "empty", "backend": backend_type, "message": "No data files found"}
    except FileNotFoundError as e:
        return {"status": "path_missing", "backend": backend_type, "error": str(e)}
    except Exception as e:
        return {"status": "error", "backend": backend_type, "error": f"{type(e).__name__}: {str(e)}"}


def create_app() -> Starlette:
    """Create the Starlette ASGI application.

    Creates separate MCP server instances per tool group:
      /mcp       — all tools (backward compatible)
      /mcp/core  — core tools only (tasks, progress, calendar, handoff, quorum, incidents, context)
      /mcp/dns   — DNS Sentinel tools only
      /mcp/docs  — document generation tools only
    """
    backend = _create_storage_backend()

    # Create a server + session manager for each group
    managers: dict[str, StreamableHTTPSessionManager] = {}
    for group_name in [None, "core", "dns", "docs"]:
        srv = create_server(backend, group=group_name)
        managers[group_name or "all"] = StreamableHTTPSessionManager(app=srv, stateless=True)

    @asynccontextmanager
    async def lifespan(app):
        """Application lifespan — startup/shutdown for all managers."""
        logger.info("Om Apex MCP HTTP Server starting...")
        async with AsyncExitStack() as stack:
            for mgr in managers.values():
                await stack.enter_async_context(mgr.run())
            yield
        logger.info("Om Apex MCP HTTP Server shut down.")

    async def health(request: Request) -> JSONResponse:
        """Enhanced health endpoint with dependency checks.

        Returns:
            - status: "healthy" (all OK), "degraded" (some issues), or "unhealthy" (critical failure)
            - server: server name
            - checks: detailed status of each dependency
        """
        checks = {
            "supabase": _check_supabase_health(),
            "storage": _check_storage_health(),
        }

        # Count loaded tool modules
        try:
            from .tools import context, tasks, progress, documents, calendar, handoff, ai_quorum, incidents, dns_sentinel
            modules_loaded = 9  # All 9 tool modules
            checks["modules"] = {"status": "ok", "count": modules_loaded}
        except ImportError as e:
            checks["modules"] = {"status": "error", "error": str(e)}

        # Determine overall status
        statuses = [c.get("status", "unknown") for c in checks.values()]

        if all(s in ("ok", "not_configured", "empty") for s in statuses):
            overall_status = "healthy"
        elif any(s == "error" for s in statuses):
            overall_status = "degraded"
        else:
            overall_status = "healthy"  # Warnings don't make it unhealthy

        return JSONResponse({
            "status": overall_status,
            "server": "om-apex-mcp",
            "checks": checks,
        })

    # Custom ASGI sub-router: a single Mount at /mcp dispatches to the
    # correct session manager based on the sub-path.  Avoids Starlette's
    # overlapping-prefix issue where Mount("/mcp") catches /mcp/core.
    async def mcp_router(scope, receive, send):
        path = scope.get("path", "")
        logger.info(f"mcp_router: path={path!r} type={scope.get('type')}")
        if path.startswith("/core"):
            scope = dict(scope, path=path[5:] or "/", root_path=scope.get("root_path", "") + "/core")
            logger.info("mcp_router: dispatching to CORE manager")
            await managers["core"].handle_request(scope, receive, send)
        elif path.startswith("/dns"):
            scope = dict(scope, path=path[4:] or "/", root_path=scope.get("root_path", "") + "/dns")
            logger.info("mcp_router: dispatching to DNS manager")
            await managers["dns"].handle_request(scope, receive, send)
        elif path.startswith("/docs"):
            scope = dict(scope, path=path[5:] or "/", root_path=scope.get("root_path", "") + "/docs")
            logger.info("mcp_router: dispatching to DOCS manager")
            await managers["docs"].handle_request(scope, receive, send)
        else:
            logger.info("mcp_router: dispatching to ALL manager")
            await managers["all"].handle_request(scope, receive, send)

    routes = [
        Route("/health", health, methods=["GET"]),
        Mount("/mcp", app=mcp_router),
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
