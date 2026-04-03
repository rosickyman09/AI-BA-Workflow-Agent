# ============================================================
#  MASTER COPILOT IMPLEMENTATION PROMPT
#  Dynamic Word Template Engine
#  版本：1.0 | 語言：Python + FastAPI
# ============================================================
# 使用方法：將此文件整個貼入 GitHub Copilot Chat / Cursor AI
# ============================================================


## 🎯 PROJECT OVERVIEW

You are implementing a **Dynamic Word Template Engine** backend system.
The system allows users to:
1. Upload Word (.docx) templates (with or without placeholders)
2. Upload source documents (PDF/DOCX/TXT)
3. Use an LLM to extract structured data from the source document
4. Automatically fill the Word template with extracted data
5. Download the completed Word document

The codebase has already been provided as separate Python files.
Your job is to integrate them into the existing project correctly.

---

## 📁 PROVIDED FILES (already written — DO NOT rewrite logic)

The following files are provided and should be placed into the project AS-IS:

| File | Role |
|------|------|
| `template_parser.py` | Parses any Word template to extract structure/placeholders |
| `llm_client.py` | Calls LLM (Claude/GPT/DeepSeek) and returns structured JSON |
| `document_filler.py` | Fills Word template with JSON data, preserving formatting |
| `template_db.py` | SQLite-based template storage with pre-parsed structure cache |
| `api_server.py` | FastAPI REST API server exposing all functionality |
| `main.py` | CLI entry point for local testing |

---

## 🗂️ STEP-BY-STEP IMPLEMENTATION TASKS

### TASK 1 — Project Structure Setup

Create the following folder structure inside the existing project:

```
your_project/
├── template_engine/          ← NEW: create this folder
│   ├── __init__.py           ← NEW: empty file
│   ├── template_parser.py    ← COPY from provided files
│   ├── llm_client.py         ← COPY from provided files
│   ├── document_filler.py    ← COPY from provided files
│   ├── template_db.py        ← COPY from provided files
│   ├── api_server.py         ← COPY from provided files
│   └── main.py               ← COPY from provided files
├── template_files/           ← NEW: auto-created at runtime for storing .docx templates
├── templates.db              ← NEW: auto-created at runtime (SQLite database)
├── requirements.txt          ← MODIFY: add the dependencies below
└── .env                      ← MODIFY: add API key variables
```

**Action:** Create the `template_engine/` folder and copy all provided `.py` files into it.
Create an empty `template_engine/__init__.py`.

---

### TASK 2 — Install Dependencies

Add these lines to `requirements.txt`:

```
python-docx>=1.1.2
docxtpl>=0.17.0
pdfplumber>=0.11.4
anthropic>=0.28.0
openai>=1.35.0
fastapi>=0.111.0
uvicorn>=0.30.1
python-multipart>=0.0.9
lxml>=5.2.2
```

Then run:
```bash
pip install -r requirements.txt
```

**Verify installation by running:**
```bash
python -c "from docx import Document; from anthropic import Anthropic; print('OK')"
```

---

### TASK 3 — Environment Variables

Add to `.env` file (create if not exists):

```env
# LLM Provider Keys (add whichever you use)
ANTHROPIC_API_KEY=your_anthropic_key_here
OPENAI_API_KEY=your_openai_key_here
DEEPSEEK_API_KEY=your_deepseek_key_here

# Storage paths (optional, defaults shown)
TEMPLATE_DB_PATH=templates.db
TEMPLATE_STORAGE_DIR=template_files
```

In `api_server.py`, ensure dotenv is loaded at the top:
```python
from dotenv import load_dotenv
load_dotenv()
```

If `python-dotenv` is not installed, add it to requirements.txt.

---

### TASK 4 — Fix Import Paths (IMPORTANT)

Because the files are now inside `template_engine/` folder,
**update all internal imports** in each file:

In `api_server.py`, change:
```python
# BEFORE
from template_db import TemplateDatabase
from llm_client import LLMClient
from document_filler import DocumentFiller
from main import extract_document_content

# AFTER
from template_engine.template_db import TemplateDatabase
from template_engine.llm_client import LLMClient
from template_engine.document_filler import DocumentFiller
from template_engine.main import extract_document_content
```

In `template_db.py`, change:
```python
# BEFORE
from template_parser import TemplateParser

# AFTER
from template_engine.template_parser import TemplateParser
```

In `main.py`, change:
```python
# BEFORE
from template_parser import TemplateParser
from llm_client import LLMClient
from document_filler import DocumentFiller

# AFTER
from template_engine.template_parser import TemplateParser
from template_engine.llm_client import LLMClient
from template_engine.document_filler import DocumentFiller
```

---

### TASK 5 — Run and Verify the API Server

Start the server:
```bash
cd your_project
python -m uvicorn template_engine.api_server:app --reload --port 8000
```

Open browser at: `http://localhost:8000/docs`
You should see the FastAPI Swagger UI with all endpoints listed.

**Expected endpoints:**
- `POST /templates/upload`
- `GET  /templates`
- `GET  /templates/{template_id}`
- `DELETE /templates/{template_id}`
- `POST /generate`
- `GET  /health`

---

### TASK 6 — Integration with Existing Frontend

Your existing frontend (the Generate URS / Requirement Document page) needs to call these APIs.

#### 6a. Template Upload (triggered by "+ Upload New Template")

