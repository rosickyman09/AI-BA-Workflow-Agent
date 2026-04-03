from __future__ import annotations

import io
import json
import logging
import re
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from googleapiclient.http import MediaIoBaseUpload  # type: ignore
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, make_require_role, require_admin
from app.services import google_drive
from app.services.db_service import get_db
from app.services.urs_generator import (
    _download_file_bytes,
    _post_process_placeholders,
    build_formatted_docx,
    build_docx_with_template_engine,
    compute_placeholder_summary,
    convert_docx_to_pdf,
    extract_content_from_documents,
    extract_template_text,
    fill_pdf_form_fields,
    generate_with_ai,
    save_generated_to_drive,
    scan_placeholders,
    download_file_content,
)

logger = logging.getLogger(__name__)

router = APIRouter()

require_urs_user = make_require_role(["admin", "ba", "pm", "business_owner"])


class GenerateDocumentRequest(BaseModel):
    template_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    doc_ids: List[str] = Field(min_length=1)
    output_filename: str = Field(min_length=1, max_length=255)
    llm_provider: str = Field(default="auto")
    output_format: str = Field(default="")  # "docx" or "pdf"; empty = follow template format


class SaveGeneratedRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)


def _safe_filename(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "_", (value or "").strip())
    cleaned = re.sub(r"\s+", "_", cleaned).strip("._")
    if not cleaned:
        cleaned = fallback
    return cleaned[:200]


def _with_extension(filename: str, file_format: str) -> str:
    ext = (file_format or "docx").strip().lower()
    if ext not in {"docx", "txt", "xlsx", "pdf"}:
        ext = "docx"
    lower_name = filename.lower()
    if lower_name.endswith(f".{ext}"):
        return filename
    return f"{filename}.{ext}"


def _is_valid_docx(data: bytes) -> bool:
    """Check if bytes are a valid DOCX (ZIP with word/document.xml)."""
    import zipfile as _zf
    try:
        with _zf.ZipFile(io.BytesIO(data)) as z:
            return "word/document.xml" in z.namelist()
    except Exception:
        return False


