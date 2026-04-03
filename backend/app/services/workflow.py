"""Approval workflow service: multi-step approvals, returns, and HITL triggers."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.audit import log_audit_event

logger = logging.getLogger(__name__)


# Single-step approval — only Step 1 is used
APPROVAL_STEPS = {
    1: "business_owner",
}


def _resolve_dynamic_roles(submitter_role: str) -> str:
    """Return step_1_role based on the submitter's role (single-step workflow)."""
    if submitter_role == "business_owner":
        return "ba"
    if submitter_role in ("ba", "pm"):
        return "business_owner"
    if submitter_role == "admin":
        return "admin"
    # tech_lead, legal, finance, viewer → default
    return "business_owner"


def _get_expected_role(wf: Dict[str, Any]) -> str:
    """Return the role required for the workflow step (always step 1)."""
    return wf.get("step_1_role") or APPROVAL_STEPS.get(1, "business_owner")


def create_approval_workflow(
    *,
    doc_id: UUID,
    project_id: UUID,
    created_by: UUID,
    workflow_type: str,
    db: Session,
    submitter_role: str = "ba",
) -> Dict[str, Any]:
    """Create a new approval workflow with dynamic role assignment.

    Admin submitters are auto-approved immediately.
    """
    workflow_id = uuid4()
    now = datetime.utcnow()

    # step_2_role retained in DB but no longer used
    step_2_role = None
    step_1_role = _resolve_dynamic_roles(submitter_role)
    total_steps = 1

    initial_status = "in_progress"
    doc_status = "pending_approval"

    db.execute(
        text(
            """
            INSERT INTO approval_workflows
                (workflow_id, doc_id, project_id, current_step, total_steps, status,
                 step_1_role, step_2_role, submitter_id, created_at, updated_at)
            VALUES
                (:workflow_id, :doc_id, :project_id, 1, :total_steps, :status,
                 :step_1_role, :step_2_role, :submitter_id, :created_at, :updated_at)
            """
        ),
        {
            "workflow_id": str(workflow_id),
            "doc_id": str(doc_id),
            "project_id": str(project_id),
            "total_steps": total_steps,
            "status": initial_status,
            "step_1_role": step_1_role,
            "step_2_role": step_2_role,
            "submitter_id": str(created_by),
            "created_at": now,
            "updated_at": now,
        },
    )

    db.execute(
        text(
            "UPDATE documents SET status = :s, updated_at = :t WHERE doc_id = :id"
        ),
        {"s": doc_status, "t": now, "id": str(doc_id)},
    )

    log_audit_event(
        db=db,
        project_id=project_id,
        action="APPROVAL_CREATED",
        entity_type="approval",
        entity_id=workflow_id,
        user_id=created_by,
        old_values={},
        new_values={
            "doc_id": str(doc_id),
            "workflow_type": workflow_type,
            "status": initial_status,
            "step_1_role": step_1_role,
            "step_2_role": step_2_role,
            "submitter_role": submitter_role,
            "total_steps": total_steps,
        },
        succeeded=True,
    )

    return {
        "workflow_id": str(workflow_id),
        "doc_id": str(doc_id),
        "project_id": str(project_id),
        "workflow_type": workflow_type,
        "status": initial_status,
        "current_step": 1,
        "total_steps": total_steps,
        "step_1_role": step_1_role,
        "step_2_role": step_2_role,
        "timestamp": now.isoformat(),
    }


def get_workflow(workflow_id: UUID, db: Session) -> Optional[Dict[str, Any]]:
    row = db.execute(
        text(
            """
            SELECT workflow_id, doc_id, project_id, current_step, total_steps,
                   status, version_id, step_1_role, step_2_role, submitter_id
            FROM approval_workflows
            WHERE workflow_id = :wid
            """
        ),
        {"wid": str(workflow_id)},
    ).fetchone()
    if row is None:
        return None

    step_1 = row[7] or APPROVAL_STEPS.get(1, "business_owner")
    # step_2_role retained in DB but no longer used

    return {
        "workflow_id": str(row[0]),
        "doc_id": str(row[1]),
        "project_id": str(row[2]),
        "current_step": 1,
        "total_steps": 1,
        "status": str(row[5] or "in_progress"),
        "version_id": str(row[6]) if row[6] else None,
        "step_1_role": step_1,
        "step_2_role": None,
        "submitter_id": str(row[9]) if row[9] else None,
    }


