# Om Apex Deployment Playbook

**All agents (Claude, Cursor, Codex, Gemini) must read this before any deploy.**

This playbook covers all Om Apex products and services. It defines the branch strategy, service map, deploy checklists, verification procedures, and rollback rules that apply portfolio-wide. Feature-specific runbooks are linked at the bottom.

---

## Core Rules

1. **Branch strategy is universal** — `main` → staging, `main` → `production` → production. No exceptions.
2. **Verify with the Render API, not just `/health`** — `/health` confirms the service is up, not which commit is running. Use the deploys API to confirm your commit message is live.
3. **Manual redeploy re-runs the last built commit** — it does NOT pick up new commits. Ensure your commit is on the branch the service watches before triggering.
4. **PUT replaces all env vars** — Render's `PUT /env-vars` is a full replace, not a patch. Always send the complete set or you will lose existing vars.
5. **Pushing to `main` alone does not deploy production** — merge `main` → `production` and push to trigger production auto-deploy.
6. **Required env vars must be verified on every new backend** — missing `DOCX_SERVICE_URL` or `GOTENBERG_URL` silently breaks DOCX/PDF export with no obvious error.

---

## Branch Strategy

```
main ──────────────────────────────────────────► staging auto-deploys
  │
  └─── merge main→production ──────────────────► production auto-deploys
```

Applies to: all Render backend services, all Vercel frontend projects, `tool-docx-service`.

---

## Service Map

### AI Quorum

| Service | URL | Platform | Service/Project ID | Repo | Branch | Health/Verification |
|---------|-----|----------|--------------------|------|--------|---------------------|
| Backend (staging) | `product-ai-quorum.onrender.com` | Render | `srv-d60m0r63jp1c73a8fthg` | `om-apex/product-ai-quorum` | `main` | `/health` |
| Backend (production) | `ai-quorum-backend-prod.onrender.com` | Render | `srv-d7cnpbv7f7vs73c955bg` | `om-apex/product-ai-quorum` | `production` | `/health` |
| Frontend (staging) | `staging.aiquorum.ai` | Vercel | `prj_yP011XY2ZPT4Dpouacpv5Uxl3xfX` | `om-apex/product-ai-quorum` | `main` | Load page |
| Frontend (production) | `aiquorum.ai` | Vercel | `prj_o4xCreJuBKjiIl3OpDOh0Im79q90` | `om-apex/product-ai-quorum` | `production` | Load page |
| Supabase (staging) | `ixncscosicyjzlopbfiz.supabase.co` | Supabase | `ixncscosicyjzlopbfiz` | — | — | Supabase dashboard |
| Supabase (production) | `mljvfepuhgwogoeolhrd.supabase.co` | Supabase | `mljvfepuhgwogoeolhrd` | — | — | Supabase dashboard |
| Gotenberg (staging) | `om-gotenberg.onrender.com` | Render (Docker) | `srv-d7bgjcfkijhs73amc42g` | Docker: `omapex/gotenberg-brand-fonts:staging` | — | `/health` |
| Gotenberg (production) | `ai-quorum-gotenberg-prod.onrender.com` | Render (Docker) | `srv-d7cnpjnaqgkc73b1g6kg` | Docker: `omapex/gotenberg-brand-fonts:production` | — | `/health` |

**Config files:** staging → `backend/.env.render` | production → `~/om-apex/config/.env.ai-quorum-production`

### Websites

| Service | URL | Platform | Repo | Branch | Notes |
|---------|-----|----------|------|--------|-------|
| omapex.com | `omapex.com` | Vercel | `om-apex/website-apex` | `main` | Next.js, port 3001 local |
| omaisolutions.com | `omaisolutions.com` | Vercel | `om-apex/website-ai-solutions` | `main` | Next.js, port 3002 local |
| omsupplychain.com | `omsupplychain.com` | Vercel | `om-apex/website-supply-chain` | `main` | Next.js, port 3003 local |
| omluxeproperties.com | `omluxeproperties.com` | Vercel | `om-apex/website-luxe-properties` | `main` | Next.js, port 3004 local |

