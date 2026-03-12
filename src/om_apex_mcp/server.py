"""
Om Apex MCP Server

A Model Context Protocol server providing persistent memory for Om Apex Holdings
across all Claude interfaces (Chat, Cowork, Claude Code).

Author: Nishad Tambe
Started: January 19, 2026

Error Handling Strategy:
- All startup phases are wrapped in try/except with detailed logging
- Errors are logged to stderr for visibility in Claude Desktop logs
- The server attempts graceful degradation where possible
- Tool execution errors return error messages instead of crashing
"""

import logging
import sys
import traceback
from typing import Any, Optional

# Configure logging FIRST, before any other imports that might log
# Log to stderr so messages appear in Claude Desktop's MCP server logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("om-apex-mcp")

# Wrap all imports in try/except to catch import errors during startup
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError as e:
    logger.critical(f"Failed to import MCP library: {e}")
    logger.critical("Make sure 'mcp' is installed: pip install mcp")
    sys.exit(1)

try:
    from .storage import StorageBackend, LocalStorage
    from .tools import ToolModule
    from .tools.helpers import init_storage
    from .tools import context, tasks, progress, documents, calendar, handoff, ai_quorum, incidents, dns_sentinel, miro
except ImportError as e:
    logger.critical(f"Failed to import local modules: {e}")
    logger.critical(f"Traceback:\n{traceback.format_exc()}")
    sys.exit(1)


# Module group definitions for selective loading
_CORE_MODULES = frozenset({"tasks", "progress", "calendar", "handoff", "ai_quorum", "incidents", "context"})
_DNS_MODULES = frozenset({"dns_sentinel"})
_DOCS_MODULES = frozenset({"documents"})
_MIRO_MODULES = frozenset({"miro"})
_ALL_MODULES = _CORE_MODULES | _DNS_MODULES | _DOCS_MODULES | _MIRO_MODULES

SERVER_GROUPS = {
    "core": _CORE_MODULES,
    "dns": _DNS_MODULES,
    "docs": _DOCS_MODULES,
    None: _ALL_MODULES,
}


