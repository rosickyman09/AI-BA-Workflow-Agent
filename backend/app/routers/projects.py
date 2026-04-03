from __future__ import annotations

from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, make_require_role, require_admin, require_readonly
from app.services.db_service import get_db
from app.services.audit import log_audit_event
from app.services import google_drive

router = APIRouter()

require_admin_or_ba = make_require_role(["admin", "ba", "business_owner"])
require_project_creator = make_require_role(["admin", "ba", "business_owner"])
_ALLOWED_PROJECT_STATUSES = {"active", "inactive", "completed"}
_ALLOWED_PROJECT_STATUSES_WITH_FROZEN = {"active", "inactive", "completed", "frozen"}


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = None


class ProjectStatusUpdateRequest(BaseModel):
    status: str = Field(min_length=1, max_length=50)


def _has_project_access(db: Session, project_id: UUID, user_id: str) -> bool:
    row = db.execute(
        text(
            """
            SELECT 1
            FROM user_projects
            WHERE user_id = :user_id AND project_id = :project_id
            LIMIT 1
            """
        ),
        {"user_id": user_id, "project_id": str(project_id)},
    ).fetchone()
    return row is not None


@router.get("")
async def list_projects(
    status: Optional[str] = None,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    filters = []
    params: dict = {}
    if status is not None and status.strip():
        normalized = status.strip().lower()
        if normalized not in _ALLOWED_PROJECT_STATUSES_WITH_FROZEN:
            raise HTTPException(status_code=400, detail="invalid_project_status")
        filters.append("LOWER(COALESCE(p.status, 'active')) = :status")
        params["status"] = normalized

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    rows = db.execute(
        text(
            """
            SELECT p.project_id, p.name, p.description, p.status, COALESCE(p.is_frozen, false) AS is_frozen,
                   p.updated_at
            FROM projects p
            """
            + where_clause
            + """
            ORDER BY p.updated_at DESC
            """
        ),
        params,
    ).fetchall()

    return {
        "items": [
            {
                "project_id": str(r[0]),
                "name": r[1],
                "description": r[2] or "",
                "status": r[3] or "active",
                "is_frozen": bool(r[4]),
                "updated_at": r[5].isoformat() if r[5] else None,
            }
            for r in rows
        ]
    }


@router.post("")
async def create_project(
    request: ProjectCreateRequest,
    current_user: TokenUser = Depends(require_project_creator),
    db: Session = Depends(get_db),
):
    project_id = uuid4()

    try:
        db.execute(
            text(
                """
                INSERT INTO projects (project_id, name, description, status, is_frozen, owner_id, created_by, created_at, updated_at)
                VALUES (:project_id, :name, :description, 'active', false, :owner_id, :created_by, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            {
                "project_id": str(project_id),
                "name": request.name,
                "description": request.description,
                "owner_id": str(current_user.user_id),
                "created_by": str(current_user.user_id),
            },
        )

        db.execute(
            text(
                """
                INSERT INTO user_projects (user_id, project_id, role, created_at)
                VALUES (:user_id, :project_id, 'admin', CURRENT_TIMESTAMP)
                ON CONFLICT (user_id, project_id) DO UPDATE SET role = EXCLUDED.role
                """
            ),
            {"user_id": str(current_user.user_id), "project_id": str(project_id)},
        )

        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"create_project_failed: {exc}")

    # Create project Drive folders only on explicit Create Project action (best-effort)
    folder_info = google_drive.create_project_folders(request.name)
    drive_folder_id: Optional[str] = folder_info.get("project_folder_id") if folder_info else None
    if drive_folder_id:
        try:
            db.execute(
                text(
                    "UPDATE projects SET google_drive_folder_id = :fid WHERE project_id = :pid"
                ),
                {"fid": drive_folder_id, "pid": str(project_id)},
            )
            db.commit()
        except Exception:
            db.rollback()
            # Non-fatal — project record exists, folder ID just won't be stored

    return {
        "project_id": str(project_id),
        "name": request.name,
        "description": request.description,
        "status": "active",
        "is_frozen": False,
        "google_drive_folder_id": drive_folder_id,
        "pending_folder_id": folder_info.get("pending_folder_id") if folder_info else None,
        "approved_folder_id": folder_info.get("approved_folder_id") if folder_info else None,
    }


@router.get("/{project_id}")
async def get_project(
    project_id: UUID,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    row = db.execute(
        text(
            """
            SELECT
                p.project_id,
                p.name,
                p.description,
                p.status,
                COALESCE(p.is_frozen, false) AS is_frozen,
                p.created_at,
                p.updated_at,
                COALESCE(dc.doc_count, 0) AS doc_count
            FROM projects p
            LEFT JOIN (
                SELECT project_id, COUNT(*) AS doc_count
                FROM documents
                GROUP BY project_id
            ) dc ON dc.project_id = p.project_id
            WHERE p.project_id = :project_id
            LIMIT 1
            """
        ),
        {"project_id": str(project_id)},
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="project_not_found")

    return {
        "project_id": str(row[0]),
        "name": row[1],
        "description": row[2] or "",
        "status": row[3] or "active",
        "is_frozen": bool(row[4]),
        "created_at": row[5].isoformat() if row[5] else None,
        "updated_at": row[6].isoformat() if row[6] else None,
        "doc_count": int(row[7] or 0),
    }


@router.get("/{project_id}/documents")
async def list_project_documents(
    project_id: UUID,
    tab: str = "all",
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    tab_value = (tab or "all").strip().lower()
    if tab_value not in {"all", "in_progress", "approved", "rejected"}:
        raise HTTPException(status_code=400, detail="invalid_tab")

    project_exists = db.execute(
        text("SELECT 1 FROM projects WHERE project_id = :project_id LIMIT 1"),
        {"project_id": str(project_id)},
    ).fetchone()
    if project_exists is None:
        raise HTTPException(status_code=404, detail="project_not_found")

    conditions = ["d.project_id = :project_id"]
    if tab_value == "in_progress":
        conditions.append("aw.status IN ('in_progress', 'returned_to_submitter', 'returned_to_step1')")
    elif tab_value == "approved":
        conditions.append("d.status = 'approved'")
        conditions.append("aw.status = 'approved'")
    elif tab_value == "rejected":
        conditions.append("aw.status = 'rejected'")

    where_clause = " AND ".join(conditions)

    rows = db.execute(
        text(
            f"""
            WITH latest_workflow AS (
                SELECT DISTINCT ON (doc_id)
                    doc_id,
                    status,
                    current_step,
                    total_steps,
                    resubmit_count,
                    step_1_role,
                    step_2_role
                FROM approval_workflows
                ORDER BY doc_id, updated_at DESC, created_at DESC
            )
            SELECT
                d.doc_id,
                d.title,
                d.status,
                d.doc_type,
                d.created_at,
                d.updated_at,
                d.google_drive_link,
                d.submission_notes,
                d.google_drive_folder,
                u.full_name AS submitter_name,
                u.role AS submitter_role,
                aw.status AS workflow_status,
                aw.current_step,
                aw.total_steps,
                aw.resubmit_count,
                aw.step_1_role,
                aw.step_2_role,
                d.is_active
            FROM documents d
            LEFT JOIN users u ON d.created_by = u.user_id
            LEFT JOIN latest_workflow aw ON aw.doc_id = d.doc_id
            WHERE {where_clause}
            ORDER BY d.created_at DESC
            """
        ),
        {"project_id": str(project_id)},
    ).fetchall()

    return {
        "project_id": str(project_id),
        "tab": tab_value,
        "documents": [
            {
                "doc_id": str(r[0]),
                "title": r[1],
                "status": r[2],
                "doc_type": r[3],
                "created_at": r[4].isoformat() if r[4] else None,
                "updated_at": r[5].isoformat() if r[5] else None,
                "google_drive_link": r[6] or None,
                "submission_notes": r[7] or None,
                "google_drive_folder": r[8] or None,
                "submitter_name": r[9] or None,
                "submitter_role": r[10] or None,
                "workflow_status": r[11] or None,
                "current_step": int(r[12]) if r[12] is not None else None,
                "total_steps": int(r[13]) if r[13] is not None else None,
                "resubmit_count": int(r[14]) if r[14] is not None else 0,
                "step_1_role": r[15] or None,
                "step_2_role": r[16] or None,
                "is_active": bool(r[17]) if r[17] is not None else True,
            }
            for r in rows
        ],
    }


@router.put("/{project_id}/status")
async def update_project_status(
    project_id: UUID,
    request: ProjectStatusUpdateRequest,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    new_status = request.status.strip().lower()
    if new_status not in _ALLOWED_PROJECT_STATUSES_WITH_FROZEN:
        raise HTTPException(status_code=400, detail="invalid_project_status")

    role = (current_user.role or "").strip().lower()
    if role == "business_owner" and new_status == "frozen":
        raise HTTPException(status_code=403, detail="forbidden_project_status_change")
    if role not in {"admin", "business_owner"}:
        raise HTTPException(status_code=403, detail="forbidden_project_status_change")

    row = db.execute(
        text(
            """
            SELECT project_id, name, status
            FROM projects
            WHERE project_id = :project_id
            LIMIT 1
            """
        ),
        {"project_id": str(project_id)},
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="project_not_found")

    current_status = (row[2] or "active").strip().lower()
    if current_status == "completed" and new_status != "completed":
        raise HTTPException(status_code=400, detail="completed_project_status_locked")

    if current_status == new_status:
        refreshed = db.execute(
            text(
                """
                SELECT project_id, name, status, updated_at
                FROM projects
                WHERE project_id = :project_id
                LIMIT 1
                """
            ),
            {"project_id": str(project_id)},
        ).fetchone()
        return {
            "project_id": str(refreshed[0]),
            "name": refreshed[1],
            "status": refreshed[2] or "active",
            "updated_at": refreshed[3].isoformat() if refreshed[3] else None,
        }

    db.execute(
        text(
            """
            UPDATE projects
            SET status = :new_status,
                updated_at = CURRENT_TIMESTAMP
            WHERE project_id = :project_id
            """
        ),
        {
            "project_id": str(project_id),
            "new_status": new_status,
        },
    )

    log_audit_event(
        db=db,
        project_id=project_id,
        action="PROJECT_STATUS_CHANGED",
        entity_type="project",
        entity_id=project_id,
        user_id=UUID(str(current_user.user_id)),
        old_values={"status": current_status},
        new_values={"status": new_status},
    )

    db.commit()

    refreshed = db.execute(
        text(
            """
            SELECT project_id, name, status, updated_at
            FROM projects
            WHERE project_id = :project_id
            LIMIT 1
            """
        ),
        {"project_id": str(project_id)},
    ).fetchone()

    return {
        "project_id": str(refreshed[0]),
        "name": refreshed[1],
        "status": refreshed[2] or "active",
        "updated_at": refreshed[3].isoformat() if refreshed[3] else None,
    }


@router.put("/{project_id}")
async def update_project(
    project_id: UUID,
    request: ProjectUpdateRequest,
    current_user: TokenUser = Depends(require_admin_or_ba),
    db: Session = Depends(get_db),
):
    row = db.execute(
        text("SELECT is_frozen FROM projects WHERE project_id = :project_id LIMIT 1"),
        {"project_id": str(project_id)},
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="project_not_found")

    if bool(row[0]):
        raise HTTPException(status_code=400, detail="project_is_frozen")

    existing = db.execute(
        text("SELECT name, description, status FROM projects WHERE project_id = :project_id"),
        {"project_id": str(project_id)},
    ).fetchone()

    new_name = request.name if request.name is not None else str(existing[0])
    new_description = request.description if request.description is not None else str(existing[1] or "")
    new_status = str(existing[2] or "active")
    if request.status is not None:
        normalized_status = request.status.strip().lower()
        if normalized_status not in _ALLOWED_PROJECT_STATUSES:
            raise HTTPException(status_code=400, detail="invalid_project_status")
        new_status = normalized_status

    db.execute(
        text(
            """
            UPDATE projects
            SET name = :name,
                description = :description,
                status = :status,
                updated_at = CURRENT_TIMESTAMP
            WHERE project_id = :project_id
            """
        ),
        {
            "project_id": str(project_id),
            "name": new_name,
            "description": new_description,
            "status": new_status,
        },
    )
    db.commit()

    refreshed = db.execute(
        text(
            """
            SELECT project_id, name, description, status, COALESCE(is_frozen, false) AS is_frozen
            FROM projects
            WHERE project_id = :project_id
            LIMIT 1
            """
        ),
        {"project_id": str(project_id)},
    ).fetchone()

    return {
        "project_id": str(refreshed[0]),
        "name": refreshed[1],
        "description": refreshed[2] or "",
        "status": refreshed[3] or "active",
        "is_frozen": bool(refreshed[4]),
    }


@router.post("/{project_id}/freeze")
async def freeze_project(
    project_id: UUID,
    current_user: TokenUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    row = db.execute(
        text("SELECT project_id, name, COALESCE(is_frozen, false) FROM projects WHERE project_id = :project_id LIMIT 1"),
        {"project_id": str(project_id)},
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="project_not_found")

    if bool(row[2]):
        return {"project_id": str(row[0]), "name": row[1], "is_frozen": True}

    db.execute(
        text(
            """
            UPDATE projects
            SET is_frozen = true,
                updated_at = CURRENT_TIMESTAMP
            WHERE project_id = :project_id
            """
        ),
        {"project_id": str(project_id)},
    )
    db.commit()

    return {"project_id": str(row[0]), "name": row[1], "is_frozen": True}