### Owner Portal

| Service | URL | Platform | Service/Project ID | Repo | Branch | Health/Verification |
|---------|-----|----------|--------------------|------|--------|---------------------|
| Frontend | `portal.omapex.com` | Vercel | — | `om-apex/owner-portal` | `main` | Load page |
| Supabase | — | Supabase | `hympgocuivzxzxllgmcy` | — | — | Supabase dashboard |

### Om Cortex

| Service | URL | Platform | Service/Project ID | Repo | Branch | Health/Verification |
|---------|-----|----------|--------------------|------|--------|---------------------|
| Backend | `om-cortex.onrender.com` | Render | `srv-d67jupngi27c739uj4ag` | `om-apex/product-om-cortex` | `production` | `/health` |

### Shared Services

| Service | URL | Platform | Service/Project ID | Repo | Branch | Health/Verification |
|---------|-----|----------|--------------------|------|--------|---------------------|
| om-docx-service | `om-docx-service.onrender.com` | Render (Docker) | `srv-d769na0gjchc73859t1g` | `om-apex/tool-docx-service` | **`production`** | `/health` |
| MCP Server | `om-apex-mcp.onrender.com` | Render | `srv-d5snc28gjchc73b2se10` | `om-apex/mcp-server` | `production` | — |

> **om-docx-service critical note:** Deploys from `production` branch, NOT `main`. Pushing to `main` does nothing. See deploy checklist below.

---

## Required Env Vars

### AI Quorum Backend (both staging and production)

Missing any of these silently breaks DOCX/PDF export:

| Variable | Staging | Production |
|----------|---------|------------|
| `DOCX_SERVICE_URL` | `https://om-docx-service.onrender.com` | `https://om-docx-service.onrender.com` |
| `GOTENBERG_URL` | `https://om-gotenberg.onrender.com` | `https://ai-quorum-gotenberg-prod.onrender.com` |
| `GOTENBERG_TIMEOUT_SECONDS` | `120` | `120` |

**Verify env vars (Render API):**
```bash
source ~/om-apex/config/.env.render-api
curl -s -H "Authorization: Bearer $RENDER_API_KEY" \
  "https://api.render.com/v1/services/<SERVICE_ID>/env-vars" \
  | python3 -c "import sys,json; [print(v['envVar']['key'],'=',v['envVar']['value']) for v in json.load(sys.stdin) if v['envVar']['key'] in ('DOCX_SERVICE_URL','GOTENBERG_URL','GOTENBERG_TIMEOUT_SECONDS')]"
```

### Om Cortex (for social publishing)

| Variable | Notes |
|----------|-------|
| `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET` | LinkedIn OAuth app |
| `X_CLIENT_ID` / `X_CLIENT_SECRET` | X OAuth app |
| `CORTEX_OAUTH_ENCRYPTION_KEY` | Token encryption |
| `CORTEX_BASE_URL` | Self-reference |

### Owner Portal (for Content Studio)

| Variable | Notes |
|----------|-------|
| `CORTEX_BASE_URL` | Points to Om Cortex |
| `CORTEX_GATEWAY_TOKEN` | Auth to Om Cortex |

---

## Deploy Checklists

### Backend change (Render — any service)
- [ ] Code committed and pushed to `main`
- [ ] For production: `main` merged to `production` branch and pushed
- [ ] Render shows deploy `live` with your commit message — verify via API:
  ```bash
  source ~/om-apex/config/.env.render-api
  curl -s -H "Authorization: Bearer $RENDER_API_KEY" \
    "https://api.render.com/v1/services/<SERVICE_ID>/deploys?limit=1" \
    | python3 -c "import sys,json; d=json.load(sys.stdin)[0]['deploy']; print(d['status'], d['updatedAt'][:19], d.get('commit',{}).get('message','')[:80])"
  ```