def approve_step(
    *,
    workflow_id: UUID,
    actor_user_id: UUID,
    actor_role: str,
    comment: str,
    db: Session,
) -> Dict[str, Any]:
    wf = get_workflow(workflow_id, db)
    if wf is None:
        raise ValueError("Approval workflow not found")

    if wf["status"] in {"approved", "rejected"}:
        raise ValueError(f"Workflow already closed with status={wf['status']}")

    expected_role = _get_expected_role(wf)
    if actor_role != expected_role and actor_role != "admin":
        raise PermissionError(f"Current step requires role '{expected_role}'")

    completed_step = wf["current_step"]
    decision_id = uuid4()
    now = datetime.utcnow()
    db.execute(
        text(
            """
            INSERT INTO approval_decisions
                (decision_id, workflow_id, step_number, approver_id, decision, comments, created_at)
            VALUES
                (:decision_id, :workflow_id, :step_number, :approver_id, 'approved', :comments, :created_at)
            """
        ),
        {
            "decision_id": str(decision_id),
            "workflow_id": wf["workflow_id"],
            "step_number": completed_step,
            "approver_id": str(actor_user_id),
            "comments": comment or None,
            "created_at": now,
        },
    )

    # Single-step workflow: Step 1 approval always results in fully approved
    new_status = "approved"
    new_doc_status = "approved"

    version_id = create_document_version(
        doc_id=UUID(wf["doc_id"]),
        created_by=actor_user_id,
        approval_status=new_status,
        reason=(
            f"Approval action at step {completed_step}: {comment}"
            if comment
            else f"Approval action at step {completed_step}"
        ),
        project_id=UUID(wf["project_id"]),
        workflow_id=workflow_id,
        db=db,
    )

    db.execute(
        text(
            """
            UPDATE approval_workflows
            SET current_step = 1,
                status       = :status,
                version_id   = :version_id,
                updated_at   = :updated_at
            WHERE workflow_id = :workflow_id
            """
        ),
        {
            "status": new_status,
            "version_id": str(version_id),
            "updated_at": now,
            "workflow_id": wf["workflow_id"],
        },
    )
    db.execute(
        text("UPDATE documents SET status = :s, updated_at = :t WHERE doc_id = :id"),
        {"s": new_doc_status, "t": now, "id": wf["doc_id"]},
    )

    # ── Move file to Approved documents/ on final approval ────────────────────
    if new_status == "approved":
        try:
            from app.services import google_drive as _gdrive
            doc_row = db.execute(
                text(
                    """
                    SELECT d.google_drive_file_id, p.name AS project_name
                    FROM documents d
                    LEFT JOIN projects p ON p.project_id = d.project_id
                    WHERE d.doc_id = :did
                    """
                ),
                {"did": wf["doc_id"]},
            ).fetchone()
            if doc_row and doc_row[0]:
                new_link = _gdrive.move_file_to_approved(
                    file_id=doc_row[0],
                    project_name=doc_row[1] or "Unknown Project",
                )
                if new_link:
                    db.execute(
                        text(
                            "UPDATE documents SET google_drive_link = :link, "
                            "google_drive_folder = 'approved', updated_at = :t "
                            "WHERE doc_id = :id"
                        ),
                        {"link": new_link, "t": now, "id": wf["doc_id"]},
                    )
        except Exception as exc:
            logger.warning("Failed to move Drive file to Approved on approval: %s", exc)

    action = "APPROVAL_APPROVED"
    log_audit_event(
        db=db,
        project_id=UUID(wf["project_id"]),
        action=action,
        entity_type="approval",
        entity_id=workflow_id,
        user_id=actor_user_id,
        old_values={"status": wf["status"], "current_step": 1},
        new_values={"status": new_status, "current_step": 1, "version_id": str(version_id)},
        succeeded=True,
    )

    return {
        "workflow_id": wf["workflow_id"],
        "decision_id": str(decision_id),
        "status": new_status,
        "completed_step": completed_step,
        "current_step": 1,
        "next_required_role": None,
        "version_id": str(version_id),
        "submitter_id": wf.get("submitter_id"),
        "timestamp": now.isoformat(),
    }


