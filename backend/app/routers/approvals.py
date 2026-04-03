"""Approval workflow endpoints."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_approver, require_ba, require_readonly, require_reviewer
from app.services.db_service import get_db
from app.services import google_sheets
from app.services.workflow import APPROVAL_STEPS, approve_step, create_approval_workflow, get_workflow, reject_step, return_step, trigger_hitl
from app.services.notifications import create_notification, get_role_user_ids

router = APIRouter()
logger = logging.getLogger(__name__)


class ApprovalActionRequest(BaseModel):
    comment: str = ""


class CreateApprovalRequest(BaseModel):
    document_id: UUID
    project_id: UUID
    workflow_type: str = "approval"


class RejectionRequest(BaseModel):
    reason: str = Field(min_length=1)


class ReturnRequest(BaseModel):
    comment: str = Field(min_length=1)


class HitlTriggerRequest(BaseModel):
    document_id: UUID
    project_id: Optional[UUID] = None
    reason: str = Field(min_length=1)
    risk_flags: Dict[str, Any] = {}


@router.post("")
async def create_workflow(
    request: CreateApprovalRequest,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Create a new approval workflow for a document."""
    try:
        result = create_approval_workflow(
            doc_id=request.document_id,
            project_id=request.project_id,
            created_by=UUID(str(current_user.user_id)),
            workflow_type=request.workflow_type,
            db=db,
        )
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"create_workflow_failed: {exc}")


