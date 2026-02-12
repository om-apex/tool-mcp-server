# CLI Access Reference

> Last updated: 2026-02-12

## Installed CLIs

| CLI | Command | Auth Status | Account |
|-----|---------|-------------|---------|
| Supabase | `supabase` | Authenticated | nishad@omapex.com |
| Vercel | `vercel` | Logged in | nishad-apex |
| Render | `render` | Logged in | nishad@omapex.com |
| Cloudflare | `wrangler` | Token-based | `~/om-apex/config/.env.cloudflare` |
| GitHub | `gh` | Logged in | nishad-apex |
| Google Cloud | `gcloud` | Logged in | nishad@omapex.com |
| HubSpot | `hs` | Needs `hs account auth` | Browser-based |

## Supabase Projects

| Project | Ref | Database |
|---------|-----|----------|
| AI Quorum | `ixncscosicyjzlopbfiz` | Sessions, LLM orchestration, models |
| Owner Portal | `hympgocuivzxzxllgmcy` | Tasks, decisions, companies, handoff |

**CLI notes:**
- `supabase db push` to push migrations (no `--sql` flag)
- Migration files must use `YYYYMMDDHHMMSS` timestamp prefix
- AI Quorum is linked in: `~/om-apex/products/ai-quorum/`
- Owner Portal NOT linked — use temp dir workaround to push migrations
- `supabase migration repair --status applied/reverted <version>` to fix sync issues

**Owner Portal workaround:**
```bash
mkdir -p /tmp/sb-push && cd /tmp/sb-push
cp -r ~/om-apex/websites/apex/supabase .
supabase init --force 2>/dev/null || true
supabase link --project-ref hympgocuivzxzxllgmcy
supabase db push
```

## Deployed URLs

| Project | URL | Platform |
|---------|-----|----------|
| AI Quorum Frontend | https://frontend-eosin-one-68.vercel.app | Vercel |
| AI Quorum Backend | Render service `srv-d5snc28gjchc73b2se10` | Render |
| Owner Portal | https://om-apex-site.vercel.app | Vercel |

## Local Development Ports

| Project | Port | Folder |
|---------|------|--------|
| AI Quorum | 3000 | `products/ai-quorum/` |
| Owner Portal | 3001 | `websites/apex/` |
| AI Solutions | 3002 | `websites/ai-solutions/` |
| Supply Chain | 3003 | `websites/supply-chain/` |
| Luxe Properties | 3004 | `websites/luxe-properties/` |

## Start/Stop Commands

**AI Quorum (backend + frontend):**
```bash
startquorum   # alias — kills existing, starts backend (8000) + frontend (3000)
stopquorum    # alias — kills all uvicorn, next-server, port processes
```
Scripts: `~/om-apex/products/ai-quorum/scripts/startquorum.sh` / `stopquorum.sh`
Logs: `/tmp/quorum-backend.log`, `/tmp/quorum-frontend.log`

**Other projects:** `cd <project-folder> && npm run dev`

## Centralized Config

**Location:** `/Users/nishad/om-apex/config/` (Mac) | `C:/Users/14042/om-apex/config/` (Windows)

| File | Contents |
|------|----------|
| `.env.supabase` | AI Quorum Supabase credentials |
| `.env.supabase.omapex-dashboard` | Owner Portal Supabase credentials |
| `.env.openrouter` | OpenRouter API key |
| `.env.providers` | OpenAI, Anthropic, Google, xAI, Perplexity API keys |
| `.env.factcheck` | Google Fact Check, Tavily API keys |
| `.env.cloudflare` | Cloudflare API token |

**Sync scripts:**
- Mac: `~/om-apex/scripts/sync-env.sh`
- Windows: `~/om-apex/scripts/sync-env.ps1`

## Project Map

```
om-apex/
├── products/ai-quorum/          # AI Quorum (Next.js + FastAPI)
├── websites/
│   ├── apex/                    # Owner Portal (Next.js, port 3001)
│   ├── ai-solutions/            # omaisolutions.com
│   ├── luxe-properties/         # omluxeproperties.com
│   └── supply-chain/            # omsupplychain.com
├── tools/
│   ├── mcp-server/              # MCP Server (Python)
│   └── crm-integration/         # HubSpot + Retell
├── config/                      # All API keys (.env files)
├── docs/                        # Reference docs (this file)
├── shared/                      # Shared assets, templates, configs
├── scripts/                     # Deploy and sync scripts
└── archive/                     # Archived projects
```

## GitHub Organization

