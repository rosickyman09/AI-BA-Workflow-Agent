"""
api_server.py
=============
FastAPI Web 服務器：
提供 REST API 供前端（你的現有系統）呼叫

API 端點：
  POST /templates/upload       上傳新模板
  GET  /templates              列出所有模板
  GET  /templates/{id}         獲取模板詳情
  DELETE /templates/{id}       刪除模板
  POST /generate               生成文件（主功能）
"""

import os
import uuid
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from template_db import TemplateDatabase
from llm_client import LLMClient
from document_filler import DocumentFiller
from main import extract_document_content

app = FastAPI(
    title="Dynamic Word Template Engine",
    description="動態 Word 模板填寫引擎 API",
    version="1.0.0"
)

db = TemplateDatabase()


# ──────────────────────────────────────────────────────────────────
# 模板管理 API
# ──────────────────────────────────────────────────────────────────

@app.post("/templates/upload")
async def upload_template(
    file: UploadFile = File(...),
    name: str = Form(None)
):
    """上傳並解析 Word 模板"""
    if not file.filename.endswith(".docx"):
        raise HTTPException(400, "只支援 .docx 格式")

    # 暫存上傳文件
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = db.upload_template(tmp_path, name or file.filename)
        return {
            "success": True,
            "template_id": result["id"],
            "name": result["name"],
            "mode": result["mode"],
            "placeholders": result["structure"]["placeholders"],
            "table_count": len(result["structure"]["tables"])
        }
    finally:
        os.unlink(tmp_path)


@app.get("/templates")
async def list_templates():
    """列出所有可用模板"""
    return {"templates": db.list_templates()}


@app.get("/templates/{template_id}")
async def get_template(template_id: str):
    """獲取模板結構詳情"""
    try:
        info = db.get_template(template_id)
        return {
            "id": info["id"],
            "name": info["name"],
            "mode": info["mode"],
            "structure": info["structure"]
        }
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.delete("/templates/{template_id}")
async def delete_template(template_id: str):
    """刪除模板"""
    try:
        db.delete_template(template_id)
        return {"success": True}
    except ValueError as e:
        raise HTTPException(404, str(e))


# ──────────────────────────────────────────────────────────────────
# 文件生成 API（主功能）
# ──────────────────────────────────────────────────────────────────

@app.post("/generate")
async def generate_document(
    template_id: str = Form(...),
    document: UploadFile = File(...),
    llm_provider: str = Form("anthropic"),  # anthropic | openai | deepseek
    output_filename: str = Form(None)
):
    """
    主功能：上傳用戶文件，選擇模板，生成填寫後的 Word 文件
    
    - template_id: 已上傳的模板 ID
    - document: 用戶文件（PDF / DOCX / TXT）
    - llm_provider: 使用的 LLM Provider
    """

    # 1. 讀取模板結構（已預解析，直接讀取）
    try:
        template_info = db.get_template(template_id)
    except ValueError:
        raise HTTPException(404, f"找不到模板：{template_id}")

    template_structure = template_info["structure"]

    # 2. 暫存用戶文件
    ext = Path(document.filename).suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        content = await document.read()
        tmp.write(content)
        doc_tmp_path = tmp.name

    # 3. 準備輸出文件路徑
    out_filename = output_filename or f"output_{uuid.uuid4().hex[:8]}.docx"
    out_tmp_path = tempfile.mktemp(suffix=".docx")

    try:
        # 4. 提取文件內容
        document_content = extract_document_content(doc_tmp_path)

        # 5. LLM 分析
        llm = LLMClient(provider=llm_provider)
        extracted_data = llm.extract_data(template_structure, document_content)

        # 6. 填入模板
        filler = DocumentFiller(template_info["file_path"])
        filler.fill(extracted_data, out_tmp_path)

        # 7. 返回文件
        return FileResponse(
            path=out_tmp_path,
            filename=out_filename,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    except Exception as e:
        raise HTTPException(500, f"生成失敗：{str(e)}")

    finally:
        os.unlink(doc_tmp_path)


# ──────────────────────────────────────────────────────────────────
# 健康檢查
# ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