def create_server(backend: Optional[StorageBackend] = None, group: Optional[str] = None) -> Server:
    """Create and configure the MCP server with given storage backend.

    Args:
        backend: Storage backend to use. Defaults to LocalStorage if None.
        group: Tool group to load: "core", "dns", "docs", or None for all.

    Returns:
        Configured MCP Server instance.
    """
    allowed = SERVER_GROUPS.get(group, _ALL_MODULES)
    logger.info(f"Creating MCP server (group={group or 'all'}, {len(allowed)} module types)...")

    # Phase 1: Initialize storage backend
    try:
        if backend is None:
            logger.info("Initializing LocalStorage backend...")
            backend = LocalStorage()
        init_storage(backend)
        logger.info("Storage backend ready")
    except Exception as e:
        logger.error(f"Storage initialization failed: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        # Continue with degraded functionality - tools will fail gracefully
        logger.warning("Continuing with degraded storage - some tools may not work")

    # Phase 2: Create server instance
    try:
        server = Server("om-apex-mcp")
        logger.info("Server instance created")
    except Exception as e:
        logger.critical(f"Failed to create Server instance: {e}")
        raise RuntimeError(f"Cannot create MCP Server: {e}") from e

    # Phase 3: Register tool modules (filtered by group)
    modules: list[ToolModule] = []
    _task_mod = _progress_mod = _documents_mod = _calendar_mod = None
    _handoff_mod = _quorum_mod = _incidents_mod = _dns_sentinel_mod = _miro_mod = None

    if "tasks" in allowed:
        try:
            _task_mod = tasks.register()
            modules.append(_task_mod)
            logger.info(f"Tasks module loaded ({len(_task_mod.tools)} tools)")
        except Exception as e:
            logger.error(f"Failed to load tasks module: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")

    if "progress" in allowed:
        try:
            _progress_mod = progress.register()
            modules.append(_progress_mod)
            logger.info(f"Progress module loaded ({len(_progress_mod.tools)} tools)")
        except Exception as e:
            logger.error(f"Failed to load progress module: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")

    if "documents" in allowed:
        try:
            _documents_mod = documents.register()
            modules.append(_documents_mod)
            logger.info(f"Documents module loaded ({len(_documents_mod.tools)} tools)")
        except Exception as e:
            logger.error(f"Failed to load documents module: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")

    if "calendar" in allowed:
        try:
            _calendar_mod = calendar.register()
            modules.append(_calendar_mod)
            logger.info(f"Calendar module loaded ({len(_calendar_mod.tools)} tools)")
        except Exception as e:
            logger.error(f"Failed to load calendar module: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")

    if "handoff" in allowed:
        try:
            _handoff_mod = handoff.register()
            modules.append(_handoff_mod)
            logger.info(f"Handoff module loaded ({len(_handoff_mod.tools)} tools)")
        except Exception as e:
            logger.error(f"Failed to load handoff module: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")

    if "ai_quorum" in allowed:
        try:
            _quorum_mod = ai_quorum.register()
            modules.append(_quorum_mod)
            logger.info(f"AI Quorum module loaded ({len(_quorum_mod.tools)} tools)")
        except Exception as e:
            logger.error(f"Failed to load AI Quorum module: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")

    if "incidents" in allowed:
        try:
            _incidents_mod = incidents.register()
            modules.append(_incidents_mod)
            logger.info(f"Incidents module loaded ({len(_incidents_mod.tools)} tools)")
        except Exception as e:
            logger.error(f"Failed to load incidents module: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")

    if "dns_sentinel" in allowed:
        try:
            _dns_sentinel_mod = dns_sentinel.register()
            modules.append(_dns_sentinel_mod)
            logger.info(f"DNS Sentinel module loaded ({len(_dns_sentinel_mod.tools)} tools)")
        except Exception as e:
            logger.error(f"Failed to load DNS Sentinel module: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")

    if "miro" in allowed:
        try:
            _miro_mod = miro.register()
            modules.append(_miro_mod)
            logger.info(f"Miro module loaded ({len(_miro_mod.tools)} tools)")
        except Exception as e:
            logger.error(f"Failed to load Miro module: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")

    # Phase 4: Build tool lists and register context module (core + all groups only)
    if "context" in allowed:
        try:
            _all_reading = context.READING.copy()
            _all_writing = context.WRITING.copy()

            for mod in [_task_mod, _progress_mod, _documents_mod, _calendar_mod,
                        _handoff_mod, _quorum_mod, _incidents_mod, _dns_sentinel_mod, _miro_mod]:
                if mod:
                    _all_reading += mod.reading_tools
                    _all_writing += mod.writing_tools

            _context_mod = context.register(_all_reading, _all_writing)
            modules.insert(0, _context_mod)  # Context module first
            logger.info(f"Context module loaded ({len(_context_mod.tools)} tools)")
        except Exception as e:
            logger.error(f"Failed to load context module: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")

    total_tools = sum(len(m.tools) for m in modules)
    logger.info(f"Total modules loaded: {len(modules)}, Total tools: {total_tools}")

    # Phase 5: Register server handlers
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Return list of available tools."""
        try:
            all_tools = [tool for m in modules for tool in m.tools]
            logger.debug(f"list_tools called, returning {len(all_tools)} tools")
            return all_tools
        except Exception as e:
            logger.error(f"Error in list_tools: {e}")
            return []

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Dispatch tool calls to the appropriate module.

        Wraps all tool execution in try/except to prevent server crashes.
        Errors are logged and returned as error messages rather than exceptions.
        """
        logger.info(f"Tool call: {name}")
        try:
            for m in modules:
                result = await m.handler(name, arguments)
                if result is not None:
                    logger.info(f"Tool {name} completed successfully")
                    return result
            logger.warning(f"Unknown tool requested: {name}")
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        except Exception as e:
            # Log the full traceback for debugging
            logger.error(f"Tool '{name}' failed with error: {e}")
            logger.error(f"Arguments: {arguments}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")

            # Return a user-friendly error message instead of crashing
            error_type = type(e).__name__
            error_msg = str(e)

            # Provide context-specific hints for common errors
            hint = ""
            if "FileNotFoundError" in error_type or "No such file" in error_msg:
                hint = " (Check if the path exists or Google Drive is synced)"
            elif "Permission" in error_msg:
                hint = " (Check file permissions)"
            elif "Connection" in error_msg or "timeout" in error_msg.lower():
                hint = " (Check network connectivity to Supabase/Google Drive)"
            elif "JSONDecodeError" in error_type:
                hint = " (Data file may be corrupted)"
            elif "httpx" in error_msg.lower() or "http" in error_type.lower():
                hint = " (Network request failed - check internet connection)"
            elif "supabase" in error_msg.lower():
                hint = " (Supabase error - check credentials and connection)"

            return [TextContent(
                type="text",
                text=f"Error in {name}: {error_type}: {error_msg}{hint}\n\n"
                     f"The server is still running. You can try again or check the logs for details."
            )]

    logger.info("Server handlers registered")
    return server


# =============================================================================
# Main Entry Point (stdio transport — local Claude Desktop)
# =============================================================================

async def run():
    """Run the MCP server via stdio transport.

    This is the main async entry point. All errors are caught and logged
    to ensure the server doesn't crash silently.
    """
    logger.info("=" * 60)
    logger.info("Starting Om Apex MCP Server (stdio)...")
    logger.info("=" * 60)

    try:
        server = create_server()
    except Exception as e:
        logger.critical(f"Failed to create server: {e}")
        logger.critical(f"Traceback:\n{traceback.format_exc()}")
        raise

    try:
        logger.info("Opening stdio transport...")
        async with stdio_server() as (read_stream, write_stream):
            logger.info("Transport ready, starting server loop...")
            init_options = server.create_initialization_options()
            await server.run(read_stream, write_stream, init_options)
    except KeyboardInterrupt:
        logger.info("Server stopped by user (Ctrl+C)")
    except Exception as e:
        logger.critical(f"Server runtime error: {e}")
        logger.critical(f"Traceback:\n{traceback.format_exc()}")
        raise
    finally:
        logger.info("Server shutdown complete")


def main():
    """Main entry point with comprehensive error handling.

    Catches all exceptions during startup and runtime to ensure
    errors are logged to stderr for Claude Desktop to capture.
    """
    import asyncio

    try:
        # Check Python version
        if sys.version_info < (3, 10):
            logger.warning(f"Python {sys.version_info} detected. Python 3.10+ recommended.")

        logger.info(f"Python version: {sys.version}")
        logger.info(f"Platform: {sys.platform}")

        asyncio.run(run())

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        # Log the full error to stderr for Claude Desktop logs
        logger.critical(f"FATAL ERROR: {type(e).__name__}: {e}")
        logger.critical(f"Full traceback:\n{traceback.format_exc()}")
        # Exit with error code so Claude Desktop knows something went wrong
        sys.exit(1)


if __name__ == "__main__":
    main()
