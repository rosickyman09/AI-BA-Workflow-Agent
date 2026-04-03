---
name: stage8d-railway-frontend-deploy
description: Deploys the frontend and gateway to Railway with TLS and HTTPS redirect. Use this skill when the user wants to deploy a Next.js or React frontend to Railway, set up an Nginx gateway on Railway, configure TLS certificates, enable HTTP to HTTPS redirect, or verify the production URL is accessible. Trigger when the user mentions "deploy frontend Railway", "Railway Next.js", "Railway gateway", "Railway TLS", "Railway HTTPS", "Railway production URL", "Railway Nginx", or wants to implement Stage 8D after backend services are healthy on Railway.
---

## Stage 8D — Agent Mode: Railway Frontend + Gateway Deployment

### Purpose
Deploy the frontend application and Nginx gateway to Railway, configure TLS via Railway's automatic certificate management, and verify the production URL is accessible over HTTPS with correct HTTP→HTTPS redirect.

> ⚠️ Deploy gateway LAST — after frontend is healthy. The production URL becomes live at this step.

---

### Prerequisites

- [ ] Stage 8C complete — all 3 backend services healthy on Railway
- [ ] `docs/05_deployment_plan.md` exists
- [ ] `NEXT_PUBLIC_API_URL` value ready (Railway backend URL)
- [ ] Frontend code committed and pushed to GitHub
- [ ] `gateway/nginx.conf` exists with routing rules

---

### Step 1 — Switch to Agent Mode and Attach Input File

1. Open Copilot Chat (`Ctrl+Shift+I` / `Cmd+Shift+I`)
2. Switch to **Agent Mode**
3. Attach:
   ```
   docs/05_deployment_plan.md
   ```
4. Use the full prompt in Step 2 below

---

### Step 2 — Copilot Prompt

```
Deploy frontend and gateway to Railway.

Task 1 — Frontend Deployment:
- Root directory: frontend/
- Build command: npm run build
- Start command: npm start (or serve built files)
- Required env vars:
  NEXT_PUBLIC_API_URL=[Railway backend URL]
  NEXT_PUBLIC_AUTH_URL=[Railway auth_service URL]
  NEXT_PUBLIC_RAG_URL=[Railway rag_service URL]
- Health check: GET / → HTTP 200

Task 2 — Gateway Deployment (Nginx):
- Root directory: gateway/
- Use Dockerfile to build Nginx image
- Update nginx.conf to use Railway service internal URLs
- TLS: handled by Railway automatically
- HTTP → HTTPS redirect: configure in nginx.conf

Task 3 — Verification:
- Frontend accessible: https://[project].railway.app
- Login page loads
- TLS certificate valid (padlock in browser)
- HTTP → HTTPS redirect working

Provide Railway dashboard step-by-step instructions.
```

---

### Step 3 — Update nginx.conf for Railway

Before deploying gateway, update `gateway/nginx.conf` to use Railway internal service URLs:

```nginx
upstream backend {
    server [backend-railway-internal-url]:5000;
}

upstream auth {
    server [auth-railway-internal-url]:5001;
}

upstream rag {
    server [rag-railway-internal-url]:5002;
}

server {
    listen 80;
    
    # HTTP → HTTPS redirect
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    
    location /api/ {
        proxy_pass http://backend;
    }
    
    location /auth/ {
        proxy_pass http://auth;
    }
    
    location /rag/ {
        proxy_pass http://rag;
    }
    
    location / {
        proxy_pass http://frontend:3000;
    }
}
```

---

### Step 4 — Manual: Deploy Frontend on Railway

1. Railway dashboard → **New Service** → **GitHub Repo**
2. Root directory: `frontend/`
3. Build: `npm run build`
4. Start: `npm start`
5. Set `NEXT_PUBLIC_API_URL` to Railway backend URL
6. Deploy → wait for green status
7. Verify: `curl https://[frontend-url]/` → HTTP 200

---

### Step 5 — Manual: Deploy Gateway on Railway

1. Railway dashboard → **New Service** → **GitHub Repo**
2. Root directory: `gateway/`
3. Railway detects Dockerfile automatically
4. Set environment variables (internal service URLs)
5. Deploy → wait for green status

---

### Step 6 — Acceptance Tests (Must All Pass)

#### Test 1 — Production URL Accessible
```bash
curl https://[project].railway.app
# Expected: HTML response (login page), HTTP 200
```

#### Test 2 — TLS Valid
- Open `https://[project].railway.app` in browser
- Expected: padlock icon shown, no certificate warning ✅

#### Test 3 — HTTP → HTTPS Redirect
```bash
curl -I http://[project].railway.app
# Expected: 301 redirect to https://
```

#### Test 4 — Login Works on Production
- Navigate to `https://[project].railway.app`
- Login with `admin@ai-ba.local` / `password123`
- Expected: successful login, redirected to dashboard ✅

---

### Output

```
Frontend live at Railway ✅
Gateway live at Railway ✅
Production URL: https://[project].railway.app ✅
TLS working ✅
HTTP → HTTPS redirect working ✅
Ready for Stage 8E (External API Integration) ✅
```

---

### Checklist

- [ ] Agent Mode used for deployment instructions
- [ ] `docs/05_deployment_plan.md` attached
- [ ] `NEXT_PUBLIC_API_URL` set to Railway backend URL
- [ ] `NEXT_PUBLIC_AUTH_URL` set to Railway auth_service URL
- [ ] Frontend deployed and accessible
- [ ] Frontend build (npm run build) successful
- [ ] nginx.conf updated with Railway internal service URLs
- [ ] Gateway deployed using Dockerfile
- [ ] TLS certificate valid (Railway manages automatically)
- [ ] HTTP → HTTPS redirect configured and working
- [ ] Production URL accessible in browser
- [ ] Login page loads on production
- [ ] Login test passes on production
- [ ] All 4 acceptance tests pass
- [ ] Production URL saved for Stage 8E and Stage 9A
- [ ] 🔒 All tests pass before proceeding to Stage 8E!
