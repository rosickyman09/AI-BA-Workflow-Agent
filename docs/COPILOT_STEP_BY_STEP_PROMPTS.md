# ============================================================
#  COPILOT BITE-SIZED TASK PROMPTS
#  逐步執行版本 — 每次只貼一個 Prompt 入 Copilot Chat
# ============================================================


## ════════════════════════════════════════════════════════════
## PROMPT #1 — 建立資料夾結構
## 適用時機：第一步，甚麼都未做
## ════════════════════════════════════════════════════════════

```
I am building a Dynamic Word Template Engine.
Please create the following folder structure in my project root:

1. Create folder: template_engine/
2. Create empty file: template_engine/__init__.py
3. Create folder: template_files/  (for storing uploaded .docx templates)

Do not create any other files yet.
After creating, show me the folder structure using a tree diagram.
```


## ════════════════════════════════════════════════════════════
## PROMPT #2 — 安裝依賴套件
## 適用時機：資料夾建立後
## ════════════════════════════════════════════════════════════

```
Add the following packages to my requirements.txt file.
If requirements.txt doesn't exist, create it.
Then run pip install -r requirements.txt and show me the output.

Packages to add:
python-docx>=1.1.2
docxtpl>=0.17.0
pdfplumber>=0.11.4
anthropic>=0.28.0
openai>=1.35.0
fastapi>=0.111.0
uvicorn>=0.30.1
python-multipart>=0.0.9
lxml>=5.2.2
python-dotenv>=1.0.0

After installing, verify with:
python -c "from docx import Document; import anthropic; import fastapi; print('All packages OK')"
```


## ════════════════════════════════════════════════════════════
## PROMPT #3 — 設置環境變量
## 適用時機：套件安裝後
## ════════════════════════════════════════════════════════════

```
Set up environment variables for my project.

1. If .env file doesn't exist, create it.
2. Add these variables to .env (do NOT overwrite existing content):

ANTHROPIC_API_KEY=your_anthropic_key_here
OPENAI_API_KEY=your_openai_key_here
DEEPSEEK_API_KEY=your_deepseek_key_here
TEMPLATE_DB_PATH=templates.db
TEMPLATE_STORAGE_DIR=template_files

3. If .gitignore exists, make sure .env is listed in it.
   If .gitignore doesn't exist, create it with just: .env

Show me the .env file content (mask the key values with ***) and confirm .gitignore is updated.
```


## ════════════════════════════════════════════════════════════
## PROMPT #4 — 複製 PY 文件並修正 Import 路徑
## 適用時機：已下載所有 6 個 .py 文件到本地
## 使用方法：同時把此 Prompt + 6個py文件一齊貼給 Copilot
## ════════════════════════════════════════════════════════════

```
I have 6 Python files that form a Word template engine.
I need you to:

1. Copy all 6 files into the template_engine/ folder:
   - template_parser.py → template_engine/template_parser.py
   - llm_client.py      → template_engine/llm_client.py
   - document_filler.py → template_engine/document_filler.py
   - template_db.py     → template_engine/template_db.py
   - api_server.py      → template_engine/api_server.py
   - main.py            → template_engine/main.py

2. Fix ALL internal imports in each file.
   Change any import like:
     from template_parser import ...
     from llm_client import ...
     from document_filler import ...
     from template_db import ...
     from main import ...
   To:
     from template_engine.template_parser import ...
     from template_engine.llm_client import ...
     etc.

3. At the TOP of template_engine/api_server.py, add these two lines
   BEFORE any other imports from template_engine:
     from dotenv import load_dotenv
     load_dotenv()

4. Verify all files are in the right place by listing template_engine/ contents.

Show me each file's updated import section after changes.
```


## ════════════════════════════════════════════════════════════
## PROMPT #5 — 啟動服務器並測試
## 適用時機：文件都已複製和修正 import 後
## ════════════════════════════════════════════════════════════

