---
name: stage8a-railway-setup
description: Sets up a Railway cloud deployment project including GitHub connection, environment variables, and build configuration. Use this skill when the user wants to deploy to Railway, create a Railway project, connect a GitHub repository to Railway, configure all secret environment variables on Railway, or set up build settings for cloud deployment. Trigger when the user mentions "Railway", "Railway setup", "Railway project", "deploy to cloud", "Railway env vars", "Railway GitHub connect", "cloud deployment setup", or wants to configure the Railway platform before deploying any services.
---

## Stage 8A — Manual + Ask Mode: Railway Setup

### Purpose
Configure the Railway cloud platform for deployment: create a new Railway project, connect the GitHub repository, set all required environment variables (secrets), and configure build settings. This is the foundation for all subsequent Railway deployment stages.

> ⚠️ Never commit secrets to GitHub. All API keys and passwords must be set directly in Railway's Variables dashboard — not in code.

---

### Prerequisites

- [ ] Stage 7J complete — E2E testing all passing locally
- [ ] `docs/05_deployment_plan.md` exists (deployment design complete)
- [ ] GitHub repository exists with all code committed
- [ ] All API keys obtained (OpenRouter, DeepSeek, ElevenLabs, Telegram, Google, Qdrant)
- [ ] Railway account created at railway.app

---

### Step 1 — Manual: Create Railway Project

Perform these steps manually in the Railway dashboard:

1. Go to [railway.app](https://railway.app) and log in
2. Click **New Project**
3. Select **Deploy from GitHub repo**
4. Authorise Railway to access your GitHub account
5. Select your AI BA Agent repository
6. Railway will detect the project — **do not deploy yet**

---

### Step 2 — Ask Mode: Get Setup Guidance

Use Copilot in Ask Mode for step-by-step instructions:

1. Open Copilot Chat (`Ctrl+Shift+I` / `Cmd+Shift+I`)
2. Use **Ask Mode**
3. Attach the deployment plan:
   ```
   docs/05_deployment_plan.md
   ```
4. Use the prompt in Step 3 below

---

### Step 3 — Copilot Prompt

```
Based on the deployment plan, guide me through Railway setup:

1. Create Railway account and new project
2. Connect GitHub repository
3. Set ALL environment variables for each service:
   - DB_PASSWORD
   - JWT_SECRET
   - OPENROUTER_API_KEY
   - DEEPSEEK_API_KEY
   - ELEVENLABS_API_KEY
   - TELEGRAM_BOT_TOKEN
   - TELEGRAM_CHAT_ID
   - Google Drive credentials
   - QDRANT_API_KEY
   - N8N_API_KEY
4. Configure build settings per service
5. Set environment-specific variables (production vs dev)

Provide step-by-step instructions for the Railway dashboard.
```

---

### Step 4 — Manual: Set Environment Variables in Railway

In the Railway dashboard for each service:

1. Click on the service → **Variables** tab
2. Add each variable below:

#### All Services
| Variable | Description |
|---|---|
| `JWT_SECRET` | Strong random string (min 32 chars) |
| `ENVIRONMENT` | `production` |

#### auth_service
| Variable | Description |
|---|---|
| `DB_HOST` | Railway PostgreSQL internal URL |
| `DB_PORT` | 5432 |
| `DB_NAME` | railway |
| `DB_USER` | postgres |
| `DB_PASSWORD` | Railway-generated or custom |

#### backend
| Variable | Description |
|---|---|
| `AUTH_SERVICE_URL` | Railway auth_service internal URL |
| `RAG_SERVICE_URL` | Railway rag_service internal URL |
| `OPENROUTER_API_KEY` | Your OpenRouter key |
| `GOOGLE_DRIVE_CREDENTIALS` | Base64-encoded service account JSON |

#### rag_service
| Variable | Description |
|---|---|
| `ELEVENLABS_API_KEY` | Your ElevenLabs key |
| `DEEPSEEK_API_KEY` | Your DeepSeek key |
| `QDRANT_URL` | Railway Qdrant internal URL |
| `QDRANT_API_KEY` | Your Qdrant key |

#### Notification
| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | From BotFather |
| `TELEGRAM_CHAT_ID` | Target group/chat ID |

---

### Step 5 — Completion Checklist

Verify all items before proceeding to Step 22 (DB deployment):

| Item | Check |
|---|---|
| Railway project created | ☐ |
| GitHub repository connected | ☐ |
| `DB_PASSWORD` set in Railway | ☐ |
| `JWT_SECRET` set in Railway | ☐ |
| `OPENROUTER_API_KEY` set | ☐ |
| `DEEPSEEK_API_KEY` set | ☐ |
| `ELEVENLABS_API_KEY` set | ☐ |
| `TELEGRAM_BOT_TOKEN` set | ☐ |
| `TELEGRAM_CHAT_ID` set | ☐ |
| Google Drive credentials set | ☐ |
| `QDRANT_API_KEY` set | ☐ |
| No secrets committed to GitHub | ☐ |

---

### Output

```
Railway project ✅
GitHub connected ✅
All env vars set ✅
Ready for Step 22 (DB deployment) ✅
```

---

### Checklist

- [ ] Railway account created at railway.app
- [ ] New project created — deploy from GitHub
- [ ] GitHub repo connected and authorised
- [ ] Railway dashboard open — NOT deployed yet
- [ ] All secrets entered in Railway Variables (not in .env in repo)
- [ ] JWT_SECRET is a strong random string
- [ ] ENVIRONMENT set to `production`
- [ ] No `.env` file with real secrets committed to GitHub
- [ ] `.gitignore` includes `.env` and all `.env.*` variants
- [ ] All items in Step 5 checklist completed
- [ ] 🔒 All checklist items complete before proceeding to Stage 8B Railway DB!
