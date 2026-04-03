"""
Document management endpoints.

POST /upload          — Accept file + metadata, store to DB, upload to Drive, trigger pipeline
GET  /{doc_id}/status — Return current processing status + progress
"""
import logging
import mimetypes
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query, UploadFile, File, Body
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_ba, require_readonly
from app.services.db_service import get_db
from app.services import google_drive, google_sheets, elevenlabs, n8n_webhook
from app.services.workflow import create_approval_workflow as _create_workflow
from app.services.notifications import create_notification, get_role_user_ids

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── status constants ────────────────────────────────────────────────────────

STATUS_PENDING    = "PENDING"
STATUS_PROCESSING = "PROCESSING"
STATUS_COMPLETED  = "COMPLETED"
STATUS_FAILED     = "FAILED"

# ─── background processing task ──────────────────────────────────────────────

async def _process_document(
    doc_id: str,
    workflow_id: str,
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    project_name: str = "",
) -> None:
    """
    Background task: upload to Google Drive, trigger STT + n8n, update status.
    Status transitions: PENDING → PROCESSING → COMPLETED (or FAILED).
    """
    db: Session = next(get_db())
    try:
        # ── 1. Mark PROCESSING ────────────────────────────────────────────────
        db.execute(
            text("UPDATE documents SET status = :s, updated_at = :t WHERE doc_id = :id"),
            {"s": STATUS_PROCESSING, "t": datetime.utcnow(), "id": doc_id},
        )
        db.commit()

        # ── 2. Upload to Google Drive (Pending documents/{project_name}/) ────────────────────
        drive_result = google_drive.upload_file(
            file_bytes, filename, mime_type, project_name or None
        )
        drive_view_link: Optional[str] = None
        if drive_result:
            drive_view_link = drive_result["view_link"]
            db.execute(
                text(
                    "UPDATE documents SET google_drive_link = :url, "
                    "google_drive_file_id = :fid, updated_at = :t WHERE doc_id = :id"
                ),
                {
                    "url": drive_view_link,
                    "fid": drive_result["file_id"],
                    "t": datetime.utcnow(),
                    "id": doc_id,
                },
            )
            db.commit()

        # ── 3. ElevenLabs STT (audio/video only) ──────────────────────────────
        transcript: Optional[str] = None
        if elevenlabs.is_audio(mime_type):
            transcript = await elevenlabs.transcribe(file_bytes, filename, mime_type)
            if transcript:
                # Store transcript as version 1 in document_versions
                version_id = str(uuid.uuid4())
                db.execute(
                    text("""INSERT INTO document_versions
                         (version_id, doc_id, version_number, content, approval_status, created_at)
                       VALUES (:vid, :did, 1, :content, 'pending', :ts)"""),
                    {
                        "vid": version_id,
                        "did": doc_id,
                        "content": transcript,
                        "ts": datetime.utcnow(),
                    },
                )
                db.commit()

        # ── 4. Trigger n8n webhook ─────────────────────────────────────────────
        await n8n_webhook.trigger_document_workflow(
            workflow_id=workflow_id,
            document_id=doc_id,
            google_drive_url=drive_view_link,
            file_type=mime_type,
            filename=filename,
        )

        # ── 5. Mark COMPLETED ─────────────────────────────────────────────────
        db.execute(
            text("UPDATE documents SET status = :s, updated_at = :t WHERE doc_id = :id"),
            {"s": STATUS_COMPLETED, "t": datetime.utcnow(), "id": doc_id},
        )
        db.commit()
        logger.info("Document %s processing completed (workflow %s)", doc_id, workflow_id)

    except Exception as exc:
        logger.error("Processing failed for document %s: %s", doc_id, exc)
        try:
            db.execute(
                text("UPDATE documents SET status = :s, updated_at = :t WHERE doc_id = :id"),
                {"s": STATUS_FAILED, "t": datetime.utcnow(), "id": doc_id},
            )
            db.commit()
        except Exception:
            pass
    finally:
        db.close()


