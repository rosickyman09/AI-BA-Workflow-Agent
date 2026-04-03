---
name: stage7h-notification
description: Implements the notification module including Telegram Bot integration and three n8n automated workflows (daily backlog scan, weekly digest, approval reminder). Use this skill when the user wants to set up Telegram notifications, build a Telegram bot, create n8n workflow automations, implement scheduled cron jobs, send daily backlog alerts, generate weekly digest reports, or trigger approval reminder notifications. Trigger when the user mentions "Telegram", "Telegram bot", "n8n workflow", "notification", "daily backlog", "weekly digest", "approval reminder", "cron", "scheduled notification", or wants to implement Stage 7H after the approval workflow is working.
---

## Stage 7H — Agent Mode: Notification Module

### Purpose
Build the complete notification system: a Telegram Bot for real-time notifications and queries, and three n8n automated workflows — daily backlog scan, weekly digest report, and approval reminder — to keep teams informed without manual effort.

> ⚠️ Do NOT change the architecture, docker-compose.yml, or port assignments. Implementation only.

---

### Prerequisites

- [ ] Stage 7G complete — approval workflow working
- [ ] `docs/02c_workflow_design.md` exists (Workflow C, D, E definitions)
- [ ] `docs/03_system_architecture.md` exists
- [ ] Telegram Bot token available (from BotFather)
- [ ] n8n running (port 5678)
- [ ] Google Sheets accessible (for backlog data source)

---

### Step 1 — Switch to Agent Mode and Attach Input Files

1. Open Copilot Chat (`Ctrl+Shift+I` / `Cmd+Shift+I`)
2. Switch to **Agent Mode**
3. Attach both input files:
   ```
   docs/02c_workflow_design.md
   docs/03_system_architecture.md
   ```
4. Use the full prompt in Step 2 below

---

### Step 2 — Copilot Prompt

Copy and paste the following prompt into Copilot Chat (Agent Mode):

```
Implement the Notification Module.

Task 1 — Telegram Bot:
- Send notifications to configured chat/group
- Receive and respond to queries from users
- Commands to support:
  /status → show pending approvals count
  /backlog → show today's overdue items
  /help → list commands
- Use python-telegram-bot library
- Env var: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

Task 2 — n8n Workflow C: Daily Backlog Scan
- Cron trigger: 8:00 AM daily (Mon-Fri)
- Scan Google Sheets for overdue action items
- For each overdue item, send Telegram notification to owner
- Format: "⚠️ Overdue: [item] assigned to [owner] — due [date]"

Task 3 — n8n Workflow D: Weekly Digest
- Cron trigger: Friday 5:00 PM
- Aggregate all action items completed this week
- Aggregate all pending approvals
- Generate summary and send to team Telegram group
- Format: "📊 Weekly Summary — Completed: N | Pending: M"

Task 4 — n8n Workflow E: Approval Reminder
- Event trigger: approval pending > 2 days
- Alert the assigned approver via Telegram
- Include: document name, pending since date, approve link
- Repeat daily until actioned

Create:
- backend/app/services/telegram_bot.py
- backend/app/services/notification.py
- n8n/workflow_c_backlog.json
- n8n/workflow_d_digest.json
- n8n/workflow_e_reminder.json

Do NOT change architecture or docker-compose.yml.
```

---

### Step 3 — Expected Output Files

```
backend/app/services/
├── telegram_bot.py             ← Telegram Bot setup + command handlers
└── notification.py             ← Notification dispatcher service

n8n/
├── workflow_c_backlog.json     ← Daily backlog scan workflow
├── workflow_d_digest.json      ← Weekly digest workflow
└── workflow_e_reminder.json    ← Approval reminder workflow
```

---

### Step 4 — Environment Variables Required

Add to `.env.example`:

```
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_CHAT_ID=your_group_or_chat_id

# n8n
N8N_BASE_URL=http://n8n:5678
N8N_API_KEY=your_n8n_api_key

# Google Sheets (for Workflow C)
GOOGLE_SHEETS_ID=your_spreadsheet_id
GOOGLE_SHEETS_RANGE=Backlog!A:F
```

---

### Step 5 — Acceptance Tests (Must All Pass)

#### Test 1 — Telegram Bot Responds
- Send `/status` to the bot
- Expected: response with pending approval count ✅

#### Test 2 — Manual Notification Send
```powershell
$token = "your_access_token"
$body = '{"message":"Test notification","type":"info"}'
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:5000/api/notifications/send" `
  -Headers @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" } `
  -Body $body
# Expected: { sent: true }
```

#### Test 3 — n8n Workflow C Imported
- Open n8n dashboard at http://localhost:5678
- Confirm workflow_c_backlog is imported ✅
- Manually trigger → confirm Telegram message sent ✅

#### Test 4 — n8n Workflow D Imported
- Confirm workflow_d_digest is imported ✅
- Confirm cron is set to Friday 5 PM ✅

#### Test 5 — Approval Reminder Triggered
- Create approval → set created_at to 3 days ago
- Trigger workflow_e_reminder manually
- Confirm Telegram alert sent ✅

---

### n8n Workflow Reference

| Workflow | Trigger | Action | Frequency |
|---|---|---|---|
| C — Daily Backlog | Cron: 8 AM Mon-Fri | Scan Sheets → Telegram | Daily |
| D — Weekly Digest | Cron: Fri 5 PM | Aggregate → Telegram | Weekly |
| E — Approval Reminder | Event: pending > 2d | Alert approver | Daily until done |

---

### Output

```
backend/app/services/telegram_bot.py    ← Bot + commands
backend/app/services/notification.py   ← Dispatcher
n8n/workflow_c_backlog.json             ← n8n Workflow C
n8n/workflow_d_digest.json              ← n8n Workflow D
n8n/workflow_e_reminder.json            ← n8n Workflow E
```

---

### Checklist

- [ ] Agent Mode activated before submitting prompt
- [ ] Both input files attached
- [ ] `telegram_bot.py` created with /status, /backlog, /help commands
- [ ] `notification.py` dispatcher service created
- [ ] `POST /api/notifications/send` endpoint created
- [ ] Workflow C JSON exported/created (daily backlog, 8 AM cron)
- [ ] Workflow D JSON exported/created (weekly digest, Fri 5 PM cron)
- [ ] Workflow E JSON exported/created (approval reminder, event trigger)
- [ ] All workflows imported into n8n
- [ ] All environment variables added to `.env.example`
- [ ] All 5 acceptance tests pass
- [ ] Workflow D + E confirmed as the sub-workflows from the requirements doc
- [ ] 🔒 All tests pass before proceeding to Stage 7I