**Org:** `om-apex` (https://github.com/om-apex)

| Repo | Project |
|------|---------|
| `tool-mcp-server` | MCP Server |
| `ai-quorum` | AI Quorum product |
| `om-apex-site` | Owner Portal website |

## Common Render Commands

```bash
render logs -r srv-d5snc28gjchc73b2se10 --limit 50 -o text
render deploys create srv-d5snc28gjchc73b2se10 --confirm -o json
render services -o json
```
**Workspace:** Om Apex Holdings (`tea-d5smshe3jp1c738d4s9g`)

## Deploy Scripts

```bash
~/om-apex/scripts/deploy-staging.sh [quorum|portal|all]
```

## Local Development Setup Checklist

When setting up a new laptop or onboarding a project for local dev, complete these steps:

### 1. Supabase Auth Redirect URLs
Each Supabase project with auth must allow localhost redirects. Without this, OAuth login redirects to production instead of localhost.

| Supabase Project | Dashboard → Authentication → URL Configuration |
|---|---|
| Owner Portal (`hympgocuivzxzxllgmcy`) | Add `http://localhost:3001/**` |
| AI Quorum (`ixncscosicyjzlopbfiz`) | Add `http://localhost:3000/**` |

**Required redirect URLs per project** (all should be present):
- `http://localhost:<port>/**` (local dev)
- `https://<production-url>/**` (deployed site)
- `https://*-<vercel-team>.vercel.app/**` (Vercel preview deploys, if needed)

### 2. Environment Files
Run the sync script to pull `.env.local` files from central config:
- **Mac:** `~/om-apex/scripts/sync-env.sh`
- **Windows:** `~/om-apex/scripts/sync-env.ps1`

### 3. Port Verification
Before starting a dev server, confirm the assigned port is free:
```bash
lsof -ti:<port>  # should return nothing
```

### 4. New Project Checklist
When creating a new Supabase project or new local dev project:
- [ ] Add localhost redirect URL to Supabase Auth settings
- [ ] Add production redirect URL to Supabase Auth settings
- [ ] Create `.env.local` with Supabase credentials
- [ ] Add env file to `~/om-apex/config/` for central management
- [ ] Update `sync-env.sh` / `sync-env.ps1` to include new project
- [ ] Add port assignment to this doc (Local Development Ports table)
- [ ] Test OAuth login flow locally before deploying

## Diagnostic Scripts

### Model Connectivity Test (ping_models.py)

**Location:** `products/ai-quorum/backend/scripts/ping_models.py`

Standalone script to verify connectivity to all AI model providers. Sends a minimal prompt ("Reply with exactly: PONG") to each provider and reports status, latency, and response. Does not modify any application code or state.

**Usage:**
```bash
cd ~/om-apex/products/ai-quorum/backend

# Ping all 5 providers in parallel
OM_APEX_CONFIG_DIR=~/om-apex/config python scripts/ping_models.py

# Ping a single provider
python scripts/ping_models.py openai
python scripts/ping_models.py anthropic
python scripts/ping_models.py google
python scripts/ping_models.py xai
python scripts/ping_models.py perplexity
```

**Models tested:**

| Provider | Model ID | Friendly Name |
|----------|----------|---------------|
| OpenAI | `openai/gpt-4o` | GPT-4o |
| Anthropic | `anthropic/claude-3-5-sonnet-20241022` | Claude Sonnet 4.5 |
| Google | `google/gemini-2.0-flash-001` | Gemini 2.0 Flash |
| xAI | `x-ai/grok-4-1-fast-reasoning` | Grok 4 Fast |
| Perplexity | `perplexity/sonar-pro` | Sonar Pro |

**Requirements:** `OM_APEX_CONFIG_DIR` env var set (points to `~/om-apex/config/`) or API keys in `backend/.env`

**Example output:**
```
Pinging 5 model(s)...

Model                                      Status   Latency    Response
------------------------------------------------------------------------------------------
  GPT-4o (OpenAI)                          OK       491ms      PONG
  Claude Sonnet 4.5 (Anthropic)            OK       1829ms     PONG
  Gemini 2.0 Flash (Google)                OK       581ms      PONG
  Grok 4 Fast (xAI)                        OK       2152ms     PONG
  Sonar Pro (Perplexity)                   OK       1508ms     PONG

Result: 5/5 models responding
```

**When to use:**
- Before a demo — verify all models are reachable
- After API key rotation — confirm new keys work
- When models are timing out in production — isolate connectivity vs application issues
- After deploy — sanity check backend can reach all providers

## Gotchas

1. **Owner Portal Supabase** — NOT linked locally. Must use temp dir workaround (see above)
2. **Owner Portal IDs** — `companies` table uses TEXT ids (slugs like `"om-apex-holdings"`), NOT BIGSERIAL
3. **Owner Portal migrations** — Old ones use non-timestamp names (001, 002, etc.) — `migration repair` fails on these
4. **Never delete a `cd` target directory** in current session — breaks Bash tool permanently
5. **AI Quorum backend** — uses direct provider APIs (OpenAI, Anthropic, Google, xAI, Perplexity). OpenRouter is legacy/fallback only
6. **Cloudflare** — requires token from env: `CLOUDFLARE_API_TOKEN=$(grep CLOUDFLARE_API_TOKEN ~/om-apex/config/.env.cloudflare | cut -d= -f2) wrangler whoami`
7. **Google Cloud** — may need `gcloud auth login` to refresh tokens
8. **OAuth redirects to production from localhost** — Missing localhost in Supabase Auth redirect URLs. See "Local Development Setup Checklist" above

## MCP Server

**Code:** `~/om-apex/tools/mcp-server/` (Mac) | `C:/Users/14042/om-apex/tools/mcp-server/` (Windows)
**Entry point:** `src/om_apex_mcp/server.py`
**Data:** MCP reads/writes to Supabase (Owner Portal project) for tasks, decisions, handoff
**Shared Drive:** `~/Library/CloudStorage/GoogleDrive-nishad@omapex.com/Shared drives/om-apex/` (Mac) | `H:/Shared drives/om-apex/` (Windows)