# ─── endpoints ───────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_id: str = Form(...),
    title: Optional[str] = Form(None),
    submission_notes: Optional[str] = Form(None),
    current_user: TokenUser = Depends(require_ba),
    db: Session = Depends(get_db),
):
    """
    Upload a document for processing.

    - Requires role: ba / pm / tech_lead / admin  (HTTP 403 otherwise)
    - Accepts: audio, video, PDF, DOCX, XLSX, etc.
    - Returns: {document_id, workflow_id, status: "PENDING"}
    - Processing continues asynchronously in the background.
    """
    # ── Detect MIME type ──────────────────────────────────────────────────────
    mime_type: str = file.content_type or ""
    if not mime_type or mime_type == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(file.filename or "")
        mime_type = guessed or "application/octet-stream"

    doc_title = title or (file.filename or "Untitled")
    doc_id    = str(uuid.uuid4())
    workflow_id = str(uuid.uuid4())

    # ── 1. Read file into memory (needed for background task) ─────────────────
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # ── 2. Insert document record with status PENDING ─────────────────────────
    notes_value = (submission_notes or "").strip() or None
    try:
        db.execute(
            text("""INSERT INTO documents
                 (doc_id, project_id, title, doc_type, status, created_by, submission_notes, created_at, updated_at)
               VALUES (:doc_id, :project_id, :title, :doc_type, :status, :created_by, :notes, :now, :now)"""),
            {
                "doc_id":     doc_id,
                "project_id": project_id,
                "title":      doc_title,
                "doc_type":   mime_type,
                "status":     STATUS_PENDING,
                "created_by": current_user.user_id,
                "notes":      notes_value,
                "now":        datetime.utcnow(),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to insert document record: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to store document metadata")

    # ── 3. Create approval_workflow entry with dynamic step roles ─────────────
    try:
        import uuid as _uuid
        wf_result = _create_workflow(
            doc_id=_uuid.UUID(doc_id),
            project_id=_uuid.UUID(project_id),
            created_by=_uuid.UUID(str(current_user.user_id)),
            submitter_role=current_user.role,
            workflow_type="approval",
            db=db,
        )
        workflow_id = wf_result["workflow_id"]
        db.commit()
    except Exception as exc:
        logger.warning("Failed to create approval workflow entry: %s", exc)
        # Non-fatal — document record exists, workflow tracking is best-effort

    # ── 4. Fetch project name (Drive placement handled by pending/approved logic) ──
    project_name: str = ""
    try:
        proj_row = db.execute(
            text("SELECT name FROM projects WHERE project_id = :pid"),
            {"pid": project_id},
        ).fetchone()
        if proj_row:
            project_name = proj_row[0] or ""
    except Exception as exc:
        logger.warning("Could not fetch project name for %s: %s", project_id, exc)

    # ── 5. Append row to Google Sheets backlog (best-effort) ─────────────────
    try:
        import os as _os
        file_name_no_ext = _os.path.splitext(doc_title)[0]
        upload_date = datetime.utcnow().strftime("%d-%b-%Y")
        google_sheets.append_upload_row(
            user_name=current_user.email,
            project_name=project_name,
            file_name=file_name_no_ext,
            upload_date=upload_date,
        )
    except Exception as exc:
        logger.warning("Sheets append_upload_row failed for %s: %s", doc_id, exc)

    # ── 5b. Notify step-1-role users that a new doc needs review ─────────────
    try:
        s1_role = wf_result.get("step_1_role") if isinstance(wf_result, dict) else None
        submitter_name = current_user.full_name or current_user.email
        if s1_role and project_name:
            for uid in get_role_user_ids(role=s1_role, project_id=project_id, db=db):
                create_notification(
                    user_id=uid,
                    title="New Document Pending Review",
                    message=(
                        f"Project {project_name}: '{doc_title}' submitted by "
                        f"{submitter_name} requires your Step 1 review"
                    ),
                    notif_type="info",
                    workflow_id=workflow_id,
                    db=db,
                )
        db.commit()
    except Exception as exc:
        logger.warning("Upload notification failed for %s: %s", doc_id, exc)

    # ── 6. Queue background processing ───────────────────────────────────────
    background_tasks.add_task(
        _process_document,
        doc_id,
        workflow_id,
        file_bytes,
        file.filename or doc_title,
        mime_type,
        project_name,
    )

    logger.info(
        "Document %s queued for processing by %s (workflow %s)",
        doc_id, current_user.email, workflow_id,
    )

    return {
        "document_id": doc_id,
        "workflow_id": workflow_id,
        "filename":    file.filename,
        "status":      STATUS_PENDING,
        "uploaded_by": current_user.email,
    }


@router.get("")
async def list_documents(
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """List documents with optional project and status filter (auth required)."""
    safe_limit = max(1, min(limit, 200))
    safe_offset = max(0, offset)

    conditions = []
    params: dict = {"limit": safe_limit, "offset": safe_offset}
    if project_id:
        conditions.append("d.project_id = :project_id")
        params["project_id"] = project_id

    # M2: For approved status, require BOTH documents.status='approved' AND
    # approval_workflows.status='approved' to avoid orphaned approvals.
    join_clause = ""
    if status == "approved":
        join_clause = (
            "INNER JOIN approval_workflows aw ON aw.doc_id::text = d.doc_id::text "
            "AND aw.status = 'approved'"
        )
        conditions.append("d.status = 'approved'")
        # Hide inactive documents from Generate URS / Knowledge Base approved lists
        conditions.append("d.is_active = TRUE")
    elif status:
        conditions.append("d.status = :status")
        params["status"] = status

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = db.execute(
        text(
            f"""
            SELECT d.doc_id, d.project_id, d.title, d.doc_type, d.status,
                 d.updated_at, d.google_drive_link,
                 p.name AS project_name,
                 COALESCE(u.full_name, u.email, '') AS submitter_name,
                   (SELECT COUNT(*) FROM document_versions dv WHERE dv.doc_id = d.doc_id) AS version_count,
                 d.is_active
            FROM documents d
             LEFT JOIN projects p ON p.project_id = d.project_id
             LEFT JOIN users u ON u.user_id = d.created_by
            {join_clause}
            {where_clause}
            ORDER BY d.updated_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).fetchall()

    return {
        "requested_by": current_user.email,
        "project_id": project_id,
        "total": len(rows),
        "documents": [
            {
                "doc_id": str(r[0]),
                "project_id": str(r[1]),
                "title": r[2],
                "doc_type": r[3],
                "status": r[4],
                "updated_at": r[5].isoformat() if r[5] else None,
                "google_drive_link": r[6] or None,
                "project_name": r[7] or "",
                "submitter_name": r[8] or "",
                "version_count": int(r[9] or 0),
                "is_active": bool(r[10]) if r[10] is not None else True,
            }
            for r in rows
        ],
    }


@router.get("/in-review")
async def list_in_review_documents(
    project_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """List documents that currently have an active (in-progress) workflow."""
    safe_limit = max(1, min(limit, 200))
    safe_offset = max(0, offset)

    project_filter = "AND d.project_id = :project_id" if project_id else ""
    params: dict = {"limit": safe_limit, "offset": safe_offset}
    if project_id:
        params["project_id"] = project_id

    rows = db.execute(
        text(
            f"""
            WITH latest_wf AS (
                SELECT DISTINCT ON (doc_id)
                    doc_id,
                    status,
                    current_step,
                    total_steps
                FROM approval_workflows
                ORDER BY doc_id, updated_at DESC, created_at DESC
            )
            SELECT
                d.doc_id,
                d.title,
                d.doc_type,
                d.status,
                d.created_at,
                p.name AS project_name,
                lw.status AS workflow_status,
                lw.current_step,
                lw.total_steps
            FROM documents d
            JOIN projects p ON d.project_id = p.project_id
            INNER JOIN latest_wf lw ON lw.doc_id = d.doc_id
            WHERE lw.status IN ('in_progress', 'returned_to_submitter', 'returned_to_step1')
              {project_filter}
            ORDER BY d.created_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).fetchall()

    return {
        "requested_by": current_user.email,
        "total": len(rows),
        "documents": [
            {
                "doc_id": str(r[0]),
                "title": r[1] or f"Document {str(r[0])[:8]}",
                "doc_type": r[2] or None,
                "status": r[3],
                "created_at": r[4].isoformat() if r[4] else None,
                "project_name": r[5] or "",
                "workflow_status": r[6],
                "current_step": int(r[7] or 1),
                "total_steps": int(r[8] or 2),
            }
            for r in rows
        ],
    }


@router.get("/{doc_id}/status")
async def get_document_status(
    doc_id: str,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """
    Get the current processing status of a document.

    Status values: PENDING → PROCESSING → COMPLETED | FAILED
    """
    try:
        row = db.execute(
            text("""SELECT doc_id, title, status, doc_type, google_drive_link, updated_at
               FROM documents WHERE doc_id = :id"""),
            {"id": doc_id},
        ).fetchone()
    except Exception as exc:
        logger.error("DB error fetching document status for %s: %s", doc_id, exc)
        raise HTTPException(status_code=500, detail="Database error")

    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")

    status = row[2]
    progress_map = {
        STATUS_PENDING:    10,
        STATUS_PROCESSING: 50,
        STATUS_COMPLETED:  100,
        STATUS_FAILED:     0,
    }

    return {
        "document_id":     str(row[0]),
        "title":           row[1],
        "status":          status,
        "progress":        progress_map.get(status, 0),
        "doc_type":        row[3],
        "google_drive_url": row[4],
        "updated_at":      row[5].isoformat() if row[5] else None,
    }


@router.get("/{doc_id}/versions")
async def list_document_versions(
    doc_id: str,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """List all versions for a document (latest first)."""
    rows = db.execute(
        text(
            """
            SELECT version_id, version_number, content_hash, approval_status, created_by, created_at
            FROM document_versions
            WHERE doc_id = :doc_id
            ORDER BY version_number DESC
            """
        ),
        {"doc_id": doc_id},
    ).fetchall()

    return {
        "doc_id": doc_id,
        "requested_by": current_user.email,
        "total": len(rows),
        "versions": [
            {
                "version_id": str(r[0]),
                "version_number": int(r[1]),
                "content_hash": r[2],
                "approval_status": r[3],
                "created_by": str(r[4]) if r[4] else None,
                "created_at": r[5].isoformat() if r[5] else None,
            }
            for r in rows
        ],
    }


@router.get("/{doc_id}/versions/{version_id}")
async def get_document_version(
    doc_id: str,
    version_id: str,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Get a specific document version snapshot."""
    row = db.execute(
        text(
            """
            SELECT version_id, doc_id, version_number, content, content_hash, approval_status, created_by, created_at
            FROM document_versions
            WHERE doc_id = :doc_id AND version_id = :version_id
            LIMIT 1
            """
        ),
        {"doc_id": doc_id, "version_id": version_id},
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="version_not_found")

    return {
        "requested_by": current_user.email,
        "version_id": str(row[0]),
        "doc_id": str(row[1]),
        "version_number": int(row[2]),
        "content": row[3],
        "content_hash": row[4],
        "approval_status": row[5],
        "created_by": str(row[6]) if row[6] else None,
        "created_at": row[7].isoformat() if row[7] else None,
    }


@router.patch("/{doc_id}/visibility")
async def toggle_document_visibility(
    doc_id: str,
    body: dict = Body(...),
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """
    Toggle document visibility (Active / Inactive).

    Only business_owner, project_owner, or admin may call this.
    Setting is_active=False hides the document from Generate URS and Knowledge Base.
    The document is NOT deleted and remains visible on the Project Detail page.
    """
    role = (current_user.role or "").strip().lower()
    if role not in ("business_owner", "project_owner", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Only project owners can change document visibility",
        )

    is_active = body.get("is_active")
    if is_active is None:
        raise HTTPException(status_code=400, detail="is_active field required")
    if not isinstance(is_active, bool):
        raise HTTPException(status_code=400, detail="is_active must be a boolean")

    result = db.execute(
        text(
            "UPDATE documents SET is_active = :is_active, "
            "updated_at = CURRENT_TIMESTAMP "
            "WHERE doc_id = :doc_id RETURNING doc_id, is_active"
        ),
        {"doc_id": doc_id, "is_active": is_active},
    ).fetchone()

    if not result:
        raise HTTPException(status_code=404, detail="Document not found")

    db.commit()
    logger.info(
        "Document %s visibility set to is_active=%s by %s",
        doc_id, is_active, current_user.email,
    )

    return {"doc_id": str(result[0]), "is_active": result[1]}


@router.post("/{doc_id}/resubmit")
async def resubmit_document(
    doc_id: str,
    resubmit_notes: Optional[str] = Body(None, embed=True),
    current_user: TokenUser = Depends(require_ba),
    db: Session = Depends(get_db),
):
    """
    Re-submit a returned document for approval.

    Resets the existing workflow to step 1 / in_progress, creates a new version entry,
    and notifies step-1 reviewers.
    """
    import uuid as _uuid

    row = db.execute(
        text("SELECT doc_id, project_id, status, title, created_by FROM documents WHERE doc_id = :id"),
        {"id": doc_id},
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="document_not_found")

    _doc_id, project_id, doc_status, doc_title, doc_created_by = row[0], row[1], row[2], row[3], row[4]

    # Ensure the caller is the original submitter (or admin)
    if current_user.role != "admin":
        if doc_created_by and str(doc_created_by) != str(current_user.user_id):
            raise HTTPException(status_code=403, detail="Only the original submitter may resubmit")

    # Find the most recent workflow that is returned_to_submitter
    wf_row = db.execute(
        text(
            """
            SELECT workflow_id, status, step_1_role, step_2_role, total_steps
            FROM approval_workflows
            WHERE doc_id = :doc_id
              AND status = 'returned_to_submitter'
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ),
        {"doc_id": doc_id},
    ).fetchone()

    if wf_row is None:
        # Fallback: accept docs that were returned (doc.status = 'returned') or rejected
        if doc_status not in ("returned", "rejected"):
            raise HTTPException(
                status_code=409,
                detail=f"Document cannot be resubmitted from status '{doc_status}'",
            )
        # If no returned_to_submitter workflow found, look for any recent pending workflow
        wf_row = db.execute(
            text(
                """
                SELECT workflow_id, status, step_1_role, step_2_role, total_steps
                FROM approval_workflows
                WHERE doc_id = :doc_id
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ),
            {"doc_id": doc_id},
        ).fetchone()
        if wf_row is None:
            raise HTTPException(status_code=404, detail="No workflow found for this document")

    workflow_id_str = str(wf_row[0])
    s1_role = wf_row[2]
    s2_role = wf_row[3]
    total_steps = wf_row[4]
    now = datetime.utcnow()

    try:
        # Reset workflow to step 1 / in_progress, increment resubmit_count
        db.execute(
            text(
                """
                UPDATE approval_workflows
                SET current_step = 1,
                    status = 'in_progress',
                    resubmit_count = COALESCE(resubmit_count, 0) + 1,
                    updated_at = :now
                WHERE workflow_id = :wid
                """
            ),
            {"now": now, "wid": workflow_id_str},
        )
        # Reset document status to pending_approval, store resubmit notes if provided
        db.execute(
            text(
                "UPDATE documents SET status = 'pending_approval', updated_at = :t"
                + (", resubmit_notes = :rn" if resubmit_notes else "")
                + " WHERE doc_id = :id"
            ),
            {"t": now, "id": doc_id, **({"rn": resubmit_notes} if resubmit_notes else {})},
        )
        # Create new document_versions entry
        from app.services.workflow import create_document_version
        create_document_version(
            doc_id=_uuid.UUID(doc_id),
            created_by=_uuid.UUID(str(current_user.user_id)),
            approval_status="in_progress",
            reason="Document resubmitted after return",
            project_id=_uuid.UUID(str(project_id)),
            workflow_id=_uuid.UUID(workflow_id_str),
            db=db,
        )
        # Audit log
        from app.services.audit import log_audit_event
        log_audit_event(
            db=db,
            project_id=_uuid.UUID(str(project_id)),
            action="DOCUMENT_RESUBMITTED",
            entity_type="approval",
            entity_id=_uuid.UUID(workflow_id_str),
            user_id=_uuid.UUID(str(current_user.user_id)),
            old_values={"status": str(wf_row[1])},
            new_values={"status": "in_progress", "current_step": 1},
            succeeded=True,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"resubmit_failed: {exc}")

    # Update Google Sheets backlog (best-effort, non-fatal)
    try:
        import os as _os
        resubmit_info = db.execute(
            text(
                """
                SELECT d.title, p.name
                FROM documents d
                JOIN projects p ON p.project_id = d.project_id
                WHERE d.doc_id = :did
                """
            ),
            {"did": doc_id},
        ).fetchone()
        if resubmit_info:
            google_sheets.update_approval_row(
                project_name=resubmit_info[1] or "",
                file_name=_os.path.splitext(resubmit_info[0] or "")[0],
                approver_name="/",
                status="Resubmitted",
                comment="/",
            )
    except Exception as exc:
        logger.warning("Sheets update failed after resubmit (%s): %s", doc_id, exc)

    # Notify step-1 reviewers (best-effort)
    try:
        project_row = db.execute(
            text("SELECT name FROM projects WHERE project_id = :pid"),
            {"pid": str(project_id)},
        ).fetchone()
        project_name = project_row[0] if project_row else ""
        submitter_name = current_user.full_name or current_user.email
        if s1_role:
            for uid in get_role_user_ids(role=s1_role, project_id=str(project_id), db=db):
                create_notification(
                    user_id=uid,
                    title="Document Resubmitted",
                    message=(
                        f"Project {project_name}: '{doc_title}' has been revised and "
                        f"resubmitted by {submitter_name} for your review"
                    ),
                    notif_type="info",
                    workflow_id=workflow_id_str,
                    db=db,
                )
        db.commit()
    except Exception as exc:
        logger.warning("Notifications failed after resubmit (%s): %s", doc_id, exc)

    return {
        "success": True,
        "message": "Document resubmitted successfully",
        "document_id": doc_id,
        "workflow_id": workflow_id_str,
        "workflow_status": "in_progress",
        "step_1_role": s1_role,
        "step_2_role": s2_role,
    }


@router.get("/my-submissions")
async def get_my_submissions(
    status: str = Query("in_progress"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """
    Return documents submitted by the current user, with their latest workflow status.

    status: 'in_progress' | 'completed' | 'all'
    """
    normalized = status.lower()
    if normalized == "in_progress":
        wf_status_filter = "aw.status IN ('in_progress', 'human_review_required', 'returned_to_submitter', 'returned_to_step1')"
    elif normalized == "completed":
        wf_status_filter = "aw.status IN ('approved', 'rejected')"
    else:
        wf_status_filter = "1=1"

    offset = (page - 1) * page_size

    rows = db.execute(
        text(
            f"""
            WITH latest_wf AS (
                SELECT DISTINCT ON (doc_id)
                    doc_id,
                    workflow_id,
                    status,
                    current_step,
                    total_steps,
                    step_1_role,
                    step_2_role,
                    submitter_id,
                    resubmit_count,
                    updated_at AS wf_updated_at
                FROM approval_workflows
                ORDER BY doc_id, updated_at DESC, created_at DESC
            )
            SELECT
                d.doc_id,
                d.title,
                d.doc_type,
                d.status AS doc_status,
                d.project_id,
                p.name AS project_name,
                d.created_at,
                d.updated_at,
                lw.workflow_id,
                lw.status AS wf_status,
                lw.current_step,
                lw.total_steps,
                lw.step_1_role,
                lw.step_2_role,
                d.submission_notes,
                lw.resubmit_count
            FROM documents d
            LEFT JOIN projects p ON p.project_id = d.project_id
            LEFT JOIN latest_wf lw ON lw.doc_id = d.doc_id
            WHERE d.created_by = :uid
              AND ({wf_status_filter.replace('aw.status', 'lw.status')})
            ORDER BY d.updated_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {
            "uid": str(current_user.user_id),
            "limit": page_size,
            "offset": offset,
        },
    ).fetchall()

    count_row = db.execute(
        text(
            f"""
            WITH latest_wf AS (
                SELECT DISTINCT ON (doc_id)
                    doc_id,
                    status
                FROM approval_workflows
                ORDER BY doc_id, updated_at DESC, created_at DESC
            )
            SELECT COUNT(*)
            FROM documents d
            LEFT JOIN latest_wf lw ON lw.doc_id = d.doc_id
            WHERE d.created_by = :uid
              AND ({wf_status_filter.replace('aw.status', 'lw.status')})
            """
        ),
        {"uid": str(current_user.user_id)},
    ).fetchone()

    return {
        "requested_by": current_user.email,
        "filters": {"status": normalized},
        "total": int(count_row[0] or 0),
        "page": page,
        "page_size": page_size,
        "documents": [
            {
                "doc_id": str(r[0]),
                "title": r[1],
                "doc_type": r[2],
                "doc_status": r[3],
                "project_id": str(r[4]),
                "project_name": r[5] or "",
                "created_at": r[6].isoformat() if r[6] else None,
                "updated_at": r[7].isoformat() if r[7] else None,
                "workflow_id": str(r[8]) if r[8] else None,
                "workflow_status": r[9],
                "current_step": int(r[10] or 1) if r[10] else None,
                "total_steps": int(r[11] or 2) if r[11] else None,
                "step_1_role": r[12],
                "step_2_role": r[13],
                "submission_notes": r[14] or None,
                "resubmit_count": int(r[15]) if r[15] is not None else 0,
            }
            for r in rows
        ],
    }


@router.get("/{doc_id}/detail")
async def get_document_detail(
    doc_id: str,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """
    Return full document detail: metadata, workflow state, and approval history.
    """
    from app.services import google_drive as _gdrive

    doc_row = db.execute(
        text(
            """
            SELECT
                d.doc_id, d.title, d.doc_type, d.status,
                d.project_id, d.google_drive_link,
                d.created_by, d.created_at, d.updated_at,
                p.name AS project_name,
                u.full_name AS submitter_name,
                u.email AS submitter_email,
                u.role AS submitter_role,
                d.submission_notes
            FROM documents d
            LEFT JOIN projects p ON p.project_id = d.project_id
            LEFT JOIN users u ON u.user_id = d.created_by
            WHERE d.doc_id = :doc_id
            """
        ),
        {"doc_id": doc_id},
    ).fetchone()

    if doc_row is None:
        raise HTTPException(status_code=404, detail="document_not_found")

    # Latest workflow
    wf_row = db.execute(
        text(
            """
            SELECT workflow_id, status, current_step, total_steps,
                   step_1_role, step_2_role, submitter_id
            FROM approval_workflows
            WHERE doc_id = :doc_id
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 1
            """
        ),
        {"doc_id": doc_id},
    ).fetchone()

    workflow = None
    workflow_id_str = None
    if wf_row:
        workflow_id_str = str(wf_row[0])
        workflow = {
            "workflow_id": workflow_id_str,
            "status": wf_row[1],
            "current_step": int(wf_row[2] or 1),
            "total_steps": int(wf_row[3] or 2),
            "step_1_role": wf_row[4],
            "step_2_role": wf_row[5],
            "submitter_id": str(wf_row[6]) if wf_row[6] else None,
        }

    # History: approval decisions UNION audit log entries
    history = []
    if workflow_id_str:
        decision_rows = db.execute(
            text(
                """
                SELECT
                    ad.decision AS action,
                    COALESCE(u.full_name, u.email) AS actor_name,
                    u.role AS actor_role,
                    ad.step_number AS step,
                    ad.comments AS comment,
                    ad.created_at
                FROM approval_decisions ad
                LEFT JOIN users u ON u.user_id = ad.approver_id
                WHERE ad.workflow_id = :wid
                """
            ),
            {"wid": workflow_id_str},
        ).fetchall()

        audit_rows = db.execute(
            text(
                """
                SELECT
                    CASE al.action
                        WHEN 'APPROVAL_CREATED' THEN 'submitted'
                        WHEN 'DOCUMENT_RESUBMITTED' THEN 'resubmitted'
                        ELSE lower(replace(al.action, '_', ' '))
                    END AS action,
                    COALESCE(u.full_name, u.email) AS actor_name,
                    u.role AS actor_role,
                    NULL::int AS step,
                    NULL::text AS comment,
                    al.created_at
                FROM audit_logs al
                LEFT JOIN users u ON u.user_id = al.user_id
                WHERE al.entity_id::text = :wid
                  AND al.action IN ('APPROVAL_CREATED', 'DOCUMENT_RESUBMITTED')
                """
            ),
            {"wid": workflow_id_str},
        ).fetchall()

        all_rows = list(decision_rows) + list(audit_rows)
        all_rows.sort(key=lambda r: r[5] or datetime.utcnow(), reverse=True)

        history = [
            {
                "action": r[0],
                "actor_name": r[1],
                "actor_role": r[2],
                "step": r[3],
                "comment": r[4],
                "created_at": r[5].isoformat() if r[5] else None,
            }
            for r in all_rows
        ]

    # Compute edit URL
    drive_link = doc_row[5]
    mime_type = doc_row[2] or ""
    edit_url = None
    if drive_link:
        file_id = _gdrive.get_drive_file_id(drive_link)
        if file_id:
            edit_url = _gdrive.get_edit_url_for_mime(file_id, mime_type)

    return {
        "doc_id": str(doc_row[0]),
        "title": doc_row[1],
        "doc_type": mime_type,
        "status": doc_row[3],
        "project_id": str(doc_row[4]),
        "project_name": doc_row[9] or "",
        "submitter_id": str(doc_row[6]) if doc_row[6] else None,
        "submitter_name": doc_row[10] or doc_row[11],
        "submitter_role": doc_row[12],
        "google_drive_link": drive_link,
        "edit_url": edit_url,
        "file_mime_type": mime_type,
        "created_at": doc_row[7].isoformat() if doc_row[7] else None,
        "updated_at": doc_row[8].isoformat() if doc_row[8] else None,
        "submission_notes": doc_row[13] or None,
        "workflow": workflow,
        "history": history,
    }

