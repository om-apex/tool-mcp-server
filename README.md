# Om Apex MCP Server

A Model Context Protocol (MCP) server that provides persistent memory and context across all Claude interfaces (Chat, Cowork, and Claude Code).

## Purpose

This MCP server serves as:
1. **Unified Memory** - Maintains business context, decisions, and project state across all Claude sessions
2. **Document Access** - Provides searchable access to Om Apex Holdings documents
3. **Task Tracking** - Manages pending actions and project tasks
4. **Proof of Concept** - Demonstrates MCP server capabilities for Om AI Solutions customers

## Project Structure

```
om-apex-mcp/
├── src/om_apex_mcp/
│   ├── __init__.py
│   ├── server.py          # Main MCP server
│   ├── tools/             # MCP tools (actions Claude can take)
│   │   ├── __init__.py
│   │   ├── context.py     # Get/update business context
│   │   ├── documents.py   # Search/read documents
│   │   └── tasks.py       # Task management
│   └── resources/         # MCP resources (data Claude can read)
│       ├── __init__.py
│       ├── company.py     # Company information
│       └── decisions.py   # Decision log
├── data/
│   ├── context/           # Business context JSON files
│   └── documents/         # Document store
├── tests/
├── docs/
│   └── BUILD_JOURNAL.md   # Development journey documentation
├── CLAUDE.md              # Context file for Claude Code
├── pyproject.toml         # Python project config
└── README.md
```

## Tech Stack

- **Python 3.11+** - Matching Om AI Solutions architecture decisions
- **MCP SDK** - Official Anthropic MCP Python SDK
- **FastAPI** - For any HTTP endpoints needed
- **Pydantic** - Data validation

## Getting Started

See [BUILD_JOURNAL.md](docs/BUILD_JOURNAL.md) for the complete development journey.

## Connecting to Claude

After building, this server connects to:
- Claude Desktop (Chat & Cowork) via `claude_desktop_config.json`
- Claude Code via its MCP configuration

---

*Part of Om Apex Holdings | Built by Nishad Tambe*
