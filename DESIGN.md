# Om Apex MCP Server — Design Document

## Overview

Model Context Protocol (MCP) server providing persistent memory and tools across all Claude interfaces (Chat, Cowork, Claude Code). 42 tools across 7 modules for managing company context, tasks, decisions, documents, calendar, session handoffs, and AI Quorum diagnostics.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12 |
| MCP SDK | `mcp>=1.0.0` (official Python SDK) |
| HTTP Server | Starlette + uvicorn |
| Database | Supabase (2 projects: Owner Portal + AI Quorum) |
| File Storage | Local (Google Drive Desktop) or Google Drive API |
| Deployment | Docker on Render |
| Service ID | `srv-d5snc28gjchc73b2se10` |
| URL | `https://om-apex-mcp.onrender.com` |

## Directory Structure

```
mcp-server/
├── src/om_apex_mcp/
│   ├── __init__.py
│   ├── server.py              # Stdio MCP server (Claude Desktop)
│   ├── http_server.py         # HTTP server (Claude Code, remote)
│   ├── auth.py                # API key auth + demo mode
│   ├── storage.py             # Storage backend abstraction
│   ├── supabase_client.py     # Supabase client (tasks, decisions, handoff)
│   ├── quorum_supabase.py     # AI Quorum DB integration
│   └── tools/                 # 7 tool modules
│       ├── __init__.py        # ToolModule dataclass
│       ├── helpers.py         # Shared utilities, storage init
│       ├── context.py         # Company context (7 tools)
│       ├── tasks.py           # Task CRUD (5 tools)
│       ├── progress.py        # Daily progress (3 tools)
│       ├── documents.py       # Document generation (11 tools)
│       ├── calendar.py        # Google Calendar (3 tools)
│       ├── handoff.py         # Session handoff (2 tools)
│       └── ai_quorum.py       # Quorum diagnostics (10 tools)
├── data/
│   ├── context/               # JSON fallback files
│   └── demo/                  # Demo data (bundled in Docker)
├── docs/
│   ├── CLI-ACCESS-REFERENCE.md
│   ├── DB-SCHEMA-QUICK-REF.md
│   └── TEAM-PROTOCOL.md
├── pyproject.toml
├── Dockerfile
├── render.yaml
└── CLAUDE.md
```

## Server Modes

| Mode | Entry Point | Transport | Usage |
|------|-------------|-----------|-------|
| Stdio | `om-apex-mcp` | stdin/stdout JSON-RPC | Claude Desktop (local) |
| HTTP | `om-apex-mcp-http` | Streamable HTTP | Claude Code, remote access |

### HTTP Endpoints
- `GET /health` — Health check (public, no auth)
- `POST /mcp/*` — Streamable HTTP MCP endpoint (requires auth)

## Tool Modules (41 tools)

| Module | Tools | Key Functions |
|--------|-------|--------------|
| **Context** (7) | get_full_context, get_company_context, get_technology_decisions, get_domain_inventory, get_cli_status, get_claude_instructions, get_decisions_history | Company info, tech stack, CLI status |
| **Tasks** (6) | get_pending_tasks, get_task_queue, add_task, complete_task, update_task_status, update_task | Task CRUD via Supabase |
| **Progress** (3) | get_daily_progress, add_daily_progress, search_daily_progress | Session logging to files |
| **Documents** (11) | generate_branded_html, generate_company_document, view/list/create/update/delete templates, get_brand_assets, list_company_configs, sync_templates | Document generation + branding |
| **Calendar** (3) | list_calendar_events, create_calendar_event, delete_calendar_event | Google Calendar API |
| **Handoff** (2) | get_session_handoff, save_session_handoff | Cross-device session state |
| **AI Quorum** (10) | quorum_status, sessions, turns, trace, logs, performance, costs, user, stage config (get/update) | Diagnostics for AI Quorum product |

## Storage Backends

### LocalStorage (Default)
- Uses Google Drive Desktop sync path
- Mac: `~/Library/CloudStorage/GoogleDrive-.../Shared drives/om-apex/mcp-data`
- Windows: `H:/Shared drives/om-apex/mcp-data`
- Fallback: `~/.om-apex-mcp/data`

### GoogleDriveStorage (Remote)
- Uses Google Drive API with service account
- For Docker/Render deployment
- Env: `GOOGLE_SERVICE_ACCOUNT_FILE` or `GOOGLE_SERVICE_ACCOUNT_JSON`

## Supabase Integration

### Owner Portal Project (`hympgocuivzxzxllgmcy`)
Used for: tasks, decisions, session handoff, document templates, company configs

### AI Quorum Project (`ixncscosicyjzlopbfiz`)
Used for: quorum diagnostics (sessions, turns, model calls, config)

### Resilience Pattern
- Lazy singleton client initialization
- No exceptions raised (returns None on failure)
- Graceful fallback to JSON files
- HTTP/1.1 forced (avoids stream resets)

## Authentication (`auth.py`)

| Level | Access | Mechanism |
|-------|--------|-----------|
| Full | All 42 tools | `X-API-Key` header with valid key |
| Demo | 13 read-only tools | `OM_APEX_DEMO_MODE=true`, no key |
| None | 401 error | No key, demo disabled |

## Tool Registration

Modular phase-based initialization:
1. **Storage init** — Backend created, Supabase checked
2. **Module registration** — Each `register()` returns `ToolModule(tools, handler, reading_tools, writing_tools)`
3. **Context module** — Aggregates tool counts, registered first
4. **Server handlers** — `list_tools()` unions all modules, `call_tool()` dispatches

Each module loads independently — failure of one module doesn't crash the server.

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `OM_APEX_API_KEY_NISHAD` | Nishad's API key |
| `OM_APEX_API_KEY_SUMEDHA` | Sumedha's API key |
| `OM_APEX_DEMO_MODE` | Enable demo access |
| `SUPABASE_URL` | Owner Portal DB |
| `SUPABASE_SERVICE_KEY` | Owner Portal admin key |
| `QUORUM_SUPABASE_URL` | AI Quorum DB |
| `QUORUM_SUPABASE_SERVICE_KEY` | AI Quorum admin key |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Drive API credentials |
| `GOOGLE_SHARED_DRIVE_ID` | Shared drive ID |
| `PORT` | HTTP server port (default: 8000) |

## Deployment

- **Platform**: Render (Docker)
- **Plan**: Starter
- **Region**: Ohio
- **Health check**: `GET /health`
- **Build**: Docker multi-stage (python:3.12-slim)
- **Demo data**: Bundled in `data/demo/` for container