def reject_step(
    *,
    workflow_id: UUID,
    actor_user_id: UUID,
    actor_role: str,
    reason: str,
    db: Session,
) -> Dict[str, Any]:
    wf = get_workflow(workflow_id, db)
    if wf is None:
        raise ValueError("Approval workflow not found")

    if wf["status"] in {"approved", "rejected"}:
        raise ValueError(f"Workflow already closed with status={wf['status']}")

    expected_role = _get_expected_role(wf)
    if actor_role != expected_role and actor_role != "admin":
        raise PermissionError(f"Current step requires role '{expected_role}'")

    decision_id = uuid4()
    now = datetime.utcnow()
    db.execute(
        text(
            """
            INSERT INTO approval_decisions
                (decision_id, workflow_id, step_number, approver_id, decision, comments, created_at)
            VALUES
                (:decision_id, :workflow_id, :step_number, :approver_id, 'rejected', :comments, :created_at)
            """
        ),
        {
            "decision_id": str(decision_id),
            "workflow_id": wf["workflow_id"],
            "step_number": wf["current_step"],
            "approver_id": str(actor_user_id),
            "comments": reason or None,
            "created_at": now,
        },
    )

    version_id = create_document_version(
        doc_id=UUID(wf["doc_id"]),
        created_by=actor_user_id,
        approval_status="rejected",
        reason=f"Rejection at step {wf['current_step']}: {reason}" if reason else f"Rejection at step {wf['current_step']}",
        project_id=UUID(wf["project_id"]),
        workflow_id=workflow_id,
        db=db,
    )

    db.execute(
        text(
            """
            UPDATE approval_workflows
            SET status = 'rejected',
                updated_at = :updated_at,
                version_id = :version_id
            WHERE workflow_id = :workflow_id
            """
        ),
        {
            "updated_at": now,
            "version_id": str(version_id),
            "workflow_id": wf["workflow_id"],
        },
    )

    db.execute(
        text("UPDATE documents SET status = 'rejected', updated_at = :t WHERE doc_id = :id"),
        {"t": now, "id": wf["doc_id"]},
    )

    log_audit_event(
        db=db,
        project_id=UUID(wf["project_id"]),
        action="APPROVAL_REJECTED",
        entity_type="approval",
        entity_id=workflow_id,
        user_id=actor_user_id,
        old_values={"status": wf["status"], "current_step": wf["current_step"]},
        new_values={"status": "rejected", "reason": reason, "version_id": str(version_id)},
        succeeded=True,
    )

    return {
        "workflow_id": wf["workflow_id"],
        "decision_id": str(decision_id),
        "status": "rejected",
        "current_step": wf["current_step"],
        "version_id": str(version_id),
        "submitter_id": wf.get("submitter_id"),
        "timestamp": now.isoformat(),
    }


def return_step(
    *,
    workflow_id: UUID,
    actor_user_id: UUID,
    actor_role: str,
    comment: str,
    db: Session,
) -> Dict[str, Any]:
    """Return a document — always goes back to submitter (single-step workflow)."""
    wf = get_workflow(workflow_id, db)
    if wf is None:
        raise ValueError("Approval workflow not found")

    if wf["status"] in {"approved", "rejected"}:
        raise ValueError(f"Workflow already closed with status={wf['status']}")

    expected_role = _get_expected_role(wf)
    if actor_role != expected_role and actor_role != "admin":
        raise PermissionError(f"Current step requires role '{expected_role}'")

    current_step = wf["current_step"]
    now = datetime.utcnow()
    decision_id = uuid4()

    db.execute(
        text(
            """
            INSERT INTO approval_decisions
                (decision_id, workflow_id, step_number, approver_id, decision, comments, created_at)
            VALUES
                (:decision_id, :workflow_id, :step_number, :approver_id, 'returned', :comments, :created_at)
            """
        ),
        {
            "decision_id": str(decision_id),
            "workflow_id": wf["workflow_id"],
            "step_number": current_step,
            "approver_id": str(actor_user_id),
            "comments": comment or None,
            "created_at": now,
        },
    )

    # Single-step workflow: returns always go back to submitter
    new_wf_status = "returned_to_submitter"
    new_doc_status = "returned"
    audit_action = "APPROVAL_RETURNED_TO_SUBMITTER"

    reset_step = 1

    version_id = create_document_version(
        doc_id=UUID(wf["doc_id"]),
        created_by=actor_user_id,
        approval_status=new_wf_status,
        reason=(
            f"Returned at step {current_step}: {comment}"
            if comment
            else f"Returned at step {current_step}"
        ),
        project_id=UUID(wf["project_id"]),
        workflow_id=workflow_id,
        db=db,
    )

    db.execute(
        text(
            """
            UPDATE approval_workflows
            SET status     = :status,
                current_step = :current_step,
                version_id = :version_id,
                updated_at = :updated_at
            WHERE workflow_id = :workflow_id
            """
        ),
        {
            "status": new_wf_status,
            "current_step": reset_step,
            "version_id": str(version_id),
            "updated_at": now,
            "workflow_id": wf["workflow_id"],
        },
    )
    db.execute(
        text("UPDATE documents SET status = :s, updated_at = :t WHERE doc_id = :id"),
        {"s": new_doc_status, "t": now, "id": wf["doc_id"]},
    )

    log_audit_event(
        db=db,
        project_id=UUID(wf["project_id"]),
        action=audit_action,
        entity_type="approval",
        entity_id=workflow_id,
        user_id=actor_user_id,
        old_values={"status": wf["status"], "current_step": current_step},
        new_values={"status": new_wf_status, "current_step": reset_step, "version_id": str(version_id)},
        succeeded=True,
    )

    return {
        "workflow_id": wf["workflow_id"],
        "decision_id": str(decision_id),
        "status": new_wf_status,
        "current_step": reset_step,
        "version_id": str(version_id),
        "submitter_id": wf.get("submitter_id"),
        "timestamp": now.isoformat(),
    }