def _generate_pdf_bytes(content: str, title: str = "Generated Document") -> bytes:
    """Convert plain-text / markdown content to a PDF using reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    import io as _io

    buf = _io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
        title=title,
    )
    styles = getSampleStyleSheet()
    story = []
    for line in content.splitlines():
        stripped = line.rstrip()
        if stripped.startswith("#### "):
            story.append(Paragraph(stripped[5:], styles["Heading4"]))
        elif stripped.startswith("### "):
            story.append(Paragraph(stripped[4:], styles["Heading3"]))
        elif stripped.startswith("## "):
            story.append(Paragraph(stripped[3:], styles["Heading2"]))
        elif stripped.startswith("# "):
            story.append(Paragraph(stripped[2:], styles["Heading1"]))
        elif stripped == "":
            story.append(Spacer(1, 0.3 * cm))
        else:
            text = stripped
            text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
            text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
            if text.startswith("- ") or text.startswith("* "):
                text = "\u2022 " + text[2:]
            story.append(Paragraph(text, styles["Normal"]))
    if not story:
        story.append(Paragraph(content, styles["Normal"]))
    doc.build(story)
    return buf.getvalue()


def _normalize_placeholders(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, str)]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if isinstance(item, str)]
        except Exception:
            pass
    return []


@router.post("/templates/upload")
async def upload_template(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    current_user: TokenUser = Depends(require_urs_user),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="template_filename_required")

    file_format = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if file_format not in {"docx", "xlsx", "txt", "pdf"}:
        raise HTTPException(status_code=400, detail="Only .docx, .xlsx, .txt, .pdf templates are supported")

    service = google_drive.get_drive_service()
    if service is None:
        raise HTTPException(status_code=500, detail="google_drive_not_configured")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="empty_template_file")

    templates_folder_id = await google_drive.get_urs_templates_folder(service)
    if not templates_folder_id:
        raise HTTPException(status_code=500, detail="urs_templates_folder_unavailable")

    upload_name = _safe_filename(file.filename, "urs_template")
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=file.content_type or "application/octet-stream")
    uploaded = (
        service.files()
        .create(
            body={"name": upload_name, "parents": [templates_folder_id]},
            media_body=media,
            fields="id,webViewLink",
            supportsAllDrives=True,
        )
        .execute()
    )

    file_id = uploaded.get("id", "")
    view_link = uploaded.get("webViewLink", f"https://drive.google.com/file/d/{file_id}/view")

    template_text = extract_template_text(file_bytes, upload_name, file.content_type or "")
    placeholders = scan_placeholders(template_text)

    logger.info("Attempting DB insert: name=%s format=%s user=%s", name.strip(), file_format, str(current_user.user_id))

    try:
        row = db.execute(
            text(
                """
                INSERT INTO urs_templates (
                    name,
                    description,
                    file_format,
                    google_drive_link,
                    google_drive_file_id,
                    detected_placeholders,
                    uploaded_by,
                    created_at,
                    updated_at
                )
                VALUES (
                    :name,
                    :description,
                    :file_format,
                    :google_drive_link,
                    :google_drive_file_id,
                    CAST(:detected_placeholders AS JSONB),
                    :uploaded_by,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                RETURNING template_id, created_at
                """
            ),
            {
                "name": name.strip(),
                "description": (description or "").strip() or None,
                "file_format": file_format,
                "google_drive_link": view_link,
                "google_drive_file_id": file_id,
                "detected_placeholders": json.dumps(placeholders),
                "uploaded_by": str(current_user.user_id),
            },
        ).fetchone()
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("template_insert_failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"template_insert_failed: {exc}")

    if row is None:
        logger.error("DB insert returned no row despite 200 OK")
        raise HTTPException(status_code=500, detail="template_insert_returned_no_row")
    logger.info("Template inserted successfully: template_id=%s", str(row[0]))

    return {
        "template_id": str(row[0]),
        "name": name.strip(),
        "description": (description or "").strip() or None,
        "file_format": file_format,
        "detected_placeholders": placeholders,
        "google_drive_link": view_link,
        "google_drive_file_id": file_id,
        "created_at": row[1].isoformat() if row[1] else None,
    }


@router.get("/templates")
async def list_templates(
    current_user: TokenUser = Depends(require_urs_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        text(
            """
            SELECT
                template_id,
                name,
                description,
                file_format,
                detected_placeholders,
                google_drive_link,
                google_drive_file_id,
                created_at,
                updated_at
            FROM urs_templates
            ORDER BY created_at DESC
            """
        )
    ).fetchall()

    items = []
    for row in rows:
        items.append(
            {
                "template_id": str(row[0]),
                "name": row[1],
                "description": row[2] or "",
                "file_format": row[3],
                "detected_placeholders": _normalize_placeholders(row[4]),
                "google_drive_link": row[5] or None,
                "google_drive_file_id": row[6] or None,
                "created_at": row[7].isoformat() if row[7] else None,
                "updated_at": row[8].isoformat() if row[8] else None,
            }
        )

    return {"templates": items}


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    current_user: TokenUser = Depends(require_urs_user),
    db: Session = Depends(get_db),
):
    existing = db.execute(
        text(
            "SELECT template_id, google_drive_file_id FROM urs_templates WHERE template_id = :template_id LIMIT 1"
        ),
        {"template_id": template_id},
    ).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail="template_not_found")

    drive_file_id = existing[1] if existing[1] else None

    # Delete from Google Drive first
    if drive_file_id:
        try:
            service = google_drive.get_drive_service()
            if service:
                service.files().delete(fileId=str(drive_file_id)).execute()
                logger.info("Deleted template file from Google Drive: %s", drive_file_id)
        except Exception as exc:
            logger.warning("Failed to delete template from Drive (file_id=%s): %s", drive_file_id, exc)

    try:
        # Nullify FK references in generated docs before deleting the template
        db.execute(
            text("UPDATE urs_generated_docs SET template_id = NULL WHERE template_id = :template_id"),
            {"template_id": template_id},
        )
        db.execute(
            text("DELETE FROM urs_templates WHERE template_id = :template_id"),
            {"template_id": template_id},
        )
        db.commit()
        logger.info("Deleted template %s by user %s", template_id, current_user.email)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"template_delete_failed: {exc}")

    return {"deleted": True, "template_id": template_id}


@router.post("/generate")
async def generate_document(
    payload: GenerateDocumentRequest,
    current_user: TokenUser = Depends(require_urs_user),
    db: Session = Depends(get_db),
):
    template_row = db.execute(
        text(
            """
            SELECT
                template_id,
                name,
                file_format,
                google_drive_file_id,
                google_drive_link,
                detected_placeholders
            FROM urs_templates
            WHERE template_id = :template_id
            LIMIT 1
            """
        ),
        {"template_id": payload.template_id},
    ).fetchone()
    if template_row is None:
        raise HTTPException(status_code=404, detail="template_not_found")

    project_row = db.execute(
        text("SELECT project_id, name FROM projects WHERE project_id = :project_id LIMIT 1"),
        {"project_id": payload.project_id},
    ).fetchone()
    if project_row is None:
        raise HTTPException(status_code=404, detail="project_not_found")

    doc_ids = [doc_id.strip() for doc_id in payload.doc_ids if doc_id and doc_id.strip()]
    if not doc_ids:
        raise HTTPException(status_code=400, detail="doc_ids must not be empty")

    for doc_id in doc_ids:
        doc_row = db.execute(
            text(
                """
                SELECT doc_id, project_id, status
                FROM documents
                WHERE doc_id = :doc_id
                LIMIT 1
                """
            ),
            {"doc_id": doc_id},
        ).fetchone()
        if doc_row is None:
            raise HTTPException(status_code=404, detail=f"document_not_found: {doc_id}")
        if str(doc_row[1]) != payload.project_id:
            raise HTTPException(status_code=400, detail=f"document_not_in_project: {doc_id}")
        if (doc_row[2] or "").strip().lower() != "approved":
            raise HTTPException(status_code=400, detail=f"document_not_approved: {doc_id}")

    template_file_id = template_row[3] or google_drive.get_drive_file_id(template_row[4] or "")
    if not template_file_id:
        raise HTTPException(status_code=400, detail="template_google_drive_file_id_missing")

    try:
        template_content = await download_file_content(str(template_file_id))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"template_download_failed: {exc}")
    if not template_content.strip():
        raise HTTPException(status_code=400, detail="template_content_empty")

    extracted_data = await extract_content_from_documents(doc_ids, db)
    if not extracted_data.get("raw_content"):
        raise HTTPException(status_code=400, detail="no_content_extracted_from_documents")

    placeholders = _normalize_placeholders(template_row[5]) or scan_placeholders(template_content)
    user_name = (current_user.full_name or current_user.email or "Unknown User").strip()

    try:
        generated_content = await generate_with_ai(
            template_content=template_content,
            extracted_data=extracted_data,
            project_name=str(project_row[1]),
            user_name=user_name,
            placeholders=placeholders,
            llm_provider=payload.llm_provider,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"urs_generation_failed: {exc}")

    # Post-process: replace any remaining {{PLACEHOLDER}} markers the LLM missed
    from datetime import datetime
    from zoneinfo import ZoneInfo
    hk_now = datetime.now(ZoneInfo("Asia/Hong_Kong"))
    approved_titles = ", ".join(
        str(item.get("title") or "Untitled")
        for item in extracted_data.get("raw_content", [])
    )

    # Compute placeholder summary BEFORE post-processing (to see what the LLM missed)
    placeholder_summary = compute_placeholder_summary(generated_content, placeholders)

    generated_content = _post_process_placeholders(
        generated_content,
        project_name=str(project_row[1]),
        user_name=user_name,
        approved_titles=approved_titles,
        hk_date=hk_now.strftime("%d %b %Y"),
    )

    # --- Pre-build the output file so download/save never re-runs the LLM ---
    template_drive_file_id = template_row[3]
    tpl_bytes = None
    if template_drive_file_id:
        try:
            svc = google_drive.get_drive_service()
            if svc:
                tpl_bytes = _download_file_bytes(svc, str(template_drive_file_id))
        except Exception as exc:
            logger.warning("Template file download for pre-build failed: %s", exc)

    # Output format: user's explicit choice (docx/pdf) overrides template format
    output_name_base = _safe_filename(payload.output_filename, "generated_urs")
    template_file_format = str(template_row[2] or "docx").lower()
    if template_file_format not in {"docx", "txt", "xlsx", "pdf"}:
        template_file_format = "docx"
    # Determine effective output format
    requested = (payload.output_format or "").strip().lower()
    effective_format = requested if requested in {"docx", "pdf"} else template_file_format

    prebuilt_bytes = None
    if effective_format == "pdf":
        # ── PDF output ──────────────────────────────────────────────
        if tpl_bytes and template_file_format == "docx":
            # DOCX template → fill with docxtpl → convert to PDF via LibreOffice
            docx_bytes = build_docx_with_template_engine(
                template_bytes=tpl_bytes,
                generated_content=generated_content,
                project_name=str(project_row[1]),
                user_name=user_name,
                llm_provider=payload.llm_provider,
            )
            if not docx_bytes:
                docx_bytes = build_formatted_docx(generated_content, template_bytes=tpl_bytes)
            try:
                prebuilt_bytes = convert_docx_to_pdf(docx_bytes)
                logger.info("Pre-built PDF via DOCX→LibreOffice (%d bytes)", len(prebuilt_bytes))
            except Exception as exc:
                logger.warning("LibreOffice conversion failed, falling back to reportlab: %s", exc)
                prebuilt_bytes = _generate_pdf_bytes(generated_content, output_name_base)
        elif tpl_bytes and template_file_format == "pdf":
            # PDF template → fill AcroForm fields with pypdf
            prebuilt_bytes = fill_pdf_form_fields(
                pdf_bytes=tpl_bytes,
                generated_content=generated_content,
                project_name=str(project_row[1]),
                user_name=user_name,
                llm_provider=payload.llm_provider,
            )
            if not prebuilt_bytes:
                prebuilt_bytes = _generate_pdf_bytes(generated_content, output_name_base)
            logger.info("Pre-built PDF output (%d bytes)", len(prebuilt_bytes))
        else:
            prebuilt_bytes = _generate_pdf_bytes(generated_content, output_name_base)
            logger.info("Pre-built PDF via reportlab (%d bytes)", len(prebuilt_bytes))
    elif effective_format == "docx":
        docx_bytes = None
        # Only attempt template-engine merge when the template itself is a DOCX
        if tpl_bytes and template_file_format == "docx":
            docx_bytes = build_docx_with_template_engine(
                template_bytes=tpl_bytes,
                generated_content=generated_content,
                project_name=str(project_row[1]),
                user_name=user_name,
                llm_provider=payload.llm_provider,
            )
            if docx_bytes:
                logger.info("Pre-built .docx via template engine (%d bytes)", len(docx_bytes))
        if not docx_bytes:
            # Template engine returned None — log a WARNING so we can diagnose
            logger.warning(
                "build_docx_with_template_engine returned None for template %s — "
                "check logs above for docxtpl errors. Using styled markdown fallback.",
                template_row[0] if template_row else "unknown",
            )
            style_bytes = tpl_bytes if template_file_format == "docx" else None
            docx_bytes = build_formatted_docx(generated_content, template_bytes=style_bytes)
            logger.info("Fallback: pre-built .docx via markdown converter (%d bytes)", len(docx_bytes))
        # Validate that the generated bytes are actually a valid DOCX
        if not _is_valid_docx(docx_bytes):
            logger.error("Generated DOCX failed validation — falling back to plain markdown converter")
            docx_bytes = build_formatted_docx(generated_content, template_bytes=None)
            if not _is_valid_docx(docx_bytes):
                raise HTTPException(status_code=500, detail="docx_generation_produced_invalid_file")
        prebuilt_bytes = docx_bytes
    else:
        # txt / xlsx fallback
        prebuilt_bytes = build_formatted_docx(generated_content, template_bytes=None)
        effective_format = "docx"

    file_format = effective_format

    # Strip trailing date suffix (e.g. _20260326) so versioning is project-based only
    version_base = re.sub(r'_\d{8}$', '', output_name_base)

    # Auto-versioning: check existing docs with same base name and increment
    version_row = db.execute(
        text(
            """
            SELECT title FROM urs_generated_docs
            WHERE project_id = :project_id
              AND title LIKE :title_pattern
            ORDER BY created_at DESC
            """
        ),
        {
            "project_id": payload.project_id,
            "title_pattern": f"{version_base}%",
        },
    ).fetchall()

    if version_row:
        max_version = 0
        for vr in version_row:
            title = str(vr[0] or "")
            match = re.search(r"_v(\d+)", title)
            if match:
                max_version = max(max_version, int(match.group(1)))
            else:
                max_version = max(max_version, 1)
        output_name_base = f"{version_base}_v{max_version + 1}"
    else:
        output_name_base = f"{version_base}_v1"

    output_filename = _with_extension(output_name_base, file_format)
    logger.info("Generating URS document: %s for project %s by %s", output_filename, payload.project_id, current_user.email)

    try:
        generated_row = db.execute(
            text(
                """
                INSERT INTO urs_generated_docs (
                    template_id,
                    project_id,
                    title,
                    source_doc_ids,
                    generated_content,
                    generated_docx,
                    placeholder_summary,
                    status,
                    generated_by,
                    created_at
                )
                VALUES (
                    :template_id,
                    :project_id,
                    :title,
                    CAST(:source_doc_ids AS JSONB),
                    :generated_content,
                    :generated_docx,
                    CAST(:placeholder_summary AS JSONB),
                    'generated',
                    :generated_by,
                    CURRENT_TIMESTAMP
                )
                RETURNING generated_id
                """
            ),
            {
                "template_id": payload.template_id,
                "project_id": payload.project_id,
                "title": output_filename,
                "source_doc_ids": json.dumps(doc_ids),
                "generated_content": generated_content,
                "generated_docx": prebuilt_bytes,
                "placeholder_summary": json.dumps(placeholder_summary),
                "generated_by": str(current_user.user_id),
            },
        ).fetchone()
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"save_generated_preview_failed: {exc}")

    return {
        "generated_id": str(generated_row[0]),
        "content": generated_content,
        "filename": output_filename,
        "effective_format": file_format,
        "status": "generated",
        "placeholder_summary": placeholder_summary,
    }


@router.post("/save/{generated_id}")
async def save_generated_document(
    generated_id: str,
    payload: SaveGeneratedRequest,
    current_user: TokenUser = Depends(require_urs_user),
    db: Session = Depends(get_db),
):
    row = db.execute(
        text(
            """
            SELECT
                g.generated_id,
                g.generated_content,
                g.title,
                p.name AS project_name,
                t.file_format,
                t.google_drive_file_id AS template_drive_file_id,
                g.generated_docx
            FROM urs_generated_docs g
            LEFT JOIN projects p ON p.project_id = g.project_id
            LEFT JOIN urs_templates t ON t.template_id = g.template_id
            WHERE g.generated_id = :generated_id
            LIMIT 1
            """
        ),
        {"generated_id": generated_id},
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="generated_document_not_found")

    generated_content = str(row[1] or "").strip()
    if not generated_content:
        raise HTTPException(status_code=400, detail="generated_content_empty")

    project_name = str(row[3] or "Unknown Project")
    # Derive actual format from the stored title extension (user's chosen format)
    stored_title = str(row[2] or "").lower()
    if stored_title.endswith(".pdf"):
        file_format = "pdf"
    elif stored_title.endswith(".txt"):
        file_format = "txt"
    else:
        file_format = "docx"
    template_drive_file_id = str(row[5]) if row[5] else None
    stored_docx = row[6]  # Pre-built .docx bytes from generate step
    filename_base = _safe_filename(payload.filename, _safe_filename(str(row[2] or "generated_urs"), "generated_urs"))
    final_filename = _with_extension(filename_base, file_format)

    try:
        drive_result = await save_generated_to_drive(
            content=generated_content,
            filename=final_filename,
            project_name=project_name,
            file_format=file_format,
            template_drive_file_id=template_drive_file_id,
            prebuilt_docx=bytes(stored_docx) if stored_docx else None,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"save_to_drive_failed: {exc}")

    try:
        db.execute(
            text(
                """
                UPDATE urs_generated_docs
                SET title = :title,
                    google_drive_link = :google_drive_link,
                    google_drive_file_id = :google_drive_file_id,
                    google_drive_folder = 'pending',
                    status = 'saved'
                WHERE generated_id = :generated_id
                """
            ),
            {
                "generated_id": generated_id,
                "title": final_filename,
                "google_drive_link": drive_result.get("view_link"),
                "google_drive_file_id": drive_result.get("file_id"),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"generated_document_update_failed: {exc}")

    return {
        "generated_id": generated_id,
        "filename": final_filename,
        "status": "saved",
        "drive_link": drive_result.get("view_link"),
        "google_drive_file_id": drive_result.get("file_id"),
    }


@router.get("/download/{generated_id}")
async def download_generated_document(
    generated_id: str,
    current_user: TokenUser = Depends(require_urs_user),
    db: Session = Depends(get_db),
):
    """Return the generated document as a formatted .docx download."""
    row = db.execute(
        text(
            """
            SELECT g.generated_content, g.title, t.file_format,
                   t.google_drive_file_id AS template_drive_file_id,
                   g.generated_docx
            FROM urs_generated_docs g
            LEFT JOIN urs_templates t ON t.template_id = g.template_id
            WHERE g.generated_id = :generated_id
            LIMIT 1
            """
        ),
        {"generated_id": generated_id},
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="generated_document_not_found")

    content = str(row[0] or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="generated_content_empty")

    title = str(row[1] or "generated_urs")
    file_format = str(row[2] or "docx").lower()
    # Derive actual format from the stored filename extension (overrides template format)
    title_lower = title.lower()
    if title_lower.endswith(".pdf"):
        file_format = "pdf"
    elif title_lower.endswith(".txt"):
        file_format = "txt"
    elif title_lower.endswith(".docx"):
        file_format = "docx"
    template_drive_file_id = str(row[3]) if row[3] else None
    stored_docx = row[4]  # Pre-built .docx bytes from generate step

    if file_format == "docx":
        if stored_docx:
            # Use pre-built .docx — no LLM re-run needed
            file_bytes = bytes(stored_docx)
            logger.info("Serving pre-built .docx for %s (%d bytes)", generated_id, len(file_bytes))
        else:
            # Legacy fallback: build .docx on-the-fly (for docs generated before this change)
            logger.warning("No pre-built .docx found for %s, building on-the-fly", generated_id)
            tpl_bytes = None
            if template_drive_file_id:
                try:
                    from app.services.google_drive import get_drive_service
                    svc = get_drive_service()
                    if svc:
                        tpl_bytes = _download_file_bytes(svc, template_drive_file_id)
                except Exception as exc:
                    logger.warning("Template download for styling failed: %s", exc)

            file_bytes = build_formatted_docx(content, template_bytes=tpl_bytes)

        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ext = ".docx"
    elif file_format == "pdf":
        if stored_docx:
            file_bytes = bytes(stored_docx)
            logger.info("Serving pre-built PDF for %s (%d bytes)", generated_id, len(file_bytes))
        else:
            # Try LibreOffice conversion, fall back to reportlab
            try:
                docx_bytes = build_formatted_docx(content, template_bytes=None)
                file_bytes = convert_docx_to_pdf(docx_bytes)
            except Exception:
                file_bytes = _generate_pdf_bytes(content, title)
        media_type = "application/pdf"
        ext = ".pdf"
    else:
        # Unsupported format — default to DOCX rather than falling back to .txt
        logger.warning("Unexpected file_format '%s' for %s, defaulting to DOCX", file_format, generated_id)
        file_bytes = build_formatted_docx(content, template_bytes=None)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ext = ".docx"

    fname = title if title.lower().endswith(ext) else f"{title}{ext}"
    safe_fname = fname.replace('"', '_')

    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_fname}"'},
    )


@router.get("/debug/template/{template_id}/placeholders")
async def debug_template_placeholders(
    template_id: str,
    current_user: TokenUser = Depends(require_urs_user),
    db: Session = Depends(get_db),
):
    """Diagnostic: show what placeholders are detected in a template."""
    row = db.execute(
        text(
            "SELECT name, file_format, google_drive_file_id "
            "FROM urs_templates WHERE template_id = :id"
        ),
        {"id": template_id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="template_not_found")

    file_id = row[2]
    if not file_id:
        raise HTTPException(status_code=400, detail="no_drive_file_id")

    svc = google_drive.get_drive_service()
    if not svc:
        raise HTTPException(status_code=500, detail="drive_not_configured")

    tpl_bytes = _download_file_bytes(svc, str(file_id))

    result: dict = {
        "template_name": row[0],
        "file_format": row[1],
        "template_bytes_size": len(tpl_bytes),
    }

    # docxtpl undeclared variables
    if str(row[1]).lower() == "docx":
        try:
            from docxtpl import DocxTemplate  # type: ignore
            tpl = DocxTemplate(io.BytesIO(tpl_bytes))
            undeclared = tpl.get_undeclared_template_variables()
            result["docxtpl_undeclared_variables"] = sorted(undeclared)
        except Exception as exc:
            result["docxtpl_error"] = str(exc)

    # template_engine placeholders
    try:
        from template_engine.template_parser import TemplateParser
        import tempfile as _tf
        with _tf.NamedTemporaryFile(suffix=".docx", delete=False) as _tmp:
            _tmp.write(tpl_bytes)
            _tmp_path = _tmp.name
        parser = TemplateParser(_tmp_path)
        structure = parser.parse()
        result["template_engine_placeholders"] = structure.get("placeholders", [])
        result["template_engine_mode"] = structure.get("mode")
        result["template_engine_tables"] = len(structure.get("tables", []))
        import os as _os
        _os.unlink(_tmp_path)
    except Exception as exc:
        result["template_engine_error"] = str(exc)

    return result