@router.get("")
async def list_approvals(
    project_id: Optional[UUID] = None,
    status: str = Query("pending"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """List approvals filtered by current user role and status (across all projects or one)."""
    normalized = status.lower()
    if normalized not in {"pending", "completed", "all"}:
        raise HTTPException(status_code=400, detail="status must be pending, completed, or all")

    # Case E: IT / viewer roles see nothing in the Approvals page
    if current_user.role in ("it", "viewer"):
        return {
            "requested_by": current_user.email,
            "filters": {"status": normalized},
            "items": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
        }

    if normalized == "pending":
        status_filter = "aw.status IN ('in_progress', 'human_review_required')"
        # Role-based filter:
        # A – step 1 in_progress, current user is step_1_role, NOT the submitter
        # D – admin single-step workflow
        role_filter = """(
            (aw.step_1_role = :urole AND aw.current_step = 1 AND aw.status = 'in_progress' AND aw.submitter_id::text != :uid)
            OR (:urole = 'admin' AND aw.step_1_role = 'admin' AND aw.current_step = 1 AND aw.status = 'in_progress')
        )"""
    elif normalized == "completed":
        status_filter = "aw.status IN ('approved', 'rejected')"
        role_filter = "1=1"
    else:
        status_filter = "aw.status IN ('in_progress', 'human_review_required', 'approved', 'rejected', 'returned_to_submitter')"
        role_filter = "1=1"

    # Optional project filter
    project_filter = "AND aw.project_id = :project_id" if project_id is not None else ""

    offset = (page - 1) * page_size
    query_params: Dict[str, Any] = {
        "limit": page_size,
        "offset": offset,
        "urole": current_user.role,
        "uid": str(current_user.user_id),
    }
    count_params: Dict[str, Any] = {
        "urole": current_user.role,
        "uid": str(current_user.user_id),
    }
    if project_id is not None:
        query_params["project_id"] = str(project_id)
        count_params["project_id"] = str(project_id)

    rows = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT
                    aw.workflow_id,
                    aw.doc_id,
                    COALESCE(d.title, '') AS doc_title,
                    COALESCE(d.doc_type, '') AS doc_type,
                    aw.current_step,
                    aw.total_steps,
                    aw.status,
                    aw.updated_at,
                    d.google_drive_link,
                    aw.step_1_role,
                    d.created_at AS submitted_at,
                    p.name AS project_name,
                    d.submission_notes,
                    aw.resubmit_count,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                LEFT JOIN documents d ON d.doc_id = aw.doc_id
                LEFT JOIN projects p ON p.project_id = aw.project_id
                WHERE 1=1
                  {project_filter}
                  AND {status_filter}
                  AND {role_filter}
            )
                 SELECT workflow_id, doc_id, doc_title, doc_type, current_step, total_steps, status,
                   updated_at, google_drive_link, step_1_role,
                   submitted_at, project_name, submission_notes, resubmit_count
            FROM ranked
            WHERE rn = 1
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        query_params,
    ).fetchall()

    count_row = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT
                    aw.doc_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                WHERE 1=1
                  {project_filter}
                  AND {status_filter}
                  AND {role_filter}
            )
            SELECT COUNT(*)
            FROM ranked
            WHERE rn = 1
            """
        ),
        count_params,
    ).fetchone()

    items = [
        {
            "workflow_id": str(r[0]),
            "doc_id": str(r[1]),
            "doc_title": r[2] or None,
            "doc_type": r[3] or None,
            "current_step": 1,
            "total_steps": 1,
            "status": r[6],
            "updated_at": r[7].isoformat() if r[7] else None,
            "google_drive_link": r[8] or None,
            "step_1_role": r[9] or None,
            "step_2_role": None,
            "submitted_at": r[10].isoformat() if r[10] else None,
            "project_name": r[11] or "",
            "submission_notes": r[12] or None,
            "resubmit_count": int(r[13]) if r[13] is not None else 0,
        }
        for r in rows
    ]

    return {
        "requested_by": current_user.email,
        "filters": {"status": normalized},
        "items": items,
        "total": int(count_row[0] or 0),
        "page": page,
        "page_size": page_size,
    }


@router.get("/pending")
async def get_pending_approvals(
    project_id: UUID,
    user_id: Optional[UUID] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Get pending approvals for a project."""
    offset = (page - 1) * page_size

    rows = db.execute(
        text(
            """
            WITH ranked AS (
                SELECT
                    aw.workflow_id,
                    aw.doc_id,
                    COALESCE(d.title, '') AS doc_title,
                    aw.current_step,
                    aw.total_steps,
                    aw.status,
                    aw.updated_at,
                    d.google_drive_link,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                LEFT JOIN documents d ON d.doc_id = aw.doc_id
                WHERE aw.project_id = :project_id
                  AND aw.status IN ('in_progress', 'human_review_required')
            )
            SELECT workflow_id, doc_id, doc_title, current_step, total_steps, status, updated_at, google_drive_link
            FROM ranked
            WHERE rn = 1
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {
            "project_id": str(project_id),
            "limit": page_size,
            "offset": offset,
        },
    ).fetchall()

    count_row = db.execute(
        text(
            """
            WITH ranked AS (
                SELECT
                    aw.doc_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                WHERE aw.project_id = :project_id
                  AND aw.status IN ('in_progress', 'human_review_required')
            )
            SELECT COUNT(*)
            FROM ranked
            WHERE rn = 1
            """
        ),
        {"project_id": str(project_id)},
    ).fetchone()

    items = [
        {
            "workflow_id": str(r[0]),
            "doc_id": str(r[1]),
            "doc_title": r[2] or None,
            "current_step": 1,
            "total_steps": 1,
            "status": r[5],
            "updated_at": r[6].isoformat() if r[6] else None,
            "google_drive_link": r[7] or None,
        }
        for r in rows
    ]
    return {
        "project_id": str(project_id),
        "requested_by": current_user.email,
        "filters": {"user_id": str(user_id) if user_id else None},
        "items": items,
        "total": int(count_row[0] or 0),
        "page": page,
        "page_size": page_size,
    }


@router.post("/{workflow_id}/approve")
async def approve_document(
    workflow_id: UUID,
    request: ApprovalActionRequest,
    current_user: TokenUser = Depends(require_approver),
    db: Session = Depends(get_db),
):
    """Approve current workflow step and advance to the next role."""
    try:
        result = approve_step(
            workflow_id=workflow_id,
            actor_user_id=UUID(str(current_user.user_id)),
            actor_role=current_user.role,
            comment=request.comment,
            db=db,
        )
        db.commit()
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"approve_failed: {exc}")

    # Notifications (best-effort)
    try:
        wf_info = db.execute(
            text(
                """
                SELECT aw.project_id, d.title, aw.status, aw.step_1_role, aw.submitter_id
                FROM approval_workflows aw
                JOIN documents d ON d.doc_id = aw.doc_id
                WHERE aw.workflow_id = :wid
                """
            ),
            {"wid": str(workflow_id)},
        ).fetchone()
        if wf_info:
            proj_id_str, doc_title, wf_status, s1_role, submitter_id = wf_info
            if wf_status == "approved" and submitter_id:
                create_notification(
                    user_id=submitter_id,
                    title="Document Approved",
                    message=f"Your document '{doc_title}' has been fully approved.",
                    notif_type="success",
                    workflow_id=workflow_id,
                    db=db,
                )
        db.commit()
    except Exception as exc:
        logger.warning("Notifications failed after approve (%s): %s", workflow_id, exc)

    # Update Google Sheets backlog (best-effort, non-fatal)
    try:
        import os as _os
        info = db.execute(
            text(
                """
                SELECT d.title, p.name
                FROM approval_workflows aw
                JOIN documents d ON d.doc_id = aw.doc_id
                JOIN projects p ON p.project_id = aw.project_id
                WHERE aw.workflow_id = :wid
                """
            ),
            {"wid": str(workflow_id)},
        ).fetchone()
        if info:
            google_sheets.update_approval_row(
                project_name=info[1] or "",
                file_name=_os.path.splitext(info[0] or "")[0],
                approver_name=current_user.email,
                status="Approved",
                comment=request.comment if request.comment else "/",
            )
    except Exception as exc:
        logger.warning("Sheets update failed after approve (%s): %s", workflow_id, exc)

    return result


@router.post("/{workflow_id}/reject")
async def reject_document(
    workflow_id: UUID,
    request: RejectionRequest,
    current_user: TokenUser = Depends(require_approver),
    db: Session = Depends(get_db),
):
    """Reject current workflow step and close workflow."""
    try:
        result = reject_step(
            workflow_id=workflow_id,
            actor_user_id=UUID(str(current_user.user_id)),
            actor_role=current_user.role,
            reason=request.reason,
            db=db,
        )
        db.commit()
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"reject_failed: {exc}")

    # Notifications (best-effort)
    try:
        submitter_id = result.get("submitter_id")
        doc_title_row = db.execute(
            text("SELECT d.title FROM approval_workflows aw JOIN documents d ON d.doc_id = aw.doc_id WHERE aw.workflow_id = :wid"),
            {"wid": str(workflow_id)},
        ).fetchone()
        doc_title = doc_title_row[0] if doc_title_row else "document"
        if submitter_id:
            create_notification(
                user_id=submitter_id,
                title="Document Rejected",
                message=f"Your document '{doc_title}' was rejected. Reason: {request.reason}",
                notif_type="error",
                workflow_id=workflow_id,
                db=db,
            )
        db.commit()
    except Exception as exc:
        logger.warning("Notifications failed after reject (%s): %s", workflow_id, exc)

    # Update Google Sheets backlog (best-effort, non-fatal)
    try:
        import os as _os
        info = db.execute(
            text(
                """
                SELECT d.title, p.name
                FROM approval_workflows aw
                JOIN documents d ON d.doc_id = aw.doc_id
                JOIN projects p ON p.project_id = aw.project_id
                WHERE aw.workflow_id = :wid
                """
            ),
            {"wid": str(workflow_id)},
        ).fetchone()
        if info:
            google_sheets.update_approval_row(
                project_name=info[1] or "",
                file_name=_os.path.splitext(info[0] or "")[0],
                approver_name=current_user.email,
                status="Rejected",
                comment=request.reason if request.reason else "/",
            )
    except Exception as exc:
        logger.warning("Sheets update failed after reject (%s): %s", workflow_id, exc)

    return result


@router.post("/{workflow_id}/return")
async def return_document(
    workflow_id: UUID,
    request: ReturnRequest,
    current_user: TokenUser = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    """Return a document to the submitter for revision."""
    try:
        result = return_step(
            workflow_id=workflow_id,
            actor_user_id=UUID(str(current_user.user_id)),
            actor_role=current_user.role,
            comment=request.comment,
            db=db,
        )
        db.commit()
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"return_failed: {exc}")

    # Notifications (best-effort)
    try:
        submitter_id = result.get("submitter_id")
        returned_to = result.get("status")
        doc_title_row = db.execute(
            text("SELECT d.title FROM approval_workflows aw JOIN documents d ON d.doc_id = aw.doc_id WHERE aw.workflow_id = :wid"),
            {"wid": str(workflow_id)},
        ).fetchone()
        doc_title = doc_title_row[0] if doc_title_row else "document"
        if returned_to == "returned_to_submitter" and submitter_id:
            create_notification(
                user_id=submitter_id,
                title="Document Returned",
                message=f"Your document '{doc_title}' has been returned to you for revision. Comment: {request.comment}",
                notif_type="warning",
                workflow_id=workflow_id,
                db=db,
            )
        db.commit()
    except Exception as exc:
        logger.warning("Notifications failed after return (%s): %s", workflow_id, exc)

    # Update Google Sheets backlog (best-effort, non-fatal)
    try:
        import os as _os
        info = db.execute(
            text(
                """
                SELECT d.title, p.name
                FROM approval_workflows aw
                JOIN documents d ON d.doc_id = aw.doc_id
                JOIN projects p ON p.project_id = aw.project_id
                WHERE aw.workflow_id = :wid
                """
            ),
            {"wid": str(workflow_id)},
        ).fetchone()
        if info:
            google_sheets.update_approval_row(
                project_name=info[1] or "",
                file_name=_os.path.splitext(info[0] or "")[0],
                approver_name=current_user.email,
                status="Awaiting Resubmission",
                comment=request.comment if request.comment else "/",
            )
    except Exception as exc:
        logger.warning("Sheets update failed after return (%s): %s", workflow_id, exc)

    return result


@router.post("/hitl-trigger")
async def hitl_trigger(
    request: HitlTriggerRequest,
    current_user: TokenUser = Depends(require_ba),
    db: Session = Depends(get_db),
):
    """Create human-review-required workflow for high-risk content."""
    try:
        project_id = request.project_id
        if project_id is None:
            row = db.execute(
                text("SELECT project_id FROM documents WHERE doc_id = :doc_id LIMIT 1"),
                {"doc_id": str(request.document_id)},
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="document_not_found")
            project_id = UUID(str(row[0]))

        result = trigger_hitl(
            doc_id=request.document_id,
            project_id=project_id,
            triggered_by=UUID(str(current_user.user_id)),
            risk_flags=request.risk_flags,
            reason=request.reason,
            db=db,
        )
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"hitl_trigger_failed: {exc}")


@router.get("/{workflow_id}")
async def get_workflow_status(
    workflow_id: UUID,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Get approval workflow status and decision history."""
    workflow = get_workflow(workflow_id, db)
    if workflow is None:
        raise HTTPException(status_code=404, detail="workflow_not_found")

    decisions = db.execute(
        text(
            """
            SELECT decision_id, step_number, approver_id, decision, comments, created_at
            FROM approval_decisions
            WHERE workflow_id = :workflow_id
            ORDER BY created_at ASC
            """
        ),
        {"workflow_id": str(workflow_id)},
    ).fetchall()

    return {
        **workflow,
        "requested_by": current_user.email,
        "decisions": [
            {
                "decision_id": str(d[0]),
                "step_number": int(d[1]),
                "approver_id": str(d[2]),
                "decision": d[3],
                "comments": d[4],
                "created_at": d[5].isoformat() if d[5] else None,
            }
            for d in decisions
        ],
    }
