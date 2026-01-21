# Setting Up Om Apex MCP Server on a Second Laptop

This guide helps set up the Om Apex MCP server on Sumedha's laptop (or any additional machine) to share context across both devices.

## Prerequisites

- macOS with Homebrew installed
- Python 3.10+ installed
- Claude Code CLI installed (`npm install -g @anthropic-ai/claude-code`)
- Access to the Om Apex Google Drive

## Step 1: Clone the MCP Server Repository

```bash
# Create directory structure
mkdir -p ~/om-apex/om-ai
cd ~/om-apex/om-ai

# Clone the repository
git clone https://github.com/nishad-apex/om-apex-mcp.git
cd om-apex-mcp
```

## Step 2: Install the MCP Server

```bash
# Install the package in editable mode
pip install -e .

# Verify installation
python -c "import om_apex_mcp; print('OK')"
```

## Step 3: Set Up Google Drive for Shared Data

The MCP server stores context in JSON files. To share data between laptops, we use Google Drive.

### 3a. Install Google Drive for Desktop
1. Download from https://www.google.com/drive/download/
2. Sign in with the Om Apex Google account
3. Enable "Mirror files" or "Stream files" for the Om Apex shared drive

### 3b. Create the MCP Data Folder in Google Drive
If not already created, create this folder structure in Google Drive:
```
Om Apex/
└── mcp-data/
    ├── company_structure.json
    ├── technology_decisions.json
    ├── domain_inventory.json
    └── pending_tasks.json
```

### 3c. Find Your Google Drive Path
The path depends on how Google Drive is configured. Common paths:
```bash
# Check which path exists on your system:
ls ~/Library/CloudStorage/

# It will be something like:
# GoogleDrive-sumedha@omapex.com
# or
# GoogleDrive-nishad@omapex.com
```

## Step 4: Configure Claude Code MCP Server

Add the MCP server using the Claude CLI. Replace the paths with the correct values for the user:

```bash
# Add the om-apex MCP server with Google Drive data path
claude mcp add om-apex --scope user \
  -e OM_APEX_DATA_DIR="/Users/YOUR_USERNAME/Library/CloudStorage/GoogleDrive-YOUR_EMAIL@omapex.com/My Drive/om-apex/mcp-data" \
  -- python -m om_apex_mcp.server
```

**Example for Sumedha's laptop:**
```bash
claude mcp add om-apex --scope user \
  -e OM_APEX_DATA_DIR="/Users/sumedha/Library/CloudStorage/GoogleDrive-sumedha@omapex.com/My Drive/om-apex/mcp-data" \
  -- python -m om_apex_mcp.server
```

**Verify the server was added:**
```bash
claude mcp list
```

You should see:
```
om-apex: python -m om_apex_mcp.server - ✓ Connected
```

## Step 5: Create the Global CLAUDE.md

Create `~/CLAUDE.md` with the following content:

```markdown
# Global Claude Context - Om Apex Holdings

## Session Start Protocol

**IMPORTANT:** At the beginning of every conversation, automatically call `mcp__om-apex__get_full_context` to load the Om Apex Holdings context. Do this before responding to the user's first message.

This provides:
- Company structure (Om Apex Holdings, Om Luxe Properties, Om AI Solutions)
- Technology stack decisions
- Domain inventory
- Pending tasks

## Quick Reference

**Owners:** Nishad Tambe & Sumedha Tambe
**Email:** nishad@omapex.com
**MCP Server:** om-apex (provides persistent context across all Claude sessions)

## Session End Protocol

When the user says "let's end this session" (or similar phrases like "wrap up", "save our work", "end session"), Claude should:

1. **Review the entire conversation** and identify:
   - Any decisions made that should be recorded
   - Any new tasks that came up
   - Any tasks that were completed or worked on

2. **Summarize findings** to the user:
   - "I found X decisions, Y new tasks, and Z completed tasks from our session"
   - List each item briefly

3. **Get confirmation** from the user, then call the MCP tools:
   - `add_decision` for each decision (with area, decision, rationale, company)
   - `add_task` for each new task
   - `complete_task` for each completed task

4. **Confirm** everything was persisted successfully

This ensures nothing is lost between sessions.

## Available MCP Tools

### Reading Context
- `get_full_context` - Get everything (use at session start)
- `get_company_context` - Company structure only
- `get_technology_decisions` - Tech stack decisions
- `get_decisions_history` - All decisions with rationale (filterable)
- `get_domain_inventory` - Domain list
- `get_pending_tasks` - Tasks (filterable by company, category, status)

### Writing Context
- `add_task` - Add a new task
- `complete_task` - Mark a task complete
- `update_task_status` - Change task status (pending/in_progress/completed)
- `add_decision` - Record a decision with reasoning

## Companies

1. **Om Apex Holdings LLC** - Parent holding company
2. **Om Luxe Properties LLC** - Vacation rentals (Perch in the Clouds)
3. **Om AI Solutions LLC** - AI-powered supply chain software
```

## Step 6: Test the Setup

```bash
# Start Claude Code
claude

# In Claude, ask:
# "What MCP tools do you have available?"

# Then ask:
# "get_full_context"

# You should see the Om Apex Holdings context
```

## Step 7: Verify Sync

1. On one laptop, add a test task:
   > "Add a task: Test sync between laptops - for Om Apex Holdings, category Administrative, priority Low"

2. On the other laptop, check:
   > "get_full_context"

3. The test task should appear on both machines (may take a few seconds for Google Drive to sync)

## Troubleshooting

### MCP Server Not Found
```bash
# Verify the package is installed
pip show om-apex-mcp

# If not found, reinstall
cd ~/om-apex/om-ai/om-apex-mcp
pip install -e .
```

### Data Not Syncing
1. Check Google Drive is running and synced
2. Verify the `OM_APEX_DATA_DIR` path is correct
3. Check the files exist in Google Drive

### Claude Can't Find MCP Tools
1. Restart Claude Code after config changes
2. Run `claude mcp list` to verify server is configured
3. Run Claude with debug: `claude --mcp-debug`

## Updating the MCP Server

When updates are made to the MCP server code:

```bash
cd ~/om-apex/om-ai/om-apex-mcp
git pull origin main
pip install -e .
# Restart Claude Code
```