def trigger_hitl(
    *,
    doc_id: UUID,
    project_id: UUID,
    triggered_by: UUID,
    risk_flags: Dict[str, Any],
    reason: str,
    db: Session,
) -> Dict[str, Any]:
    workflow_id = uuid4()
    now = datetime.utcnow()

    db.execute(
        text(
            """
            INSERT INTO approval_workflows
                (workflow_id, doc_id, project_id, current_step, total_steps, status, submitter_id, created_at, updated_at)
            VALUES
                (:workflow_id, :doc_id, :project_id, 1, :total_steps, 'human_review_required', :submitter_id, :created_at, :updated_at)
            """
        ),
        {
            "workflow_id": str(workflow_id),
            "doc_id": str(doc_id),
            "project_id": str(project_id),
            "total_steps": len(APPROVAL_STEPS),
            "submitter_id": str(triggered_by),
            "created_at": now,
            "updated_at": now,
        },
    )

    log_audit_event(
        db=db,
        project_id=project_id,
        action="APPROVAL_CREATED",
        entity_type="approval",
        entity_id=workflow_id,
        user_id=triggered_by,
        old_values={},
        new_values={"status": "human_review_required", "doc_id": str(doc_id), "total_steps": len(APPROVAL_STEPS)},
        succeeded=True,
    )

    version_id = create_document_version(
        doc_id=doc_id,
        created_by=triggered_by,
        approval_status="human_review_required",
        reason=f"HITL triggered: {reason}",
        project_id=project_id,
        workflow_id=workflow_id,
        db=db,
    )

    db.execute(
        text(
            """
            UPDATE approval_workflows
            SET version_id = :version_id, updated_at = :updated_at
            WHERE workflow_id = :workflow_id
            """
        ),
        {
            "version_id": str(version_id),
            "updated_at": now,
            "workflow_id": str(workflow_id),
        },
    )
    db.execute(
        text(
            """
            UPDATE documents
            SET status = 'human_review_required', updated_at = :updated_at
            WHERE doc_id = :doc_id
            """
        ),
        {"updated_at": now, "doc_id": str(doc_id)},
    )

    log_audit_event(
        db=db,
        project_id=project_id,
        action="HITL_TRIGGERED",
        entity_type="approval",
        entity_id=workflow_id,
        user_id=triggered_by,
        old_values={"doc_id": str(doc_id), "status": "pending_approval"},
        new_values={
            "status": "human_review_required",
            "workflow_id": str(workflow_id),
            "risk_flags": risk_flags,
            "reason": reason,
            "version_id": str(version_id),
        },
        succeeded=True,
    )

    return {
        "workflow_id": str(workflow_id),
        "doc_id": str(doc_id),
        "project_id": str(project_id),
        "status": "human_review_required",
        "current_step": 1,
        "next_required_role": APPROVAL_STEPS[1],
        "version_id": str(version_id),
        "timestamp": now.isoformat(),
    }


def create_document_version(
    *,
    doc_id: UUID,
    created_by: UUID,
    approval_status: str,
    reason: str,
    project_id: UUID,
    workflow_id: UUID,
    db: Session,
) -> UUID:
    latest = db.execute(
        text(
            """
            SELECT version_number, content
            FROM document_versions
            WHERE doc_id = :doc_id
            ORDER BY version_number DESC
            LIMIT 1
            """
        ),
        {"doc_id": str(doc_id)},
    ).fetchone()

    version_number = (int(latest[0]) + 1) if latest else 1
    content = str(latest[1]) if latest and latest[1] is not None else ""
    if reason:
        content = f"{content}\n\n[workflow_change] {reason}".strip()

    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    version_id = uuid4()

    db.execute(
        text(
            """
            INSERT INTO document_versions
                (version_id, doc_id, version_number, content, content_hash, created_by, approval_status, created_at)
            VALUES
                (:version_id, :doc_id, :version_number, :content, :content_hash, :created_by, :approval_status, :created_at)
            """
        ),
        {
            "version_id": str(version_id),
            "doc_id": str(doc_id),
            "version_number": version_number,
            "content": content,
            "content_hash": content_hash,
            "created_by": str(created_by),
            "approval_status": approval_status,
            "created_at": datetime.utcnow(),
        },
    )

    log_audit_event(
        db=db,
        project_id=project_id,
        action="VERSION_CREATED",
        entity_type="document_version",
        entity_id=version_id,
        user_id=created_by,
        old_values={},
        new_values={
            "doc_id": str(doc_id),
            "version_number": version_number,
            "approval_status": approval_status,
            "workflow_id": str(workflow_id),
        },
        succeeded=True,
    )

    logger.info("Created document version %s for doc %s", version_number, doc_id)
    return version_id