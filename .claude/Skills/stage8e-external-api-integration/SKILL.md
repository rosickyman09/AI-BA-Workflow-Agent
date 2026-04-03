---
name: stage8e-external-api-integration
description: Connects all external APIs to the production Railway deployment including ElevenLabs webhook, n8n workflows, Google Drive API, and Telegram Bot webhook. Use this skill when the user wants to configure ElevenLabs webhook URL for production, update n8n workflows with production URLs, set up Google Drive API service account, configure Telegram Bot webhook to point to Railway, or verify all external integrations work end-to-end. Trigger when the user mentions "ElevenLabs webhook", "n8n production", "Google Drive setup", "Telegram webhook", "external API", "API integration", "connect APIs production", or wants to implement Stage 8E after the frontend and gateway are live on Railway.
---

## Stage 8E — Manual + Ask Mode: External API Integration

### Purpose
Connect all external third-party APIs to the live Railway production environment: update ElevenLabs webhook to the Railway URL, reconfigure n8n workflows with production endpoints, set up Google Drive API service account, and register the Telegram Bot webhook with the Railway gateway URL.

> ⚠️ This stage is mostly manual configuration in external dashboards. Copilot guides the steps. Test each integration individually before marking complete.

---

### Prerequisites

- [ ] Stage 8D complete — production URL live at `https://[project].railway.app`
- [ ] `docs/02c_workflow_design.md` exists (workflow integration specs)
- [ ] All API accounts set up:
  - ElevenLabs account with Scribe v2 access
  - n8n running (Railway or external)
  - Google Cloud project with Drive API enabled
  - Telegram Bot created via BotFather

---

### Step 1 — Ask Mode: Get Integration Instructions

1. Open Copilot Chat (`Ctrl+Shift+I` / `Cmd+Shift+I`)
2. Use **Ask Mode**
3. Attach:
   ```
   docs/02c_workflow_design.md
   ```
4. Use the prompt in Step 2 below

---

### Step 2 — Copilot Prompt

```
Guide me through setting up all external API integrations
for the production Railway deployment at https://[project].railway.app

1. ElevenLabs webhook:
   - Set webhook URL to: https://[project].railway.app/api/elevenlabs/webhook
   - Verify webhook secret matches ELEVENLABS_WEBHOOK_SECRET env var
   - Test: upload audio → webhook fires → transcript stored

2. n8n workflows:
   - Update all webhook URLs to Railway production URL
   - Update Workflow C: Google Sheets connection
   - Update Workflow D: Telegram group target
   - Update Workflow E: Approval pending check URL
   - Verify all 3 workflows trigger correctly

3. Google Drive API:
   - Create/verify service account in Google Cloud Console
   - Enable Google Drive API
   - Download service account JSON
   - Base64 encode and set as GOOGLE_DRIVE_CREDENTIALS in Railway
   - Share target Drive folder with service account email
   - Test: upload file → appears in Drive folder

4. Telegram Bot webhook:
   - Call Telegram setWebhook API to point to Railway URL:
     https://api.telegram.org/bot[TOKEN]/setWebhook
     URL: https://[project].railway.app/api/telegram/webhook
   - Verify webhook is registered
   - Test: send /status to bot → receives response

Provide step-by-step instructions for each integration.
```

---

### Step 3 — Manual: ElevenLabs Webhook

1. Log into [elevenlabs.io](https://elevenlabs.io)
2. Go to **Settings** → **Webhooks**
3. Set webhook URL: `https://[project].railway.app/api/elevenlabs/webhook`
4. Copy webhook secret → set as `ELEVENLABS_WEBHOOK_SECRET` in Railway
5. Save and test

---

### Step 4 — Manual: n8n Workflow Updates

For each of the 3 workflows (C, D, E):

1. Open n8n dashboard
2. Edit workflow → find all HTTP Request nodes
3. Update URLs from `localhost` or old URLs to Railway production URL
4. Save and activate workflow
5. Manual trigger to verify

---

### Step 5 — Manual: Google Drive API

```bash
# Encode service account JSON for Railway
base64 -i service_account.json | tr -d '\n'
# Copy output → set as GOOGLE_DRIVE_CREDENTIALS in Railway Variables
```

Then share your Google Drive folder with the service account email:
`your-service-account@your-project.iam.gserviceaccount.com`

---

### Step 6 — Manual: Telegram Bot Webhook

```bash
# Register webhook
curl "https://api.telegram.org/bot[YOUR_BOT_TOKEN]/setWebhook" \
  -d "url=https://[project].railway.app/api/telegram/webhook"

# Verify registration
curl "https://api.telegram.org/bot[YOUR_BOT_TOKEN]/getWebhookInfo"
# Expected: url field shows Railway URL
```

---

### Step 7 — Acceptance Tests (Must All Pass)

#### Test 1 — ElevenLabs STT
- Upload an audio file via production UI
- Expected: transcript appears after processing ✅

#### Test 2 — n8n Workflow C
- Manually trigger Workflow C in n8n
- Expected: Telegram notification sent ✅

#### Test 3 — Google Drive
- Upload document via production UI
- Open Google Drive → confirm file appears in folder ✅

#### Test 4 — Telegram Bot
- Send `/status` to the Telegram bot
- Expected: response with current pending approvals count ✅

---

### Completion Checklist

| Integration | Configured | Tested | Status |
|---|---|---|---|
| ElevenLabs webhook | ☐ | ☐ | |
| n8n Workflow C updated | ☐ | ☐ | |
| n8n Workflow D updated | ☐ | ☐ | |
| n8n Workflow E updated | ☐ | ☐ | |
| Google Drive API service account | ☐ | ☐ | |
| Drive folder shared with service account | ☐ | ☐ | |
| Telegram webhook registered | ☐ | ☐ | |
| All 4 acceptance tests pass | ☐ | ☐ | |

---

### Output

```
ElevenLabs webhook → Railway ✅
n8n all 3 workflows → Railway URLs ✅
Google Drive API → service account connected ✅
Telegram Bot → webhook registered ✅
Ready for Stage 9A (Production Validation) ✅
```

---

### Checklist

- [ ] Ask Mode used for integration guidance
- [ ] `docs/02c_workflow_design.md` attached
- [ ] ElevenLabs webhook set to Railway production URL
- [ ] ELEVENLABS_WEBHOOK_SECRET matches between ElevenLabs and Railway
- [ ] n8n Workflow C updated and activated
- [ ] n8n Workflow D updated and activated
- [ ] n8n Workflow E updated and activated
- [ ] Google Cloud service account JSON base64 encoded in Railway
- [ ] Google Drive folder shared with service account email
- [ ] Telegram setWebhook called with Railway production URL
- [ ] Telegram getWebhookInfo confirms registration
- [ ] All 4 acceptance tests pass
- [ ] 🔒 All integrations working before proceeding to Stage 9A (Production Validation)!
