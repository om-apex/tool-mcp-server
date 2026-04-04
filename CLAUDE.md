# Om Apex MCP Server

Model Context Protocol server for persistent memory and tools across all Claude interfaces.

## 1. Product Vision

**Claude's toolbelt.** The MCP server gives Claude Code, Claude Desktop, and Claude Chat
access to Om Apex's task system, decisions, progress tracking, calendar, documents,
DNS management, and AI Quorum diagnostics — all through a unified tool interface.

Secondary purpose: **Proof of concept** demonstrating MCP capabilities for Om AI Solutions
customers (demo mode with 13 read-only tools, no API key required).

### What Quality Means
- Tools are reliable — every call returns a useful result or a clear error
- Tools are fast — response time under 2 seconds for reads, under 5 for writes
- Tools are discoverable — clear names, descriptions, and parameter docs

### What Success Means
- Claude Code sessions have full access to task/decision/progress state
- Session continuity works across multiple Claude instances and interfaces
- DNS Sentinel catches misconfigurations before they cause outages

## 2. Technical Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12 |
| MCP SDK | `mcp>=1.0.0` (official Anthropic Python SDK) |
| HTTP | FastAPI + Starlette + Uvicorn |
| Deployment | Docker on Render |

## 3. Architecture Overview

### Entry Points
- **stdio** (`om-apex-mcp`) — for Claude Desktop
- **HTTP** (`om-apex-mcp-http`) — for Claude Code, remote access

### 58 Tools Across 9 Modules

| Module | File | Tools | Purpose |
|--------|------|-------|---------|
| Context | `tools/context.py` | 8 | Company info, tech decisions, CLI status |
| Tasks | `tools/tasks.py` | 10 | Task CRUD, advance, history, schedule |
| Progress | `tools/progress.py` | 3 | Session logging to markdown files |
| Documents | `tools/documents.py` | 10 | Branded document generation |
| Calendar | `tools/calendar.py` | 3 | Google Calendar API |
| Handoff | `tools/handoff.py` | 2 | Session handoff history |
| AI Quorum | `tools/ai_quorum.py` | 10 | Query diagnostics and monitoring |
| Incidents | `tools/incidents.py` | 2 | Production incident tracking |
| DNS Sentinel | `tools/dns_sentinel.py` | 10 | DNS audit, auto-heal, change management |

### Data Sources
| Supabase Project | Ref | Used For |
|---------|-----|---------|
| Owner Portal | `hympgocuivzxzxllgmcy` | Tasks, decisions, handoff, documents, DNS |
| AI Quorum | `ixncscosicyjzlopbfiz` | Quorum diagnostics (sessions, turns, config) |
| Om Cortex | `sgcfettixymowtokytwk` | Production incidents |

External: Cloudflare API (DNS), Google Calendar API, Google Drive (documents).

### Key Patterns
- Modular tool registration — each module loads independently, one failure doesn't crash server
- Lazy singleton Supabase clients — graceful degradation if DB unavailable
- HTTP/1.1 forced (avoids stream resets)
- Demo mode: 13 read-only tools, no API key required

## 4. Project Infrastructure

| Resource | Location |
|----------|----------|
| Production URL | https://om-apex-mcp.onrender.com |
| Render service ID | `srv-d5snc28gjchc73b2se10` |
| GitHub repo | `om-apex/tool-mcp-server` |
| Local dev | `uvicorn src.om_apex_mcp.http_server:app --reload --port 8000` |
| Deploy | Merge main → production (Docker rebuild on Render) |

## 5. Key Files

- `src/om_apex_mcp/server.py` — stdio entry point (Claude Desktop)
- `src/om_apex_mcp/http_server.py` — HTTP entry point (Claude Code)
- `src/om_apex_mcp/tools/` — 9 tool modules
- `src/om_apex_mcp/supabase_client.py` — Owner Portal DB client
- `src/om_apex_mcp/quorum_supabase.py` — AI Quorum DB client
- `src/om_apex_mcp/cortex_supabase.py` — Om Cortex DB client
- `src/om_apex_mcp/cloudflare_client.py` — DNS API client
- `src/om_apex_mcp/auth.py` — API key auth + demo mode
- `src/om_apex_mcp/storage.py` — File storage abstraction

## 6. Project-Specific Rules

1. **Tool descriptions are the API** — users discover tools through descriptions.
   Every tool must have a clear, complete description with parameter docs.
2. **Graceful degradation** — if one Supabase project is down, other modules
   must still work. Never let a single client failure crash the server.
3. **Demo mode is incomplete** — auth middleware sets `demo_mode` flag but
   `call_tool()` doesn't enforce it. Demo users can call write tools (bug).
4. **Migration planned** — 28 tools (tasks, handoff, progress, context, incidents)
   planned for migration to Om Cortex (DEV-632). Documents (10) and DNS (10)
   stay in MCP server.

## 7. Future: Migration to Om Cortex (DEV-632)

See `products/om-cortex/docs/MCP-TO-CORTEX-MIGRATION.md` for the full plan.
28 tools move to Cortex as agent skills, 20 remain here (documents + DNS).
