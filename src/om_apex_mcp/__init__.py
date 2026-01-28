"""
Om Apex MCP Server

Provides persistent memory for Om Apex Holdings across Claude interfaces.
"""

from .server import main, run, create_server

__version__ = "0.2.0"
__all__ = ["main", "run", "create_server"]