- [ ] Health check returns expected response
- [ ] Required env vars verified (new environments only)

### om-docx-service change (special multi-repo process)
- [ ] Edit `tools/shared-libs/om_docx/` files
- [ ] `pytest` passes in `tools/shared-libs/` — all tests green
- [ ] Sync: `cp tools/shared-libs/om_docx/report_generator.py tools/docx-service/om_docx/report_generator.py`
- [ ] Commit `tools/shared-libs` first, push to `main`
- [ ] Commit `tools/docx-service`, push to `main`
- [ ] Merge `main` → `production` in `tools/docx-service` and push:
  ```bash
  cd ~/om-apex/tools/docx-service
  git checkout production && git merge main --ff-only && git push origin production && git checkout main
  ```
- [ ] Verify via Render API that `srv-d769na0gjchc73859t1g` shows your commit as `live`
- [ ] Smoke test: export a real DOCX and verify key markers in `document.xml`

### Frontend change (Vercel — any project)
- [ ] Code committed and pushed to `main`
- [ ] For production: `main` merged to `production` and pushed
- [ ] Vercel build succeeds (check Vercel dashboard or `vercel ls`)
- [ ] Spot-check the changed UI in browser

### Gotenberg Docker image change
- [ ] Dockerfile or fonts changed in `docker/` directory
- [ ] Push to `main` → GitHub Actions builds `:staging` + `:latest` automatically
- [ ] For production: push to `production` branch → builds `:production` tag
- [ ] **Manual Render dashboard**: confirm service uses correct tag (API cannot update image tags)
  - Staging: `:staging` | Production: `:production`
- [ ] Test PDF export after font changes

---

## How to Verify a Deploy Is Actually Live

Three levels — use in order:

```bash
# 1. Render API — tells you exact commit running (definitive)
source ~/om-apex/config/.env.render-api
curl -s -H "Authorization: Bearer $RENDER_API_KEY" \
  "https://api.render.com/v1/services/<SERVICE_ID>/deploys?limit=1" \
  | python3 -c "import sys,json; d=json.load(sys.stdin)[0]['deploy']; print(d['status'], d['updatedAt'][:19], d.get('commit',{}).get('message','')[:80])"

# 2. Health check — confirms service is up (NOT which code version)
curl -s https://<service-url>/health

# 3. Functional smoke test — verify the actual changed behavior works end-to-end
```

---

## How to Trigger a Manual Redeploy

```bash
source ~/om-apex/config/.env.render-api
curl -s -X POST -H "Authorization: Bearer $RENDER_API_KEY" \
  "https://api.render.com/v1/services/<SERVICE_ID>/deploys" \
  -H "Content-Type: application/json" \
  -d '{"clearCache":"do_not_clear"}'
```

> **Warning:** Re-runs the last built commit. Does NOT pull new commits. Ensure your commit is on the branch the service watches first.

---

## Rollback Rules

- **Render backend:** In Render dashboard → service → Deploys → click "Rollback" on the previous deploy. Or revert the git commit and push.
- **Vercel frontend:** In Vercel dashboard → project → Deployments → promote a previous deployment to production.
- **om-docx-service:** Revert the commit in `tool-docx-service`, merge to `production` branch, push. Render auto-deploys the reverted version.
- **DNS (post-cutover):** Revert Cloudflare CNAME to previous Vercel URL. Propagates within ~60 seconds.
- **Do not delete OAuth records** during a UI rollback unless token corruption is confirmed.

---

## Feature-Specific Runbooks

Feature-specific deploy procedures that are too detailed for this playbook:

- **FEATURE-713** — Create Production Environment (AI Quorum DNS cutover)
  - See: `products/ai-quorum/docs/tasks/FEATURE-713/REQ-04.md`

- **FEATURE-742** — Content Studio, social publishing, Om Cortex integration
  - See: `websites/portal/docs/tasks/FEATURE-742/DEPLOY-742.md`
