# Next Steps - Claude Code Session

## How to Continue in Claude Code

### Step 1: Open the Project

```bash
cd /Users/nishad/om-apex-projects/om-apex-mcp
claude
```

Or open Claude Code and navigate to this folder.

### Step 2: Start the Conversation

Claude Code will automatically read `CLAUDE.md` and have full context. You can start with:

> "Let's continue building the MCP server. I'm coming from Cowork where we set up the project structure and extracted business context. Let's build the actual server now."

### Step 3: What Claude Code Should Build

1. **pyproject.toml** - Python project configuration with dependencies:
   - `mcp` (official MCP Python SDK)
   - `pydantic` (data validation)
   - `python-dotenv` (environment variables)

2. **src/om_apex_mcp/server.py** - Main MCP server with:
   - Connection handling
   - Tool registration
   - Resource registration

3. **Tools to implement:**
   ```python
   @tool
   def get_company_context() -> dict:
       """Returns Om Apex Holdings company structure"""

   @tool
   def get_technology_decisions() -> dict:
       """Returns all tech stack decisions"""

   @tool
   def get_pending_tasks() -> list:
       """Returns current pending tasks"""

   @tool
   def add_task(description: str, category: str, company: str) -> dict:
       """Adds a new task"""

   @tool
   def complete_task(task_id: str) -> dict:
       """Marks a task as complete"""
   ```

4. **Test the server locally**

5. **Configure Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
   ```json
   {
     "mcpServers": {
       "om-apex": {
         "command": "python",
         "args": ["-m", "om_apex_mcp.server"],
         "cwd": "/Users/nishad/om-apex-projects/om-apex-mcp"
       }
     }
   }
   ```

### Step 4: Update Documentation

After each significant step, update `docs/BUILD_JOURNAL.md` with:
- What was built
- Any decisions made
- Code snippets
- Lessons learned

---

## Quick Reference

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Context for Claude Code (auto-read) |
| `docs/BUILD_JOURNAL.md` | Development journal |
| `data/context/*.json` | Business context data |
| `src/om_apex_mcp/` | MCP server code |

## Success Criteria

The MCP server is complete when:
1. ✅ Server starts without errors
2. ✅ Claude Desktop connects to it
3. ✅ All three windows (Chat, Cowork, Code) can access company context
4. ✅ Tasks can be added/completed from any window
5. ✅ BUILD_JOURNAL.md is complete enough to become a how-to guide