```
Start the FastAPI server and verify it works.

1. Run this command:
   python -m uvicorn template_engine.api_server:app --reload --port 8000

2. If there are import errors, fix them and show me what was changed.

3. Once running, test the health endpoint:
   curl http://localhost:8000/health

4. Open http://localhost:8000/docs in browser — confirm these endpoints exist:
   - POST /templates/upload
   - GET  /templates
   - GET  /templates/{template_id}
   - DELETE /templates/{template_id}
   - POST /generate
   - GET  /health

If any endpoint is missing or there are errors, show me the full error message.
```


## ════════════════════════════════════════════════════════════
## PROMPT #6 — 測試模板上傳功能
## 適用時機：Server 已啟動
## ════════════════════════════════════════════════════════════

```
Test the template upload functionality.

1. Create a simple test Word document called test_template.docx with this content:
   - Title: "Test Report"
   - A line: "Client: {{client_name}}"
   - A line: "Date: {{date}}"
   - A simple table with header row: "Item | Quantity | Price"
     and one data row: "{{item_name}} | {{quantity}} | {{price}}"

   Use python-docx to create this file programmatically.

2. Upload it to the API:
   curl -X POST http://localhost:8000/templates/upload \
     -F "file=@test_template.docx" \
     -F "name=Test Template"

3. Show me the full API response including the template_id.

4. Call GET /templates to confirm it appears in the list.
```


## ════════════════════════════════════════════════════════════
## PROMPT #7 — 測試完整端到端流程
## 適用時機：模板上傳成功後
## ════════════════════════════════════════════════════════════

```
Test the full end-to-end document generation.

1. Create a test source document called test_source.txt with this content:
   ---
   Project Report - ABC Company
   Client: XYZ Corporation
   Date: 2026-03-27
   
   Items purchased:
   - Laptop, Quantity: 5, Price: HK$8,000 each
   - Mouse, Quantity: 10, Price: HK$150 each
   - Keyboard, Quantity: 10, Price: HK$300 each
   ---

2. Call the generate endpoint using the template_id from the previous step:
   curl -X POST http://localhost:8000/generate \
     -F "template_id=REPLACE_WITH_ACTUAL_ID" \
     -F "document=@test_source.txt" \
     -F "llm_provider=anthropic" \
     -o test_output.docx

3. Confirm test_output.docx was created and is not empty (check file size).

4. If there are errors, show me the full error message and stack trace.

Note: Make sure ANTHROPIC_API_KEY is set in .env before running.
```


## ════════════════════════════════════════════════════════════
## PROMPT #8 — 整合到現有前端（適用 Next.js / React）
## 適用時機：後端全部測試通過後
## ════════════════════════════════════════════════════════════

```
Integrate the Word Template Engine API into my existing frontend.
My frontend is [REPLACE WITH: Next.js / React / Vue / plain HTML].

I need these 3 functions added to my frontend code:

--- FUNCTION 1: Upload Template ---
When user clicks "+ Upload New Template" and selects a .docx file,
call POST /api/templates/upload and save the returned template_id.

--- FUNCTION 2: Load Template Dropdown ---
When the page loads, call GET /api/templates and populate
the "Select Template" dropdown with the returned template names.
Store the template_id as the option value.

--- FUNCTION 3: Generate Document ---
When user clicks "Proceed - Generate Document":
- Get the selected template_id from dropdown
- Get the selected source document file
- Get the selected LLM provider (from the "LLM Provider" dropdown)
- Call POST /api/generate with these values as FormData
- On success: trigger a file download of the returned .docx
- On error: show an error message to the user

Please also add a proxy config so /api/* routes forward to http://localhost:8000/*.

Show me the complete code changes needed.
```


## ════════════════════════════════════════════════════════════
## PROMPT #9 — 錯誤排查（備用）
## 適用時機：遇到任何錯誤時
## ════════════════════════════════════════════════════════════

```
I am getting this error when running the Word Template Engine:

[PASTE YOUR FULL ERROR MESSAGE HERE]

Context:
- I am running: [PASTE THE COMMAND YOU RAN]
- Python version: [run: python --version]
- The error happens at: [which step — upload / generate / server start]

Please:
1. Explain what is causing this error in simple terms
2. Show me exactly which file and line needs to be changed
3. Give me the corrected code
4. Tell me how to verify the fix worked
```
