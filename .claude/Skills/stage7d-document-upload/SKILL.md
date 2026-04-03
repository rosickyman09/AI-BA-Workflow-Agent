---
name: stage7d-document-upload
description: Implements the document upload module including file storage, Google Drive integration, ElevenLabs Scribe v2 speech-to-text, n8n webhook trigger, and status tracking. Use this skill when the user wants to build the document upload endpoint, store file metadata to PostgreSQL, upload files to Google Drive, trigger STT transcription via ElevenLabs, track processing status (PENDING → PROCESSING → COMPLETED), or wire up n8n webhook for document workflow automation. Trigger when the user mentions "document upload", "file upload", "STT", "speech to text", "ElevenLabs", "Google Drive upload", "n8n webhook", "upload endpoint", "transcript", "workflow_id", or wants to implement Stage 7D after real auth is working.
---

## Stage 7D — Agent Mode: Document Upload Module

### Purpose
Build the complete document upload pipeline: accept uploaded files via REST API, store metadata to PostgreSQL, upload files to Google Drive, trigger ElevenLabs Scribe v2 for speech-to-text transcription, and track processing status from PENDING through to COMPLETED.

> ⚠️ Do NOT change the architecture, docker-compose.yml, database schema, or port assignments. Implementation only.

---

### Prerequisites

- [ ] Stage 7C complete — real auth + RBAC working
- [ ] `backend/app/main.py` exists with RBAC middleware in place
- [ ] `docs/02c_workflow_design.md` exists (workflow for document processing)
- [ ] `docs/03_system_architecture.md` exists
- [ ] PostgreSQL running with `documents` and `workflow_status` tables
- [ ] Google Drive API credentials available (service account JSON)
- [ ] ElevenLabs API key available
- [ ] n8n running or webhook URL configured

---

### Step 1 — Switch to Agent Mode and Attach Input Files

1. Open Copilot Chat (`Ctrl+Shift+I` / `Cmd+Shift+I`)
2. Switch to **Agent Mode**
3. Attach all three input files:
   ```
   backend/app/main.py
   docs/02c_workflow_design.md
   docs/03_system_architecture.md
   ```
4. Use the full prompt in Step 2 below

---

### Step 2 — Copilot Prompt

Copy and paste the following prompt into Copilot Chat (Agent Mode):

```
Implement the Document Upload module for the backend service.

Task 1 — Upload Endpoint (POST /api/documents/upload):
- Accept multipart/form-data (file + metadata)
- Require authentication (use require_ba() RBAC dependency)
- Store document metadata to PostgreSQL documents table:
  {document_id, filename, file_type, project_id, uploaded_by, status: "PENDING", created_at}
- Upload file to Google Drive (service account auth)
- Return: {workflow_id, document_id, status: "PENDING"}

Task 2 — Trigger n8n Webhook:
- After successful upload, POST to n8n webhook URL
- Payload: {workflow_id, document_id, google_drive_url, file_type}
- Use env var: N8N_WEBHOOK_URL

Task 3 — ElevenLabs Scribe v2 STT:
- For audio/video files, call ElevenLabs Scribe v2 API
- Async: send request → receive webhook callback
- On callback, store transcript to PostgreSQL
- Update document status: PENDING → PROCESSING → COMPLETED

Task 4 — Status Tracking:
- GET /api/documents/{document_id}/status
  → return current status + progress
- Status flow: PENDING → PROCESSING → COMPLETED (or FAILED)

Constraints:
- Do NOT change docker-compose.yml
- Do NOT change database schema
- Do NOT change port assignments
- Keep all existing endpoints working
```

---

### Step 3 — Expected Output Files

Agent Mode must produce:

```
backend/app/
├── routers/
│   └── documents.py            ← Upload endpoint + status endpoint
├── services/
│   ├── google_drive.py         ← Google Drive upload service
│   ├── elevenlabs.py           ← ElevenLabs Scribe v2 STT service
│   └── n8n_webhook.py          ← n8n webhook trigger service
└── models/
    └── document.py             ← Document model / schema
```

---

### Step 4 — Environment Variables Required

Add to `.env.example`:

```
# Google Drive
GOOGLE_DRIVE_CREDENTIALS_PATH=./secrets/google_service_account.json
GOOGLE_DRIVE_FOLDER_ID=your_folder_id

# ElevenLabs
ELEVENLABS_API_KEY=your_api_key
ELEVENLABS_WEBHOOK_SECRET=your_webhook_secret

# n8n
N8N_WEBHOOK_URL=http://n8n:5678/webhook/document-upload
```

---

### Step 5 — Acceptance Tests (Must All Pass)

#### Test 1 — Upload a Document
```powershell
# Upload a file (requires BA or Admin token)
$token = "your_access_token"
$form = @{
    file = Get-Item "./test_document.pdf"
    project_id = "660e8400-e29b-41d4-a716-446655440000"
}
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:5000/api/documents/upload" `
  -Headers @{ Authorization = "Bearer $token" } `
  -Form $form
# Expected: { workflow_id, document_id, status: "PENDING" }
```

#### Test 2 — Check Status
```powershell
Invoke-RestMethod -Method GET `
  -Uri "http://localhost:5000/api/documents/{document_id}/status" `
  -Headers @{ Authorization = "Bearer $token" }
# Expected: { status: "PROCESSING" or "COMPLETED" }
```

#### Test 3 — RBAC Block (IT user cannot upload)
```powershell
# Use IT user token
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:5000/api/documents/upload" `
  -Headers @{ Authorization = "Bearer [IT_TOKEN]" }
# Expected: HTTP 403
```

#### Test 4 — Google Drive Confirmation
- Log into Google Drive
- Confirm uploaded file appears in the configured folder ✅

#### Test 5 — Status Progression
- Upload → check status = PENDING ✅
- Wait for n8n/ElevenLabs → check status = PROCESSING ✅
- After completion → check status = COMPLETED ✅

---

### Status Flow Reference

```
[Upload Received]
      ↓
   PENDING
      ↓ (n8n webhook triggered)
  PROCESSING
      ↓ (ElevenLabs callback received)
  COMPLETED
      ↓ (on any error)
   FAILED
```

---

### Output

```
backend/app/routers/documents.py      ← Upload + status endpoints
backend/app/services/google_drive.py  ← Google Drive service
backend/app/services/elevenlabs.py    ← ElevenLabs STT service
backend/app/services/n8n_webhook.py   ← n8n webhook trigger
```

---

### Checklist

- [ ] Agent Mode activated before submitting prompt
- [ ] All three input files attached
- [ ] `POST /api/documents/upload` endpoint created
- [ ] Multipart/form-data accepted (file + metadata)
- [ ] RBAC applied — require_ba() dependency used
- [ ] Document metadata saved to PostgreSQL
- [ ] File uploaded to Google Drive
- [ ] `workflow_id` returned in response
- [ ] n8n webhook triggered after upload
- [ ] ElevenLabs Scribe v2 called for audio/video files
- [ ] Transcript stored to PostgreSQL on callback
- [ ] `GET /api/documents/{id}/status` endpoint created
- [ ] Status flow: PENDING → PROCESSING → COMPLETED works
- [ ] All environment variables added to `.env.example`
- [ ] All 5 acceptance tests pass
- [ ] 🔒 All tests pass before proceeding to Stage 7E