```javascript
// Frontend code — upload template
async function uploadTemplate(file, name) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('name', name || file.name);

  const response = await fetch('/api/templates/upload', {
    method: 'POST',
    body: formData
  });
  const result = await response.json();
  // result.template_id — save this for later use
  return result;
}
```

#### 6b. Load Template List (for the "Select Template" dropdown)

```javascript
async function loadTemplates() {
  const response = await fetch('/api/templates');
  const data = await response.json();
  return data.templates; // array of { id, name, mode, created_at }
}
```

#### 6c. Generate Document (triggered by "Proceed - Generate Document")

```javascript
async function generateDocument(templateId, documentFile, llmProvider) {
  const formData = new FormData();
  formData.append('template_id', templateId);
  formData.append('document', documentFile);
  formData.append('llm_provider', llmProvider || 'anthropic');

  const response = await fetch('/api/generate', {
    method: 'POST',
    body: formData
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail);
  }

  // Download the returned .docx file
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'generated_document.docx';
  a.click();
}
```

---

### TASK 7 — Proxy API Routes (if using Next.js / Express)

If your frontend and backend are on different ports, add a proxy.

**For Next.js** (`next.config.js`):
```javascript
module.exports = {
  async rewrites() {
    return [
      { source: '/api/:path*', destination: 'http://localhost:8000/:path*' }
    ];
  }
};
```

**For Express.js**:
```javascript
const { createProxyMiddleware } = require('http-proxy-middleware');
app.use('/api', createProxyMiddleware({
  target: 'http://localhost:8000',
  changeOrigin: true
}));
```

---

### TASK 8 — Word Template Preparation Guide

Tell users to prepare their Word templates using `{{placeholder}}` syntax.

Example template content:
```
Project Name:    {{project_name}}
Client:          {{client_name}}
Date:            {{date}}
Prepared by:     {{prepared_by}}

Requirements Table:
| ID          | Requirement       | Priority     | Status     |
|-------------|-------------------|--------------|------------|
| {{req_id}}  | {{requirement}}   | {{priority}} | {{status}} |
```

If templates have NO placeholders, the system will still work —
it reads table headers and asks the LLM to fill based on context.

---

## ⚠️ KNOWN PITFALLS & HOW TO AVOID THEM

### Pitfall 1: Word splits placeholders across multiple XML runs
**Problem:** `{{client_name}}` might be stored as 3 separate runs in Word XML:
`{{` + `client_` + `name}}`
**Solution:** `document_filler.py` already handles this by merging run text
before replacement. Do NOT edit this logic.

### Pitfall 2: LLM returns markdown-wrapped JSON
**Problem:** LLM might return ` ```json { ... } ``` ` instead of raw JSON.
**Solution:** `llm_client.py` strips markdown fences automatically.

### Pitfall 3: Table rows not duplicating correctly
**Problem:** If your template table has only 1 data row with placeholders,
repeating row logic works. If there are 2+ template rows, the system picks
the FIRST row with placeholders.
**Solution:** Keep exactly 1 placeholder row in repeating tables.

### Pitfall 4: PDF text extraction fails
**Problem:** Scanned PDFs return empty text.
**Solution:** Add OCR support — install `pytesseract` and `pdf2image`,
then add an OCR fallback in `main.py`'s `extract_document_content()`.

### Pitfall 5: API key not found at runtime
**Problem:** `ANTHROPIC_API_KEY` not loaded.
**Solution:** Add `load_dotenv()` at the TOP of `api_server.py` before
any other imports from `template_engine`.

---

## ✅ QUICK VERIFICATION CHECKLIST

After implementation, verify each step:

- [ ] `python -c "from template_engine.template_parser import TemplateParser; print('OK')`
- [ ] `python -c "from template_engine.llm_client import LLMClient; print('OK')`
- [ ] Server starts: `uvicorn template_engine.api_server:app --reload`
- [ ] Swagger UI loads: `http://localhost:8000/docs`
- [ ] Upload a test .docx template via `/templates/upload`
- [ ] Verify template appears in `/templates` list
- [ ] Upload a test PDF + select template → call `/generate` → get .docx back
- [ ] Open generated .docx → confirm placeholders are replaced correctly

---

## 🔧 TESTING WITH CURL (no frontend needed)

```bash
# 1. Health check
curl http://localhost:8000/health

# 2. Upload a template
curl -X POST http://localhost:8000/templates/upload \
  -F "file=@my_template.docx" \
  -F "name=URS Template"

# 3. List templates
curl http://localhost:8000/templates

# 4. Generate document (replace TEMPLATE_ID with actual ID from step 2)
curl -X POST http://localhost:8000/generate \
  -F "template_id=TEMPLATE_ID" \
  -F "document=@source_document.pdf" \
  -F "llm_provider=anthropic" \
  -o output.docx

# 5. Open output.docx to verify
```

---

## 📌 SUMMARY OF WHAT COPILOT SHOULD DO

1. Create `template_engine/` folder + `__init__.py`
2. Copy all 6 provided `.py` files into it
3. Fix internal import paths (see Task 4)
4. Add dependencies to `requirements.txt` and install
5. Add API keys to `.env`
6. Add `load_dotenv()` to `api_server.py`
7. Start server and verify Swagger UI
8. Wire up frontend API calls (Tasks 6 + 7)
9. Test end-to-end with a real template + document
