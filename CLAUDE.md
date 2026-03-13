# Om Apex MCP Server

Model Context Protocol server providing persistent memory and tools across all Claude interfaces. 56 tools across 9 modules.

## Architecture
- **Language:** Python 3.12
- **MCP SDK:** `mcp>=1.0.0` (official Python SDK)
- **Entry point (stdio):** `src/om_apex_mcp/server.py` — for Claude Desktop
- **Entry point (HTTP):** `src/om_apex_mcp/http_server.py` — for Claude Code, remote access
- **Deployment:** Docker on Render (`srv-d5snc28gjchc73b2se10`)
- **URL:** https://om-apex-mcp.onrender.com

## Data Sources

| Project | Ref | Used For |
|---------|-----|----------|
| Owner Portal | `hympgocuivzxzxllgmcy` | Tasks, decisions, handoff, documents, DNS |
| AI Quorum | `ixncscosicyjzlopbfiz` | Quorum diagnostics (sessions, turns, config) |
| Om Cortex | `sgcfettixymowtokytwk` | Production incidents |

Also: Cloudflare API (DNS Sentinel), Google Calendar API, Google Drive (local or API).

## Tool Modules (59 tools)

| Module | File | Tools | Purpose |
|--------|------|-------|---------|
| Context | `tools/context.py` | 7 | Company info, tech stack, CLI status |
| Tasks | `tools/tasks.py` | 7 | Task CRUD via Supabase |
| Progress | `tools/progress.py` | 3 | Session logging to files |
| Documents | `tools/documents.py` | 11 | Document generation + branding |
| Calendar | `tools/calendar.py` | 3 | Google Calendar API |
| Handoff | `tools/handoff.py` | 2 | Cross-device session state |
| AI Quorum | `tools/ai_quorum.py` | 10 | Quorum product diagnostics |
| Incidents | `tools/incidents.py` | 2 | Production incident tracking |
| DNS Sentinel | `tools/dns_sentinel.py` | 10 | DNS audit, auto-heal, change mgmt |

## Reference Docs (in `docs/`)

| File | Contents |
|------|----------|
| `CLI-ACCESS-REFERENCE.md` | CLIs, project map, ports, config, gotchas |
| `DB-SCHEMA-QUICK-REF.md` | Table schemas for all Supabase projects |
| `TEAM-STRUCTURE.md` | Multi-agent coordination, roles, sizing (in `dotfiles/`) |
| `SESSION-OPS.md` | Session start flow, .zshrc reference, known quirks |

## Key Patterns
- Modular tool registration — each module loads independently, failure of one doesn't crash server
- Lazy singleton Supabase clients — no exceptions raised (returns None on failure)
- HTTP/1.1 forced to avoid stream resets
- Demo mode with 13 read-only tools (no API key required)
