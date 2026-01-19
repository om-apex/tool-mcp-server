# Om Apex MCP Server

## Project Overview

This is a Model Context Protocol (MCP) server for Om Apex Holdings. It provides persistent memory across all Claude interfaces (Chat, Cowork, Claude Code).

**Owner:** Nishad Tambe (nishad@omapex.com)
**Started:** January 19, 2026

## Business Context

### Om Apex Holdings LLC (Parent Company)
- **Ownership:** Nishad Tambe (50%) + Sumedha Tambe (50%)
- **Domain:** omapex.com

### Subsidiaries

1. **Om Luxe Properties LLC** - Vacation rentals
   - Currently operating "Perch in the Clouds" in Ellijay, GA
   - Managed by Home Team Luxury Rentals at 22% commission
   - Domain: omluxeproperties.com

2. **Om AI Solutions LLC** - AI-powered supply chain software
   - Domain: omaisolutions.com
   - Products planned:
     - Self-Learning WMS (Core - MVP Q2 2026)
     - Warehouse Maturity Study (Consulting)
     - AI Maturity Study (Consulting)
     - Voice Agents for SMBs
     - Enterprise MCP Knowledge Base Server ← THIS PROJECT IS THE POC

## Tech Stack Decisions

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 15 + Tailwind + Shadcn UI (Vercel) |
| Backend | Python + FastAPI (Render) |
| Database | Supabase (Postgres + RLS + Realtime) |
| AI Agents | LangGraph + Claude API |
| MCP | Official Python SDK |

## This Project's Purpose

1. **Immediate:** Solve Nishad's memory problem across Claude windows
2. **Strategic:** Proof of concept for Enterprise MCP Knowledge Base product
3. **Documentation:** Create a how-to guide for customers

## Project Structure

```
om-apex-mcp/
├── src/om_apex_mcp/
│   ├── server.py          # Main MCP server (TO BUILD)
│   ├── tools/             # MCP tools
│   └── resources/         # MCP resources
├── data/
│   ├── context/           # Business context JSON ✅ EXISTS
│   └── documents/         # Document store
├── docs/
│   └── BUILD_JOURNAL.md   # Development journal ✅ EXISTS
└── tests/
```

## Current Phase

**Day 1 Complete (Cowork):** Project structure, context extraction, documentation
**Day 2 Pending (Claude Code):** Build the actual MCP server

## What to Build Next

1. `pyproject.toml` with dependencies (mcp, fastapi, pydantic)
2. `src/om_apex_mcp/server.py` - Main MCP server
3. Tools to implement:
   - `get_company_context` - Returns company structure
   - `get_decisions` - Returns tech decisions
   - `get_tasks` - Returns pending tasks
   - `add_task` / `complete_task` - Task management
   - `search_documents` - Search knowledge base
4. Test the server locally
5. Configure Claude Desktop to connect

## Important Files

- `data/context/company_structure.json` - Company info
- `data/context/technology_decisions.json` - Tech stack decisions
- `data/context/domain_inventory.json` - 20 domains
- `data/context/pending_tasks.json` - Current tasks
- `docs/BUILD_JOURNAL.md` - Development journal (UPDATE THIS!)

## Commands Reference

```bash
# Install dependencies (after pyproject.toml exists)
pip install -e .

# Run MCP server for testing
python -m om_apex_mcp.server

# Run tests
pytest tests/
```

## Notes for Claude

- This project uses Python (matching Om AI Solutions architecture)
- Update BUILD_JOURNAL.md as you make progress
- The goal is both a working server AND comprehensive documentation
- Nishad plans to publish a how-to guide, so document everything clearly
