# Om Apex MCP Server - Build Journal

A step-by-step record of building a Model Context Protocol (MCP) server for persistent memory across Claude interfaces.

**Author:** Nishad Tambe
**Started:** January 19, 2026
**Purpose:** Create unified memory for Om Apex Holdings across Claude Chat, Cowork, and Claude Code

---

## Table of Contents

1. [Day 1: Project Setup & Context Extraction](#day-1-project-setup--context-extraction)
2. [Day 2: Building the MCP Server (Pending)](#day-2-building-the-mcp-server)
3. [Day 3: Connecting to Claude (Pending)](#day-3-connecting-to-claude)

---

## Day 1: Project Setup & Context Extraction

**Date:** January 19, 2026
**Window Used:** Claude Desktop - Cowork
**Duration:** ~30 minutes

### The Problem We're Solving

Claude Desktop has three windows (Chat, Cowork, Code), but they don't share memory. Every new conversation starts fresh. For a business like Om Apex Holdings with multiple subsidiaries and ongoing projects, this means constantly re-uploading documents and re-explaining context.

### The Solution: Personal MCP Server

Build an MCP (Model Context Protocol) server that:
1. Stores business context (company structure, decisions, domain inventory)
2. Provides document access (searchable knowledge base)
3. Tracks tasks (pending actions across all projects)
4. Connects to ALL Claude interfaces (Chat, Cowork, AND Claude Code)

### Why This Matters for Om AI Solutions

This project serves double duty:
- **Immediate:** Solves Nishad's productivity problem
- **Strategic:** Proof of concept for the "Enterprise MCP Knowledge Base Server" product

### Steps Completed

#### Step 1: Create Project Structure

```bash
mkdir -p src/om_apex_mcp src/om_apex_mcp/tools src/om_apex_mcp/resources
mkdir -p data/context data/documents tests docs
```

**Resulting structure:**
```
om-apex-mcp/
├── src/om_apex_mcp/      # MCP server code
│   ├── tools/            # Actions Claude can take
│   └── resources/        # Data Claude can read
├── data/
│   ├── context/          # Business context JSON
│   └── documents/        # Document store
├── tests/
├── docs/
│   └── BUILD_JOURNAL.md  # You're reading it!
├── CLAUDE.md             # Context for Claude Code
└── README.md
```

#### Step 2: Extract Business Context

Uploaded `ClaudePlanFinal.zip` containing:
- `Om_Apex_Master_Decision_Log_v1.1.docx`
- `Om_Apex_Domain_Inventory.docx`
- Various other planning documents

Extracted key information into structured JSON files:

| File | Contents |
|------|----------|
| `company_structure.json` | Om Apex Holdings, Om Luxe Properties, Om AI Solutions - structure, ownership, products |
| `technology_decisions.json` | All tech stack decisions (Next.js, FastAPI, Supabase, LangGraph, etc.) |
| `domain_inventory.json` | 20 domains across 5 tiers with renewal strategy |
| `pending_tasks.json` | Current tasks and product development status |

#### Step 3: Create Documentation Files

- `README.md` - Project overview and structure
- `BUILD_JOURNAL.md` - This file (development journey)
- `CLAUDE.md` - Coming next (context for Claude Code)

### Key Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Server Language | Python | Matches Om AI Solutions tech stack; official MCP SDK available |
| Data Format | JSON | Human-readable, easy to edit, good for prototyping |
| Project Location | Local first | Easier to iterate; will push to GitHub when stable |
| Target Clients | All three | Chat, Cowork, AND Claude Code for true unified memory |

### What's Next (Day 2 - In Claude Code)

1. Set up Python environment (pyproject.toml, dependencies)
2. Build basic MCP server using official SDK
3. Implement tools:
   - `get_company_context` - Returns company structure
   - `get_decisions` - Returns technology decisions
   - `get_tasks` - Returns pending tasks
   - `add_task` / `complete_task` - Task management
4. Implement resources (read-only data access)
5. Test locally before configuring Claude Desktop

### Files Created Today

```
om-apex-mcp/
├── README.md                              ✅ Created
├── docs/BUILD_JOURNAL.md                  ✅ Created
├── data/context/company_structure.json    ✅ Created
├── data/context/technology_decisions.json ✅ Created
├── data/context/domain_inventory.json     ✅ Created
├── data/context/pending_tasks.json        ✅ Created
├── CLAUDE.md                              ⏳ Coming next
└── src/om_apex_mcp/server.py              ⏳ Day 2
```

### Lessons Learned

1. **Start with data structure** - Before building the server, we organized all business context into clean JSON. This makes the MCP server implementation much clearer.

2. **Document as you go** - This journal will become the how-to guide for customers.

3. **Use the right Claude window** - Cowork is great for document extraction and file organization; Claude Code will be better for the actual Python development.

---

## Day 2: Building the MCP Server

**Date:** January 19, 2026
**Window Used:** Claude Code
**Status:** ✅ Complete

### What We Built

A fully functional MCP server with 8 tools for managing Om Apex Holdings context.

### Steps Completed

#### Step 1: Create Python Project Configuration

Created `pyproject.toml` with:
- MCP SDK (`mcp>=1.0.0`)
- Pydantic for data validation
- python-dotenv for environment variables
- pytest for testing

```toml
[project]
name = "om-apex-mcp"
version = "0.1.0"
dependencies = [
    "mcp>=1.0.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
]
```

#### Step 2: Build the MCP Server

Created `src/om_apex_mcp/server.py` with:
- Server initialization using the MCP Python SDK
- JSON data loading/saving utilities
- Tool registration and handlers

**Core Architecture:**
```python
from mcp.server import Server
from mcp.server.stdio import stdio_server

server = Server("om-apex-mcp")

@server.list_tools()
async def list_tools() -> list[Tool]:
    # Returns list of available tools

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    # Handles tool execution
```

#### Step 3: Implement Tools

| Tool | Purpose |
|------|---------|
| `get_company_context` | Returns Om Apex Holdings structure, subsidiaries, ownership |
| `get_technology_decisions` | Returns full tech stack decisions |
| `get_domain_inventory` | Returns 20 domains with tier classifications |
| `get_pending_tasks` | Returns tasks (filterable by company, category, status) |
| `add_task` | Creates new task with auto-generated ID |
| `complete_task` | Marks a task as completed |
| `update_task_status` | Changes task status (pending/in_progress/completed) |
| `get_full_context` | Returns comprehensive summary for new conversations |

**Example Tool Implementation:**
```python
Tool(
    name="get_pending_tasks",
    description="Get all pending tasks across Om Apex Holdings companies",
    inputSchema={
        "type": "object",
        "properties": {
            "company": {"type": "string", "description": "Filter by company name"},
            "category": {"type": "string", "description": "Filter by category"},
            "status": {"type": "string", "description": "Filter by status"}
        },
        "required": []
    }
)
```

#### Step 4: Write Tests

Created `tests/test_server.py` with unit tests for:
- JSON data loading
- Company structure validation
- Subsidiary verification
- Task structure validation

**All 7 tests passing:**
```
tests/test_server.py::TestDataLoading::test_load_company_structure PASSED
tests/test_server.py::TestDataLoading::test_load_technology_decisions PASSED
tests/test_server.py::TestDataLoading::test_load_domain_inventory PASSED
tests/test_server.py::TestDataLoading::test_load_pending_tasks PASSED
tests/test_server.py::TestCompanyContext::test_subsidiaries PASSED
tests/test_server.py::TestCompanyContext::test_ownership PASSED
tests/test_server.py::TestTasks::test_task_structure PASSED
```

#### Step 5: Configure Claude Desktop

Created `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "om-apex": {
      "command": "/Users/nishad/.pyenv/versions/3.14.0/bin/python",
      "args": ["-m", "om_apex_mcp.server"],
      "cwd": "/Users/nishad/om-apex-projects/om-apex-mcp"
    }
  }
}
```

### Files Created Today

```
om-apex-mcp/
├── pyproject.toml                         ✅ Created
├── src/om_apex_mcp/
│   ├── __init__.py                        ✅ Updated
│   └── server.py                          ✅ Created (main server)
└── tests/
    └── test_server.py                     ✅ Created
```

### Key Implementation Details

1. **Data Loading:** Uses `pathlib.Path` for reliable path resolution regardless of working directory

2. **Tool Registration:** Uses async decorators (`@server.list_tools()`, `@server.call_tool()`)

3. **Task ID Generation:** Auto-increments from highest existing ID (TASK-001, TASK-002, etc.)

4. **Filtering:** `get_pending_tasks` supports optional filters for company, category, and status

5. **Full Context Tool:** `get_full_context` provides a summary ideal for starting new Claude conversations

### Lessons Learned

1. **MCP SDK is straightforward** - The official Python SDK makes it easy to create tools with proper typing and documentation

2. **Use absolute Python path** - In `claude_desktop_config.json`, use the full path to Python to avoid environment issues

3. **Test data loading first** - Before testing the full server, verify JSON files load correctly

4. **Include a "full context" tool** - This is invaluable for quickly bootstrapping context in new conversations

---

## Day 3: Connecting to Claude

**Date:** January 19, 2026
**Window Used:** Claude Desktop
**Status:** Ready for testing

### Next Steps

1. **Restart Claude Desktop** to load the new MCP configuration

2. **Test in Chat/Cowork** - Open a new conversation and verify the om-apex tools appear

3. **Test each tool:**
   - `get_full_context` - Should return company overview
   - `get_pending_tasks` - Should show current tasks
   - `add_task` - Create a test task
   - `complete_task` - Mark it done

4. **Test persistence** - Close Claude, reopen, verify data persists

### Troubleshooting

If tools don't appear:
1. Check Claude Desktop logs: `~/Library/Logs/Claude/`
2. Verify Python path in config matches: `which python` in terminal
3. Test server manually: `python -m om_apex_mcp.server`

---

## Appendix: Resources

- [MCP Documentation](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Claude Desktop MCP Configuration](https://modelcontextprotocol.io/quickstart/user)

---

*This journal is part of the Om Apex Holdings project. It will be converted to a polished how-to guide upon completion.*
