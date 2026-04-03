# Code Citations

## License: unknown
https://github.com/RakanAji/SMARTPLANTMONITORING_KELOMPOK6/blob/ebf90229ddf582f567c06fafa486befebe2eab2d/src/components/Header.js

```
I now have a complete picture of the codebase. I'm in Ask mode so I cannot write files directly — I'll provide the complete, implementation-ready code for every file to create or modify. Apply them in order.

---

## Implementation

### File 1 — `infra/migrations/005_add_notifications.sql` (NEW)

```sql
-- 005: In-app notifications table
CREATE TABLE IF NOT EXISTS notifications (
  notification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(user_id),
  title VARCHAR(255) NOT NULL,
  message TEXT NOT NULL,
  type VARCHAR(50) NOT NULL DEFAULT 'info',
  is_read BOOLEAN DEFAULT false,
  related_doc_id UUID REFERENCES documents(doc_id),
  related_workflow_id UUID REFERENCES approval_workflows(workflow_id),
  project_name VARCHAR(255),
  doc_name VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_is_read  ON notifications(is_read);
```

---

### File 2 — `infra/migrations/006_add_workflow_roles.sql` (NEW)

```sql
-- 006: Per-workflow dynamic role assignment + submitter tracking
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS step_1_role   VARCHAR(50);
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS step_2_role   VARCHAR(50);
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS submitter_id  UUID REFERENCES users(user_id);
```

---

### File 3 — `backend/app/services/notifications.py` (NEW)

```python
"""DB-backed in-app notification service (distinct from notification.py which is Telegram)."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def create_notification(
    *,
    db: Session,
    user_id: UUID,
    title: str,
    message: str,
    notif_type: str = "info",
    doc_id: Optional[UUID] = None,
    workflow_id: Optional[UUID] = None,
    project_name: str = "",
    doc_name: str = "",
) -> Optional[str]:
    """Insert a notification row. Returns notification_id or None on failure."""
    try:
        nid = str(uuid4())
        db.execute(
            text(
                """
                INSERT INTO notifications
                    (notification_id, user_id, title, message, type, is_read,
                     related_doc_id, related_workflow_id, project_name, doc_name, created_at)
                VALUES
                    (:nid, :uid, :title, :msg, :type, false,
                     :doc_id, :wf_id, :pname, :dname, :ts)
                """
            ),
            {
                "nid": nid,
                "uid": str(user_id),
                "title": title,
                "msg": message,
                "type": notif_type,
                "doc_id": str(doc_id) if doc_id else None,
                "wf_id": str(workflow_id) if workflow_id else None,
                "pname": project_name,
                "dname": doc_name,
                "ts": datetime.utcnow(),
            },
        )
        return nid
    except Exception as exc:
        logger.error("create_notification failed: %s", exc)
        return None


def get_user_notifications(
    *, db: Session, user_id: UUID, limit: int = 20
) -> List[Dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT notification_id, title, message, type, is_read,
                   related_doc_id, related_workflow_id,
                   project_name, doc_name, created_at
            FROM notifications
            WHERE user_id = :uid
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"uid": str(user_id), "limit": limit},
    ).fetchall()
    return [
        {
            "notification_id": str(r[0]),
            "title": r[1],
            "message": r[2],
            "type": r[3],
            "is_read": bool(r[4]),
            "related_doc_id": str(r[5]) if r[5] else None,
            "related_workflow_id": str(r[6]) if r[6] else None,
            "project_name": r[7],
            "doc_name": r[8],
            "created_at": r[9].isoformat() if r[9] else None,
        }
        for r in rows
    ]


def mark_as_read(*, db: Session, notification_id: UUID, user_id: UUID) -> bool:
    result = db.execute(
        text(
            """
            UPDATE notifications
            SET is_read = true
            WHERE notification_id = :nid AND user_id = :uid
            """
        ),
        {"nid": str(notification_id), "uid": str(user_id)},
    )
    return (result.rowcount or 0) > 0


def mark_all_as_read(*, db: Session, user_id: UUID) -> int:
    result = db.execute(
        text(
            "UPDATE notifications SET is_read = true WHERE user_id = :uid AND is_read = false"
        ),
        {"uid": str(user_id)},
    )
    return result.rowcount or 0


def get_unread_count(*, db: Session, user_id: UUID) -> int:
    row = db.execute(
        text(
            "SELECT COUNT(*) FROM notifications WHERE user_id = :uid AND is_read = false"
        ),
        {"uid": str(user_id)},
    ).fetchone()
    return int(row[0] or 0)


def get_role_user_ids(
    *, db: Session, project_id: UUID, role: str
) -> List[str]:
    """Return user_ids that have the given role (system-wide or project-scoped)."""
    rows = db.execute(
        text(
            """
            SELECT DISTINCT u.user_id
            FROM users u
            LEFT JOIN user_projects up
                ON up.user_id = u.user_id AND up.project_id = :pid
            WHERE u.role = :role OR up.role = :role
            LIMIT 20
            """
        ),
        {"pid": str(project_id), "role": role},
    ).fetchall()
    return [str(r[0]) for r in rows]
```

---

### File 4 — `backend/app/services/workflow.py` (COMPLETE REPLACEMENT)

```python
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


# Fallback static step roles — used when a workflow pre-dates dynamic assignment
APPROVAL_STEPS = {
    1: "business_owner",
    2: "admin",
}


def _resolve_dynamic_roles(submitter_role: str) -> Tuple[str, str]:
    """Return (step_1_role, step_2_role) based on the submitter's role."""
    if submitter_role == "business_owner":
        return ("ba", "business_owner")
    if submitter_role in ("ba", "pm"):
        return ("business_owner", "ba")
    # tech_lead, legal, finance, viewer → default
    return ("business_owner", "admin")


def _get_expected_role(wf: Dict[str, Any]) -> str:
    """Return the role required for the current workflow step."""
    if wf["current_step"] == 1:
        return wf.get("step_1_role") or APPROVAL_STEPS.get(1, "business_owner")
    return wf.get("step_2_role") or APPROVAL_STEPS.get(2, "admin")


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
    step_1_role, step_2_role = _resolve_dynamic_roles(submitter_role)
    total_steps = len(APPROVAL_STEPS)

    if submitter_role == "admin":
        initial_status = "approved"
        doc_status = "approved"
    else:
        initial_status = "pending"
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
    step_2 = row[8] or APPROVAL_STEPS.get(2, "admin")

    return {
        "workflow_id": str(row[0]),
        "doc_id": str(row[1]),
        "project_id": str(row[2]),
        "current_step": int(row[3] or 1),
        "total_steps": len(APPROVAL_STEPS),
        "status": str(row[5] or "in_progress"),
        "version_id": str(row[6]) if row[6] else None,
        "step_1_role": step_1,
        "step_2_role": step_2,
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

    next_step = completed_step + 1
    final_step = len(APPROVAL_STEPS)
    new_status = "approved" if next_step > final_step else "in_progress"
    new_doc_status = "approved" if new_status == "approved" else "pending_approval"

    step_roles = {1: wf.get("step_1_role"), 2: wf.get("step_2_role")}
    next_required_role = step_roles.get(next_step) or APPROVAL_STEPS.get(next_step)

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
            SET current_step = :current_step,
                status       = :status,
                version_id   = :version_id,
                updated_at   = :updated_at
            WHERE workflow_id = :workflow_id
            """
        ),
        {
            "current_step": min(next_step, final_step),
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

    log_audit_event(
        db=db,
        project_id=UUID(wf["project_id"]),
        action="APPROVAL_APPROVED",
        entity_type="approval",
        entity_id=workflow_id,
        user_id=actor_user_id,
        old_values={"status": wf["status"], "current_step": completed_step},
        new_values={
            "status": new_status,
            "current_step": min(next_step, final_step),
            "version_id": str(version_id),
        },
        succeeded=True,
    )

    return {
        "workflow_id": wf["workflow_id"],
        "decision_id": str(decision_id),
        "status": new_status,
        "completed_step": completed_step,
        "current_step": min(next_step, final_step),
        "next_required_role": None if new_status == "approved" else next_required_role,
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
        reason=(
            f"Rejection at step {wf['current_step']}: {reason}"
            if reason
            else f"Rejection at step {wf['current_step']}"
        ),
        project_id=UUID(wf["project_id"]),
        workflow_id=workflow_id,
        db=db,
    )

    db.execute(
        text(
            """
            UPDATE approval_workflows
            SET status     = 'rejected',
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
    """Return a document for revision.

    Step 1 → sets status = returned_to_submitter, doc status = returned
    Step 2 → sets status = returned_to_step1, resets to step 1
    """
    wf = get_workflow(workflow_id, db)
    if wf is None:
        raise ValueError("Approval workflow not found")

    if wf["status"] in {"approved", "rejected"}:
        raise ValueError(f"Workflow already closed with status={wf['status']}")

    expected_role = _get_expected_role(wf)
    if actor_role != expected_role and actor_role != "admin":
        raise PermissionError(f"Current step requires role '{expected_role}'")

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
            "step_number": wf["current_step"],
            "approver_id": str(actor_user_id),
            "comments": comment,
            "created_at": now,
        },
    )

    from_step = wf["current_step"]
    if from_step == 1:
        new_wf_status = "returned_to_submitter"
        new_doc_status = "returned"
        audit_action = "APPROVAL_RETURNED_TO_SUBMITTER"
    else:
        new_wf_status = "returned_to_step1"
        new_doc_status = "pending_approval"
        audit_action = "APPROVAL_RETURNED_TO_STEP1"

    version_id = create_document_version(
        doc_id=UUID(wf["doc_id"]),
        created_by=actor_user_id,
        approval_status=new_wf_status,
        reason=f"Returned at step {from_step}: {comment}",
        project_id=UUID(wf["project_id"]),
        workflow_id=workflow_id,
        db=db,
    )

    db.execute(
        text(
            """
            UPDATE approval_workflows
            SET status       = :status,
                current_step = 1,
                version_id   = :version_id,
                updated_at   = :updated_at
            WHERE workflow_id = :workflow_id
            """
        ),
        {
            "status": new_wf_status,
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
        old_values={"status": wf["status"], "current_step": from_step},
        new_values={"status": new_wf_status, "comment": comment, "version_id": str(version_id)},
        succeeded=True,
    )

    return {
        "workflow_id": wf["workflow_id"],
        "decision_id": str(decision_id),
        "status": new_wf_status,
        "current_step": 1,
        "previous_step": from_step,
        "comment": comment,
        "version_id": str(version_id),
        "submitter_id": wf.get("submitter_id"),
        "step_1_role": wf.get("step_1_role"),
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
                (workflow_id, doc_id, project_id, current_step, total_steps, status,
                 submitter_id, created_at, updated_at)
            VALUES
                (:workflow_id, :doc_id, :project_id, 1, :total_steps,
                 'human_review_required', :submitter_id, :created_at, :updated_at)
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
        new_values={
            "status": "human_review_required",
            "doc_id": str(doc_id),
            "total_steps": len(APPROVAL_STEPS),
        },
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
        {"version_id": str(version_id), "updated_at": now, "workflow_id": str(workflow_id)},
    )
    db.execute(
        text(
            "UPDATE documents SET status = 'human_review_required', updated_at = :t WHERE doc_id = :id"
        ),
        {"t": now, "id": str(doc_id)},
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
                (version_id, doc_id, version_number, content, content_hash,
                 created_by, approval_status, created_at)
            VALUES
                (:version_id, :doc_id, :version_number, :content, :content_hash,
                 :created_by, :approval_status, :created_at)
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
```

---

### File 5 — `backend/app/services/google_drive.py` — append at bottom

Add these three functions to the end of the existing [google_drive.py](backend/app/services/google_drive.py):

```python
import re as _re

_MIME_EDIT_URLS = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        "https://docs.google.com/document/d/{id}/edit",
    "application/msword":
        "https://docs.google.com/document/d/{id}/edit",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
    "application/vnd.ms-excel":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
    "text/csv":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
}


def get_drive_file_id(drive_url: str) -> Optional[str]:
    """Extract the Drive file ID from a webViewLink URL."""
    match = _re.search(r"/(?:file/)?d/([a-zA-Z0-9_-]+)", drive_url or "")
    return match.group(1) if match else None


def get_edit_url(file_id: str, mime_type: str) -> str:
    """Return the correct Google Drive / Docs / Sheets URL for the given MIME type."""
    template = _MIME_EDIT_URLS.get(mime_type)
    if template:
        return template.format(id=file_id)
    return f"https://drive.google.com/file/d/{file_id}/view"


def register_file_watch(file_id: str, document_id: str) -> bool:
    """Register a Google Drive push-notification watch (requires verified HTTPS endpoint).

    This stub logs the intent.  In production, call files().watch() with your
    verified webhook URL and store the channel/resource IDs for later expiry renewal.
    """
    logger.info(
        "register_file_watch: file_id=%s doc_id=%s (stub – HTTPS endpoint required)",
        file_id,
        document_id,
    )
    return False
```

---

### File 6 — `backend/app/middleware/rbac.py` — append one line after `require_approver`

Add after `require_approver = ...`:

```python
# Broader reviewer set: includes BA and PM (needed for dynamic step approver assignment)
require_reviewer = make_require_role(["admin", "business_owner", "ba", "pm", "legal"])
```

---

### File 7 — `backend/app/routers/approvals.py` (COMPLETE REPLACEMENT)

```python
"""Approval workflow endpoints."""

from __future__ import annotations

import logging
import os as _os
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_ba, require_readonly, require_reviewer
from app.services.db_service import get_db
from app.services import google_sheets
from app.services import notifications as notif_svc
from app.services.workflow import (
    APPROVAL_STEPS,
    approve_step,
    create_approval_workflow,
    get_workflow,
    reject_step,
    return_step,
    trigger_hitl,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Statuses considered "active / pending" for the dashboard
_PENDING_STATUSES = (
    "in_progress",
    "human_review_required",
    "returned_to_submitter",
    "returned_to_step1",
)
_COMPLETED_STATUSES = ("approved", "rejected")


class ApprovalActionRequest(BaseModel):
    comment: str = ""


class ReturnRequest(BaseModel):
    comment: str = Field(min_length=1)


class CreateApprovalRequest(BaseModel):
    document_id: UUID
    project_id: UUID
    workflow_type: str = "approval"


class RejectionRequest(BaseModel):
    reason: str = Field(min_length=1)


class HitlTriggerRequest(BaseModel):
    document_id: UUID
    project_id: Optional[UUID] = None
    reason: str = Field(min_length=1)
    risk_flags: Dict[str, Any] = {}


# ─── helpers ─────────────────────────────────────────────────────────────────

def _get_doc_project_info(workflow_id: UUID, db: Session):
    """Return (doc_title, project_name, submitter_id) for a workflow."""
    return db.execute(
        text(
            """
            SELECT d.title, p.name, aw.submitter_id
            FROM approval_workflows aw
            JOIN documents d ON d.doc_id = aw.doc_id
            JOIN projects p ON p.project_id = aw.project_id
            WHERE aw.workflow_id = :wid
            """
        ),
        {"wid": str(workflow_id)},
    ).fetchone()


def _status_badge_color(status: str) -> str:
    colors = {
        "in_progress": "info",
        "approved": "success",
        "rejected": "danger",
        "returned_to_submitter": "warning",
        "returned_to_step1": "warning",
        "human_review_required": "secondary",
    }
    return colors.get(status, "secondary")


# ─── endpoints ───────────────────────────────────────────────────────────────

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
            submitter_role=current_user.role,
            db=db,
        )
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"create_workflow_failed: {exc}")


@router.get("")
async def list_approvals(
    project_id: UUID,
    status: str = Query("pending"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """List approvals by status for dashboard views."""
    normalized = status.lower()
    if normalized not in {"pending", "completed", "all"}:
        raise HTTPException(status_code=400, detail="status must be pending, completed, or all")

    pending_in = ", ".join(f"'{s}'" for s in _PENDING_STATUSES)
    completed_in = ", ".join(f"'{s}'" for s in _COMPLETED_STATUSES)

    if normalized == "pending":
        status_filter = f"aw.status IN ({pending_in})"
    elif normalized == "completed":
        status_filter = f"aw.status IN ({completed_in})"
    else:
        status_filter = f"aw.status IN ({pending_in}, {completed_in})"

    offset = (page - 1) * page_size

    rows = db.execute(
        text(
            f"""
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
                    d.doc_type,
                    p.name AS project_name,
                    COALESCE(u.full_name, u.email, '') AS submitter_name,
                    u.role AS submitter_role,
                    aw.step_1_role,
                    aw.step_2_role,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                LEFT JOIN documents d ON d.doc_id = aw.doc_id
                LEFT JOIN projects p ON p.project_id = aw.project_id
                LEFT JOIN users u ON u.user_id = aw.submitter_id
                WHERE aw.project_id = :project_id
                  AND {status_filter}
            )
            SELECT workflow_id, doc_id, doc_title, current_step, total_steps, status,
                   updated_at, google_drive_link, doc_type, project_name,
                   submitter_name, submitter_role, step_1_role, step_2_role
            FROM ranked
            WHERE rn = 1
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"project_id": str(project_id), "limit": page_size, "offset": offset},
    ).fetchall()

    count_row = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT aw.doc_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                WHERE aw.project_id = :project_id AND {status_filter}
            )
            SELECT COUNT(*) FROM ranked WHERE rn = 1
            """
        ),
        {"project_id": str(project_id)},
    ).fetchone()

    items = [
        {
            "workflow_id": str(r[0]),
            "doc_id": str(r[1]),
            "doc_title": r[2] or None,
            "current_step": int(r[3] or 1),
            "total_steps": len(APPROVAL_STEPS),
            "status": r[5],
            "status_color": _status_badge_color(r[5]),
            "updated_at": r[6].isoformat() if r[6] else None,
            "google_drive_link": r[7] or None,
            "doc_type": r[8] or None,
            "project_name": r[9] or None,
            "submitter_name": r[10] or None,
            "submitter_role": r[11] or None,
            "step_1_role": r[12] or None,
            "step_2_role": r[13] or None,
        }
        for r in rows
    ]

    return {
        "project_id": str(project_id),
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
    pending_in = ", ".join(f"'{s}'" for s in _PENDING_STATUSES)
    offset = (page - 1) * page_size

    rows = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT
                    aw.workflow_id, aw.doc_id,
                    COALESCE(d.title, '') AS doc_title,
                    aw.current_step, aw.total_steps, aw.status, aw.updated_at,
                    d.google_drive_link, d.doc_type, p.name AS project_name,
                    COALESCE(u.full_name, u.email, '') AS submitter_name,
                    u.role AS submitter_role, aw.step_1_role, aw.step_2_role,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                LEFT JOIN documents d ON d.doc_id = aw.doc_id
                LEFT JOIN projects p ON p.project_id = aw.project_id
                LEFT JOIN users u ON u.user_id = aw.submitter_id
                WHERE aw.project_id = :project_id
                  AND aw.status IN ({pending_in})
            )
            SELECT workflow_id, doc_id, doc_title, current_step, total_steps, status,
                   updated_at, google_drive_link, doc_type, project_name,
                   submitter_name, submitter_role, step_1_role, step_2_role
            FROM ranked
            WHERE rn = 1
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"project_id": str(project_id), "limit": page_size, "offset": offset},
    ).fetchall()

    count_row = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT aw.doc_id,
                    ROW_NUMBER() OVER (PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC) AS rn
                FROM approval_workflows aw
                WHERE aw.project_id = :project_id
                  AND aw.status IN ({pending_in})
            )
            SELECT COUNT(*) FROM ranked WHERE rn = 1
            """
        ),
        {"project_id": str(project_id)},
    ).fetchone()

    items = [
        {
            "workflow_id": str(r[0]),
            "doc_id": str(r[1]),
            "doc_title": r[2] or None,
            "current_step": int(r[3] or 1),
            "total_steps": len(APPROVAL_STEPS),
            "status": r[5],
            "status_color": _status_badge_color(r[5]),
            "updated_at": r[6].isoformat() if r[6] else None,
            "google_drive_link": r[7] or None,
            "doc_type": r[8] or None,
            "project_name": r[9] or None,
            "submitter_name": r[10] or None,
            "submitter_role": r[11] or None,
            "step_1_role": r[12] or None,
            "step_2_role": r[13] or None,
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
    current_user: TokenUser = Depends(require_reviewer),
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

    # ── Google Sheets update (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            google_sheets.update_approval_row(
                project_name=info[1] or "",
                file_name=_os.path.splitext(info[0] or "")[0],
                approver_name=current_user.email,
                status="Approved",
                comment=request.comment,
            )
    except Exception as exc:
        logger.warning("Sheets update failed after approve (%s): %s", workflow_id, exc)

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            completed_step = result.get("completed_step", 1)
            final_approved = result["status"] == "approved"

            if submitter_id:
                title = "Document Approved ✅" if final_approved else "Document Progressed"
                if final_approved:
                    msg = f"Project {project_name}: '{doc_title}' has been fully approved!"
                else:
                    msg = f"Project {project_name}: '{doc_title}' passed step {completed_step} review."
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title=title,
                    message=msg,
                    notif_type="approved",
                    doc_id=UUID(result["workflow_id"]) if False else None,
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()
    except Exception as exc:
        logger.warning("Notification failed after approve (%s): %s", workflow_id, exc)

    return result


@router.post("/{workflow_id}/reject")
async def reject_document(
    workflow_id: UUID,
    request: RejectionRequest,
    current_user: TokenUser = Depends(require_reviewer),
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

    # ── Google Sheets update (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            google_sheets.update_approval_row(
                project_name=info[1] or "",
                file_name=_os.path.splitext(info[0] or "")[0],
                approver_name=current_user.email,
                status="Rejected",
                comment=request.reason,
            )
    except Exception as exc:
        logger.warning("Sheets update failed after reject (%s): %s", workflow_id, exc)

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            if submitter_id:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title="Document Rejected",
                    message=f"Project {project_name}: '{doc_title}' was rejected. Reason: {request.reason}",
                    notif_type="rejected",
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()
    except Exception as exc:
        logger.warning("Notification failed after reject (%s): %s", workflow_id, exc)

    return result


@router.post("/{workflow_id}/return")
async def return_document(
    workflow_id: UUID,
    request: ReturnRequest,
    current_user: TokenUser = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    """Return a document for revision.

    Step 1 → returned_to_submitter (document status = returned)
    Step 2 → returned_to_step1 (resets to step 1)
    """
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

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            new_status = result["status"]

            if new_status == "returned_to_submitter" and submitter_id:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title="Document Returned",
                    message=(
                        f"Project {project_name}: '{doc_title}' has been returned "
                        f"for revision. Comment: {request.comment}"
                    ),
                    notif_type="returned",
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()

            elif new_status == "returned_to_step1":
                step_1_role = result.get("step_1_role") or "business_owner"
                wf_row = db.execute(
                    text("SELECT project_id FROM approval_workflows WHERE workflow_id = :wid"),
                    {"wid": str(workflow_id)},
                ).fetchone()
                if wf_row:
                    approver_ids = notif_svc.get_role_user_ids(
                        db=db,
                        project_id=UUID(str(wf_row[0])),
                        role=step_1_role,
                    )
                    for uid_str in approver_ids:
                        notif_svc.create_notification(
                            db=db,
                            user_id=UUID(uid_str),
                            title="Re-review Required",
                            message=(
                                f"Project {project_name}: '{doc_title}' has been "
                                f"returned to you for re-review. Comment: {request.comment}"
                            ),
                            notif_type="returned_to_step1",
                            workflow_id=workflow_id,
                            project_name=project_name or "",
                            doc_name=doc_title or "",
                        )
                    db.commit()
    except Exception as exc:
        logger.warning("Notification failed after return (%s): %s", workflow_id, exc)

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
        "status_color": _status_badge_color(workflow["status"]),
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
```

---

### File 8 — `backend/app/routers/documents.py` (COMPLETE REPLACEMENT)

```python
"""
Document management endpoints.

POST /upload            – Accept file + metadata, store to DB, upload to Drive, trigger pipeline
POST /{doc_id}/resubmit – Resubmit a returned document for re-review
GET  /{doc_id}/status   – Return current processing status + progress
"""
import hashlib
import logging
import mimetypes
import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile, File
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_ba, require_readonly
from app.services.db_service import get_db
from app.services import google_drive, google_sheets, elevenlabs, n8n_webhook
from app.services import notifications as notif_svc
from app.services.workflow import _resolve_dynamic_roles

logger = logging.getLogger(__name__)
router = APIRouter()

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
    project_folder_id: Optional[str] = None,
) -> None:
    """Background task: upload to Google Drive, trigger STT + n8n, update status."""
    db: Session = next(get_db())
    try:
        db.execute(
            text("UPDATE documents SET status = :s, updated_at = :t WHERE doc_id = :id"),
            {"s": STATUS_PROCESSING, "t": datetime.utcnow(), "id": doc_id},
        )
        db.commit()

        drive_url: Optional[str] = google_drive.upload_file(
            file_bytes, filename, mime_type, project_folder_id
        )
        if drive_url:
            db.execute(
                text(
                    "UPDATE documents SET google_drive_link = :url, updated_at = :t WHERE doc_id = :id"
                ),
                {"url": drive_url, "t": datetime.utcnow(), "id": doc_id},
            )
            db.commit()

        transcript: Optional[str] = None
        if elevenlabs.is_audio(mime_type):
            transcript = await elevenlabs.transcribe(file_bytes, filename, mime_type)
            if transcript:
                version_id = str(uuid.uuid4())
                db.execute(
                    text(
                        """INSERT INTO document_versions
                             (version_id, doc_id, version_number, content, approval_status, created_at)
                           VALUES (:vid, :did, 1, :content, 'pending', :ts)"""
                    ),
                    {
                        "vid": version_id,
                        "did": doc_id,
                        "content": transcript,
                        "ts": datetime.utcnow(),
                    },
                )
                db.commit()

        await n8n_webhook.trigger_document_workflow(
            workflow_id=workflow_id,
            document_id=doc_id,
            google_drive_url=drive_url,
            file_type=mime_type,
            filename=filename,
        )

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
    current_user: TokenUser = Depends(require_ba),
    db: Session = Depends(get_db),
):
    """
    Upload a document for processing.

    - Requires role: ba / pm / tech_lead / admin  (HTTP 403 otherwise)
    - Returns: {document_id, workflow_id, status: "PENDING"}
    """
    mime_type: str = file.content_type or ""
    if not mime_type or mime_type == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(file.filename or "")
        mime_type = guessed or "application/octet-stream"

    doc_title  = title or (file.filename or "Untitled")
    doc_id     = str(uuid.uuid4())
    workflow_id = str(uuid.uuid4())

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # ── 1. Insert document record ─────────────────────────────────────────
    try:
        db.execute(
            text(
                """INSERT INTO documents
                     (doc_id, project_id, title, doc_type, status, created_by, created_at, updated_at)
                   VALUES (:doc_id, :project_id, :title, :doc_type, :status, :created_by, :now, :now)"""
            ),
            {
                "doc_id":     doc_id,
                "project_id": project_id,
                "title":      doc_title,
                "doc_type":   mime_type,
                "status":     STATUS_PENDING,
                "created_by": current_user.user_id,
                "now":        datetime.utcnow(),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to insert document record: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to store document metadata")

    # ── 2. Determine dynamic roles ────────────────────────────────────────
    step_1_role, step_2_role = _resolve_dynamic_roles(current_user.role)
    auto_approve = current_user.role == "admin"
    initial_wf_status = "approved" if auto_approve else "in_progress"

    # ── 3. Create approval_workflow entry ─────────────────────────────────
    try:
        db.execute(
            text(
                """INSERT INTO approval_workflows
                     (workflow_id, doc_id, project_id, status, current_step, total_steps,
                      step_1_role, step_2_role, submitter_id, created_at, updated_at)
                   VALUES
                     (:wid, :did, :pid, :status, 1, 2,
                      :step_1_role, :step_2_role, :submitter_id, :now, :now)"""
            ),
            {
                "wid":          workflow_id,
                "did":          doc_id,
                "pid":          project_id,
                "status":       initial_wf_status,
                "step_1_role":  step_1_role,
                "step_2_role":  step_2_role,
                "submitter_id": str(current_user.user_id),
                "now":          datetime.utcnow(),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to create approval workflow entry: %s", exc)

    # ── 4. Fetch project Drive folder ─────────────────────────────────────
    project_folder_id: Optional[str] = None
    project_name: str = ""
    try:
        proj_row = db.execute(
            text("SELECT name, google_drive_folder_id FROM projects WHERE project_id = :pid"),
            {"pid": project_id},
        ).fetchone()
        if proj_row:
            project_name     = proj_row[0] or ""
            project_folder_id = proj_row[1] or None
            if project_folder_id is None:
                project_folder_id = google_drive.create_project_folder(project_name)
                if project_folder_id:
                    db.execute(
                        text(
                            "UPDATE projects SET google_drive_folder_id = :fid WHERE project_id = :pid"
                        ),
                        {"fid": project_folder_id, "pid": project_id},
                    )
                    db.commit()
    except Exception as exc:
        logger.warning("Could not fetch project Drive folder for %s: %s", project_id, exc)

    # ── 5. Append row to Google Sheets backlog (best-effort) ──────────────
    try:
        import os as _os
        file_name_no_ext = _os.path.splitext(doc_title)[0]
        google_sheets.append_upload_row(
            user_name=current_user.email,
            project_name=project_name,
            file_name=file_name_no_ext,
            upload_date=datetime.utcnow().strftime("%d-%b-%Y"),
        )
    except Exception as exc:
        logger.warning("Sheets append_upload_row failed for %s: %s", doc_id, exc)

    # ── 6. Notify step-1 approvers (best-effort) ──────────────────────────
    try:
        approver_ids = notif_svc.get_role_user_ids(
            db=db, project_id=UUID(project_id), role=step_1_role
        )
        for uid_str in approver_ids:
            notif_svc.create_notification(
                db=db,
                user_id=UUID(uid_str),
                title="New Review Request",
                message=f"Project {project_name}: '{doc_title}' needs your review.",
                notif_type="upload",
                workflow_id=UUID(workflow_id),
                project_name=project_name,
                doc_name=doc_title,
            )
        db.commit()
    except Exception as exc:
        logger.warning("Upload notification failed for %s: %s", doc_id, exc)

    # ── 7. Queue background processing ────────────────────────────────────
    background_tasks.add_task(
        _process_document,
        doc_id,
        workflow_id,
        file_bytes,
        file.filename or doc_title,
        mime_type,
        project_folder_id,
    )

    logger.info(
        "Document %s queued for processing by %s (workflow %s)",
        doc_id, current_user.email, workflow_id,
    )
    return {
        "document_id":  doc_id,
        "workflow_id":  workflow_id,
        "filename":     file.filename,
        "status":       STATUS_PENDING,
        "uploaded_by":  current_user.email,
        "step_1_role":  step_1_role,
        "step_2_role":  step_2_role,
    }


@router.post("/{doc_id}/resubmit")
async def resubmit_document(
    doc_id: str,
    current_user: TokenUser = Depends(require_ba),
    db: Session = Depends(get_db),
):
    """Resubmit a returned document for re-review (only the original submitter or admin)."""
    doc_row = db.execute(
        text(
            "SELECT doc_id, project_id, title, status, created_by FROM documents WHERE doc_id = :did"
        ),
        {"did": doc_id},
    ).fetchone()
    if doc_row is None:
        raise HTTPException(status_code=404, detail="document_not_found")

    if current_user.role != "admin" and str(doc_row[4]) != str(current_user.user_id):
        raise HTTPException(status_code=403, detail="Only the document submitter can resubmit")

    if doc_row[3] != "returned":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not in 'returned' status (current: {doc_row[3]})",
        )

    wf_row = db.execute(
        text(
            """
            SELECT workflow_id, step_1_role, step_2_role, project_id
            FROM approval_workflows
            WHERE doc_id = :did AND status = 'returned_to_submitter'
            ORDER BY updated_at DESC LIMIT 1
            """
        ),
        {"did": doc_id},
    ).fetchone()

    now = datetime.utcnow()

    # Create new document version
    prev = db.execute(
        text(
            "SELECT version_number, content FROM document_versions WHERE doc_id = :did ORDER BY version_number DESC LIMIT 1"
        ),
        {"did": doc_id},
    ).fetchone()
    new_version_num = (int(prev[0]) + 1) if prev else 1
    content = f"{prev[1] or ''}\n\n[resubmitted by {current_user.email}]".strip() if prev else "[resubmitted]"
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    version_id = str(uuid.uuid4())

    db.execute(
        text(
            """
            INSERT INTO document_versions
                (version_id, doc_id, version_number, content, content_hash,
                 created_by, approval_status, created_at)
            VALUES (:vid, :did, :vn, :content, :hash, :uid, 'pending', :ts)
            """
        ),
        {
            "vid": version_id, "did": doc_id, "vn": new_version_num,
            "content": content, "hash": content_hash,
            "uid": str(current_user.user_id), "ts": now,
        },
    )

    db.execute(
        text("UPDATE documents SET status = 'pending_approval', updated_at = :ts WHERE doc_id = :did"),
        {"ts": now, "did": doc_id},
    )

    wf_id_str: Optional[str] = None
    step_1_role = "business_owner"
    project_id_str = str(doc_row[1])

    if wf_row:
        wf_id_str   = str(wf_row[0])
        step_1_role = wf_row[1] or "business_owner"
        db.execute(
            text(
                "UPDATE approval_workflows SET status = 'in_progress', current_step = 1, updated_at = :ts WHERE workflow_id = :wid"
            ),
            {"ts": now, "wid": wf_id_str},
        )

    db.commit()

    # Notify step-1 approvers (best-effort)
    try:
        pname_row = db.execute(
            text("SELECT name FROM projects WHERE project_id = :pid"),
            {"pid": project_id_str},
        ).fetchone()
        pname = pname_row[0] if pname_row else ""
        approver_ids = notif_svc.get_role_user_ids(
            db=db, project_id=UUID(project_id_str), role=step_1_role
        )
        for uid_str in approver_ids:
            notif_svc.create_notification(
                db=db,
                user_id=UUID(uid_str),
                title="Document Resubmitted",
                message=f"Project {pname}: '{doc_row[2]}' has been revised and resubmitted.",
                notif_type="resubmit",
                workflow_id=UUID(wf_id_str) if wf_id_str else None,
                project_name=pname,
                doc_name=doc_row[2] or "",
            )
        db.commit()
    except Exception as exc:
        logger.warning("Resubmit notification failed for %s: %s", doc_id, exc)

    return {
        "document_id":    doc_id,
        "status":         "pending_approval",
        "version_id":     version_id,
        "resubmitted_by": current_user.email,
    }


@router.get("")
async def list_documents(
    project_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """List documents with optional project filter (auth required)."""
    safe_limit  = max(1, min(limit, 200))
    safe_offset = max(0, offset)

    if project_id:
        rows = db.execute(
            text(
                """SELECT doc_id, project_id, title, doc_type, status, updated_at
                   FROM documents WHERE project_id = :pid
                   ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"""
            ),
            {"pid": project_id, "limit": safe_limit, "offset": safe_offset},
        ).fetchall()
    else:
        rows = db.execute(
            text(
                """SELECT doc_id, project_id, title, doc_type, status, updated_at
                   FROM documents
                   ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"""
            ),
            {"limit": safe_limit, "offset": safe_offset},
        ).fetchall()

    return {
        "requested_by": current_user.email,
        "project_id": project_id,
        "total": len(rows),
        "documents": [
            {
                "doc_id":     str(r[0]),
                "project_id": str(r[1]),
                "title":      r[2],
                "doc_type":   r[3],
                "status":     r[4],
                "updated_at": r[5].isoformat() if r[5] else None,
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
    """Get the current processing status of a document."""
    try:
        row = db.execute(
            text(
                "SELECT doc_id, title, status, doc_type, google_drive_link, updated_at FROM documents WHERE doc_id = :id"
            ),
            {"id": doc_id},
        ).fetchone()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"db_error: {exc}")

    if row is None:
        raise HTTPException(status_code=404, detail="document_not_found")

    status = row[2]
    progress_map = {
        STATUS_PENDING:    10,
        STATUS_PROCESSING: 50,
        STATUS_COMPLETED:  100,
        STATUS_FAILED:     0,
    }

    # Build edit URL if Drive link exists
    edit_url: Optional[str] = None
    drive_link = row[4]
    if drive_link:
        file_id = google_drive.get_drive_file_id(drive_link)
        if file_id:
            edit_url = google_drive.get_edit_url(file_id, row[3] or "")

    return {
        "document_id":      str(row[0]),
        "title":            row[1],
        "status":           status,
        "progress":         progress_map.get(status, 0),
        "doc_type":         row[3],
        "google_drive_url": drive_link,
        "edit_url":         edit_url,
        "updated_at":       row[5].isoformat() if row[5] else None,
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
                "version_id":       str(r[0]),
                "version_number":   int(r[1]),
                "content_hash":     r[2],
                "approval_status":  r[3],
                "created_by":       str(r[4]) if r[4] else None,
                "created_at":       r[5].isoformat() if r[5] else None,
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
            SELECT version_id, version_number, content, content_hash, approval_status, created_by, created_at
            FROM document_versions
            WHERE doc_id = :doc_id AND version_id = :version_id
            """
        ),
        {"doc_id": doc_id, "version_id": version_id},
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="version_not_found")

    return {
        "version_id":       str(row[0]),
        "version_number":   int(row[1]),
        "content":          row[2],
        "content_hash":     row[3],
        "approval_status":  row[4],
        "created_by":       str(row[5]) if row[5] else None,
        "created_at":       row[6].isoformat() if row[6] else None,
    }
```

---

### File 9 — `backend/app/routers/notifications.py` (COMPLETE REPLACEMENT)

```python
"""Notification endpoints — Telegram + in-app DB notifications."""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_admin, require_readonly
from app.services.db_service import get_db
from app.services.notification import notification_service
from app.services.telegram_bot import telegram_bot_service
from app.services import notifications as notif_svc

router = APIRouter()


class NotificationSendRequest(BaseModel):
    message: str = Field(min_length=1)
    type: str = "info"
    project_id: Optional[UUID] = None
    metadata: Dict[str, Any] = {}


class TelegramUpdateRequest(BaseModel):
    update_id: Optional[int] = None
    message: Dict[str, Any] = {}


# ─── Telegram endpoints (unchanged) ──────────────────────────────────────────

@router.post("/send")
async def send_notification(
    request: NotificationSendRequest,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Send a notification through the configured Telegram bot."""
    result = await notification_service.dispatch_notification(
        db=db,
        message=request.message,
        notification_type=request.type,
        actor_user_id=UUID(str(current_user.user_id)),
        project_id=request.project_id,
        metadata=request.metadata,
    )
    db.commit()
    return result


@router.post("/telegram/webhook")
async def telegram_webhook(
    payload: TelegramUpdateRequest,
    db: Session = Depends(get_db),
):
    """Receive Telegram updates and reply to /status, /backlog, /help."""
    message = payload.message or {}
    command_text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id")) if chat.get("id") is not None else None

    if not command_text.startswith("/"):
        return {"ok": True, "handled": False}

    reply_text = notification_service.process_telegram_command(command_text, db)
    sent = await telegram_bot_service.send_message(reply_text, chat_id=chat_id)
    return {
        "ok": True,
        "handled": True,
        "command": command_text.split(" ")[0].lower(),
        "sent": sent,
    }


@router.post("/approval-reminders/run")
async def run_approval_reminders(
    current_user: TokenUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Manual trigger for approval reminders (used by n8n workflow E)."""
    result = await notification_service.send_approval_reminders(db)
    return {**result, "triggered_by": current_user.email}


# ─── In-app DB notifications ─────────────────────────────────────────────────

@router.get("")
async def get_notifications(
    limit: int = 20,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Get in-app notifications for the current user."""
    items = notif_svc.get_user_notifications(
        db=db, user_id=UUID(str(current_user.user_id)), limit=min(limit, 100)
    )
    unread = notif_svc.get_unread_count(db=db, user_id=UUID(str(current_user.user_id)))
    return {"notifications": items, "unread_count": unread}


@router.get("/unread-count")
async def get_unread_count(
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Return unread notification count for the current user."""
    count = notif_svc.get_unread_count(db=db, user_id=UUID(str(current_user.user_id)))
    return {"count": count}


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Mark a single notification as read."""
    updated = notif_svc.mark_as_read(
        db=db,
        notification_id=notification_id,
        user_id=UUID(str(current_user.user_id)),
    )
    db.commit()
    return {"notification_id": str(notification_id), "marked_read": updated}


@router.post("/read-all")
async def mark_all_read(
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Mark all notifications as read for the current user."""
    count = notif_svc.mark_all_as_read(db=db, user_id=UUID(str(current_user.user_id)))
    db.commit()
    return {"marked_count": count}
```

---

### File 10 — `backend/app/routers/webhooks.py` (NEW)

```python
"""Webhook receivers for external integrations (Google Drive change notifications)."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.db_service import get_db
from app.services import notifications as notif_svc

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/drive-changes")
async def drive_changes_webhook(
    request: Request,
    x_goog_resource_id: str = Header(None, alias="X-Goog-Resource-Id"),
    x_goog_channel_id: str = Header(None, alias="X-Goog-Channel-Id"),
    x_goog_resource_state: str = Header(None, alias="X-Goog-Resource-State"),
    db: Session = Depends(get_db),
):
    """Receive Google Drive push notifications for file changes.

    channel_id convention: "doc:{document_id}" (set during register_file_watch).
    """
    logger.info(
        "Drive webhook: channel=%s resource=%s state=%s",
        x_goog_channel_id, x_goog_resource_id, x_goog_resource_state,
    )

    if x_goog_resource_state == "sync":
        return {"ok": True, "type": "sync"}

    if x_goog_channel_id and x_goog_channel_id.startswith("doc:"):
        try:
            doc_id_str = x_goog_channel_id[4:]
            row = db.execute(
                text(
                    """
                    SELECT d.title, d.created_by, p.name
                    FROM documents d
                    JOIN projects p ON p.project_id = d.project_id
                    WHERE d.doc_id = :did
                    """
                ),
                {"did": doc_id_str},
            ).fetchone()
            if row and row[1]:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(row[1])),
                    title="Document Modified",
                    message=f"Your document '{row[0]}' in project '{row[2]}' was modified.",
                    notif_type="file_edited",
                    project_name=row[2] or "",
                    doc_name=row[0] or "",
                )
                db.commit()
        except Exception as exc:
            logger.warning("drive_changes_webhook notification failed: %s", exc)

    return {"ok": True, "type": x_goog_resource_state or "change"}
```

---

### File 11 — `backend/app/main.py` — add webhooks router

In [main.py](backend/app/main.py), add after the existing imports:

```python
from .routers import webhooks as webhooks_router
```

And add the router registration after the existing `app.include_router(notifications_router...)`:

```python
app.include_router(
    webhooks_router.router,
    prefix="/api/webhooks",
    tags=["webhooks"],
)
```

---

### File 12 — `frontend/src/services/documents.ts` — add to end of file

Append to the existing [documents.ts](frontend/src/services/documents.ts):

```typescript
export async function returnWorkflow(workflowId: string, comment: string): Promise<void> {
  await approvalsClient.post(`/${workflowId}/return`, { comment })
}

export async function resubmitDocument(docId: string): Promise<void> {
  const docsClient2 = axios.create({ baseURL: '/api/documents', withCredentials: true })
  await docsClient2.post(`/${docId}/resubmit`)
}

export interface ApprovalItemExtended extends PendingApprovalItem {
  project_name?: string | null
  submitter_name?: string | null
  submitter_role?: string | null
  doc_type?: string | null
  status_color?: string | null
  step_1_role?: string | null
  step_2_role?: string | null
}
```

---

### File 13 — `frontend/src/services/notifications.ts` (NEW)

```typescript
import axios from 'axios'

export interface NotificationItem {
  notification_id: string
  title: string
  message: string
  type: string
  is_read: boolean
  related_doc_id: string | null
  related_workflow_id: string | null
  project_name: string | null
  doc_name: string | null
  created_at: string | null
}

const client = axios.create({
  baseURL: '/api/notifications',
  withCredentials: true,
})

export async function getNotifications(limit = 20): Promise<{ notifications: NotificationItem[]; unread_count: number }> {
  const response = await client.get('', { params: { limit } })
  return response.data
}

export async function getUnreadCount(): Promise<number> {
  const response = await client.get('/unread-count')
  return (response.data as { count: number }).count
}

export async function markAsRead(notificationId: string): Promise<void> {
  await client.post(`/${notificationId}/read`)
}

export async function markAllAsRead(): Promise<void> {
  await client.post('/read-all')
}
```

---

### File 14 — `frontend/src/components/NotificationBell.tsx` (NEW)

```tsx
import React, { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/router'
import {
  getNotifications,
  getUnreadCount,
  markAllAsRead,
  markAsRead,
  type NotificationItem,
} from '@/services/notifications'

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} minute${mins > 1 ? 's' : ''} ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs} hour${hrs > 1 ? 's' : ''} ago`
  return `${Math.floor(hrs / 24)} day${Math.floor(hrs / 24) > 1 ? 's' : ''} ago`
}

export default function NotificationBell() {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<NotificationItem[]>([])
  const [unread, setUnread] = useState(0)
  const ref = useRef<HTMLDivElement>(null)

  const load = async () => {
    try {
      const { notifications, unread_count } = await getNotifications(20)
      setItems(notifications)
      setUnread(unread_count)
    } catch {
      // silent — not authenticated yet
    }
  }

  useEffect(() => {
    void load()
    const interval = setInterval(() => void load(), 30000)
    return () => clearInterval(interval)
  }, [])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleMarkAll = async () => {
    await markAllAsRead()
    setUnread(0)
    setItems((prev) => prev.map((n) => ({ ...n, is_read: true })))
  }

  const handleItemClick = async (item: NotificationItem) => {
    if (!item.is_read) {
      await markAsRead(item.notification_id)
      setItems((prev) =>
        prev.map((n) =>
          n.notification_id === item.notification_id ? { ...n, is_read: true } : n
        )
      )
      setUnread((c) => Math.max(0, c - 1))
    }
    if (item.related_workflow_id) {
      void router.push('/approvals')
    }
    setOpen(false)
  }

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        type="button"
        className="btn btn-link nav-link position-relative p-0 me-3"
        onClick={() => setOpen((o) => !o)}
        aria-label="Notifications"
        style={{ color: 'rgba(255,255,255,0.75)' }}
      >
        🔔
        {unread > 0 && (
          <span
            className="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger"
            style={{ fontSize: '0.65rem' }}
          >
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          className="card shadow"
          style={{
            position: 'absolute',
            right: 0,
            top: '2rem',
            width: '360px',
            maxHeight: '480px',
            overflowY: 'auto',
            zIndex: 1050,
          }}
        >
          <div className="card-header d-flex justify-content-between align-items-center py-2">
            <strong>Notifications</strong>
            {unread > 0 && (
              <button
                type="button"
                className="btn btn-link btn-sm p-0 text-muted"
                onClick={() => void handleMarkAll()}
              >
                Mark all as read
              </button>
            )}
          </div>

          {items.length === 0 ? (
            <div className="card-body text-muted small text-center py-4">No notifications</div>
          ) : (
            <ul className="list-group list-group-flush">
              {items.map((item) => (
                <li
                  key={item.notification_id}
                  className={`list-group-item list-group-item-action ${!item.is_read ? 'fw-bold' : ''}`}
                  style={{ cursor: 'pointer', backgroundColor: item.is_read ? '' : '#f0f7ff' }}
                  onClick={() => void handleItemClick(item)}
                >
                  <div className="d-flex justify-content-between">
                    <span className="small">{item.title}</span>
                    <span className="text-muted" style={{ fontSize: '0.7rem', whiteSpace: 'nowrap' }}>
                      {timeAgo(item.created_at)}
                    </span>
                  </div>
                  <div className="text-muted small" style={{ fontSize: '0.8rem' }}>
                    {(item.message || '').length > 80
                      ? `${item.message.slice(0, 80)}…`
                      : item.message}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
```

---

### File 15 — `frontend/src/components/Layout.tsx` (COMPLETE REPLACEMENT)

```tsx
/**
 * Main Layout Component
 */
import React from 'react'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/router'
import 'bootstrap/dist/css/bootstrap.min.css'
import styles from '@/styles/layout.module.css'
import { getCurrentUser, logout } from '@/services/auth'
import NotificationBell from '@/components/NotificationBell'

interface LayoutProps {
  children: React.ReactNode
}

export function Layout({ children }: LayoutProps) {
  const router = useRouter()
  const [isAuthenticated, setIsAuthenticated] = useState(false)

  useEffect(() => {
    const bootstrap = async () => {
      const user = await getCurrentUser()
      setIsAuthenticated(user !== null)
    }
    void bootstrap()
  }, [router.pathname])

  const handleLogout = async () => {
    await logout()
    router.push('/login')
  }

  return (
    <div className={styles.layout}>
      {isAuthenticated && (
        <nav className={`${styles.navbar} navbar navbar-expand-lg navbar-dark bg-dark`}>
          <div className="container-fluid">
            <Link href="/" className="navbar-brand">
              AI BA Agent
            </Link>
            <div className="collapse navbar-collapse">
              <ul className="navbar-nav ms-auto align-items-center">
                <li className="nav-item">
                  <Link href="/projects" className="nav-link">
                    Projects
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/documents" className="nav-link">
                    Documents
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/approvals" className="nav-link">
                    Approvals
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/knowledge-base" className="nav-link">
                    Knowledge Base
                  </Link>
                </li>
                <li className="nav-item d-flex align-items-center">
                  <NotificationBell />
                </li>
                <li className="nav-item">
                  <button
                    className="nav-link btn btn-link"
                    onClick={handleLogout}
                  >
                    Logout
                  </button>
                </li>
              </ul>
            </div>
          </div>
        </nav>
      )}

      
```


## License: unknown
https://github.com/RakanAji/SMARTPLANTMONITORING_KELOMPOK6/blob/ebf90229ddf582f567c06fafa486befebe2eab2d/src/components/Header.js

```
I now have a complete picture of the codebase. I'm in Ask mode so I cannot write files directly — I'll provide the complete, implementation-ready code for every file to create or modify. Apply them in order.

---

## Implementation

### File 1 — `infra/migrations/005_add_notifications.sql` (NEW)

```sql
-- 005: In-app notifications table
CREATE TABLE IF NOT EXISTS notifications (
  notification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(user_id),
  title VARCHAR(255) NOT NULL,
  message TEXT NOT NULL,
  type VARCHAR(50) NOT NULL DEFAULT 'info',
  is_read BOOLEAN DEFAULT false,
  related_doc_id UUID REFERENCES documents(doc_id),
  related_workflow_id UUID REFERENCES approval_workflows(workflow_id),
  project_name VARCHAR(255),
  doc_name VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_is_read  ON notifications(is_read);
```

---

### File 2 — `infra/migrations/006_add_workflow_roles.sql` (NEW)

```sql
-- 006: Per-workflow dynamic role assignment + submitter tracking
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS step_1_role   VARCHAR(50);
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS step_2_role   VARCHAR(50);
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS submitter_id  UUID REFERENCES users(user_id);
```

---

### File 3 — `backend/app/services/notifications.py` (NEW)

```python
"""DB-backed in-app notification service (distinct from notification.py which is Telegram)."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def create_notification(
    *,
    db: Session,
    user_id: UUID,
    title: str,
    message: str,
    notif_type: str = "info",
    doc_id: Optional[UUID] = None,
    workflow_id: Optional[UUID] = None,
    project_name: str = "",
    doc_name: str = "",
) -> Optional[str]:
    """Insert a notification row. Returns notification_id or None on failure."""
    try:
        nid = str(uuid4())
        db.execute(
            text(
                """
                INSERT INTO notifications
                    (notification_id, user_id, title, message, type, is_read,
                     related_doc_id, related_workflow_id, project_name, doc_name, created_at)
                VALUES
                    (:nid, :uid, :title, :msg, :type, false,
                     :doc_id, :wf_id, :pname, :dname, :ts)
                """
            ),
            {
                "nid": nid,
                "uid": str(user_id),
                "title": title,
                "msg": message,
                "type": notif_type,
                "doc_id": str(doc_id) if doc_id else None,
                "wf_id": str(workflow_id) if workflow_id else None,
                "pname": project_name,
                "dname": doc_name,
                "ts": datetime.utcnow(),
            },
        )
        return nid
    except Exception as exc:
        logger.error("create_notification failed: %s", exc)
        return None


def get_user_notifications(
    *, db: Session, user_id: UUID, limit: int = 20
) -> List[Dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT notification_id, title, message, type, is_read,
                   related_doc_id, related_workflow_id,
                   project_name, doc_name, created_at
            FROM notifications
            WHERE user_id = :uid
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"uid": str(user_id), "limit": limit},
    ).fetchall()
    return [
        {
            "notification_id": str(r[0]),
            "title": r[1],
            "message": r[2],
            "type": r[3],
            "is_read": bool(r[4]),
            "related_doc_id": str(r[5]) if r[5] else None,
            "related_workflow_id": str(r[6]) if r[6] else None,
            "project_name": r[7],
            "doc_name": r[8],
            "created_at": r[9].isoformat() if r[9] else None,
        }
        for r in rows
    ]


def mark_as_read(*, db: Session, notification_id: UUID, user_id: UUID) -> bool:
    result = db.execute(
        text(
            """
            UPDATE notifications
            SET is_read = true
            WHERE notification_id = :nid AND user_id = :uid
            """
        ),
        {"nid": str(notification_id), "uid": str(user_id)},
    )
    return (result.rowcount or 0) > 0


def mark_all_as_read(*, db: Session, user_id: UUID) -> int:
    result = db.execute(
        text(
            "UPDATE notifications SET is_read = true WHERE user_id = :uid AND is_read = false"
        ),
        {"uid": str(user_id)},
    )
    return result.rowcount or 0


def get_unread_count(*, db: Session, user_id: UUID) -> int:
    row = db.execute(
        text(
            "SELECT COUNT(*) FROM notifications WHERE user_id = :uid AND is_read = false"
        ),
        {"uid": str(user_id)},
    ).fetchone()
    return int(row[0] or 0)


def get_role_user_ids(
    *, db: Session, project_id: UUID, role: str
) -> List[str]:
    """Return user_ids that have the given role (system-wide or project-scoped)."""
    rows = db.execute(
        text(
            """
            SELECT DISTINCT u.user_id
            FROM users u
            LEFT JOIN user_projects up
                ON up.user_id = u.user_id AND up.project_id = :pid
            WHERE u.role = :role OR up.role = :role
            LIMIT 20
            """
        ),
        {"pid": str(project_id), "role": role},
    ).fetchall()
    return [str(r[0]) for r in rows]
```

---

### File 4 — `backend/app/services/workflow.py` (COMPLETE REPLACEMENT)

```python
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


# Fallback static step roles — used when a workflow pre-dates dynamic assignment
APPROVAL_STEPS = {
    1: "business_owner",
    2: "admin",
}


def _resolve_dynamic_roles(submitter_role: str) -> Tuple[str, str]:
    """Return (step_1_role, step_2_role) based on the submitter's role."""
    if submitter_role == "business_owner":
        return ("ba", "business_owner")
    if submitter_role in ("ba", "pm"):
        return ("business_owner", "ba")
    # tech_lead, legal, finance, viewer → default
    return ("business_owner", "admin")


def _get_expected_role(wf: Dict[str, Any]) -> str:
    """Return the role required for the current workflow step."""
    if wf["current_step"] == 1:
        return wf.get("step_1_role") or APPROVAL_STEPS.get(1, "business_owner")
    return wf.get("step_2_role") or APPROVAL_STEPS.get(2, "admin")


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
    step_1_role, step_2_role = _resolve_dynamic_roles(submitter_role)
    total_steps = len(APPROVAL_STEPS)

    if submitter_role == "admin":
        initial_status = "approved"
        doc_status = "approved"
    else:
        initial_status = "pending"
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
    step_2 = row[8] or APPROVAL_STEPS.get(2, "admin")

    return {
        "workflow_id": str(row[0]),
        "doc_id": str(row[1]),
        "project_id": str(row[2]),
        "current_step": int(row[3] or 1),
        "total_steps": len(APPROVAL_STEPS),
        "status": str(row[5] or "in_progress"),
        "version_id": str(row[6]) if row[6] else None,
        "step_1_role": step_1,
        "step_2_role": step_2,
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

    next_step = completed_step + 1
    final_step = len(APPROVAL_STEPS)
    new_status = "approved" if next_step > final_step else "in_progress"
    new_doc_status = "approved" if new_status == "approved" else "pending_approval"

    step_roles = {1: wf.get("step_1_role"), 2: wf.get("step_2_role")}
    next_required_role = step_roles.get(next_step) or APPROVAL_STEPS.get(next_step)

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
            SET current_step = :current_step,
                status       = :status,
                version_id   = :version_id,
                updated_at   = :updated_at
            WHERE workflow_id = :workflow_id
            """
        ),
        {
            "current_step": min(next_step, final_step),
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

    log_audit_event(
        db=db,
        project_id=UUID(wf["project_id"]),
        action="APPROVAL_APPROVED",
        entity_type="approval",
        entity_id=workflow_id,
        user_id=actor_user_id,
        old_values={"status": wf["status"], "current_step": completed_step},
        new_values={
            "status": new_status,
            "current_step": min(next_step, final_step),
            "version_id": str(version_id),
        },
        succeeded=True,
    )

    return {
        "workflow_id": wf["workflow_id"],
        "decision_id": str(decision_id),
        "status": new_status,
        "completed_step": completed_step,
        "current_step": min(next_step, final_step),
        "next_required_role": None if new_status == "approved" else next_required_role,
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
        reason=(
            f"Rejection at step {wf['current_step']}: {reason}"
            if reason
            else f"Rejection at step {wf['current_step']}"
        ),
        project_id=UUID(wf["project_id"]),
        workflow_id=workflow_id,
        db=db,
    )

    db.execute(
        text(
            """
            UPDATE approval_workflows
            SET status     = 'rejected',
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
    """Return a document for revision.

    Step 1 → sets status = returned_to_submitter, doc status = returned
    Step 2 → sets status = returned_to_step1, resets to step 1
    """
    wf = get_workflow(workflow_id, db)
    if wf is None:
        raise ValueError("Approval workflow not found")

    if wf["status"] in {"approved", "rejected"}:
        raise ValueError(f"Workflow already closed with status={wf['status']}")

    expected_role = _get_expected_role(wf)
    if actor_role != expected_role and actor_role != "admin":
        raise PermissionError(f"Current step requires role '{expected_role}'")

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
            "step_number": wf["current_step"],
            "approver_id": str(actor_user_id),
            "comments": comment,
            "created_at": now,
        },
    )

    from_step = wf["current_step"]
    if from_step == 1:
        new_wf_status = "returned_to_submitter"
        new_doc_status = "returned"
        audit_action = "APPROVAL_RETURNED_TO_SUBMITTER"
    else:
        new_wf_status = "returned_to_step1"
        new_doc_status = "pending_approval"
        audit_action = "APPROVAL_RETURNED_TO_STEP1"

    version_id = create_document_version(
        doc_id=UUID(wf["doc_id"]),
        created_by=actor_user_id,
        approval_status=new_wf_status,
        reason=f"Returned at step {from_step}: {comment}",
        project_id=UUID(wf["project_id"]),
        workflow_id=workflow_id,
        db=db,
    )

    db.execute(
        text(
            """
            UPDATE approval_workflows
            SET status       = :status,
                current_step = 1,
                version_id   = :version_id,
                updated_at   = :updated_at
            WHERE workflow_id = :workflow_id
            """
        ),
        {
            "status": new_wf_status,
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
        old_values={"status": wf["status"], "current_step": from_step},
        new_values={"status": new_wf_status, "comment": comment, "version_id": str(version_id)},
        succeeded=True,
    )

    return {
        "workflow_id": wf["workflow_id"],
        "decision_id": str(decision_id),
        "status": new_wf_status,
        "current_step": 1,
        "previous_step": from_step,
        "comment": comment,
        "version_id": str(version_id),
        "submitter_id": wf.get("submitter_id"),
        "step_1_role": wf.get("step_1_role"),
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
                (workflow_id, doc_id, project_id, current_step, total_steps, status,
                 submitter_id, created_at, updated_at)
            VALUES
                (:workflow_id, :doc_id, :project_id, 1, :total_steps,
                 'human_review_required', :submitter_id, :created_at, :updated_at)
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
        new_values={
            "status": "human_review_required",
            "doc_id": str(doc_id),
            "total_steps": len(APPROVAL_STEPS),
        },
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
        {"version_id": str(version_id), "updated_at": now, "workflow_id": str(workflow_id)},
    )
    db.execute(
        text(
            "UPDATE documents SET status = 'human_review_required', updated_at = :t WHERE doc_id = :id"
        ),
        {"t": now, "id": str(doc_id)},
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
                (version_id, doc_id, version_number, content, content_hash,
                 created_by, approval_status, created_at)
            VALUES
                (:version_id, :doc_id, :version_number, :content, :content_hash,
                 :created_by, :approval_status, :created_at)
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
```

---

### File 5 — `backend/app/services/google_drive.py` — append at bottom

Add these three functions to the end of the existing [google_drive.py](backend/app/services/google_drive.py):

```python
import re as _re

_MIME_EDIT_URLS = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        "https://docs.google.com/document/d/{id}/edit",
    "application/msword":
        "https://docs.google.com/document/d/{id}/edit",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
    "application/vnd.ms-excel":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
    "text/csv":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
}


def get_drive_file_id(drive_url: str) -> Optional[str]:
    """Extract the Drive file ID from a webViewLink URL."""
    match = _re.search(r"/(?:file/)?d/([a-zA-Z0-9_-]+)", drive_url or "")
    return match.group(1) if match else None


def get_edit_url(file_id: str, mime_type: str) -> str:
    """Return the correct Google Drive / Docs / Sheets URL for the given MIME type."""
    template = _MIME_EDIT_URLS.get(mime_type)
    if template:
        return template.format(id=file_id)
    return f"https://drive.google.com/file/d/{file_id}/view"


def register_file_watch(file_id: str, document_id: str) -> bool:
    """Register a Google Drive push-notification watch (requires verified HTTPS endpoint).

    This stub logs the intent.  In production, call files().watch() with your
    verified webhook URL and store the channel/resource IDs for later expiry renewal.
    """
    logger.info(
        "register_file_watch: file_id=%s doc_id=%s (stub – HTTPS endpoint required)",
        file_id,
        document_id,
    )
    return False
```

---

### File 6 — `backend/app/middleware/rbac.py` — append one line after `require_approver`

Add after `require_approver = ...`:

```python
# Broader reviewer set: includes BA and PM (needed for dynamic step approver assignment)
require_reviewer = make_require_role(["admin", "business_owner", "ba", "pm", "legal"])
```

---

### File 7 — `backend/app/routers/approvals.py` (COMPLETE REPLACEMENT)

```python
"""Approval workflow endpoints."""

from __future__ import annotations

import logging
import os as _os
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_ba, require_readonly, require_reviewer
from app.services.db_service import get_db
from app.services import google_sheets
from app.services import notifications as notif_svc
from app.services.workflow import (
    APPROVAL_STEPS,
    approve_step,
    create_approval_workflow,
    get_workflow,
    reject_step,
    return_step,
    trigger_hitl,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Statuses considered "active / pending" for the dashboard
_PENDING_STATUSES = (
    "in_progress",
    "human_review_required",
    "returned_to_submitter",
    "returned_to_step1",
)
_COMPLETED_STATUSES = ("approved", "rejected")


class ApprovalActionRequest(BaseModel):
    comment: str = ""


class ReturnRequest(BaseModel):
    comment: str = Field(min_length=1)


class CreateApprovalRequest(BaseModel):
    document_id: UUID
    project_id: UUID
    workflow_type: str = "approval"


class RejectionRequest(BaseModel):
    reason: str = Field(min_length=1)


class HitlTriggerRequest(BaseModel):
    document_id: UUID
    project_id: Optional[UUID] = None
    reason: str = Field(min_length=1)
    risk_flags: Dict[str, Any] = {}


# ─── helpers ─────────────────────────────────────────────────────────────────

def _get_doc_project_info(workflow_id: UUID, db: Session):
    """Return (doc_title, project_name, submitter_id) for a workflow."""
    return db.execute(
        text(
            """
            SELECT d.title, p.name, aw.submitter_id
            FROM approval_workflows aw
            JOIN documents d ON d.doc_id = aw.doc_id
            JOIN projects p ON p.project_id = aw.project_id
            WHERE aw.workflow_id = :wid
            """
        ),
        {"wid": str(workflow_id)},
    ).fetchone()


def _status_badge_color(status: str) -> str:
    colors = {
        "in_progress": "info",
        "approved": "success",
        "rejected": "danger",
        "returned_to_submitter": "warning",
        "returned_to_step1": "warning",
        "human_review_required": "secondary",
    }
    return colors.get(status, "secondary")


# ─── endpoints ───────────────────────────────────────────────────────────────

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
            submitter_role=current_user.role,
            db=db,
        )
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"create_workflow_failed: {exc}")


@router.get("")
async def list_approvals(
    project_id: UUID,
    status: str = Query("pending"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """List approvals by status for dashboard views."""
    normalized = status.lower()
    if normalized not in {"pending", "completed", "all"}:
        raise HTTPException(status_code=400, detail="status must be pending, completed, or all")

    pending_in = ", ".join(f"'{s}'" for s in _PENDING_STATUSES)
    completed_in = ", ".join(f"'{s}'" for s in _COMPLETED_STATUSES)

    if normalized == "pending":
        status_filter = f"aw.status IN ({pending_in})"
    elif normalized == "completed":
        status_filter = f"aw.status IN ({completed_in})"
    else:
        status_filter = f"aw.status IN ({pending_in}, {completed_in})"

    offset = (page - 1) * page_size

    rows = db.execute(
        text(
            f"""
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
                    d.doc_type,
                    p.name AS project_name,
                    COALESCE(u.full_name, u.email, '') AS submitter_name,
                    u.role AS submitter_role,
                    aw.step_1_role,
                    aw.step_2_role,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                LEFT JOIN documents d ON d.doc_id = aw.doc_id
                LEFT JOIN projects p ON p.project_id = aw.project_id
                LEFT JOIN users u ON u.user_id = aw.submitter_id
                WHERE aw.project_id = :project_id
                  AND {status_filter}
            )
            SELECT workflow_id, doc_id, doc_title, current_step, total_steps, status,
                   updated_at, google_drive_link, doc_type, project_name,
                   submitter_name, submitter_role, step_1_role, step_2_role
            FROM ranked
            WHERE rn = 1
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"project_id": str(project_id), "limit": page_size, "offset": offset},
    ).fetchall()

    count_row = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT aw.doc_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                WHERE aw.project_id = :project_id AND {status_filter}
            )
            SELECT COUNT(*) FROM ranked WHERE rn = 1
            """
        ),
        {"project_id": str(project_id)},
    ).fetchone()

    items = [
        {
            "workflow_id": str(r[0]),
            "doc_id": str(r[1]),
            "doc_title": r[2] or None,
            "current_step": int(r[3] or 1),
            "total_steps": len(APPROVAL_STEPS),
            "status": r[5],
            "status_color": _status_badge_color(r[5]),
            "updated_at": r[6].isoformat() if r[6] else None,
            "google_drive_link": r[7] or None,
            "doc_type": r[8] or None,
            "project_name": r[9] or None,
            "submitter_name": r[10] or None,
            "submitter_role": r[11] or None,
            "step_1_role": r[12] or None,
            "step_2_role": r[13] or None,
        }
        for r in rows
    ]

    return {
        "project_id": str(project_id),
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
    pending_in = ", ".join(f"'{s}'" for s in _PENDING_STATUSES)
    offset = (page - 1) * page_size

    rows = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT
                    aw.workflow_id, aw.doc_id,
                    COALESCE(d.title, '') AS doc_title,
                    aw.current_step, aw.total_steps, aw.status, aw.updated_at,
                    d.google_drive_link, d.doc_type, p.name AS project_name,
                    COALESCE(u.full_name, u.email, '') AS submitter_name,
                    u.role AS submitter_role, aw.step_1_role, aw.step_2_role,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                LEFT JOIN documents d ON d.doc_id = aw.doc_id
                LEFT JOIN projects p ON p.project_id = aw.project_id
                LEFT JOIN users u ON u.user_id = aw.submitter_id
                WHERE aw.project_id = :project_id
                  AND aw.status IN ({pending_in})
            )
            SELECT workflow_id, doc_id, doc_title, current_step, total_steps, status,
                   updated_at, google_drive_link, doc_type, project_name,
                   submitter_name, submitter_role, step_1_role, step_2_role
            FROM ranked
            WHERE rn = 1
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"project_id": str(project_id), "limit": page_size, "offset": offset},
    ).fetchall()

    count_row = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT aw.doc_id,
                    ROW_NUMBER() OVER (PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC) AS rn
                FROM approval_workflows aw
                WHERE aw.project_id = :project_id
                  AND aw.status IN ({pending_in})
            )
            SELECT COUNT(*) FROM ranked WHERE rn = 1
            """
        ),
        {"project_id": str(project_id)},
    ).fetchone()

    items = [
        {
            "workflow_id": str(r[0]),
            "doc_id": str(r[1]),
            "doc_title": r[2] or None,
            "current_step": int(r[3] or 1),
            "total_steps": len(APPROVAL_STEPS),
            "status": r[5],
            "status_color": _status_badge_color(r[5]),
            "updated_at": r[6].isoformat() if r[6] else None,
            "google_drive_link": r[7] or None,
            "doc_type": r[8] or None,
            "project_name": r[9] or None,
            "submitter_name": r[10] or None,
            "submitter_role": r[11] or None,
            "step_1_role": r[12] or None,
            "step_2_role": r[13] or None,
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
    current_user: TokenUser = Depends(require_reviewer),
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

    # ── Google Sheets update (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            google_sheets.update_approval_row(
                project_name=info[1] or "",
                file_name=_os.path.splitext(info[0] or "")[0],
                approver_name=current_user.email,
                status="Approved",
                comment=request.comment,
            )
    except Exception as exc:
        logger.warning("Sheets update failed after approve (%s): %s", workflow_id, exc)

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            completed_step = result.get("completed_step", 1)
            final_approved = result["status"] == "approved"

            if submitter_id:
                title = "Document Approved ✅" if final_approved else "Document Progressed"
                if final_approved:
                    msg = f"Project {project_name}: '{doc_title}' has been fully approved!"
                else:
                    msg = f"Project {project_name}: '{doc_title}' passed step {completed_step} review."
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title=title,
                    message=msg,
                    notif_type="approved",
                    doc_id=UUID(result["workflow_id"]) if False else None,
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()
    except Exception as exc:
        logger.warning("Notification failed after approve (%s): %s", workflow_id, exc)

    return result


@router.post("/{workflow_id}/reject")
async def reject_document(
    workflow_id: UUID,
    request: RejectionRequest,
    current_user: TokenUser = Depends(require_reviewer),
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

    # ── Google Sheets update (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            google_sheets.update_approval_row(
                project_name=info[1] or "",
                file_name=_os.path.splitext(info[0] or "")[0],
                approver_name=current_user.email,
                status="Rejected",
                comment=request.reason,
            )
    except Exception as exc:
        logger.warning("Sheets update failed after reject (%s): %s", workflow_id, exc)

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            if submitter_id:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title="Document Rejected",
                    message=f"Project {project_name}: '{doc_title}' was rejected. Reason: {request.reason}",
                    notif_type="rejected",
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()
    except Exception as exc:
        logger.warning("Notification failed after reject (%s): %s", workflow_id, exc)

    return result


@router.post("/{workflow_id}/return")
async def return_document(
    workflow_id: UUID,
    request: ReturnRequest,
    current_user: TokenUser = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    """Return a document for revision.

    Step 1 → returned_to_submitter (document status = returned)
    Step 2 → returned_to_step1 (resets to step 1)
    """
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

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            new_status = result["status"]

            if new_status == "returned_to_submitter" and submitter_id:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title="Document Returned",
                    message=(
                        f"Project {project_name}: '{doc_title}' has been returned "
                        f"for revision. Comment: {request.comment}"
                    ),
                    notif_type="returned",
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()

            elif new_status == "returned_to_step1":
                step_1_role = result.get("step_1_role") or "business_owner"
                wf_row = db.execute(
                    text("SELECT project_id FROM approval_workflows WHERE workflow_id = :wid"),
                    {"wid": str(workflow_id)},
                ).fetchone()
                if wf_row:
                    approver_ids = notif_svc.get_role_user_ids(
                        db=db,
                        project_id=UUID(str(wf_row[0])),
                        role=step_1_role,
                    )
                    for uid_str in approver_ids:
                        notif_svc.create_notification(
                            db=db,
                            user_id=UUID(uid_str),
                            title="Re-review Required",
                            message=(
                                f"Project {project_name}: '{doc_title}' has been "
                                f"returned to you for re-review. Comment: {request.comment}"
                            ),
                            notif_type="returned_to_step1",
                            workflow_id=workflow_id,
                            project_name=project_name or "",
                            doc_name=doc_title or "",
                        )
                    db.commit()
    except Exception as exc:
        logger.warning("Notification failed after return (%s): %s", workflow_id, exc)

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
        "status_color": _status_badge_color(workflow["status"]),
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
```

---

### File 8 — `backend/app/routers/documents.py` (COMPLETE REPLACEMENT)

```python
"""
Document management endpoints.

POST /upload            – Accept file + metadata, store to DB, upload to Drive, trigger pipeline
POST /{doc_id}/resubmit – Resubmit a returned document for re-review
GET  /{doc_id}/status   – Return current processing status + progress
"""
import hashlib
import logging
import mimetypes
import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile, File
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_ba, require_readonly
from app.services.db_service import get_db
from app.services import google_drive, google_sheets, elevenlabs, n8n_webhook
from app.services import notifications as notif_svc
from app.services.workflow import _resolve_dynamic_roles

logger = logging.getLogger(__name__)
router = APIRouter()

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
    project_folder_id: Optional[str] = None,
) -> None:
    """Background task: upload to Google Drive, trigger STT + n8n, update status."""
    db: Session = next(get_db())
    try:
        db.execute(
            text("UPDATE documents SET status = :s, updated_at = :t WHERE doc_id = :id"),
            {"s": STATUS_PROCESSING, "t": datetime.utcnow(), "id": doc_id},
        )
        db.commit()

        drive_url: Optional[str] = google_drive.upload_file(
            file_bytes, filename, mime_type, project_folder_id
        )
        if drive_url:
            db.execute(
                text(
                    "UPDATE documents SET google_drive_link = :url, updated_at = :t WHERE doc_id = :id"
                ),
                {"url": drive_url, "t": datetime.utcnow(), "id": doc_id},
            )
            db.commit()

        transcript: Optional[str] = None
        if elevenlabs.is_audio(mime_type):
            transcript = await elevenlabs.transcribe(file_bytes, filename, mime_type)
            if transcript:
                version_id = str(uuid.uuid4())
                db.execute(
                    text(
                        """INSERT INTO document_versions
                             (version_id, doc_id, version_number, content, approval_status, created_at)
                           VALUES (:vid, :did, 1, :content, 'pending', :ts)"""
                    ),
                    {
                        "vid": version_id,
                        "did": doc_id,
                        "content": transcript,
                        "ts": datetime.utcnow(),
                    },
                )
                db.commit()

        await n8n_webhook.trigger_document_workflow(
            workflow_id=workflow_id,
            document_id=doc_id,
            google_drive_url=drive_url,
            file_type=mime_type,
            filename=filename,
        )

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
    current_user: TokenUser = Depends(require_ba),
    db: Session = Depends(get_db),
):
    """
    Upload a document for processing.

    - Requires role: ba / pm / tech_lead / admin  (HTTP 403 otherwise)
    - Returns: {document_id, workflow_id, status: "PENDING"}
    """
    mime_type: str = file.content_type or ""
    if not mime_type or mime_type == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(file.filename or "")
        mime_type = guessed or "application/octet-stream"

    doc_title  = title or (file.filename or "Untitled")
    doc_id     = str(uuid.uuid4())
    workflow_id = str(uuid.uuid4())

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # ── 1. Insert document record ─────────────────────────────────────────
    try:
        db.execute(
            text(
                """INSERT INTO documents
                     (doc_id, project_id, title, doc_type, status, created_by, created_at, updated_at)
                   VALUES (:doc_id, :project_id, :title, :doc_type, :status, :created_by, :now, :now)"""
            ),
            {
                "doc_id":     doc_id,
                "project_id": project_id,
                "title":      doc_title,
                "doc_type":   mime_type,
                "status":     STATUS_PENDING,
                "created_by": current_user.user_id,
                "now":        datetime.utcnow(),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to insert document record: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to store document metadata")

    # ── 2. Determine dynamic roles ────────────────────────────────────────
    step_1_role, step_2_role = _resolve_dynamic_roles(current_user.role)
    auto_approve = current_user.role == "admin"
    initial_wf_status = "approved" if auto_approve else "in_progress"

    # ── 3. Create approval_workflow entry ─────────────────────────────────
    try:
        db.execute(
            text(
                """INSERT INTO approval_workflows
                     (workflow_id, doc_id, project_id, status, current_step, total_steps,
                      step_1_role, step_2_role, submitter_id, created_at, updated_at)
                   VALUES
                     (:wid, :did, :pid, :status, 1, 2,
                      :step_1_role, :step_2_role, :submitter_id, :now, :now)"""
            ),
            {
                "wid":          workflow_id,
                "did":          doc_id,
                "pid":          project_id,
                "status":       initial_wf_status,
                "step_1_role":  step_1_role,
                "step_2_role":  step_2_role,
                "submitter_id": str(current_user.user_id),
                "now":          datetime.utcnow(),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to create approval workflow entry: %s", exc)

    # ── 4. Fetch project Drive folder ─────────────────────────────────────
    project_folder_id: Optional[str] = None
    project_name: str = ""
    try:
        proj_row = db.execute(
            text("SELECT name, google_drive_folder_id FROM projects WHERE project_id = :pid"),
            {"pid": project_id},
        ).fetchone()
        if proj_row:
            project_name     = proj_row[0] or ""
            project_folder_id = proj_row[1] or None
            if project_folder_id is None:
                project_folder_id = google_drive.create_project_folder(project_name)
                if project_folder_id:
                    db.execute(
                        text(
                            "UPDATE projects SET google_drive_folder_id = :fid WHERE project_id = :pid"
                        ),
                        {"fid": project_folder_id, "pid": project_id},
                    )
                    db.commit()
    except Exception as exc:
        logger.warning("Could not fetch project Drive folder for %s: %s", project_id, exc)

    # ── 5. Append row to Google Sheets backlog (best-effort) ──────────────
    try:
        import os as _os
        file_name_no_ext = _os.path.splitext(doc_title)[0]
        google_sheets.append_upload_row(
            user_name=current_user.email,
            project_name=project_name,
            file_name=file_name_no_ext,
            upload_date=datetime.utcnow().strftime("%d-%b-%Y"),
        )
    except Exception as exc:
        logger.warning("Sheets append_upload_row failed for %s: %s", doc_id, exc)

    # ── 6. Notify step-1 approvers (best-effort) ──────────────────────────
    try:
        approver_ids = notif_svc.get_role_user_ids(
            db=db, project_id=UUID(project_id), role=step_1_role
        )
        for uid_str in approver_ids:
            notif_svc.create_notification(
                db=db,
                user_id=UUID(uid_str),
                title="New Review Request",
                message=f"Project {project_name}: '{doc_title}' needs your review.",
                notif_type="upload",
                workflow_id=UUID(workflow_id),
                project_name=project_name,
                doc_name=doc_title,
            )
        db.commit()
    except Exception as exc:
        logger.warning("Upload notification failed for %s: %s", doc_id, exc)

    # ── 7. Queue background processing ────────────────────────────────────
    background_tasks.add_task(
        _process_document,
        doc_id,
        workflow_id,
        file_bytes,
        file.filename or doc_title,
        mime_type,
        project_folder_id,
    )

    logger.info(
        "Document %s queued for processing by %s (workflow %s)",
        doc_id, current_user.email, workflow_id,
    )
    return {
        "document_id":  doc_id,
        "workflow_id":  workflow_id,
        "filename":     file.filename,
        "status":       STATUS_PENDING,
        "uploaded_by":  current_user.email,
        "step_1_role":  step_1_role,
        "step_2_role":  step_2_role,
    }


@router.post("/{doc_id}/resubmit")
async def resubmit_document(
    doc_id: str,
    current_user: TokenUser = Depends(require_ba),
    db: Session = Depends(get_db),
):
    """Resubmit a returned document for re-review (only the original submitter or admin)."""
    doc_row = db.execute(
        text(
            "SELECT doc_id, project_id, title, status, created_by FROM documents WHERE doc_id = :did"
        ),
        {"did": doc_id},
    ).fetchone()
    if doc_row is None:
        raise HTTPException(status_code=404, detail="document_not_found")

    if current_user.role != "admin" and str(doc_row[4]) != str(current_user.user_id):
        raise HTTPException(status_code=403, detail="Only the document submitter can resubmit")

    if doc_row[3] != "returned":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not in 'returned' status (current: {doc_row[3]})",
        )

    wf_row = db.execute(
        text(
            """
            SELECT workflow_id, step_1_role, step_2_role, project_id
            FROM approval_workflows
            WHERE doc_id = :did AND status = 'returned_to_submitter'
            ORDER BY updated_at DESC LIMIT 1
            """
        ),
        {"did": doc_id},
    ).fetchone()

    now = datetime.utcnow()

    # Create new document version
    prev = db.execute(
        text(
            "SELECT version_number, content FROM document_versions WHERE doc_id = :did ORDER BY version_number DESC LIMIT 1"
        ),
        {"did": doc_id},
    ).fetchone()
    new_version_num = (int(prev[0]) + 1) if prev else 1
    content = f"{prev[1] or ''}\n\n[resubmitted by {current_user.email}]".strip() if prev else "[resubmitted]"
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    version_id = str(uuid.uuid4())

    db.execute(
        text(
            """
            INSERT INTO document_versions
                (version_id, doc_id, version_number, content, content_hash,
                 created_by, approval_status, created_at)
            VALUES (:vid, :did, :vn, :content, :hash, :uid, 'pending', :ts)
            """
        ),
        {
            "vid": version_id, "did": doc_id, "vn": new_version_num,
            "content": content, "hash": content_hash,
            "uid": str(current_user.user_id), "ts": now,
        },
    )

    db.execute(
        text("UPDATE documents SET status = 'pending_approval', updated_at = :ts WHERE doc_id = :did"),
        {"ts": now, "did": doc_id},
    )

    wf_id_str: Optional[str] = None
    step_1_role = "business_owner"
    project_id_str = str(doc_row[1])

    if wf_row:
        wf_id_str   = str(wf_row[0])
        step_1_role = wf_row[1] or "business_owner"
        db.execute(
            text(
                "UPDATE approval_workflows SET status = 'in_progress', current_step = 1, updated_at = :ts WHERE workflow_id = :wid"
            ),
            {"ts": now, "wid": wf_id_str},
        )

    db.commit()

    # Notify step-1 approvers (best-effort)
    try:
        pname_row = db.execute(
            text("SELECT name FROM projects WHERE project_id = :pid"),
            {"pid": project_id_str},
        ).fetchone()
        pname = pname_row[0] if pname_row else ""
        approver_ids = notif_svc.get_role_user_ids(
            db=db, project_id=UUID(project_id_str), role=step_1_role
        )
        for uid_str in approver_ids:
            notif_svc.create_notification(
                db=db,
                user_id=UUID(uid_str),
                title="Document Resubmitted",
                message=f"Project {pname}: '{doc_row[2]}' has been revised and resubmitted.",
                notif_type="resubmit",
                workflow_id=UUID(wf_id_str) if wf_id_str else None,
                project_name=pname,
                doc_name=doc_row[2] or "",
            )
        db.commit()
    except Exception as exc:
        logger.warning("Resubmit notification failed for %s: %s", doc_id, exc)

    return {
        "document_id":    doc_id,
        "status":         "pending_approval",
        "version_id":     version_id,
        "resubmitted_by": current_user.email,
    }


@router.get("")
async def list_documents(
    project_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """List documents with optional project filter (auth required)."""
    safe_limit  = max(1, min(limit, 200))
    safe_offset = max(0, offset)

    if project_id:
        rows = db.execute(
            text(
                """SELECT doc_id, project_id, title, doc_type, status, updated_at
                   FROM documents WHERE project_id = :pid
                   ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"""
            ),
            {"pid": project_id, "limit": safe_limit, "offset": safe_offset},
        ).fetchall()
    else:
        rows = db.execute(
            text(
                """SELECT doc_id, project_id, title, doc_type, status, updated_at
                   FROM documents
                   ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"""
            ),
            {"limit": safe_limit, "offset": safe_offset},
        ).fetchall()

    return {
        "requested_by": current_user.email,
        "project_id": project_id,
        "total": len(rows),
        "documents": [
            {
                "doc_id":     str(r[0]),
                "project_id": str(r[1]),
                "title":      r[2],
                "doc_type":   r[3],
                "status":     r[4],
                "updated_at": r[5].isoformat() if r[5] else None,
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
    """Get the current processing status of a document."""
    try:
        row = db.execute(
            text(
                "SELECT doc_id, title, status, doc_type, google_drive_link, updated_at FROM documents WHERE doc_id = :id"
            ),
            {"id": doc_id},
        ).fetchone()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"db_error: {exc}")

    if row is None:
        raise HTTPException(status_code=404, detail="document_not_found")

    status = row[2]
    progress_map = {
        STATUS_PENDING:    10,
        STATUS_PROCESSING: 50,
        STATUS_COMPLETED:  100,
        STATUS_FAILED:     0,
    }

    # Build edit URL if Drive link exists
    edit_url: Optional[str] = None
    drive_link = row[4]
    if drive_link:
        file_id = google_drive.get_drive_file_id(drive_link)
        if file_id:
            edit_url = google_drive.get_edit_url(file_id, row[3] or "")

    return {
        "document_id":      str(row[0]),
        "title":            row[1],
        "status":           status,
        "progress":         progress_map.get(status, 0),
        "doc_type":         row[3],
        "google_drive_url": drive_link,
        "edit_url":         edit_url,
        "updated_at":       row[5].isoformat() if row[5] else None,
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
                "version_id":       str(r[0]),
                "version_number":   int(r[1]),
                "content_hash":     r[2],
                "approval_status":  r[3],
                "created_by":       str(r[4]) if r[4] else None,
                "created_at":       r[5].isoformat() if r[5] else None,
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
            SELECT version_id, version_number, content, content_hash, approval_status, created_by, created_at
            FROM document_versions
            WHERE doc_id = :doc_id AND version_id = :version_id
            """
        ),
        {"doc_id": doc_id, "version_id": version_id},
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="version_not_found")

    return {
        "version_id":       str(row[0]),
        "version_number":   int(row[1]),
        "content":          row[2],
        "content_hash":     row[3],
        "approval_status":  row[4],
        "created_by":       str(row[5]) if row[5] else None,
        "created_at":       row[6].isoformat() if row[6] else None,
    }
```

---

### File 9 — `backend/app/routers/notifications.py` (COMPLETE REPLACEMENT)

```python
"""Notification endpoints — Telegram + in-app DB notifications."""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_admin, require_readonly
from app.services.db_service import get_db
from app.services.notification import notification_service
from app.services.telegram_bot import telegram_bot_service
from app.services import notifications as notif_svc

router = APIRouter()


class NotificationSendRequest(BaseModel):
    message: str = Field(min_length=1)
    type: str = "info"
    project_id: Optional[UUID] = None
    metadata: Dict[str, Any] = {}


class TelegramUpdateRequest(BaseModel):
    update_id: Optional[int] = None
    message: Dict[str, Any] = {}


# ─── Telegram endpoints (unchanged) ──────────────────────────────────────────

@router.post("/send")
async def send_notification(
    request: NotificationSendRequest,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Send a notification through the configured Telegram bot."""
    result = await notification_service.dispatch_notification(
        db=db,
        message=request.message,
        notification_type=request.type,
        actor_user_id=UUID(str(current_user.user_id)),
        project_id=request.project_id,
        metadata=request.metadata,
    )
    db.commit()
    return result


@router.post("/telegram/webhook")
async def telegram_webhook(
    payload: TelegramUpdateRequest,
    db: Session = Depends(get_db),
):
    """Receive Telegram updates and reply to /status, /backlog, /help."""
    message = payload.message or {}
    command_text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id")) if chat.get("id") is not None else None

    if not command_text.startswith("/"):
        return {"ok": True, "handled": False}

    reply_text = notification_service.process_telegram_command(command_text, db)
    sent = await telegram_bot_service.send_message(reply_text, chat_id=chat_id)
    return {
        "ok": True,
        "handled": True,
        "command": command_text.split(" ")[0].lower(),
        "sent": sent,
    }


@router.post("/approval-reminders/run")
async def run_approval_reminders(
    current_user: TokenUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Manual trigger for approval reminders (used by n8n workflow E)."""
    result = await notification_service.send_approval_reminders(db)
    return {**result, "triggered_by": current_user.email}


# ─── In-app DB notifications ─────────────────────────────────────────────────

@router.get("")
async def get_notifications(
    limit: int = 20,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Get in-app notifications for the current user."""
    items = notif_svc.get_user_notifications(
        db=db, user_id=UUID(str(current_user.user_id)), limit=min(limit, 100)
    )
    unread = notif_svc.get_unread_count(db=db, user_id=UUID(str(current_user.user_id)))
    return {"notifications": items, "unread_count": unread}


@router.get("/unread-count")
async def get_unread_count(
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Return unread notification count for the current user."""
    count = notif_svc.get_unread_count(db=db, user_id=UUID(str(current_user.user_id)))
    return {"count": count}


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Mark a single notification as read."""
    updated = notif_svc.mark_as_read(
        db=db,
        notification_id=notification_id,
        user_id=UUID(str(current_user.user_id)),
    )
    db.commit()
    return {"notification_id": str(notification_id), "marked_read": updated}


@router.post("/read-all")
async def mark_all_read(
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Mark all notifications as read for the current user."""
    count = notif_svc.mark_all_as_read(db=db, user_id=UUID(str(current_user.user_id)))
    db.commit()
    return {"marked_count": count}
```

---

### File 10 — `backend/app/routers/webhooks.py` (NEW)

```python
"""Webhook receivers for external integrations (Google Drive change notifications)."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.db_service import get_db
from app.services import notifications as notif_svc

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/drive-changes")
async def drive_changes_webhook(
    request: Request,
    x_goog_resource_id: str = Header(None, alias="X-Goog-Resource-Id"),
    x_goog_channel_id: str = Header(None, alias="X-Goog-Channel-Id"),
    x_goog_resource_state: str = Header(None, alias="X-Goog-Resource-State"),
    db: Session = Depends(get_db),
):
    """Receive Google Drive push notifications for file changes.

    channel_id convention: "doc:{document_id}" (set during register_file_watch).
    """
    logger.info(
        "Drive webhook: channel=%s resource=%s state=%s",
        x_goog_channel_id, x_goog_resource_id, x_goog_resource_state,
    )

    if x_goog_resource_state == "sync":
        return {"ok": True, "type": "sync"}

    if x_goog_channel_id and x_goog_channel_id.startswith("doc:"):
        try:
            doc_id_str = x_goog_channel_id[4:]
            row = db.execute(
                text(
                    """
                    SELECT d.title, d.created_by, p.name
                    FROM documents d
                    JOIN projects p ON p.project_id = d.project_id
                    WHERE d.doc_id = :did
                    """
                ),
                {"did": doc_id_str},
            ).fetchone()
            if row and row[1]:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(row[1])),
                    title="Document Modified",
                    message=f"Your document '{row[0]}' in project '{row[2]}' was modified.",
                    notif_type="file_edited",
                    project_name=row[2] or "",
                    doc_name=row[0] or "",
                )
                db.commit()
        except Exception as exc:
            logger.warning("drive_changes_webhook notification failed: %s", exc)

    return {"ok": True, "type": x_goog_resource_state or "change"}
```

---

### File 11 — `backend/app/main.py` — add webhooks router

In [main.py](backend/app/main.py), add after the existing imports:

```python
from .routers import webhooks as webhooks_router
```

And add the router registration after the existing `app.include_router(notifications_router...)`:

```python
app.include_router(
    webhooks_router.router,
    prefix="/api/webhooks",
    tags=["webhooks"],
)
```

---

### File 12 — `frontend/src/services/documents.ts` — add to end of file

Append to the existing [documents.ts](frontend/src/services/documents.ts):

```typescript
export async function returnWorkflow(workflowId: string, comment: string): Promise<void> {
  await approvalsClient.post(`/${workflowId}/return`, { comment })
}

export async function resubmitDocument(docId: string): Promise<void> {
  const docsClient2 = axios.create({ baseURL: '/api/documents', withCredentials: true })
  await docsClient2.post(`/${docId}/resubmit`)
}

export interface ApprovalItemExtended extends PendingApprovalItem {
  project_name?: string | null
  submitter_name?: string | null
  submitter_role?: string | null
  doc_type?: string | null
  status_color?: string | null
  step_1_role?: string | null
  step_2_role?: string | null
}
```

---

### File 13 — `frontend/src/services/notifications.ts` (NEW)

```typescript
import axios from 'axios'

export interface NotificationItem {
  notification_id: string
  title: string
  message: string
  type: string
  is_read: boolean
  related_doc_id: string | null
  related_workflow_id: string | null
  project_name: string | null
  doc_name: string | null
  created_at: string | null
}

const client = axios.create({
  baseURL: '/api/notifications',
  withCredentials: true,
})

export async function getNotifications(limit = 20): Promise<{ notifications: NotificationItem[]; unread_count: number }> {
  const response = await client.get('', { params: { limit } })
  return response.data
}

export async function getUnreadCount(): Promise<number> {
  const response = await client.get('/unread-count')
  return (response.data as { count: number }).count
}

export async function markAsRead(notificationId: string): Promise<void> {
  await client.post(`/${notificationId}/read`)
}

export async function markAllAsRead(): Promise<void> {
  await client.post('/read-all')
}
```

---

### File 14 — `frontend/src/components/NotificationBell.tsx` (NEW)

```tsx
import React, { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/router'
import {
  getNotifications,
  getUnreadCount,
  markAllAsRead,
  markAsRead,
  type NotificationItem,
} from '@/services/notifications'

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} minute${mins > 1 ? 's' : ''} ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs} hour${hrs > 1 ? 's' : ''} ago`
  return `${Math.floor(hrs / 24)} day${Math.floor(hrs / 24) > 1 ? 's' : ''} ago`
}

export default function NotificationBell() {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<NotificationItem[]>([])
  const [unread, setUnread] = useState(0)
  const ref = useRef<HTMLDivElement>(null)

  const load = async () => {
    try {
      const { notifications, unread_count } = await getNotifications(20)
      setItems(notifications)
      setUnread(unread_count)
    } catch {
      // silent — not authenticated yet
    }
  }

  useEffect(() => {
    void load()
    const interval = setInterval(() => void load(), 30000)
    return () => clearInterval(interval)
  }, [])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleMarkAll = async () => {
    await markAllAsRead()
    setUnread(0)
    setItems((prev) => prev.map((n) => ({ ...n, is_read: true })))
  }

  const handleItemClick = async (item: NotificationItem) => {
    if (!item.is_read) {
      await markAsRead(item.notification_id)
      setItems((prev) =>
        prev.map((n) =>
          n.notification_id === item.notification_id ? { ...n, is_read: true } : n
        )
      )
      setUnread((c) => Math.max(0, c - 1))
    }
    if (item.related_workflow_id) {
      void router.push('/approvals')
    }
    setOpen(false)
  }

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        type="button"
        className="btn btn-link nav-link position-relative p-0 me-3"
        onClick={() => setOpen((o) => !o)}
        aria-label="Notifications"
        style={{ color: 'rgba(255,255,255,0.75)' }}
      >
        🔔
        {unread > 0 && (
          <span
            className="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger"
            style={{ fontSize: '0.65rem' }}
          >
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          className="card shadow"
          style={{
            position: 'absolute',
            right: 0,
            top: '2rem',
            width: '360px',
            maxHeight: '480px',
            overflowY: 'auto',
            zIndex: 1050,
          }}
        >
          <div className="card-header d-flex justify-content-between align-items-center py-2">
            <strong>Notifications</strong>
            {unread > 0 && (
              <button
                type="button"
                className="btn btn-link btn-sm p-0 text-muted"
                onClick={() => void handleMarkAll()}
              >
                Mark all as read
              </button>
            )}
          </div>

          {items.length === 0 ? (
            <div className="card-body text-muted small text-center py-4">No notifications</div>
          ) : (
            <ul className="list-group list-group-flush">
              {items.map((item) => (
                <li
                  key={item.notification_id}
                  className={`list-group-item list-group-item-action ${!item.is_read ? 'fw-bold' : ''}`}
                  style={{ cursor: 'pointer', backgroundColor: item.is_read ? '' : '#f0f7ff' }}
                  onClick={() => void handleItemClick(item)}
                >
                  <div className="d-flex justify-content-between">
                    <span className="small">{item.title}</span>
                    <span className="text-muted" style={{ fontSize: '0.7rem', whiteSpace: 'nowrap' }}>
                      {timeAgo(item.created_at)}
                    </span>
                  </div>
                  <div className="text-muted small" style={{ fontSize: '0.8rem' }}>
                    {(item.message || '').length > 80
                      ? `${item.message.slice(0, 80)}…`
                      : item.message}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
```

---

### File 15 — `frontend/src/components/Layout.tsx` (COMPLETE REPLACEMENT)

```tsx
/**
 * Main Layout Component
 */
import React from 'react'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/router'
import 'bootstrap/dist/css/bootstrap.min.css'
import styles from '@/styles/layout.module.css'
import { getCurrentUser, logout } from '@/services/auth'
import NotificationBell from '@/components/NotificationBell'

interface LayoutProps {
  children: React.ReactNode
}

export function Layout({ children }: LayoutProps) {
  const router = useRouter()
  const [isAuthenticated, setIsAuthenticated] = useState(false)

  useEffect(() => {
    const bootstrap = async () => {
      const user = await getCurrentUser()
      setIsAuthenticated(user !== null)
    }
    void bootstrap()
  }, [router.pathname])

  const handleLogout = async () => {
    await logout()
    router.push('/login')
  }

  return (
    <div className={styles.layout}>
      {isAuthenticated && (
        <nav className={`${styles.navbar} navbar navbar-expand-lg navbar-dark bg-dark`}>
          <div className="container-fluid">
            <Link href="/" className="navbar-brand">
              AI BA Agent
            </Link>
            <div className="collapse navbar-collapse">
              <ul className="navbar-nav ms-auto align-items-center">
                <li className="nav-item">
                  <Link href="/projects" className="nav-link">
                    Projects
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/documents" className="nav-link">
                    Documents
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/approvals" className="nav-link">
                    Approvals
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/knowledge-base" className="nav-link">
                    Knowledge Base
                  </Link>
                </li>
                <li className="nav-item d-flex align-items-center">
                  <NotificationBell />
                </li>
                <li className="nav-item">
                  <button
                    className="nav-link btn btn-link"
                    onClick={handleLogout}
                  >
                    Logout
                  </button>
                </li>
              </ul>
            </div>
          </div>
        </nav>
      )}

      
```


## License: unknown
https://github.com/RakanAji/SMARTPLANTMONITORING_KELOMPOK6/blob/ebf90229ddf582f567c06fafa486befebe2eab2d/src/components/Header.js

```
I now have a complete picture of the codebase. I'm in Ask mode so I cannot write files directly — I'll provide the complete, implementation-ready code for every file to create or modify. Apply them in order.

---

## Implementation

### File 1 — `infra/migrations/005_add_notifications.sql` (NEW)

```sql
-- 005: In-app notifications table
CREATE TABLE IF NOT EXISTS notifications (
  notification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(user_id),
  title VARCHAR(255) NOT NULL,
  message TEXT NOT NULL,
  type VARCHAR(50) NOT NULL DEFAULT 'info',
  is_read BOOLEAN DEFAULT false,
  related_doc_id UUID REFERENCES documents(doc_id),
  related_workflow_id UUID REFERENCES approval_workflows(workflow_id),
  project_name VARCHAR(255),
  doc_name VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_is_read  ON notifications(is_read);
```

---

### File 2 — `infra/migrations/006_add_workflow_roles.sql` (NEW)

```sql
-- 006: Per-workflow dynamic role assignment + submitter tracking
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS step_1_role   VARCHAR(50);
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS step_2_role   VARCHAR(50);
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS submitter_id  UUID REFERENCES users(user_id);
```

---

### File 3 — `backend/app/services/notifications.py` (NEW)

```python
"""DB-backed in-app notification service (distinct from notification.py which is Telegram)."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def create_notification(
    *,
    db: Session,
    user_id: UUID,
    title: str,
    message: str,
    notif_type: str = "info",
    doc_id: Optional[UUID] = None,
    workflow_id: Optional[UUID] = None,
    project_name: str = "",
    doc_name: str = "",
) -> Optional[str]:
    """Insert a notification row. Returns notification_id or None on failure."""
    try:
        nid = str(uuid4())
        db.execute(
            text(
                """
                INSERT INTO notifications
                    (notification_id, user_id, title, message, type, is_read,
                     related_doc_id, related_workflow_id, project_name, doc_name, created_at)
                VALUES
                    (:nid, :uid, :title, :msg, :type, false,
                     :doc_id, :wf_id, :pname, :dname, :ts)
                """
            ),
            {
                "nid": nid,
                "uid": str(user_id),
                "title": title,
                "msg": message,
                "type": notif_type,
                "doc_id": str(doc_id) if doc_id else None,
                "wf_id": str(workflow_id) if workflow_id else None,
                "pname": project_name,
                "dname": doc_name,
                "ts": datetime.utcnow(),
            },
        )
        return nid
    except Exception as exc:
        logger.error("create_notification failed: %s", exc)
        return None


def get_user_notifications(
    *, db: Session, user_id: UUID, limit: int = 20
) -> List[Dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT notification_id, title, message, type, is_read,
                   related_doc_id, related_workflow_id,
                   project_name, doc_name, created_at
            FROM notifications
            WHERE user_id = :uid
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"uid": str(user_id), "limit": limit},
    ).fetchall()
    return [
        {
            "notification_id": str(r[0]),
            "title": r[1],
            "message": r[2],
            "type": r[3],
            "is_read": bool(r[4]),
            "related_doc_id": str(r[5]) if r[5] else None,
            "related_workflow_id": str(r[6]) if r[6] else None,
            "project_name": r[7],
            "doc_name": r[8],
            "created_at": r[9].isoformat() if r[9] else None,
        }
        for r in rows
    ]


def mark_as_read(*, db: Session, notification_id: UUID, user_id: UUID) -> bool:
    result = db.execute(
        text(
            """
            UPDATE notifications
            SET is_read = true
            WHERE notification_id = :nid AND user_id = :uid
            """
        ),
        {"nid": str(notification_id), "uid": str(user_id)},
    )
    return (result.rowcount or 0) > 0


def mark_all_as_read(*, db: Session, user_id: UUID) -> int:
    result = db.execute(
        text(
            "UPDATE notifications SET is_read = true WHERE user_id = :uid AND is_read = false"
        ),
        {"uid": str(user_id)},
    )
    return result.rowcount or 0


def get_unread_count(*, db: Session, user_id: UUID) -> int:
    row = db.execute(
        text(
            "SELECT COUNT(*) FROM notifications WHERE user_id = :uid AND is_read = false"
        ),
        {"uid": str(user_id)},
    ).fetchone()
    return int(row[0] or 0)


def get_role_user_ids(
    *, db: Session, project_id: UUID, role: str
) -> List[str]:
    """Return user_ids that have the given role (system-wide or project-scoped)."""
    rows = db.execute(
        text(
            """
            SELECT DISTINCT u.user_id
            FROM users u
            LEFT JOIN user_projects up
                ON up.user_id = u.user_id AND up.project_id = :pid
            WHERE u.role = :role OR up.role = :role
            LIMIT 20
            """
        ),
        {"pid": str(project_id), "role": role},
    ).fetchall()
    return [str(r[0]) for r in rows]
```

---

### File 4 — `backend/app/services/workflow.py` (COMPLETE REPLACEMENT)

```python
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


# Fallback static step roles — used when a workflow pre-dates dynamic assignment
APPROVAL_STEPS = {
    1: "business_owner",
    2: "admin",
}


def _resolve_dynamic_roles(submitter_role: str) -> Tuple[str, str]:
    """Return (step_1_role, step_2_role) based on the submitter's role."""
    if submitter_role == "business_owner":
        return ("ba", "business_owner")
    if submitter_role in ("ba", "pm"):
        return ("business_owner", "ba")
    # tech_lead, legal, finance, viewer → default
    return ("business_owner", "admin")


def _get_expected_role(wf: Dict[str, Any]) -> str:
    """Return the role required for the current workflow step."""
    if wf["current_step"] == 1:
        return wf.get("step_1_role") or APPROVAL_STEPS.get(1, "business_owner")
    return wf.get("step_2_role") or APPROVAL_STEPS.get(2, "admin")


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
    step_1_role, step_2_role = _resolve_dynamic_roles(submitter_role)
    total_steps = len(APPROVAL_STEPS)

    if submitter_role == "admin":
        initial_status = "approved"
        doc_status = "approved"
    else:
        initial_status = "pending"
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
    step_2 = row[8] or APPROVAL_STEPS.get(2, "admin")

    return {
        "workflow_id": str(row[0]),
        "doc_id": str(row[1]),
        "project_id": str(row[2]),
        "current_step": int(row[3] or 1),
        "total_steps": len(APPROVAL_STEPS),
        "status": str(row[5] or "in_progress"),
        "version_id": str(row[6]) if row[6] else None,
        "step_1_role": step_1,
        "step_2_role": step_2,
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

    next_step = completed_step + 1
    final_step = len(APPROVAL_STEPS)
    new_status = "approved" if next_step > final_step else "in_progress"
    new_doc_status = "approved" if new_status == "approved" else "pending_approval"

    step_roles = {1: wf.get("step_1_role"), 2: wf.get("step_2_role")}
    next_required_role = step_roles.get(next_step) or APPROVAL_STEPS.get(next_step)

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
            SET current_step = :current_step,
                status       = :status,
                version_id   = :version_id,
                updated_at   = :updated_at
            WHERE workflow_id = :workflow_id
            """
        ),
        {
            "current_step": min(next_step, final_step),
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

    log_audit_event(
        db=db,
        project_id=UUID(wf["project_id"]),
        action="APPROVAL_APPROVED",
        entity_type="approval",
        entity_id=workflow_id,
        user_id=actor_user_id,
        old_values={"status": wf["status"], "current_step": completed_step},
        new_values={
            "status": new_status,
            "current_step": min(next_step, final_step),
            "version_id": str(version_id),
        },
        succeeded=True,
    )

    return {
        "workflow_id": wf["workflow_id"],
        "decision_id": str(decision_id),
        "status": new_status,
        "completed_step": completed_step,
        "current_step": min(next_step, final_step),
        "next_required_role": None if new_status == "approved" else next_required_role,
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
        reason=(
            f"Rejection at step {wf['current_step']}: {reason}"
            if reason
            else f"Rejection at step {wf['current_step']}"
        ),
        project_id=UUID(wf["project_id"]),
        workflow_id=workflow_id,
        db=db,
    )

    db.execute(
        text(
            """
            UPDATE approval_workflows
            SET status     = 'rejected',
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
    """Return a document for revision.

    Step 1 → sets status = returned_to_submitter, doc status = returned
    Step 2 → sets status = returned_to_step1, resets to step 1
    """
    wf = get_workflow(workflow_id, db)
    if wf is None:
        raise ValueError("Approval workflow not found")

    if wf["status"] in {"approved", "rejected"}:
        raise ValueError(f"Workflow already closed with status={wf['status']}")

    expected_role = _get_expected_role(wf)
    if actor_role != expected_role and actor_role != "admin":
        raise PermissionError(f"Current step requires role '{expected_role}'")

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
            "step_number": wf["current_step"],
            "approver_id": str(actor_user_id),
            "comments": comment,
            "created_at": now,
        },
    )

    from_step = wf["current_step"]
    if from_step == 1:
        new_wf_status = "returned_to_submitter"
        new_doc_status = "returned"
        audit_action = "APPROVAL_RETURNED_TO_SUBMITTER"
    else:
        new_wf_status = "returned_to_step1"
        new_doc_status = "pending_approval"
        audit_action = "APPROVAL_RETURNED_TO_STEP1"

    version_id = create_document_version(
        doc_id=UUID(wf["doc_id"]),
        created_by=actor_user_id,
        approval_status=new_wf_status,
        reason=f"Returned at step {from_step}: {comment}",
        project_id=UUID(wf["project_id"]),
        workflow_id=workflow_id,
        db=db,
    )

    db.execute(
        text(
            """
            UPDATE approval_workflows
            SET status       = :status,
                current_step = 1,
                version_id   = :version_id,
                updated_at   = :updated_at
            WHERE workflow_id = :workflow_id
            """
        ),
        {
            "status": new_wf_status,
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
        old_values={"status": wf["status"], "current_step": from_step},
        new_values={"status": new_wf_status, "comment": comment, "version_id": str(version_id)},
        succeeded=True,
    )

    return {
        "workflow_id": wf["workflow_id"],
        "decision_id": str(decision_id),
        "status": new_wf_status,
        "current_step": 1,
        "previous_step": from_step,
        "comment": comment,
        "version_id": str(version_id),
        "submitter_id": wf.get("submitter_id"),
        "step_1_role": wf.get("step_1_role"),
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
                (workflow_id, doc_id, project_id, current_step, total_steps, status,
                 submitter_id, created_at, updated_at)
            VALUES
                (:workflow_id, :doc_id, :project_id, 1, :total_steps,
                 'human_review_required', :submitter_id, :created_at, :updated_at)
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
        new_values={
            "status": "human_review_required",
            "doc_id": str(doc_id),
            "total_steps": len(APPROVAL_STEPS),
        },
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
        {"version_id": str(version_id), "updated_at": now, "workflow_id": str(workflow_id)},
    )
    db.execute(
        text(
            "UPDATE documents SET status = 'human_review_required', updated_at = :t WHERE doc_id = :id"
        ),
        {"t": now, "id": str(doc_id)},
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
                (version_id, doc_id, version_number, content, content_hash,
                 created_by, approval_status, created_at)
            VALUES
                (:version_id, :doc_id, :version_number, :content, :content_hash,
                 :created_by, :approval_status, :created_at)
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
```

---

### File 5 — `backend/app/services/google_drive.py` — append at bottom

Add these three functions to the end of the existing [google_drive.py](backend/app/services/google_drive.py):

```python
import re as _re

_MIME_EDIT_URLS = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        "https://docs.google.com/document/d/{id}/edit",
    "application/msword":
        "https://docs.google.com/document/d/{id}/edit",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
    "application/vnd.ms-excel":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
    "text/csv":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
}


def get_drive_file_id(drive_url: str) -> Optional[str]:
    """Extract the Drive file ID from a webViewLink URL."""
    match = _re.search(r"/(?:file/)?d/([a-zA-Z0-9_-]+)", drive_url or "")
    return match.group(1) if match else None


def get_edit_url(file_id: str, mime_type: str) -> str:
    """Return the correct Google Drive / Docs / Sheets URL for the given MIME type."""
    template = _MIME_EDIT_URLS.get(mime_type)
    if template:
        return template.format(id=file_id)
    return f"https://drive.google.com/file/d/{file_id}/view"


def register_file_watch(file_id: str, document_id: str) -> bool:
    """Register a Google Drive push-notification watch (requires verified HTTPS endpoint).

    This stub logs the intent.  In production, call files().watch() with your
    verified webhook URL and store the channel/resource IDs for later expiry renewal.
    """
    logger.info(
        "register_file_watch: file_id=%s doc_id=%s (stub – HTTPS endpoint required)",
        file_id,
        document_id,
    )
    return False
```

---

### File 6 — `backend/app/middleware/rbac.py` — append one line after `require_approver`

Add after `require_approver = ...`:

```python
# Broader reviewer set: includes BA and PM (needed for dynamic step approver assignment)
require_reviewer = make_require_role(["admin", "business_owner", "ba", "pm", "legal"])
```

---

### File 7 — `backend/app/routers/approvals.py` (COMPLETE REPLACEMENT)

```python
"""Approval workflow endpoints."""

from __future__ import annotations

import logging
import os as _os
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_ba, require_readonly, require_reviewer
from app.services.db_service import get_db
from app.services import google_sheets
from app.services import notifications as notif_svc
from app.services.workflow import (
    APPROVAL_STEPS,
    approve_step,
    create_approval_workflow,
    get_workflow,
    reject_step,
    return_step,
    trigger_hitl,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Statuses considered "active / pending" for the dashboard
_PENDING_STATUSES = (
    "in_progress",
    "human_review_required",
    "returned_to_submitter",
    "returned_to_step1",
)
_COMPLETED_STATUSES = ("approved", "rejected")


class ApprovalActionRequest(BaseModel):
    comment: str = ""


class ReturnRequest(BaseModel):
    comment: str = Field(min_length=1)


class CreateApprovalRequest(BaseModel):
    document_id: UUID
    project_id: UUID
    workflow_type: str = "approval"


class RejectionRequest(BaseModel):
    reason: str = Field(min_length=1)


class HitlTriggerRequest(BaseModel):
    document_id: UUID
    project_id: Optional[UUID] = None
    reason: str = Field(min_length=1)
    risk_flags: Dict[str, Any] = {}


# ─── helpers ─────────────────────────────────────────────────────────────────

def _get_doc_project_info(workflow_id: UUID, db: Session):
    """Return (doc_title, project_name, submitter_id) for a workflow."""
    return db.execute(
        text(
            """
            SELECT d.title, p.name, aw.submitter_id
            FROM approval_workflows aw
            JOIN documents d ON d.doc_id = aw.doc_id
            JOIN projects p ON p.project_id = aw.project_id
            WHERE aw.workflow_id = :wid
            """
        ),
        {"wid": str(workflow_id)},
    ).fetchone()


def _status_badge_color(status: str) -> str:
    colors = {
        "in_progress": "info",
        "approved": "success",
        "rejected": "danger",
        "returned_to_submitter": "warning",
        "returned_to_step1": "warning",
        "human_review_required": "secondary",
    }
    return colors.get(status, "secondary")


# ─── endpoints ───────────────────────────────────────────────────────────────

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
            submitter_role=current_user.role,
            db=db,
        )
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"create_workflow_failed: {exc}")


@router.get("")
async def list_approvals(
    project_id: UUID,
    status: str = Query("pending"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """List approvals by status for dashboard views."""
    normalized = status.lower()
    if normalized not in {"pending", "completed", "all"}:
        raise HTTPException(status_code=400, detail="status must be pending, completed, or all")

    pending_in = ", ".join(f"'{s}'" for s in _PENDING_STATUSES)
    completed_in = ", ".join(f"'{s}'" for s in _COMPLETED_STATUSES)

    if normalized == "pending":
        status_filter = f"aw.status IN ({pending_in})"
    elif normalized == "completed":
        status_filter = f"aw.status IN ({completed_in})"
    else:
        status_filter = f"aw.status IN ({pending_in}, {completed_in})"

    offset = (page - 1) * page_size

    rows = db.execute(
        text(
            f"""
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
                    d.doc_type,
                    p.name AS project_name,
                    COALESCE(u.full_name, u.email, '') AS submitter_name,
                    u.role AS submitter_role,
                    aw.step_1_role,
                    aw.step_2_role,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                LEFT JOIN documents d ON d.doc_id = aw.doc_id
                LEFT JOIN projects p ON p.project_id = aw.project_id
                LEFT JOIN users u ON u.user_id = aw.submitter_id
                WHERE aw.project_id = :project_id
                  AND {status_filter}
            )
            SELECT workflow_id, doc_id, doc_title, current_step, total_steps, status,
                   updated_at, google_drive_link, doc_type, project_name,
                   submitter_name, submitter_role, step_1_role, step_2_role
            FROM ranked
            WHERE rn = 1
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"project_id": str(project_id), "limit": page_size, "offset": offset},
    ).fetchall()

    count_row = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT aw.doc_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                WHERE aw.project_id = :project_id AND {status_filter}
            )
            SELECT COUNT(*) FROM ranked WHERE rn = 1
            """
        ),
        {"project_id": str(project_id)},
    ).fetchone()

    items = [
        {
            "workflow_id": str(r[0]),
            "doc_id": str(r[1]),
            "doc_title": r[2] or None,
            "current_step": int(r[3] or 1),
            "total_steps": len(APPROVAL_STEPS),
            "status": r[5],
            "status_color": _status_badge_color(r[5]),
            "updated_at": r[6].isoformat() if r[6] else None,
            "google_drive_link": r[7] or None,
            "doc_type": r[8] or None,
            "project_name": r[9] or None,
            "submitter_name": r[10] or None,
            "submitter_role": r[11] or None,
            "step_1_role": r[12] or None,
            "step_2_role": r[13] or None,
        }
        for r in rows
    ]

    return {
        "project_id": str(project_id),
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
    pending_in = ", ".join(f"'{s}'" for s in _PENDING_STATUSES)
    offset = (page - 1) * page_size

    rows = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT
                    aw.workflow_id, aw.doc_id,
                    COALESCE(d.title, '') AS doc_title,
                    aw.current_step, aw.total_steps, aw.status, aw.updated_at,
                    d.google_drive_link, d.doc_type, p.name AS project_name,
                    COALESCE(u.full_name, u.email, '') AS submitter_name,
                    u.role AS submitter_role, aw.step_1_role, aw.step_2_role,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                LEFT JOIN documents d ON d.doc_id = aw.doc_id
                LEFT JOIN projects p ON p.project_id = aw.project_id
                LEFT JOIN users u ON u.user_id = aw.submitter_id
                WHERE aw.project_id = :project_id
                  AND aw.status IN ({pending_in})
            )
            SELECT workflow_id, doc_id, doc_title, current_step, total_steps, status,
                   updated_at, google_drive_link, doc_type, project_name,
                   submitter_name, submitter_role, step_1_role, step_2_role
            FROM ranked
            WHERE rn = 1
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"project_id": str(project_id), "limit": page_size, "offset": offset},
    ).fetchall()

    count_row = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT aw.doc_id,
                    ROW_NUMBER() OVER (PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC) AS rn
                FROM approval_workflows aw
                WHERE aw.project_id = :project_id
                  AND aw.status IN ({pending_in})
            )
            SELECT COUNT(*) FROM ranked WHERE rn = 1
            """
        ),
        {"project_id": str(project_id)},
    ).fetchone()

    items = [
        {
            "workflow_id": str(r[0]),
            "doc_id": str(r[1]),
            "doc_title": r[2] or None,
            "current_step": int(r[3] or 1),
            "total_steps": len(APPROVAL_STEPS),
            "status": r[5],
            "status_color": _status_badge_color(r[5]),
            "updated_at": r[6].isoformat() if r[6] else None,
            "google_drive_link": r[7] or None,
            "doc_type": r[8] or None,
            "project_name": r[9] or None,
            "submitter_name": r[10] or None,
            "submitter_role": r[11] or None,
            "step_1_role": r[12] or None,
            "step_2_role": r[13] or None,
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
    current_user: TokenUser = Depends(require_reviewer),
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

    # ── Google Sheets update (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            google_sheets.update_approval_row(
                project_name=info[1] or "",
                file_name=_os.path.splitext(info[0] or "")[0],
                approver_name=current_user.email,
                status="Approved",
                comment=request.comment,
            )
    except Exception as exc:
        logger.warning("Sheets update failed after approve (%s): %s", workflow_id, exc)

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            completed_step = result.get("completed_step", 1)
            final_approved = result["status"] == "approved"

            if submitter_id:
                title = "Document Approved ✅" if final_approved else "Document Progressed"
                if final_approved:
                    msg = f"Project {project_name}: '{doc_title}' has been fully approved!"
                else:
                    msg = f"Project {project_name}: '{doc_title}' passed step {completed_step} review."
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title=title,
                    message=msg,
                    notif_type="approved",
                    doc_id=UUID(result["workflow_id"]) if False else None,
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()
    except Exception as exc:
        logger.warning("Notification failed after approve (%s): %s", workflow_id, exc)

    return result


@router.post("/{workflow_id}/reject")
async def reject_document(
    workflow_id: UUID,
    request: RejectionRequest,
    current_user: TokenUser = Depends(require_reviewer),
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

    # ── Google Sheets update (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            google_sheets.update_approval_row(
                project_name=info[1] or "",
                file_name=_os.path.splitext(info[0] or "")[0],
                approver_name=current_user.email,
                status="Rejected",
                comment=request.reason,
            )
    except Exception as exc:
        logger.warning("Sheets update failed after reject (%s): %s", workflow_id, exc)

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            if submitter_id:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title="Document Rejected",
                    message=f"Project {project_name}: '{doc_title}' was rejected. Reason: {request.reason}",
                    notif_type="rejected",
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()
    except Exception as exc:
        logger.warning("Notification failed after reject (%s): %s", workflow_id, exc)

    return result


@router.post("/{workflow_id}/return")
async def return_document(
    workflow_id: UUID,
    request: ReturnRequest,
    current_user: TokenUser = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    """Return a document for revision.

    Step 1 → returned_to_submitter (document status = returned)
    Step 2 → returned_to_step1 (resets to step 1)
    """
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

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            new_status = result["status"]

            if new_status == "returned_to_submitter" and submitter_id:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title="Document Returned",
                    message=(
                        f"Project {project_name}: '{doc_title}' has been returned "
                        f"for revision. Comment: {request.comment}"
                    ),
                    notif_type="returned",
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()

            elif new_status == "returned_to_step1":
                step_1_role = result.get("step_1_role") or "business_owner"
                wf_row = db.execute(
                    text("SELECT project_id FROM approval_workflows WHERE workflow_id = :wid"),
                    {"wid": str(workflow_id)},
                ).fetchone()
                if wf_row:
                    approver_ids = notif_svc.get_role_user_ids(
                        db=db,
                        project_id=UUID(str(wf_row[0])),
                        role=step_1_role,
                    )
                    for uid_str in approver_ids:
                        notif_svc.create_notification(
                            db=db,
                            user_id=UUID(uid_str),
                            title="Re-review Required",
                            message=(
                                f"Project {project_name}: '{doc_title}' has been "
                                f"returned to you for re-review. Comment: {request.comment}"
                            ),
                            notif_type="returned_to_step1",
                            workflow_id=workflow_id,
                            project_name=project_name or "",
                            doc_name=doc_title or "",
                        )
                    db.commit()
    except Exception as exc:
        logger.warning("Notification failed after return (%s): %s", workflow_id, exc)

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
        "status_color": _status_badge_color(workflow["status"]),
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
```

---

### File 8 — `backend/app/routers/documents.py` (COMPLETE REPLACEMENT)

```python
"""
Document management endpoints.

POST /upload            – Accept file + metadata, store to DB, upload to Drive, trigger pipeline
POST /{doc_id}/resubmit – Resubmit a returned document for re-review
GET  /{doc_id}/status   – Return current processing status + progress
"""
import hashlib
import logging
import mimetypes
import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile, File
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_ba, require_readonly
from app.services.db_service import get_db
from app.services import google_drive, google_sheets, elevenlabs, n8n_webhook
from app.services import notifications as notif_svc
from app.services.workflow import _resolve_dynamic_roles

logger = logging.getLogger(__name__)
router = APIRouter()

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
    project_folder_id: Optional[str] = None,
) -> None:
    """Background task: upload to Google Drive, trigger STT + n8n, update status."""
    db: Session = next(get_db())
    try:
        db.execute(
            text("UPDATE documents SET status = :s, updated_at = :t WHERE doc_id = :id"),
            {"s": STATUS_PROCESSING, "t": datetime.utcnow(), "id": doc_id},
        )
        db.commit()

        drive_url: Optional[str] = google_drive.upload_file(
            file_bytes, filename, mime_type, project_folder_id
        )
        if drive_url:
            db.execute(
                text(
                    "UPDATE documents SET google_drive_link = :url, updated_at = :t WHERE doc_id = :id"
                ),
                {"url": drive_url, "t": datetime.utcnow(), "id": doc_id},
            )
            db.commit()

        transcript: Optional[str] = None
        if elevenlabs.is_audio(mime_type):
            transcript = await elevenlabs.transcribe(file_bytes, filename, mime_type)
            if transcript:
                version_id = str(uuid.uuid4())
                db.execute(
                    text(
                        """INSERT INTO document_versions
                             (version_id, doc_id, version_number, content, approval_status, created_at)
                           VALUES (:vid, :did, 1, :content, 'pending', :ts)"""
                    ),
                    {
                        "vid": version_id,
                        "did": doc_id,
                        "content": transcript,
                        "ts": datetime.utcnow(),
                    },
                )
                db.commit()

        await n8n_webhook.trigger_document_workflow(
            workflow_id=workflow_id,
            document_id=doc_id,
            google_drive_url=drive_url,
            file_type=mime_type,
            filename=filename,
        )

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
    current_user: TokenUser = Depends(require_ba),
    db: Session = Depends(get_db),
):
    """
    Upload a document for processing.

    - Requires role: ba / pm / tech_lead / admin  (HTTP 403 otherwise)
    - Returns: {document_id, workflow_id, status: "PENDING"}
    """
    mime_type: str = file.content_type or ""
    if not mime_type or mime_type == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(file.filename or "")
        mime_type = guessed or "application/octet-stream"

    doc_title  = title or (file.filename or "Untitled")
    doc_id     = str(uuid.uuid4())
    workflow_id = str(uuid.uuid4())

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # ── 1. Insert document record ─────────────────────────────────────────
    try:
        db.execute(
            text(
                """INSERT INTO documents
                     (doc_id, project_id, title, doc_type, status, created_by, created_at, updated_at)
                   VALUES (:doc_id, :project_id, :title, :doc_type, :status, :created_by, :now, :now)"""
            ),
            {
                "doc_id":     doc_id,
                "project_id": project_id,
                "title":      doc_title,
                "doc_type":   mime_type,
                "status":     STATUS_PENDING,
                "created_by": current_user.user_id,
                "now":        datetime.utcnow(),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to insert document record: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to store document metadata")

    # ── 2. Determine dynamic roles ────────────────────────────────────────
    step_1_role, step_2_role = _resolve_dynamic_roles(current_user.role)
    auto_approve = current_user.role == "admin"
    initial_wf_status = "approved" if auto_approve else "in_progress"

    # ── 3. Create approval_workflow entry ─────────────────────────────────
    try:
        db.execute(
            text(
                """INSERT INTO approval_workflows
                     (workflow_id, doc_id, project_id, status, current_step, total_steps,
                      step_1_role, step_2_role, submitter_id, created_at, updated_at)
                   VALUES
                     (:wid, :did, :pid, :status, 1, 2,
                      :step_1_role, :step_2_role, :submitter_id, :now, :now)"""
            ),
            {
                "wid":          workflow_id,
                "did":          doc_id,
                "pid":          project_id,
                "status":       initial_wf_status,
                "step_1_role":  step_1_role,
                "step_2_role":  step_2_role,
                "submitter_id": str(current_user.user_id),
                "now":          datetime.utcnow(),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to create approval workflow entry: %s", exc)

    # ── 4. Fetch project Drive folder ─────────────────────────────────────
    project_folder_id: Optional[str] = None
    project_name: str = ""
    try:
        proj_row = db.execute(
            text("SELECT name, google_drive_folder_id FROM projects WHERE project_id = :pid"),
            {"pid": project_id},
        ).fetchone()
        if proj_row:
            project_name     = proj_row[0] or ""
            project_folder_id = proj_row[1] or None
            if project_folder_id is None:
                project_folder_id = google_drive.create_project_folder(project_name)
                if project_folder_id:
                    db.execute(
                        text(
                            "UPDATE projects SET google_drive_folder_id = :fid WHERE project_id = :pid"
                        ),
                        {"fid": project_folder_id, "pid": project_id},
                    )
                    db.commit()
    except Exception as exc:
        logger.warning("Could not fetch project Drive folder for %s: %s", project_id, exc)

    # ── 5. Append row to Google Sheets backlog (best-effort) ──────────────
    try:
        import os as _os
        file_name_no_ext = _os.path.splitext(doc_title)[0]
        google_sheets.append_upload_row(
            user_name=current_user.email,
            project_name=project_name,
            file_name=file_name_no_ext,
            upload_date=datetime.utcnow().strftime("%d-%b-%Y"),
        )
    except Exception as exc:
        logger.warning("Sheets append_upload_row failed for %s: %s", doc_id, exc)

    # ── 6. Notify step-1 approvers (best-effort) ──────────────────────────
    try:
        approver_ids = notif_svc.get_role_user_ids(
            db=db, project_id=UUID(project_id), role=step_1_role
        )
        for uid_str in approver_ids:
            notif_svc.create_notification(
                db=db,
                user_id=UUID(uid_str),
                title="New Review Request",
                message=f"Project {project_name}: '{doc_title}' needs your review.",
                notif_type="upload",
                workflow_id=UUID(workflow_id),
                project_name=project_name,
                doc_name=doc_title,
            )
        db.commit()
    except Exception as exc:
        logger.warning("Upload notification failed for %s: %s", doc_id, exc)

    # ── 7. Queue background processing ────────────────────────────────────
    background_tasks.add_task(
        _process_document,
        doc_id,
        workflow_id,
        file_bytes,
        file.filename or doc_title,
        mime_type,
        project_folder_id,
    )

    logger.info(
        "Document %s queued for processing by %s (workflow %s)",
        doc_id, current_user.email, workflow_id,
    )
    return {
        "document_id":  doc_id,
        "workflow_id":  workflow_id,
        "filename":     file.filename,
        "status":       STATUS_PENDING,
        "uploaded_by":  current_user.email,
        "step_1_role":  step_1_role,
        "step_2_role":  step_2_role,
    }


@router.post("/{doc_id}/resubmit")
async def resubmit_document(
    doc_id: str,
    current_user: TokenUser = Depends(require_ba),
    db: Session = Depends(get_db),
):
    """Resubmit a returned document for re-review (only the original submitter or admin)."""
    doc_row = db.execute(
        text(
            "SELECT doc_id, project_id, title, status, created_by FROM documents WHERE doc_id = :did"
        ),
        {"did": doc_id},
    ).fetchone()
    if doc_row is None:
        raise HTTPException(status_code=404, detail="document_not_found")

    if current_user.role != "admin" and str(doc_row[4]) != str(current_user.user_id):
        raise HTTPException(status_code=403, detail="Only the document submitter can resubmit")

    if doc_row[3] != "returned":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not in 'returned' status (current: {doc_row[3]})",
        )

    wf_row = db.execute(
        text(
            """
            SELECT workflow_id, step_1_role, step_2_role, project_id
            FROM approval_workflows
            WHERE doc_id = :did AND status = 'returned_to_submitter'
            ORDER BY updated_at DESC LIMIT 1
            """
        ),
        {"did": doc_id},
    ).fetchone()

    now = datetime.utcnow()

    # Create new document version
    prev = db.execute(
        text(
            "SELECT version_number, content FROM document_versions WHERE doc_id = :did ORDER BY version_number DESC LIMIT 1"
        ),
        {"did": doc_id},
    ).fetchone()
    new_version_num = (int(prev[0]) + 1) if prev else 1
    content = f"{prev[1] or ''}\n\n[resubmitted by {current_user.email}]".strip() if prev else "[resubmitted]"
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    version_id = str(uuid.uuid4())

    db.execute(
        text(
            """
            INSERT INTO document_versions
                (version_id, doc_id, version_number, content, content_hash,
                 created_by, approval_status, created_at)
            VALUES (:vid, :did, :vn, :content, :hash, :uid, 'pending', :ts)
            """
        ),
        {
            "vid": version_id, "did": doc_id, "vn": new_version_num,
            "content": content, "hash": content_hash,
            "uid": str(current_user.user_id), "ts": now,
        },
    )

    db.execute(
        text("UPDATE documents SET status = 'pending_approval', updated_at = :ts WHERE doc_id = :did"),
        {"ts": now, "did": doc_id},
    )

    wf_id_str: Optional[str] = None
    step_1_role = "business_owner"
    project_id_str = str(doc_row[1])

    if wf_row:
        wf_id_str   = str(wf_row[0])
        step_1_role = wf_row[1] or "business_owner"
        db.execute(
            text(
                "UPDATE approval_workflows SET status = 'in_progress', current_step = 1, updated_at = :ts WHERE workflow_id = :wid"
            ),
            {"ts": now, "wid": wf_id_str},
        )

    db.commit()

    # Notify step-1 approvers (best-effort)
    try:
        pname_row = db.execute(
            text("SELECT name FROM projects WHERE project_id = :pid"),
            {"pid": project_id_str},
        ).fetchone()
        pname = pname_row[0] if pname_row else ""
        approver_ids = notif_svc.get_role_user_ids(
            db=db, project_id=UUID(project_id_str), role=step_1_role
        )
        for uid_str in approver_ids:
            notif_svc.create_notification(
                db=db,
                user_id=UUID(uid_str),
                title="Document Resubmitted",
                message=f"Project {pname}: '{doc_row[2]}' has been revised and resubmitted.",
                notif_type="resubmit",
                workflow_id=UUID(wf_id_str) if wf_id_str else None,
                project_name=pname,
                doc_name=doc_row[2] or "",
            )
        db.commit()
    except Exception as exc:
        logger.warning("Resubmit notification failed for %s: %s", doc_id, exc)

    return {
        "document_id":    doc_id,
        "status":         "pending_approval",
        "version_id":     version_id,
        "resubmitted_by": current_user.email,
    }


@router.get("")
async def list_documents(
    project_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """List documents with optional project filter (auth required)."""
    safe_limit  = max(1, min(limit, 200))
    safe_offset = max(0, offset)

    if project_id:
        rows = db.execute(
            text(
                """SELECT doc_id, project_id, title, doc_type, status, updated_at
                   FROM documents WHERE project_id = :pid
                   ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"""
            ),
            {"pid": project_id, "limit": safe_limit, "offset": safe_offset},
        ).fetchall()
    else:
        rows = db.execute(
            text(
                """SELECT doc_id, project_id, title, doc_type, status, updated_at
                   FROM documents
                   ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"""
            ),
            {"limit": safe_limit, "offset": safe_offset},
        ).fetchall()

    return {
        "requested_by": current_user.email,
        "project_id": project_id,
        "total": len(rows),
        "documents": [
            {
                "doc_id":     str(r[0]),
                "project_id": str(r[1]),
                "title":      r[2],
                "doc_type":   r[3],
                "status":     r[4],
                "updated_at": r[5].isoformat() if r[5] else None,
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
    """Get the current processing status of a document."""
    try:
        row = db.execute(
            text(
                "SELECT doc_id, title, status, doc_type, google_drive_link, updated_at FROM documents WHERE doc_id = :id"
            ),
            {"id": doc_id},
        ).fetchone()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"db_error: {exc}")

    if row is None:
        raise HTTPException(status_code=404, detail="document_not_found")

    status = row[2]
    progress_map = {
        STATUS_PENDING:    10,
        STATUS_PROCESSING: 50,
        STATUS_COMPLETED:  100,
        STATUS_FAILED:     0,
    }

    # Build edit URL if Drive link exists
    edit_url: Optional[str] = None
    drive_link = row[4]
    if drive_link:
        file_id = google_drive.get_drive_file_id(drive_link)
        if file_id:
            edit_url = google_drive.get_edit_url(file_id, row[3] or "")

    return {
        "document_id":      str(row[0]),
        "title":            row[1],
        "status":           status,
        "progress":         progress_map.get(status, 0),
        "doc_type":         row[3],
        "google_drive_url": drive_link,
        "edit_url":         edit_url,
        "updated_at":       row[5].isoformat() if row[5] else None,
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
                "version_id":       str(r[0]),
                "version_number":   int(r[1]),
                "content_hash":     r[2],
                "approval_status":  r[3],
                "created_by":       str(r[4]) if r[4] else None,
                "created_at":       r[5].isoformat() if r[5] else None,
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
            SELECT version_id, version_number, content, content_hash, approval_status, created_by, created_at
            FROM document_versions
            WHERE doc_id = :doc_id AND version_id = :version_id
            """
        ),
        {"doc_id": doc_id, "version_id": version_id},
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="version_not_found")

    return {
        "version_id":       str(row[0]),
        "version_number":   int(row[1]),
        "content":          row[2],
        "content_hash":     row[3],
        "approval_status":  row[4],
        "created_by":       str(row[5]) if row[5] else None,
        "created_at":       row[6].isoformat() if row[6] else None,
    }
```

---

### File 9 — `backend/app/routers/notifications.py` (COMPLETE REPLACEMENT)

```python
"""Notification endpoints — Telegram + in-app DB notifications."""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_admin, require_readonly
from app.services.db_service import get_db
from app.services.notification import notification_service
from app.services.telegram_bot import telegram_bot_service
from app.services import notifications as notif_svc

router = APIRouter()


class NotificationSendRequest(BaseModel):
    message: str = Field(min_length=1)
    type: str = "info"
    project_id: Optional[UUID] = None
    metadata: Dict[str, Any] = {}


class TelegramUpdateRequest(BaseModel):
    update_id: Optional[int] = None
    message: Dict[str, Any] = {}


# ─── Telegram endpoints (unchanged) ──────────────────────────────────────────

@router.post("/send")
async def send_notification(
    request: NotificationSendRequest,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Send a notification through the configured Telegram bot."""
    result = await notification_service.dispatch_notification(
        db=db,
        message=request.message,
        notification_type=request.type,
        actor_user_id=UUID(str(current_user.user_id)),
        project_id=request.project_id,
        metadata=request.metadata,
    )
    db.commit()
    return result


@router.post("/telegram/webhook")
async def telegram_webhook(
    payload: TelegramUpdateRequest,
    db: Session = Depends(get_db),
):
    """Receive Telegram updates and reply to /status, /backlog, /help."""
    message = payload.message or {}
    command_text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id")) if chat.get("id") is not None else None

    if not command_text.startswith("/"):
        return {"ok": True, "handled": False}

    reply_text = notification_service.process_telegram_command(command_text, db)
    sent = await telegram_bot_service.send_message(reply_text, chat_id=chat_id)
    return {
        "ok": True,
        "handled": True,
        "command": command_text.split(" ")[0].lower(),
        "sent": sent,
    }


@router.post("/approval-reminders/run")
async def run_approval_reminders(
    current_user: TokenUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Manual trigger for approval reminders (used by n8n workflow E)."""
    result = await notification_service.send_approval_reminders(db)
    return {**result, "triggered_by": current_user.email}


# ─── In-app DB notifications ─────────────────────────────────────────────────

@router.get("")
async def get_notifications(
    limit: int = 20,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Get in-app notifications for the current user."""
    items = notif_svc.get_user_notifications(
        db=db, user_id=UUID(str(current_user.user_id)), limit=min(limit, 100)
    )
    unread = notif_svc.get_unread_count(db=db, user_id=UUID(str(current_user.user_id)))
    return {"notifications": items, "unread_count": unread}


@router.get("/unread-count")
async def get_unread_count(
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Return unread notification count for the current user."""
    count = notif_svc.get_unread_count(db=db, user_id=UUID(str(current_user.user_id)))
    return {"count": count}


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Mark a single notification as read."""
    updated = notif_svc.mark_as_read(
        db=db,
        notification_id=notification_id,
        user_id=UUID(str(current_user.user_id)),
    )
    db.commit()
    return {"notification_id": str(notification_id), "marked_read": updated}


@router.post("/read-all")
async def mark_all_read(
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Mark all notifications as read for the current user."""
    count = notif_svc.mark_all_as_read(db=db, user_id=UUID(str(current_user.user_id)))
    db.commit()
    return {"marked_count": count}
```

---

### File 10 — `backend/app/routers/webhooks.py` (NEW)

```python
"""Webhook receivers for external integrations (Google Drive change notifications)."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.db_service import get_db
from app.services import notifications as notif_svc

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/drive-changes")
async def drive_changes_webhook(
    request: Request,
    x_goog_resource_id: str = Header(None, alias="X-Goog-Resource-Id"),
    x_goog_channel_id: str = Header(None, alias="X-Goog-Channel-Id"),
    x_goog_resource_state: str = Header(None, alias="X-Goog-Resource-State"),
    db: Session = Depends(get_db),
):
    """Receive Google Drive push notifications for file changes.

    channel_id convention: "doc:{document_id}" (set during register_file_watch).
    """
    logger.info(
        "Drive webhook: channel=%s resource=%s state=%s",
        x_goog_channel_id, x_goog_resource_id, x_goog_resource_state,
    )

    if x_goog_resource_state == "sync":
        return {"ok": True, "type": "sync"}

    if x_goog_channel_id and x_goog_channel_id.startswith("doc:"):
        try:
            doc_id_str = x_goog_channel_id[4:]
            row = db.execute(
                text(
                    """
                    SELECT d.title, d.created_by, p.name
                    FROM documents d
                    JOIN projects p ON p.project_id = d.project_id
                    WHERE d.doc_id = :did
                    """
                ),
                {"did": doc_id_str},
            ).fetchone()
            if row and row[1]:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(row[1])),
                    title="Document Modified",
                    message=f"Your document '{row[0]}' in project '{row[2]}' was modified.",
                    notif_type="file_edited",
                    project_name=row[2] or "",
                    doc_name=row[0] or "",
                )
                db.commit()
        except Exception as exc:
            logger.warning("drive_changes_webhook notification failed: %s", exc)

    return {"ok": True, "type": x_goog_resource_state or "change"}
```

---

### File 11 — `backend/app/main.py` — add webhooks router

In [main.py](backend/app/main.py), add after the existing imports:

```python
from .routers import webhooks as webhooks_router
```

And add the router registration after the existing `app.include_router(notifications_router...)`:

```python
app.include_router(
    webhooks_router.router,
    prefix="/api/webhooks",
    tags=["webhooks"],
)
```

---

### File 12 — `frontend/src/services/documents.ts` — add to end of file

Append to the existing [documents.ts](frontend/src/services/documents.ts):

```typescript
export async function returnWorkflow(workflowId: string, comment: string): Promise<void> {
  await approvalsClient.post(`/${workflowId}/return`, { comment })
}

export async function resubmitDocument(docId: string): Promise<void> {
  const docsClient2 = axios.create({ baseURL: '/api/documents', withCredentials: true })
  await docsClient2.post(`/${docId}/resubmit`)
}

export interface ApprovalItemExtended extends PendingApprovalItem {
  project_name?: string | null
  submitter_name?: string | null
  submitter_role?: string | null
  doc_type?: string | null
  status_color?: string | null
  step_1_role?: string | null
  step_2_role?: string | null
}
```

---

### File 13 — `frontend/src/services/notifications.ts` (NEW)

```typescript
import axios from 'axios'

export interface NotificationItem {
  notification_id: string
  title: string
  message: string
  type: string
  is_read: boolean
  related_doc_id: string | null
  related_workflow_id: string | null
  project_name: string | null
  doc_name: string | null
  created_at: string | null
}

const client = axios.create({
  baseURL: '/api/notifications',
  withCredentials: true,
})

export async function getNotifications(limit = 20): Promise<{ notifications: NotificationItem[]; unread_count: number }> {
  const response = await client.get('', { params: { limit } })
  return response.data
}

export async function getUnreadCount(): Promise<number> {
  const response = await client.get('/unread-count')
  return (response.data as { count: number }).count
}

export async function markAsRead(notificationId: string): Promise<void> {
  await client.post(`/${notificationId}/read`)
}

export async function markAllAsRead(): Promise<void> {
  await client.post('/read-all')
}
```

---

### File 14 — `frontend/src/components/NotificationBell.tsx` (NEW)

```tsx
import React, { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/router'
import {
  getNotifications,
  getUnreadCount,
  markAllAsRead,
  markAsRead,
  type NotificationItem,
} from '@/services/notifications'

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} minute${mins > 1 ? 's' : ''} ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs} hour${hrs > 1 ? 's' : ''} ago`
  return `${Math.floor(hrs / 24)} day${Math.floor(hrs / 24) > 1 ? 's' : ''} ago`
}

export default function NotificationBell() {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<NotificationItem[]>([])
  const [unread, setUnread] = useState(0)
  const ref = useRef<HTMLDivElement>(null)

  const load = async () => {
    try {
      const { notifications, unread_count } = await getNotifications(20)
      setItems(notifications)
      setUnread(unread_count)
    } catch {
      // silent — not authenticated yet
    }
  }

  useEffect(() => {
    void load()
    const interval = setInterval(() => void load(), 30000)
    return () => clearInterval(interval)
  }, [])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleMarkAll = async () => {
    await markAllAsRead()
    setUnread(0)
    setItems((prev) => prev.map((n) => ({ ...n, is_read: true })))
  }

  const handleItemClick = async (item: NotificationItem) => {
    if (!item.is_read) {
      await markAsRead(item.notification_id)
      setItems((prev) =>
        prev.map((n) =>
          n.notification_id === item.notification_id ? { ...n, is_read: true } : n
        )
      )
      setUnread((c) => Math.max(0, c - 1))
    }
    if (item.related_workflow_id) {
      void router.push('/approvals')
    }
    setOpen(false)
  }

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        type="button"
        className="btn btn-link nav-link position-relative p-0 me-3"
        onClick={() => setOpen((o) => !o)}
        aria-label="Notifications"
        style={{ color: 'rgba(255,255,255,0.75)' }}
      >
        🔔
        {unread > 0 && (
          <span
            className="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger"
            style={{ fontSize: '0.65rem' }}
          >
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          className="card shadow"
          style={{
            position: 'absolute',
            right: 0,
            top: '2rem',
            width: '360px',
            maxHeight: '480px',
            overflowY: 'auto',
            zIndex: 1050,
          }}
        >
          <div className="card-header d-flex justify-content-between align-items-center py-2">
            <strong>Notifications</strong>
            {unread > 0 && (
              <button
                type="button"
                className="btn btn-link btn-sm p-0 text-muted"
                onClick={() => void handleMarkAll()}
              >
                Mark all as read
              </button>
            )}
          </div>

          {items.length === 0 ? (
            <div className="card-body text-muted small text-center py-4">No notifications</div>
          ) : (
            <ul className="list-group list-group-flush">
              {items.map((item) => (
                <li
                  key={item.notification_id}
                  className={`list-group-item list-group-item-action ${!item.is_read ? 'fw-bold' : ''}`}
                  style={{ cursor: 'pointer', backgroundColor: item.is_read ? '' : '#f0f7ff' }}
                  onClick={() => void handleItemClick(item)}
                >
                  <div className="d-flex justify-content-between">
                    <span className="small">{item.title}</span>
                    <span className="text-muted" style={{ fontSize: '0.7rem', whiteSpace: 'nowrap' }}>
                      {timeAgo(item.created_at)}
                    </span>
                  </div>
                  <div className="text-muted small" style={{ fontSize: '0.8rem' }}>
                    {(item.message || '').length > 80
                      ? `${item.message.slice(0, 80)}…`
                      : item.message}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
```

---

### File 15 — `frontend/src/components/Layout.tsx` (COMPLETE REPLACEMENT)

```tsx
/**
 * Main Layout Component
 */
import React from 'react'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/router'
import 'bootstrap/dist/css/bootstrap.min.css'
import styles from '@/styles/layout.module.css'
import { getCurrentUser, logout } from '@/services/auth'
import NotificationBell from '@/components/NotificationBell'

interface LayoutProps {
  children: React.ReactNode
}

export function Layout({ children }: LayoutProps) {
  const router = useRouter()
  const [isAuthenticated, setIsAuthenticated] = useState(false)

  useEffect(() => {
    const bootstrap = async () => {
      const user = await getCurrentUser()
      setIsAuthenticated(user !== null)
    }
    void bootstrap()
  }, [router.pathname])

  const handleLogout = async () => {
    await logout()
    router.push('/login')
  }

  return (
    <div className={styles.layout}>
      {isAuthenticated && (
        <nav className={`${styles.navbar} navbar navbar-expand-lg navbar-dark bg-dark`}>
          <div className="container-fluid">
            <Link href="/" className="navbar-brand">
              AI BA Agent
            </Link>
            <div className="collapse navbar-collapse">
              <ul className="navbar-nav ms-auto align-items-center">
                <li className="nav-item">
                  <Link href="/projects" className="nav-link">
                    Projects
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/documents" className="nav-link">
                    Documents
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/approvals" className="nav-link">
                    Approvals
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/knowledge-base" className="nav-link">
                    Knowledge Base
                  </Link>
                </li>
                <li className="nav-item d-flex align-items-center">
                  <NotificationBell />
                </li>
                <li className="nav-item">
                  <button
                    className="nav-link btn btn-link"
                    onClick={handleLogout}
                  >
                    Logout
                  </button>
                </li>
              </ul>
            </div>
          </div>
        </nav>
      )}

      
```


## License: unknown
https://github.com/RakanAji/SMARTPLANTMONITORING_KELOMPOK6/blob/ebf90229ddf582f567c06fafa486befebe2eab2d/src/components/Header.js

```
I now have a complete picture of the codebase. I'm in Ask mode so I cannot write files directly — I'll provide the complete, implementation-ready code for every file to create or modify. Apply them in order.

---

## Implementation

### File 1 — `infra/migrations/005_add_notifications.sql` (NEW)

```sql
-- 005: In-app notifications table
CREATE TABLE IF NOT EXISTS notifications (
  notification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(user_id),
  title VARCHAR(255) NOT NULL,
  message TEXT NOT NULL,
  type VARCHAR(50) NOT NULL DEFAULT 'info',
  is_read BOOLEAN DEFAULT false,
  related_doc_id UUID REFERENCES documents(doc_id),
  related_workflow_id UUID REFERENCES approval_workflows(workflow_id),
  project_name VARCHAR(255),
  doc_name VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_is_read  ON notifications(is_read);
```

---

### File 2 — `infra/migrations/006_add_workflow_roles.sql` (NEW)

```sql
-- 006: Per-workflow dynamic role assignment + submitter tracking
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS step_1_role   VARCHAR(50);
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS step_2_role   VARCHAR(50);
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS submitter_id  UUID REFERENCES users(user_id);
```

---

### File 3 — `backend/app/services/notifications.py` (NEW)

```python
"""DB-backed in-app notification service (distinct from notification.py which is Telegram)."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def create_notification(
    *,
    db: Session,
    user_id: UUID,
    title: str,
    message: str,
    notif_type: str = "info",
    doc_id: Optional[UUID] = None,
    workflow_id: Optional[UUID] = None,
    project_name: str = "",
    doc_name: str = "",
) -> Optional[str]:
    """Insert a notification row. Returns notification_id or None on failure."""
    try:
        nid = str(uuid4())
        db.execute(
            text(
                """
                INSERT INTO notifications
                    (notification_id, user_id, title, message, type, is_read,
                     related_doc_id, related_workflow_id, project_name, doc_name, created_at)
                VALUES
                    (:nid, :uid, :title, :msg, :type, false,
                     :doc_id, :wf_id, :pname, :dname, :ts)
                """
            ),
            {
                "nid": nid,
                "uid": str(user_id),
                "title": title,
                "msg": message,
                "type": notif_type,
                "doc_id": str(doc_id) if doc_id else None,
                "wf_id": str(workflow_id) if workflow_id else None,
                "pname": project_name,
                "dname": doc_name,
                "ts": datetime.utcnow(),
            },
        )
        return nid
    except Exception as exc:
        logger.error("create_notification failed: %s", exc)
        return None


def get_user_notifications(
    *, db: Session, user_id: UUID, limit: int = 20
) -> List[Dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT notification_id, title, message, type, is_read,
                   related_doc_id, related_workflow_id,
                   project_name, doc_name, created_at
            FROM notifications
            WHERE user_id = :uid
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"uid": str(user_id), "limit": limit},
    ).fetchall()
    return [
        {
            "notification_id": str(r[0]),
            "title": r[1],
            "message": r[2],
            "type": r[3],
            "is_read": bool(r[4]),
            "related_doc_id": str(r[5]) if r[5] else None,
            "related_workflow_id": str(r[6]) if r[6] else None,
            "project_name": r[7],
            "doc_name": r[8],
            "created_at": r[9].isoformat() if r[9] else None,
        }
        for r in rows
    ]


def mark_as_read(*, db: Session, notification_id: UUID, user_id: UUID) -> bool:
    result = db.execute(
        text(
            """
            UPDATE notifications
            SET is_read = true
            WHERE notification_id = :nid AND user_id = :uid
            """
        ),
        {"nid": str(notification_id), "uid": str(user_id)},
    )
    return (result.rowcount or 0) > 0


def mark_all_as_read(*, db: Session, user_id: UUID) -> int:
    result = db.execute(
        text(
            "UPDATE notifications SET is_read = true WHERE user_id = :uid AND is_read = false"
        ),
        {"uid": str(user_id)},
    )
    return result.rowcount or 0


def get_unread_count(*, db: Session, user_id: UUID) -> int:
    row = db.execute(
        text(
            "SELECT COUNT(*) FROM notifications WHERE user_id = :uid AND is_read = false"
        ),
        {"uid": str(user_id)},
    ).fetchone()
    return int(row[0] or 0)


def get_role_user_ids(
    *, db: Session, project_id: UUID, role: str
) -> List[str]:
    """Return user_ids that have the given role (system-wide or project-scoped)."""
    rows = db.execute(
        text(
            """
            SELECT DISTINCT u.user_id
            FROM users u
            LEFT JOIN user_projects up
                ON up.user_id = u.user_id AND up.project_id = :pid
            WHERE u.role = :role OR up.role = :role
            LIMIT 20
            """
        ),
        {"pid": str(project_id), "role": role},
    ).fetchall()
    return [str(r[0]) for r in rows]
```

---

### File 4 — `backend/app/services/workflow.py` (COMPLETE REPLACEMENT)

```python
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


# Fallback static step roles — used when a workflow pre-dates dynamic assignment
APPROVAL_STEPS = {
    1: "business_owner",
    2: "admin",
}


def _resolve_dynamic_roles(submitter_role: str) -> Tuple[str, str]:
    """Return (step_1_role, step_2_role) based on the submitter's role."""
    if submitter_role == "business_owner":
        return ("ba", "business_owner")
    if submitter_role in ("ba", "pm"):
        return ("business_owner", "ba")
    # tech_lead, legal, finance, viewer → default
    return ("business_owner", "admin")


def _get_expected_role(wf: Dict[str, Any]) -> str:
    """Return the role required for the current workflow step."""
    if wf["current_step"] == 1:
        return wf.get("step_1_role") or APPROVAL_STEPS.get(1, "business_owner")
    return wf.get("step_2_role") or APPROVAL_STEPS.get(2, "admin")


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
    step_1_role, step_2_role = _resolve_dynamic_roles(submitter_role)
    total_steps = len(APPROVAL_STEPS)

    if submitter_role == "admin":
        initial_status = "approved"
        doc_status = "approved"
    else:
        initial_status = "pending"
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
    step_2 = row[8] or APPROVAL_STEPS.get(2, "admin")

    return {
        "workflow_id": str(row[0]),
        "doc_id": str(row[1]),
        "project_id": str(row[2]),
        "current_step": int(row[3] or 1),
        "total_steps": len(APPROVAL_STEPS),
        "status": str(row[5] or "in_progress"),
        "version_id": str(row[6]) if row[6] else None,
        "step_1_role": step_1,
        "step_2_role": step_2,
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

    next_step = completed_step + 1
    final_step = len(APPROVAL_STEPS)
    new_status = "approved" if next_step > final_step else "in_progress"
    new_doc_status = "approved" if new_status == "approved" else "pending_approval"

    step_roles = {1: wf.get("step_1_role"), 2: wf.get("step_2_role")}
    next_required_role = step_roles.get(next_step) or APPROVAL_STEPS.get(next_step)

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
            SET current_step = :current_step,
                status       = :status,
                version_id   = :version_id,
                updated_at   = :updated_at
            WHERE workflow_id = :workflow_id
            """
        ),
        {
            "current_step": min(next_step, final_step),
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

    log_audit_event(
        db=db,
        project_id=UUID(wf["project_id"]),
        action="APPROVAL_APPROVED",
        entity_type="approval",
        entity_id=workflow_id,
        user_id=actor_user_id,
        old_values={"status": wf["status"], "current_step": completed_step},
        new_values={
            "status": new_status,
            "current_step": min(next_step, final_step),
            "version_id": str(version_id),
        },
        succeeded=True,
    )

    return {
        "workflow_id": wf["workflow_id"],
        "decision_id": str(decision_id),
        "status": new_status,
        "completed_step": completed_step,
        "current_step": min(next_step, final_step),
        "next_required_role": None if new_status == "approved" else next_required_role,
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
        reason=(
            f"Rejection at step {wf['current_step']}: {reason}"
            if reason
            else f"Rejection at step {wf['current_step']}"
        ),
        project_id=UUID(wf["project_id"]),
        workflow_id=workflow_id,
        db=db,
    )

    db.execute(
        text(
            """
            UPDATE approval_workflows
            SET status     = 'rejected',
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
    """Return a document for revision.

    Step 1 → sets status = returned_to_submitter, doc status = returned
    Step 2 → sets status = returned_to_step1, resets to step 1
    """
    wf = get_workflow(workflow_id, db)
    if wf is None:
        raise ValueError("Approval workflow not found")

    if wf["status"] in {"approved", "rejected"}:
        raise ValueError(f"Workflow already closed with status={wf['status']}")

    expected_role = _get_expected_role(wf)
    if actor_role != expected_role and actor_role != "admin":
        raise PermissionError(f"Current step requires role '{expected_role}'")

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
            "step_number": wf["current_step"],
            "approver_id": str(actor_user_id),
            "comments": comment,
            "created_at": now,
        },
    )

    from_step = wf["current_step"]
    if from_step == 1:
        new_wf_status = "returned_to_submitter"
        new_doc_status = "returned"
        audit_action = "APPROVAL_RETURNED_TO_SUBMITTER"
    else:
        new_wf_status = "returned_to_step1"
        new_doc_status = "pending_approval"
        audit_action = "APPROVAL_RETURNED_TO_STEP1"

    version_id = create_document_version(
        doc_id=UUID(wf["doc_id"]),
        created_by=actor_user_id,
        approval_status=new_wf_status,
        reason=f"Returned at step {from_step}: {comment}",
        project_id=UUID(wf["project_id"]),
        workflow_id=workflow_id,
        db=db,
    )

    db.execute(
        text(
            """
            UPDATE approval_workflows
            SET status       = :status,
                current_step = 1,
                version_id   = :version_id,
                updated_at   = :updated_at
            WHERE workflow_id = :workflow_id
            """
        ),
        {
            "status": new_wf_status,
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
        old_values={"status": wf["status"], "current_step": from_step},
        new_values={"status": new_wf_status, "comment": comment, "version_id": str(version_id)},
        succeeded=True,
    )

    return {
        "workflow_id": wf["workflow_id"],
        "decision_id": str(decision_id),
        "status": new_wf_status,
        "current_step": 1,
        "previous_step": from_step,
        "comment": comment,
        "version_id": str(version_id),
        "submitter_id": wf.get("submitter_id"),
        "step_1_role": wf.get("step_1_role"),
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
                (workflow_id, doc_id, project_id, current_step, total_steps, status,
                 submitter_id, created_at, updated_at)
            VALUES
                (:workflow_id, :doc_id, :project_id, 1, :total_steps,
                 'human_review_required', :submitter_id, :created_at, :updated_at)
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
        new_values={
            "status": "human_review_required",
            "doc_id": str(doc_id),
            "total_steps": len(APPROVAL_STEPS),
        },
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
        {"version_id": str(version_id), "updated_at": now, "workflow_id": str(workflow_id)},
    )
    db.execute(
        text(
            "UPDATE documents SET status = 'human_review_required', updated_at = :t WHERE doc_id = :id"
        ),
        {"t": now, "id": str(doc_id)},
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
                (version_id, doc_id, version_number, content, content_hash,
                 created_by, approval_status, created_at)
            VALUES
                (:version_id, :doc_id, :version_number, :content, :content_hash,
                 :created_by, :approval_status, :created_at)
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
```

---

### File 5 — `backend/app/services/google_drive.py` — append at bottom

Add these three functions to the end of the existing [google_drive.py](backend/app/services/google_drive.py):

```python
import re as _re

_MIME_EDIT_URLS = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        "https://docs.google.com/document/d/{id}/edit",
    "application/msword":
        "https://docs.google.com/document/d/{id}/edit",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
    "application/vnd.ms-excel":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
    "text/csv":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
}


def get_drive_file_id(drive_url: str) -> Optional[str]:
    """Extract the Drive file ID from a webViewLink URL."""
    match = _re.search(r"/(?:file/)?d/([a-zA-Z0-9_-]+)", drive_url or "")
    return match.group(1) if match else None


def get_edit_url(file_id: str, mime_type: str) -> str:
    """Return the correct Google Drive / Docs / Sheets URL for the given MIME type."""
    template = _MIME_EDIT_URLS.get(mime_type)
    if template:
        return template.format(id=file_id)
    return f"https://drive.google.com/file/d/{file_id}/view"


def register_file_watch(file_id: str, document_id: str) -> bool:
    """Register a Google Drive push-notification watch (requires verified HTTPS endpoint).

    This stub logs the intent.  In production, call files().watch() with your
    verified webhook URL and store the channel/resource IDs for later expiry renewal.
    """
    logger.info(
        "register_file_watch: file_id=%s doc_id=%s (stub – HTTPS endpoint required)",
        file_id,
        document_id,
    )
    return False
```

---

### File 6 — `backend/app/middleware/rbac.py` — append one line after `require_approver`

Add after `require_approver = ...`:

```python
# Broader reviewer set: includes BA and PM (needed for dynamic step approver assignment)
require_reviewer = make_require_role(["admin", "business_owner", "ba", "pm", "legal"])
```

---

### File 7 — `backend/app/routers/approvals.py` (COMPLETE REPLACEMENT)

```python
"""Approval workflow endpoints."""

from __future__ import annotations

import logging
import os as _os
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_ba, require_readonly, require_reviewer
from app.services.db_service import get_db
from app.services import google_sheets
from app.services import notifications as notif_svc
from app.services.workflow import (
    APPROVAL_STEPS,
    approve_step,
    create_approval_workflow,
    get_workflow,
    reject_step,
    return_step,
    trigger_hitl,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Statuses considered "active / pending" for the dashboard
_PENDING_STATUSES = (
    "in_progress",
    "human_review_required",
    "returned_to_submitter",
    "returned_to_step1",
)
_COMPLETED_STATUSES = ("approved", "rejected")


class ApprovalActionRequest(BaseModel):
    comment: str = ""


class ReturnRequest(BaseModel):
    comment: str = Field(min_length=1)


class CreateApprovalRequest(BaseModel):
    document_id: UUID
    project_id: UUID
    workflow_type: str = "approval"


class RejectionRequest(BaseModel):
    reason: str = Field(min_length=1)


class HitlTriggerRequest(BaseModel):
    document_id: UUID
    project_id: Optional[UUID] = None
    reason: str = Field(min_length=1)
    risk_flags: Dict[str, Any] = {}


# ─── helpers ─────────────────────────────────────────────────────────────────

def _get_doc_project_info(workflow_id: UUID, db: Session):
    """Return (doc_title, project_name, submitter_id) for a workflow."""
    return db.execute(
        text(
            """
            SELECT d.title, p.name, aw.submitter_id
            FROM approval_workflows aw
            JOIN documents d ON d.doc_id = aw.doc_id
            JOIN projects p ON p.project_id = aw.project_id
            WHERE aw.workflow_id = :wid
            """
        ),
        {"wid": str(workflow_id)},
    ).fetchone()


def _status_badge_color(status: str) -> str:
    colors = {
        "in_progress": "info",
        "approved": "success",
        "rejected": "danger",
        "returned_to_submitter": "warning",
        "returned_to_step1": "warning",
        "human_review_required": "secondary",
    }
    return colors.get(status, "secondary")


# ─── endpoints ───────────────────────────────────────────────────────────────

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
            submitter_role=current_user.role,
            db=db,
        )
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"create_workflow_failed: {exc}")


@router.get("")
async def list_approvals(
    project_id: UUID,
    status: str = Query("pending"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """List approvals by status for dashboard views."""
    normalized = status.lower()
    if normalized not in {"pending", "completed", "all"}:
        raise HTTPException(status_code=400, detail="status must be pending, completed, or all")

    pending_in = ", ".join(f"'{s}'" for s in _PENDING_STATUSES)
    completed_in = ", ".join(f"'{s}'" for s in _COMPLETED_STATUSES)

    if normalized == "pending":
        status_filter = f"aw.status IN ({pending_in})"
    elif normalized == "completed":
        status_filter = f"aw.status IN ({completed_in})"
    else:
        status_filter = f"aw.status IN ({pending_in}, {completed_in})"

    offset = (page - 1) * page_size

    rows = db.execute(
        text(
            f"""
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
                    d.doc_type,
                    p.name AS project_name,
                    COALESCE(u.full_name, u.email, '') AS submitter_name,
                    u.role AS submitter_role,
                    aw.step_1_role,
                    aw.step_2_role,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                LEFT JOIN documents d ON d.doc_id = aw.doc_id
                LEFT JOIN projects p ON p.project_id = aw.project_id
                LEFT JOIN users u ON u.user_id = aw.submitter_id
                WHERE aw.project_id = :project_id
                  AND {status_filter}
            )
            SELECT workflow_id, doc_id, doc_title, current_step, total_steps, status,
                   updated_at, google_drive_link, doc_type, project_name,
                   submitter_name, submitter_role, step_1_role, step_2_role
            FROM ranked
            WHERE rn = 1
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"project_id": str(project_id), "limit": page_size, "offset": offset},
    ).fetchall()

    count_row = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT aw.doc_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                WHERE aw.project_id = :project_id AND {status_filter}
            )
            SELECT COUNT(*) FROM ranked WHERE rn = 1
            """
        ),
        {"project_id": str(project_id)},
    ).fetchone()

    items = [
        {
            "workflow_id": str(r[0]),
            "doc_id": str(r[1]),
            "doc_title": r[2] or None,
            "current_step": int(r[3] or 1),
            "total_steps": len(APPROVAL_STEPS),
            "status": r[5],
            "status_color": _status_badge_color(r[5]),
            "updated_at": r[6].isoformat() if r[6] else None,
            "google_drive_link": r[7] or None,
            "doc_type": r[8] or None,
            "project_name": r[9] or None,
            "submitter_name": r[10] or None,
            "submitter_role": r[11] or None,
            "step_1_role": r[12] or None,
            "step_2_role": r[13] or None,
        }
        for r in rows
    ]

    return {
        "project_id": str(project_id),
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
    pending_in = ", ".join(f"'{s}'" for s in _PENDING_STATUSES)
    offset = (page - 1) * page_size

    rows = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT
                    aw.workflow_id, aw.doc_id,
                    COALESCE(d.title, '') AS doc_title,
                    aw.current_step, aw.total_steps, aw.status, aw.updated_at,
                    d.google_drive_link, d.doc_type, p.name AS project_name,
                    COALESCE(u.full_name, u.email, '') AS submitter_name,
                    u.role AS submitter_role, aw.step_1_role, aw.step_2_role,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                LEFT JOIN documents d ON d.doc_id = aw.doc_id
                LEFT JOIN projects p ON p.project_id = aw.project_id
                LEFT JOIN users u ON u.user_id = aw.submitter_id
                WHERE aw.project_id = :project_id
                  AND aw.status IN ({pending_in})
            )
            SELECT workflow_id, doc_id, doc_title, current_step, total_steps, status,
                   updated_at, google_drive_link, doc_type, project_name,
                   submitter_name, submitter_role, step_1_role, step_2_role
            FROM ranked
            WHERE rn = 1
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"project_id": str(project_id), "limit": page_size, "offset": offset},
    ).fetchall()

    count_row = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT aw.doc_id,
                    ROW_NUMBER() OVER (PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC) AS rn
                FROM approval_workflows aw
                WHERE aw.project_id = :project_id
                  AND aw.status IN ({pending_in})
            )
            SELECT COUNT(*) FROM ranked WHERE rn = 1
            """
        ),
        {"project_id": str(project_id)},
    ).fetchone()

    items = [
        {
            "workflow_id": str(r[0]),
            "doc_id": str(r[1]),
            "doc_title": r[2] or None,
            "current_step": int(r[3] or 1),
            "total_steps": len(APPROVAL_STEPS),
            "status": r[5],
            "status_color": _status_badge_color(r[5]),
            "updated_at": r[6].isoformat() if r[6] else None,
            "google_drive_link": r[7] or None,
            "doc_type": r[8] or None,
            "project_name": r[9] or None,
            "submitter_name": r[10] or None,
            "submitter_role": r[11] or None,
            "step_1_role": r[12] or None,
            "step_2_role": r[13] or None,
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
    current_user: TokenUser = Depends(require_reviewer),
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

    # ── Google Sheets update (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            google_sheets.update_approval_row(
                project_name=info[1] or "",
                file_name=_os.path.splitext(info[0] or "")[0],
                approver_name=current_user.email,
                status="Approved",
                comment=request.comment,
            )
    except Exception as exc:
        logger.warning("Sheets update failed after approve (%s): %s", workflow_id, exc)

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            completed_step = result.get("completed_step", 1)
            final_approved = result["status"] == "approved"

            if submitter_id:
                title = "Document Approved ✅" if final_approved else "Document Progressed"
                if final_approved:
                    msg = f"Project {project_name}: '{doc_title}' has been fully approved!"
                else:
                    msg = f"Project {project_name}: '{doc_title}' passed step {completed_step} review."
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title=title,
                    message=msg,
                    notif_type="approved",
                    doc_id=UUID(result["workflow_id"]) if False else None,
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()
    except Exception as exc:
        logger.warning("Notification failed after approve (%s): %s", workflow_id, exc)

    return result


@router.post("/{workflow_id}/reject")
async def reject_document(
    workflow_id: UUID,
    request: RejectionRequest,
    current_user: TokenUser = Depends(require_reviewer),
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

    # ── Google Sheets update (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            google_sheets.update_approval_row(
                project_name=info[1] or "",
                file_name=_os.path.splitext(info[0] or "")[0],
                approver_name=current_user.email,
                status="Rejected",
                comment=request.reason,
            )
    except Exception as exc:
        logger.warning("Sheets update failed after reject (%s): %s", workflow_id, exc)

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            if submitter_id:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title="Document Rejected",
                    message=f"Project {project_name}: '{doc_title}' was rejected. Reason: {request.reason}",
                    notif_type="rejected",
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()
    except Exception as exc:
        logger.warning("Notification failed after reject (%s): %s", workflow_id, exc)

    return result


@router.post("/{workflow_id}/return")
async def return_document(
    workflow_id: UUID,
    request: ReturnRequest,
    current_user: TokenUser = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    """Return a document for revision.

    Step 1 → returned_to_submitter (document status = returned)
    Step 2 → returned_to_step1 (resets to step 1)
    """
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

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            new_status = result["status"]

            if new_status == "returned_to_submitter" and submitter_id:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title="Document Returned",
                    message=(
                        f"Project {project_name}: '{doc_title}' has been returned "
                        f"for revision. Comment: {request.comment}"
                    ),
                    notif_type="returned",
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()

            elif new_status == "returned_to_step1":
                step_1_role = result.get("step_1_role") or "business_owner"
                wf_row = db.execute(
                    text("SELECT project_id FROM approval_workflows WHERE workflow_id = :wid"),
                    {"wid": str(workflow_id)},
                ).fetchone()
                if wf_row:
                    approver_ids = notif_svc.get_role_user_ids(
                        db=db,
                        project_id=UUID(str(wf_row[0])),
                        role=step_1_role,
                    )
                    for uid_str in approver_ids:
                        notif_svc.create_notification(
                            db=db,
                            user_id=UUID(uid_str),
                            title="Re-review Required",
                            message=(
                                f"Project {project_name}: '{doc_title}' has been "
                                f"returned to you for re-review. Comment: {request.comment}"
                            ),
                            notif_type="returned_to_step1",
                            workflow_id=workflow_id,
                            project_name=project_name or "",
                            doc_name=doc_title or "",
                        )
                    db.commit()
    except Exception as exc:
        logger.warning("Notification failed after return (%s): %s", workflow_id, exc)

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
        "status_color": _status_badge_color(workflow["status"]),
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
```

---

### File 8 — `backend/app/routers/documents.py` (COMPLETE REPLACEMENT)

```python
"""
Document management endpoints.

POST /upload            – Accept file + metadata, store to DB, upload to Drive, trigger pipeline
POST /{doc_id}/resubmit – Resubmit a returned document for re-review
GET  /{doc_id}/status   – Return current processing status + progress
"""
import hashlib
import logging
import mimetypes
import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile, File
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_ba, require_readonly
from app.services.db_service import get_db
from app.services import google_drive, google_sheets, elevenlabs, n8n_webhook
from app.services import notifications as notif_svc
from app.services.workflow import _resolve_dynamic_roles

logger = logging.getLogger(__name__)
router = APIRouter()

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
    project_folder_id: Optional[str] = None,
) -> None:
    """Background task: upload to Google Drive, trigger STT + n8n, update status."""
    db: Session = next(get_db())
    try:
        db.execute(
            text("UPDATE documents SET status = :s, updated_at = :t WHERE doc_id = :id"),
            {"s": STATUS_PROCESSING, "t": datetime.utcnow(), "id": doc_id},
        )
        db.commit()

        drive_url: Optional[str] = google_drive.upload_file(
            file_bytes, filename, mime_type, project_folder_id
        )
        if drive_url:
            db.execute(
                text(
                    "UPDATE documents SET google_drive_link = :url, updated_at = :t WHERE doc_id = :id"
                ),
                {"url": drive_url, "t": datetime.utcnow(), "id": doc_id},
            )
            db.commit()

        transcript: Optional[str] = None
        if elevenlabs.is_audio(mime_type):
            transcript = await elevenlabs.transcribe(file_bytes, filename, mime_type)
            if transcript:
                version_id = str(uuid.uuid4())
                db.execute(
                    text(
                        """INSERT INTO document_versions
                             (version_id, doc_id, version_number, content, approval_status, created_at)
                           VALUES (:vid, :did, 1, :content, 'pending', :ts)"""
                    ),
                    {
                        "vid": version_id,
                        "did": doc_id,
                        "content": transcript,
                        "ts": datetime.utcnow(),
                    },
                )
                db.commit()

        await n8n_webhook.trigger_document_workflow(
            workflow_id=workflow_id,
            document_id=doc_id,
            google_drive_url=drive_url,
            file_type=mime_type,
            filename=filename,
        )

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
    current_user: TokenUser = Depends(require_ba),
    db: Session = Depends(get_db),
):
    """
    Upload a document for processing.

    - Requires role: ba / pm / tech_lead / admin  (HTTP 403 otherwise)
    - Returns: {document_id, workflow_id, status: "PENDING"}
    """
    mime_type: str = file.content_type or ""
    if not mime_type or mime_type == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(file.filename or "")
        mime_type = guessed or "application/octet-stream"

    doc_title  = title or (file.filename or "Untitled")
    doc_id     = str(uuid.uuid4())
    workflow_id = str(uuid.uuid4())

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # ── 1. Insert document record ─────────────────────────────────────────
    try:
        db.execute(
            text(
                """INSERT INTO documents
                     (doc_id, project_id, title, doc_type, status, created_by, created_at, updated_at)
                   VALUES (:doc_id, :project_id, :title, :doc_type, :status, :created_by, :now, :now)"""
            ),
            {
                "doc_id":     doc_id,
                "project_id": project_id,
                "title":      doc_title,
                "doc_type":   mime_type,
                "status":     STATUS_PENDING,
                "created_by": current_user.user_id,
                "now":        datetime.utcnow(),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to insert document record: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to store document metadata")

    # ── 2. Determine dynamic roles ────────────────────────────────────────
    step_1_role, step_2_role = _resolve_dynamic_roles(current_user.role)
    auto_approve = current_user.role == "admin"
    initial_wf_status = "approved" if auto_approve else "in_progress"

    # ── 3. Create approval_workflow entry ─────────────────────────────────
    try:
        db.execute(
            text(
                """INSERT INTO approval_workflows
                     (workflow_id, doc_id, project_id, status, current_step, total_steps,
                      step_1_role, step_2_role, submitter_id, created_at, updated_at)
                   VALUES
                     (:wid, :did, :pid, :status, 1, 2,
                      :step_1_role, :step_2_role, :submitter_id, :now, :now)"""
            ),
            {
                "wid":          workflow_id,
                "did":          doc_id,
                "pid":          project_id,
                "status":       initial_wf_status,
                "step_1_role":  step_1_role,
                "step_2_role":  step_2_role,
                "submitter_id": str(current_user.user_id),
                "now":          datetime.utcnow(),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to create approval workflow entry: %s", exc)

    # ── 4. Fetch project Drive folder ─────────────────────────────────────
    project_folder_id: Optional[str] = None
    project_name: str = ""
    try:
        proj_row = db.execute(
            text("SELECT name, google_drive_folder_id FROM projects WHERE project_id = :pid"),
            {"pid": project_id},
        ).fetchone()
        if proj_row:
            project_name     = proj_row[0] or ""
            project_folder_id = proj_row[1] or None
            if project_folder_id is None:
                project_folder_id = google_drive.create_project_folder(project_name)
                if project_folder_id:
                    db.execute(
                        text(
                            "UPDATE projects SET google_drive_folder_id = :fid WHERE project_id = :pid"
                        ),
                        {"fid": project_folder_id, "pid": project_id},
                    )
                    db.commit()
    except Exception as exc:
        logger.warning("Could not fetch project Drive folder for %s: %s", project_id, exc)

    # ── 5. Append row to Google Sheets backlog (best-effort) ──────────────
    try:
        import os as _os
        file_name_no_ext = _os.path.splitext(doc_title)[0]
        google_sheets.append_upload_row(
            user_name=current_user.email,
            project_name=project_name,
            file_name=file_name_no_ext,
            upload_date=datetime.utcnow().strftime("%d-%b-%Y"),
        )
    except Exception as exc:
        logger.warning("Sheets append_upload_row failed for %s: %s", doc_id, exc)

    # ── 6. Notify step-1 approvers (best-effort) ──────────────────────────
    try:
        approver_ids = notif_svc.get_role_user_ids(
            db=db, project_id=UUID(project_id), role=step_1_role
        )
        for uid_str in approver_ids:
            notif_svc.create_notification(
                db=db,
                user_id=UUID(uid_str),
                title="New Review Request",
                message=f"Project {project_name}: '{doc_title}' needs your review.",
                notif_type="upload",
                workflow_id=UUID(workflow_id),
                project_name=project_name,
                doc_name=doc_title,
            )
        db.commit()
    except Exception as exc:
        logger.warning("Upload notification failed for %s: %s", doc_id, exc)

    # ── 7. Queue background processing ────────────────────────────────────
    background_tasks.add_task(
        _process_document,
        doc_id,
        workflow_id,
        file_bytes,
        file.filename or doc_title,
        mime_type,
        project_folder_id,
    )

    logger.info(
        "Document %s queued for processing by %s (workflow %s)",
        doc_id, current_user.email, workflow_id,
    )
    return {
        "document_id":  doc_id,
        "workflow_id":  workflow_id,
        "filename":     file.filename,
        "status":       STATUS_PENDING,
        "uploaded_by":  current_user.email,
        "step_1_role":  step_1_role,
        "step_2_role":  step_2_role,
    }


@router.post("/{doc_id}/resubmit")
async def resubmit_document(
    doc_id: str,
    current_user: TokenUser = Depends(require_ba),
    db: Session = Depends(get_db),
):
    """Resubmit a returned document for re-review (only the original submitter or admin)."""
    doc_row = db.execute(
        text(
            "SELECT doc_id, project_id, title, status, created_by FROM documents WHERE doc_id = :did"
        ),
        {"did": doc_id},
    ).fetchone()
    if doc_row is None:
        raise HTTPException(status_code=404, detail="document_not_found")

    if current_user.role != "admin" and str(doc_row[4]) != str(current_user.user_id):
        raise HTTPException(status_code=403, detail="Only the document submitter can resubmit")

    if doc_row[3] != "returned":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not in 'returned' status (current: {doc_row[3]})",
        )

    wf_row = db.execute(
        text(
            """
            SELECT workflow_id, step_1_role, step_2_role, project_id
            FROM approval_workflows
            WHERE doc_id = :did AND status = 'returned_to_submitter'
            ORDER BY updated_at DESC LIMIT 1
            """
        ),
        {"did": doc_id},
    ).fetchone()

    now = datetime.utcnow()

    # Create new document version
    prev = db.execute(
        text(
            "SELECT version_number, content FROM document_versions WHERE doc_id = :did ORDER BY version_number DESC LIMIT 1"
        ),
        {"did": doc_id},
    ).fetchone()
    new_version_num = (int(prev[0]) + 1) if prev else 1
    content = f"{prev[1] or ''}\n\n[resubmitted by {current_user.email}]".strip() if prev else "[resubmitted]"
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    version_id = str(uuid.uuid4())

    db.execute(
        text(
            """
            INSERT INTO document_versions
                (version_id, doc_id, version_number, content, content_hash,
                 created_by, approval_status, created_at)
            VALUES (:vid, :did, :vn, :content, :hash, :uid, 'pending', :ts)
            """
        ),
        {
            "vid": version_id, "did": doc_id, "vn": new_version_num,
            "content": content, "hash": content_hash,
            "uid": str(current_user.user_id), "ts": now,
        },
    )

    db.execute(
        text("UPDATE documents SET status = 'pending_approval', updated_at = :ts WHERE doc_id = :did"),
        {"ts": now, "did": doc_id},
    )

    wf_id_str: Optional[str] = None
    step_1_role = "business_owner"
    project_id_str = str(doc_row[1])

    if wf_row:
        wf_id_str   = str(wf_row[0])
        step_1_role = wf_row[1] or "business_owner"
        db.execute(
            text(
                "UPDATE approval_workflows SET status = 'in_progress', current_step = 1, updated_at = :ts WHERE workflow_id = :wid"
            ),
            {"ts": now, "wid": wf_id_str},
        )

    db.commit()

    # Notify step-1 approvers (best-effort)
    try:
        pname_row = db.execute(
            text("SELECT name FROM projects WHERE project_id = :pid"),
            {"pid": project_id_str},
        ).fetchone()
        pname = pname_row[0] if pname_row else ""
        approver_ids = notif_svc.get_role_user_ids(
            db=db, project_id=UUID(project_id_str), role=step_1_role
        )
        for uid_str in approver_ids:
            notif_svc.create_notification(
                db=db,
                user_id=UUID(uid_str),
                title="Document Resubmitted",
                message=f"Project {pname}: '{doc_row[2]}' has been revised and resubmitted.",
                notif_type="resubmit",
                workflow_id=UUID(wf_id_str) if wf_id_str else None,
                project_name=pname,
                doc_name=doc_row[2] or "",
            )
        db.commit()
    except Exception as exc:
        logger.warning("Resubmit notification failed for %s: %s", doc_id, exc)

    return {
        "document_id":    doc_id,
        "status":         "pending_approval",
        "version_id":     version_id,
        "resubmitted_by": current_user.email,
    }


@router.get("")
async def list_documents(
    project_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """List documents with optional project filter (auth required)."""
    safe_limit  = max(1, min(limit, 200))
    safe_offset = max(0, offset)

    if project_id:
        rows = db.execute(
            text(
                """SELECT doc_id, project_id, title, doc_type, status, updated_at
                   FROM documents WHERE project_id = :pid
                   ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"""
            ),
            {"pid": project_id, "limit": safe_limit, "offset": safe_offset},
        ).fetchall()
    else:
        rows = db.execute(
            text(
                """SELECT doc_id, project_id, title, doc_type, status, updated_at
                   FROM documents
                   ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"""
            ),
            {"limit": safe_limit, "offset": safe_offset},
        ).fetchall()

    return {
        "requested_by": current_user.email,
        "project_id": project_id,
        "total": len(rows),
        "documents": [
            {
                "doc_id":     str(r[0]),
                "project_id": str(r[1]),
                "title":      r[2],
                "doc_type":   r[3],
                "status":     r[4],
                "updated_at": r[5].isoformat() if r[5] else None,
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
    """Get the current processing status of a document."""
    try:
        row = db.execute(
            text(
                "SELECT doc_id, title, status, doc_type, google_drive_link, updated_at FROM documents WHERE doc_id = :id"
            ),
            {"id": doc_id},
        ).fetchone()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"db_error: {exc}")

    if row is None:
        raise HTTPException(status_code=404, detail="document_not_found")

    status = row[2]
    progress_map = {
        STATUS_PENDING:    10,
        STATUS_PROCESSING: 50,
        STATUS_COMPLETED:  100,
        STATUS_FAILED:     0,
    }

    # Build edit URL if Drive link exists
    edit_url: Optional[str] = None
    drive_link = row[4]
    if drive_link:
        file_id = google_drive.get_drive_file_id(drive_link)
        if file_id:
            edit_url = google_drive.get_edit_url(file_id, row[3] or "")

    return {
        "document_id":      str(row[0]),
        "title":            row[1],
        "status":           status,
        "progress":         progress_map.get(status, 0),
        "doc_type":         row[3],
        "google_drive_url": drive_link,
        "edit_url":         edit_url,
        "updated_at":       row[5].isoformat() if row[5] else None,
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
                "version_id":       str(r[0]),
                "version_number":   int(r[1]),
                "content_hash":     r[2],
                "approval_status":  r[3],
                "created_by":       str(r[4]) if r[4] else None,
                "created_at":       r[5].isoformat() if r[5] else None,
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
            SELECT version_id, version_number, content, content_hash, approval_status, created_by, created_at
            FROM document_versions
            WHERE doc_id = :doc_id AND version_id = :version_id
            """
        ),
        {"doc_id": doc_id, "version_id": version_id},
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="version_not_found")

    return {
        "version_id":       str(row[0]),
        "version_number":   int(row[1]),
        "content":          row[2],
        "content_hash":     row[3],
        "approval_status":  row[4],
        "created_by":       str(row[5]) if row[5] else None,
        "created_at":       row[6].isoformat() if row[6] else None,
    }
```

---

### File 9 — `backend/app/routers/notifications.py` (COMPLETE REPLACEMENT)

```python
"""Notification endpoints — Telegram + in-app DB notifications."""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_admin, require_readonly
from app.services.db_service import get_db
from app.services.notification import notification_service
from app.services.telegram_bot import telegram_bot_service
from app.services import notifications as notif_svc

router = APIRouter()


class NotificationSendRequest(BaseModel):
    message: str = Field(min_length=1)
    type: str = "info"
    project_id: Optional[UUID] = None
    metadata: Dict[str, Any] = {}


class TelegramUpdateRequest(BaseModel):
    update_id: Optional[int] = None
    message: Dict[str, Any] = {}


# ─── Telegram endpoints (unchanged) ──────────────────────────────────────────

@router.post("/send")
async def send_notification(
    request: NotificationSendRequest,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Send a notification through the configured Telegram bot."""
    result = await notification_service.dispatch_notification(
        db=db,
        message=request.message,
        notification_type=request.type,
        actor_user_id=UUID(str(current_user.user_id)),
        project_id=request.project_id,
        metadata=request.metadata,
    )
    db.commit()
    return result


@router.post("/telegram/webhook")
async def telegram_webhook(
    payload: TelegramUpdateRequest,
    db: Session = Depends(get_db),
):
    """Receive Telegram updates and reply to /status, /backlog, /help."""
    message = payload.message or {}
    command_text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id")) if chat.get("id") is not None else None

    if not command_text.startswith("/"):
        return {"ok": True, "handled": False}

    reply_text = notification_service.process_telegram_command(command_text, db)
    sent = await telegram_bot_service.send_message(reply_text, chat_id=chat_id)
    return {
        "ok": True,
        "handled": True,
        "command": command_text.split(" ")[0].lower(),
        "sent": sent,
    }


@router.post("/approval-reminders/run")
async def run_approval_reminders(
    current_user: TokenUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Manual trigger for approval reminders (used by n8n workflow E)."""
    result = await notification_service.send_approval_reminders(db)
    return {**result, "triggered_by": current_user.email}


# ─── In-app DB notifications ─────────────────────────────────────────────────

@router.get("")
async def get_notifications(
    limit: int = 20,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Get in-app notifications for the current user."""
    items = notif_svc.get_user_notifications(
        db=db, user_id=UUID(str(current_user.user_id)), limit=min(limit, 100)
    )
    unread = notif_svc.get_unread_count(db=db, user_id=UUID(str(current_user.user_id)))
    return {"notifications": items, "unread_count": unread}


@router.get("/unread-count")
async def get_unread_count(
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Return unread notification count for the current user."""
    count = notif_svc.get_unread_count(db=db, user_id=UUID(str(current_user.user_id)))
    return {"count": count}


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Mark a single notification as read."""
    updated = notif_svc.mark_as_read(
        db=db,
        notification_id=notification_id,
        user_id=UUID(str(current_user.user_id)),
    )
    db.commit()
    return {"notification_id": str(notification_id), "marked_read": updated}


@router.post("/read-all")
async def mark_all_read(
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Mark all notifications as read for the current user."""
    count = notif_svc.mark_all_as_read(db=db, user_id=UUID(str(current_user.user_id)))
    db.commit()
    return {"marked_count": count}
```

---

### File 10 — `backend/app/routers/webhooks.py` (NEW)

```python
"""Webhook receivers for external integrations (Google Drive change notifications)."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.db_service import get_db
from app.services import notifications as notif_svc

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/drive-changes")
async def drive_changes_webhook(
    request: Request,
    x_goog_resource_id: str = Header(None, alias="X-Goog-Resource-Id"),
    x_goog_channel_id: str = Header(None, alias="X-Goog-Channel-Id"),
    x_goog_resource_state: str = Header(None, alias="X-Goog-Resource-State"),
    db: Session = Depends(get_db),
):
    """Receive Google Drive push notifications for file changes.

    channel_id convention: "doc:{document_id}" (set during register_file_watch).
    """
    logger.info(
        "Drive webhook: channel=%s resource=%s state=%s",
        x_goog_channel_id, x_goog_resource_id, x_goog_resource_state,
    )

    if x_goog_resource_state == "sync":
        return {"ok": True, "type": "sync"}

    if x_goog_channel_id and x_goog_channel_id.startswith("doc:"):
        try:
            doc_id_str = x_goog_channel_id[4:]
            row = db.execute(
                text(
                    """
                    SELECT d.title, d.created_by, p.name
                    FROM documents d
                    JOIN projects p ON p.project_id = d.project_id
                    WHERE d.doc_id = :did
                    """
                ),
                {"did": doc_id_str},
            ).fetchone()
            if row and row[1]:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(row[1])),
                    title="Document Modified",
                    message=f"Your document '{row[0]}' in project '{row[2]}' was modified.",
                    notif_type="file_edited",
                    project_name=row[2] or "",
                    doc_name=row[0] or "",
                )
                db.commit()
        except Exception as exc:
            logger.warning("drive_changes_webhook notification failed: %s", exc)

    return {"ok": True, "type": x_goog_resource_state or "change"}
```

---

### File 11 — `backend/app/main.py` — add webhooks router

In [main.py](backend/app/main.py), add after the existing imports:

```python
from .routers import webhooks as webhooks_router
```

And add the router registration after the existing `app.include_router(notifications_router...)`:

```python
app.include_router(
    webhooks_router.router,
    prefix="/api/webhooks",
    tags=["webhooks"],
)
```

---

### File 12 — `frontend/src/services/documents.ts` — add to end of file

Append to the existing [documents.ts](frontend/src/services/documents.ts):

```typescript
export async function returnWorkflow(workflowId: string, comment: string): Promise<void> {
  await approvalsClient.post(`/${workflowId}/return`, { comment })
}

export async function resubmitDocument(docId: string): Promise<void> {
  const docsClient2 = axios.create({ baseURL: '/api/documents', withCredentials: true })
  await docsClient2.post(`/${docId}/resubmit`)
}

export interface ApprovalItemExtended extends PendingApprovalItem {
  project_name?: string | null
  submitter_name?: string | null
  submitter_role?: string | null
  doc_type?: string | null
  status_color?: string | null
  step_1_role?: string | null
  step_2_role?: string | null
}
```

---

### File 13 — `frontend/src/services/notifications.ts` (NEW)

```typescript
import axios from 'axios'

export interface NotificationItem {
  notification_id: string
  title: string
  message: string
  type: string
  is_read: boolean
  related_doc_id: string | null
  related_workflow_id: string | null
  project_name: string | null
  doc_name: string | null
  created_at: string | null
}

const client = axios.create({
  baseURL: '/api/notifications',
  withCredentials: true,
})

export async function getNotifications(limit = 20): Promise<{ notifications: NotificationItem[]; unread_count: number }> {
  const response = await client.get('', { params: { limit } })
  return response.data
}

export async function getUnreadCount(): Promise<number> {
  const response = await client.get('/unread-count')
  return (response.data as { count: number }).count
}

export async function markAsRead(notificationId: string): Promise<void> {
  await client.post(`/${notificationId}/read`)
}

export async function markAllAsRead(): Promise<void> {
  await client.post('/read-all')
}
```

---

### File 14 — `frontend/src/components/NotificationBell.tsx` (NEW)

```tsx
import React, { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/router'
import {
  getNotifications,
  getUnreadCount,
  markAllAsRead,
  markAsRead,
  type NotificationItem,
} from '@/services/notifications'

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} minute${mins > 1 ? 's' : ''} ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs} hour${hrs > 1 ? 's' : ''} ago`
  return `${Math.floor(hrs / 24)} day${Math.floor(hrs / 24) > 1 ? 's' : ''} ago`
}

export default function NotificationBell() {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<NotificationItem[]>([])
  const [unread, setUnread] = useState(0)
  const ref = useRef<HTMLDivElement>(null)

  const load = async () => {
    try {
      const { notifications, unread_count } = await getNotifications(20)
      setItems(notifications)
      setUnread(unread_count)
    } catch {
      // silent — not authenticated yet
    }
  }

  useEffect(() => {
    void load()
    const interval = setInterval(() => void load(), 30000)
    return () => clearInterval(interval)
  }, [])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleMarkAll = async () => {
    await markAllAsRead()
    setUnread(0)
    setItems((prev) => prev.map((n) => ({ ...n, is_read: true })))
  }

  const handleItemClick = async (item: NotificationItem) => {
    if (!item.is_read) {
      await markAsRead(item.notification_id)
      setItems((prev) =>
        prev.map((n) =>
          n.notification_id === item.notification_id ? { ...n, is_read: true } : n
        )
      )
      setUnread((c) => Math.max(0, c - 1))
    }
    if (item.related_workflow_id) {
      void router.push('/approvals')
    }
    setOpen(false)
  }

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        type="button"
        className="btn btn-link nav-link position-relative p-0 me-3"
        onClick={() => setOpen((o) => !o)}
        aria-label="Notifications"
        style={{ color: 'rgba(255,255,255,0.75)' }}
      >
        🔔
        {unread > 0 && (
          <span
            className="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger"
            style={{ fontSize: '0.65rem' }}
          >
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          className="card shadow"
          style={{
            position: 'absolute',
            right: 0,
            top: '2rem',
            width: '360px',
            maxHeight: '480px',
            overflowY: 'auto',
            zIndex: 1050,
          }}
        >
          <div className="card-header d-flex justify-content-between align-items-center py-2">
            <strong>Notifications</strong>
            {unread > 0 && (
              <button
                type="button"
                className="btn btn-link btn-sm p-0 text-muted"
                onClick={() => void handleMarkAll()}
              >
                Mark all as read
              </button>
            )}
          </div>

          {items.length === 0 ? (
            <div className="card-body text-muted small text-center py-4">No notifications</div>
          ) : (
            <ul className="list-group list-group-flush">
              {items.map((item) => (
                <li
                  key={item.notification_id}
                  className={`list-group-item list-group-item-action ${!item.is_read ? 'fw-bold' : ''}`}
                  style={{ cursor: 'pointer', backgroundColor: item.is_read ? '' : '#f0f7ff' }}
                  onClick={() => void handleItemClick(item)}
                >
                  <div className="d-flex justify-content-between">
                    <span className="small">{item.title}</span>
                    <span className="text-muted" style={{ fontSize: '0.7rem', whiteSpace: 'nowrap' }}>
                      {timeAgo(item.created_at)}
                    </span>
                  </div>
                  <div className="text-muted small" style={{ fontSize: '0.8rem' }}>
                    {(item.message || '').length > 80
                      ? `${item.message.slice(0, 80)}…`
                      : item.message}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
```

---

### File 15 — `frontend/src/components/Layout.tsx` (COMPLETE REPLACEMENT)

```tsx
/**
 * Main Layout Component
 */
import React from 'react'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/router'
import 'bootstrap/dist/css/bootstrap.min.css'
import styles from '@/styles/layout.module.css'
import { getCurrentUser, logout } from '@/services/auth'
import NotificationBell from '@/components/NotificationBell'

interface LayoutProps {
  children: React.ReactNode
}

export function Layout({ children }: LayoutProps) {
  const router = useRouter()
  const [isAuthenticated, setIsAuthenticated] = useState(false)

  useEffect(() => {
    const bootstrap = async () => {
      const user = await getCurrentUser()
      setIsAuthenticated(user !== null)
    }
    void bootstrap()
  }, [router.pathname])

  const handleLogout = async () => {
    await logout()
    router.push('/login')
  }

  return (
    <div className={styles.layout}>
      {isAuthenticated && (
        <nav className={`${styles.navbar} navbar navbar-expand-lg navbar-dark bg-dark`}>
          <div className="container-fluid">
            <Link href="/" className="navbar-brand">
              AI BA Agent
            </Link>
            <div className="collapse navbar-collapse">
              <ul className="navbar-nav ms-auto align-items-center">
                <li className="nav-item">
                  <Link href="/projects" className="nav-link">
                    Projects
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/documents" className="nav-link">
                    Documents
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/approvals" className="nav-link">
                    Approvals
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/knowledge-base" className="nav-link">
                    Knowledge Base
                  </Link>
                </li>
                <li className="nav-item d-flex align-items-center">
                  <NotificationBell />
                </li>
                <li className="nav-item">
                  <button
                    className="nav-link btn btn-link"
                    onClick={handleLogout}
                  >
                    Logout
                  </button>
                </li>
              </ul>
            </div>
          </div>
        </nav>
      )}

      
```


## License: unknown
https://github.com/RakanAji/SMARTPLANTMONITORING_KELOMPOK6/blob/ebf90229ddf582f567c06fafa486befebe2eab2d/src/components/Header.js

```
I now have a complete picture of the codebase. I'm in Ask mode so I cannot write files directly — I'll provide the complete, implementation-ready code for every file to create or modify. Apply them in order.

---

## Implementation

### File 1 — `infra/migrations/005_add_notifications.sql` (NEW)

```sql
-- 005: In-app notifications table
CREATE TABLE IF NOT EXISTS notifications (
  notification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(user_id),
  title VARCHAR(255) NOT NULL,
  message TEXT NOT NULL,
  type VARCHAR(50) NOT NULL DEFAULT 'info',
  is_read BOOLEAN DEFAULT false,
  related_doc_id UUID REFERENCES documents(doc_id),
  related_workflow_id UUID REFERENCES approval_workflows(workflow_id),
  project_name VARCHAR(255),
  doc_name VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_is_read  ON notifications(is_read);
```

---

### File 2 — `infra/migrations/006_add_workflow_roles.sql` (NEW)

```sql
-- 006: Per-workflow dynamic role assignment + submitter tracking
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS step_1_role   VARCHAR(50);
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS step_2_role   VARCHAR(50);
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS submitter_id  UUID REFERENCES users(user_id);
```

---

### File 3 — `backend/app/services/notifications.py` (NEW)

```python
"""DB-backed in-app notification service (distinct from notification.py which is Telegram)."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def create_notification(
    *,
    db: Session,
    user_id: UUID,
    title: str,
    message: str,
    notif_type: str = "info",
    doc_id: Optional[UUID] = None,
    workflow_id: Optional[UUID] = None,
    project_name: str = "",
    doc_name: str = "",
) -> Optional[str]:
    """Insert a notification row. Returns notification_id or None on failure."""
    try:
        nid = str(uuid4())
        db.execute(
            text(
                """
                INSERT INTO notifications
                    (notification_id, user_id, title, message, type, is_read,
                     related_doc_id, related_workflow_id, project_name, doc_name, created_at)
                VALUES
                    (:nid, :uid, :title, :msg, :type, false,
                     :doc_id, :wf_id, :pname, :dname, :ts)
                """
            ),
            {
                "nid": nid,
                "uid": str(user_id),
                "title": title,
                "msg": message,
                "type": notif_type,
                "doc_id": str(doc_id) if doc_id else None,
                "wf_id": str(workflow_id) if workflow_id else None,
                "pname": project_name,
                "dname": doc_name,
                "ts": datetime.utcnow(),
            },
        )
        return nid
    except Exception as exc:
        logger.error("create_notification failed: %s", exc)
        return None


def get_user_notifications(
    *, db: Session, user_id: UUID, limit: int = 20
) -> List[Dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT notification_id, title, message, type, is_read,
                   related_doc_id, related_workflow_id,
                   project_name, doc_name, created_at
            FROM notifications
            WHERE user_id = :uid
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"uid": str(user_id), "limit": limit},
    ).fetchall()
    return [
        {
            "notification_id": str(r[0]),
            "title": r[1],
            "message": r[2],
            "type": r[3],
            "is_read": bool(r[4]),
            "related_doc_id": str(r[5]) if r[5] else None,
            "related_workflow_id": str(r[6]) if r[6] else None,
            "project_name": r[7],
            "doc_name": r[8],
            "created_at": r[9].isoformat() if r[9] else None,
        }
        for r in rows
    ]


def mark_as_read(*, db: Session, notification_id: UUID, user_id: UUID) -> bool:
    result = db.execute(
        text(
            """
            UPDATE notifications
            SET is_read = true
            WHERE notification_id = :nid AND user_id = :uid
            """
        ),
        {"nid": str(notification_id), "uid": str(user_id)},
    )
    return (result.rowcount or 0) > 0


def mark_all_as_read(*, db: Session, user_id: UUID) -> int:
    result = db.execute(
        text(
            "UPDATE notifications SET is_read = true WHERE user_id = :uid AND is_read = false"
        ),
        {"uid": str(user_id)},
    )
    return result.rowcount or 0


def get_unread_count(*, db: Session, user_id: UUID) -> int:
    row = db.execute(
        text(
            "SELECT COUNT(*) FROM notifications WHERE user_id = :uid AND is_read = false"
        ),
        {"uid": str(user_id)},
    ).fetchone()
    return int(row[0] or 0)


def get_role_user_ids(
    *, db: Session, project_id: UUID, role: str
) -> List[str]:
    """Return user_ids that have the given role (system-wide or project-scoped)."""
    rows = db.execute(
        text(
            """
            SELECT DISTINCT u.user_id
            FROM users u
            LEFT JOIN user_projects up
                ON up.user_id = u.user_id AND up.project_id = :pid
            WHERE u.role = :role OR up.role = :role
            LIMIT 20
            """
        ),
        {"pid": str(project_id), "role": role},
    ).fetchall()
    return [str(r[0]) for r in rows]
```

---

### File 4 — `backend/app/services/workflow.py` (COMPLETE REPLACEMENT)

```python
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


# Fallback static step roles — used when a workflow pre-dates dynamic assignment
APPROVAL_STEPS = {
    1: "business_owner",
    2: "admin",
}


def _resolve_dynamic_roles(submitter_role: str) -> Tuple[str, str]:
    """Return (step_1_role, step_2_role) based on the submitter's role."""
    if submitter_role == "business_owner":
        return ("ba", "business_owner")
    if submitter_role in ("ba", "pm"):
        return ("business_owner", "ba")
    # tech_lead, legal, finance, viewer → default
    return ("business_owner", "admin")


def _get_expected_role(wf: Dict[str, Any]) -> str:
    """Return the role required for the current workflow step."""
    if wf["current_step"] == 1:
        return wf.get("step_1_role") or APPROVAL_STEPS.get(1, "business_owner")
    return wf.get("step_2_role") or APPROVAL_STEPS.get(2, "admin")


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
    step_1_role, step_2_role = _resolve_dynamic_roles(submitter_role)
    total_steps = len(APPROVAL_STEPS)

    if submitter_role == "admin":
        initial_status = "approved"
        doc_status = "approved"
    else:
        initial_status = "pending"
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
    step_2 = row[8] or APPROVAL_STEPS.get(2, "admin")

    return {
        "workflow_id": str(row[0]),
        "doc_id": str(row[1]),
        "project_id": str(row[2]),
        "current_step": int(row[3] or 1),
        "total_steps": len(APPROVAL_STEPS),
        "status": str(row[5] or "in_progress"),
        "version_id": str(row[6]) if row[6] else None,
        "step_1_role": step_1,
        "step_2_role": step_2,
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

    next_step = completed_step + 1
    final_step = len(APPROVAL_STEPS)
    new_status = "approved" if next_step > final_step else "in_progress"
    new_doc_status = "approved" if new_status == "approved" else "pending_approval"

    step_roles = {1: wf.get("step_1_role"), 2: wf.get("step_2_role")}
    next_required_role = step_roles.get(next_step) or APPROVAL_STEPS.get(next_step)

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
            SET current_step = :current_step,
                status       = :status,
                version_id   = :version_id,
                updated_at   = :updated_at
            WHERE workflow_id = :workflow_id
            """
        ),
        {
            "current_step": min(next_step, final_step),
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

    log_audit_event(
        db=db,
        project_id=UUID(wf["project_id"]),
        action="APPROVAL_APPROVED",
        entity_type="approval",
        entity_id=workflow_id,
        user_id=actor_user_id,
        old_values={"status": wf["status"], "current_step": completed_step},
        new_values={
            "status": new_status,
            "current_step": min(next_step, final_step),
            "version_id": str(version_id),
        },
        succeeded=True,
    )

    return {
        "workflow_id": wf["workflow_id"],
        "decision_id": str(decision_id),
        "status": new_status,
        "completed_step": completed_step,
        "current_step": min(next_step, final_step),
        "next_required_role": None if new_status == "approved" else next_required_role,
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
        reason=(
            f"Rejection at step {wf['current_step']}: {reason}"
            if reason
            else f"Rejection at step {wf['current_step']}"
        ),
        project_id=UUID(wf["project_id"]),
        workflow_id=workflow_id,
        db=db,
    )

    db.execute(
        text(
            """
            UPDATE approval_workflows
            SET status     = 'rejected',
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
    """Return a document for revision.

    Step 1 → sets status = returned_to_submitter, doc status = returned
    Step 2 → sets status = returned_to_step1, resets to step 1
    """
    wf = get_workflow(workflow_id, db)
    if wf is None:
        raise ValueError("Approval workflow not found")

    if wf["status"] in {"approved", "rejected"}:
        raise ValueError(f"Workflow already closed with status={wf['status']}")

    expected_role = _get_expected_role(wf)
    if actor_role != expected_role and actor_role != "admin":
        raise PermissionError(f"Current step requires role '{expected_role}'")

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
            "step_number": wf["current_step"],
            "approver_id": str(actor_user_id),
            "comments": comment,
            "created_at": now,
        },
    )

    from_step = wf["current_step"]
    if from_step == 1:
        new_wf_status = "returned_to_submitter"
        new_doc_status = "returned"
        audit_action = "APPROVAL_RETURNED_TO_SUBMITTER"
    else:
        new_wf_status = "returned_to_step1"
        new_doc_status = "pending_approval"
        audit_action = "APPROVAL_RETURNED_TO_STEP1"

    version_id = create_document_version(
        doc_id=UUID(wf["doc_id"]),
        created_by=actor_user_id,
        approval_status=new_wf_status,
        reason=f"Returned at step {from_step}: {comment}",
        project_id=UUID(wf["project_id"]),
        workflow_id=workflow_id,
        db=db,
    )

    db.execute(
        text(
            """
            UPDATE approval_workflows
            SET status       = :status,
                current_step = 1,
                version_id   = :version_id,
                updated_at   = :updated_at
            WHERE workflow_id = :workflow_id
            """
        ),
        {
            "status": new_wf_status,
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
        old_values={"status": wf["status"], "current_step": from_step},
        new_values={"status": new_wf_status, "comment": comment, "version_id": str(version_id)},
        succeeded=True,
    )

    return {
        "workflow_id": wf["workflow_id"],
        "decision_id": str(decision_id),
        "status": new_wf_status,
        "current_step": 1,
        "previous_step": from_step,
        "comment": comment,
        "version_id": str(version_id),
        "submitter_id": wf.get("submitter_id"),
        "step_1_role": wf.get("step_1_role"),
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
                (workflow_id, doc_id, project_id, current_step, total_steps, status,
                 submitter_id, created_at, updated_at)
            VALUES
                (:workflow_id, :doc_id, :project_id, 1, :total_steps,
                 'human_review_required', :submitter_id, :created_at, :updated_at)
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
        new_values={
            "status": "human_review_required",
            "doc_id": str(doc_id),
            "total_steps": len(APPROVAL_STEPS),
        },
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
        {"version_id": str(version_id), "updated_at": now, "workflow_id": str(workflow_id)},
    )
    db.execute(
        text(
            "UPDATE documents SET status = 'human_review_required', updated_at = :t WHERE doc_id = :id"
        ),
        {"t": now, "id": str(doc_id)},
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
                (version_id, doc_id, version_number, content, content_hash,
                 created_by, approval_status, created_at)
            VALUES
                (:version_id, :doc_id, :version_number, :content, :content_hash,
                 :created_by, :approval_status, :created_at)
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
```

---

### File 5 — `backend/app/services/google_drive.py` — append at bottom

Add these three functions to the end of the existing [google_drive.py](backend/app/services/google_drive.py):

```python
import re as _re

_MIME_EDIT_URLS = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        "https://docs.google.com/document/d/{id}/edit",
    "application/msword":
        "https://docs.google.com/document/d/{id}/edit",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
    "application/vnd.ms-excel":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
    "text/csv":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
}


def get_drive_file_id(drive_url: str) -> Optional[str]:
    """Extract the Drive file ID from a webViewLink URL."""
    match = _re.search(r"/(?:file/)?d/([a-zA-Z0-9_-]+)", drive_url or "")
    return match.group(1) if match else None


def get_edit_url(file_id: str, mime_type: str) -> str:
    """Return the correct Google Drive / Docs / Sheets URL for the given MIME type."""
    template = _MIME_EDIT_URLS.get(mime_type)
    if template:
        return template.format(id=file_id)
    return f"https://drive.google.com/file/d/{file_id}/view"


def register_file_watch(file_id: str, document_id: str) -> bool:
    """Register a Google Drive push-notification watch (requires verified HTTPS endpoint).

    This stub logs the intent.  In production, call files().watch() with your
    verified webhook URL and store the channel/resource IDs for later expiry renewal.
    """
    logger.info(
        "register_file_watch: file_id=%s doc_id=%s (stub – HTTPS endpoint required)",
        file_id,
        document_id,
    )
    return False
```

---

### File 6 — `backend/app/middleware/rbac.py` — append one line after `require_approver`

Add after `require_approver = ...`:

```python
# Broader reviewer set: includes BA and PM (needed for dynamic step approver assignment)
require_reviewer = make_require_role(["admin", "business_owner", "ba", "pm", "legal"])
```

---

### File 7 — `backend/app/routers/approvals.py` (COMPLETE REPLACEMENT)

```python
"""Approval workflow endpoints."""

from __future__ import annotations

import logging
import os as _os
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_ba, require_readonly, require_reviewer
from app.services.db_service import get_db
from app.services import google_sheets
from app.services import notifications as notif_svc
from app.services.workflow import (
    APPROVAL_STEPS,
    approve_step,
    create_approval_workflow,
    get_workflow,
    reject_step,
    return_step,
    trigger_hitl,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Statuses considered "active / pending" for the dashboard
_PENDING_STATUSES = (
    "in_progress",
    "human_review_required",
    "returned_to_submitter",
    "returned_to_step1",
)
_COMPLETED_STATUSES = ("approved", "rejected")


class ApprovalActionRequest(BaseModel):
    comment: str = ""


class ReturnRequest(BaseModel):
    comment: str = Field(min_length=1)


class CreateApprovalRequest(BaseModel):
    document_id: UUID
    project_id: UUID
    workflow_type: str = "approval"


class RejectionRequest(BaseModel):
    reason: str = Field(min_length=1)


class HitlTriggerRequest(BaseModel):
    document_id: UUID
    project_id: Optional[UUID] = None
    reason: str = Field(min_length=1)
    risk_flags: Dict[str, Any] = {}


# ─── helpers ─────────────────────────────────────────────────────────────────

def _get_doc_project_info(workflow_id: UUID, db: Session):
    """Return (doc_title, project_name, submitter_id) for a workflow."""
    return db.execute(
        text(
            """
            SELECT d.title, p.name, aw.submitter_id
            FROM approval_workflows aw
            JOIN documents d ON d.doc_id = aw.doc_id
            JOIN projects p ON p.project_id = aw.project_id
            WHERE aw.workflow_id = :wid
            """
        ),
        {"wid": str(workflow_id)},
    ).fetchone()


def _status_badge_color(status: str) -> str:
    colors = {
        "in_progress": "info",
        "approved": "success",
        "rejected": "danger",
        "returned_to_submitter": "warning",
        "returned_to_step1": "warning",
        "human_review_required": "secondary",
    }
    return colors.get(status, "secondary")


# ─── endpoints ───────────────────────────────────────────────────────────────

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
            submitter_role=current_user.role,
            db=db,
        )
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"create_workflow_failed: {exc}")


@router.get("")
async def list_approvals(
    project_id: UUID,
    status: str = Query("pending"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """List approvals by status for dashboard views."""
    normalized = status.lower()
    if normalized not in {"pending", "completed", "all"}:
        raise HTTPException(status_code=400, detail="status must be pending, completed, or all")

    pending_in = ", ".join(f"'{s}'" for s in _PENDING_STATUSES)
    completed_in = ", ".join(f"'{s}'" for s in _COMPLETED_STATUSES)

    if normalized == "pending":
        status_filter = f"aw.status IN ({pending_in})"
    elif normalized == "completed":
        status_filter = f"aw.status IN ({completed_in})"
    else:
        status_filter = f"aw.status IN ({pending_in}, {completed_in})"

    offset = (page - 1) * page_size

    rows = db.execute(
        text(
            f"""
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
                    d.doc_type,
                    p.name AS project_name,
                    COALESCE(u.full_name, u.email, '') AS submitter_name,
                    u.role AS submitter_role,
                    aw.step_1_role,
                    aw.step_2_role,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                LEFT JOIN documents d ON d.doc_id = aw.doc_id
                LEFT JOIN projects p ON p.project_id = aw.project_id
                LEFT JOIN users u ON u.user_id = aw.submitter_id
                WHERE aw.project_id = :project_id
                  AND {status_filter}
            )
            SELECT workflow_id, doc_id, doc_title, current_step, total_steps, status,
                   updated_at, google_drive_link, doc_type, project_name,
                   submitter_name, submitter_role, step_1_role, step_2_role
            FROM ranked
            WHERE rn = 1
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"project_id": str(project_id), "limit": page_size, "offset": offset},
    ).fetchall()

    count_row = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT aw.doc_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                WHERE aw.project_id = :project_id AND {status_filter}
            )
            SELECT COUNT(*) FROM ranked WHERE rn = 1
            """
        ),
        {"project_id": str(project_id)},
    ).fetchone()

    items = [
        {
            "workflow_id": str(r[0]),
            "doc_id": str(r[1]),
            "doc_title": r[2] or None,
            "current_step": int(r[3] or 1),
            "total_steps": len(APPROVAL_STEPS),
            "status": r[5],
            "status_color": _status_badge_color(r[5]),
            "updated_at": r[6].isoformat() if r[6] else None,
            "google_drive_link": r[7] or None,
            "doc_type": r[8] or None,
            "project_name": r[9] or None,
            "submitter_name": r[10] or None,
            "submitter_role": r[11] or None,
            "step_1_role": r[12] or None,
            "step_2_role": r[13] or None,
        }
        for r in rows
    ]

    return {
        "project_id": str(project_id),
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
    pending_in = ", ".join(f"'{s}'" for s in _PENDING_STATUSES)
    offset = (page - 1) * page_size

    rows = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT
                    aw.workflow_id, aw.doc_id,
                    COALESCE(d.title, '') AS doc_title,
                    aw.current_step, aw.total_steps, aw.status, aw.updated_at,
                    d.google_drive_link, d.doc_type, p.name AS project_name,
                    COALESCE(u.full_name, u.email, '') AS submitter_name,
                    u.role AS submitter_role, aw.step_1_role, aw.step_2_role,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                LEFT JOIN documents d ON d.doc_id = aw.doc_id
                LEFT JOIN projects p ON p.project_id = aw.project_id
                LEFT JOIN users u ON u.user_id = aw.submitter_id
                WHERE aw.project_id = :project_id
                  AND aw.status IN ({pending_in})
            )
            SELECT workflow_id, doc_id, doc_title, current_step, total_steps, status,
                   updated_at, google_drive_link, doc_type, project_name,
                   submitter_name, submitter_role, step_1_role, step_2_role
            FROM ranked
            WHERE rn = 1
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"project_id": str(project_id), "limit": page_size, "offset": offset},
    ).fetchall()

    count_row = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT aw.doc_id,
                    ROW_NUMBER() OVER (PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC) AS rn
                FROM approval_workflows aw
                WHERE aw.project_id = :project_id
                  AND aw.status IN ({pending_in})
            )
            SELECT COUNT(*) FROM ranked WHERE rn = 1
            """
        ),
        {"project_id": str(project_id)},
    ).fetchone()

    items = [
        {
            "workflow_id": str(r[0]),
            "doc_id": str(r[1]),
            "doc_title": r[2] or None,
            "current_step": int(r[3] or 1),
            "total_steps": len(APPROVAL_STEPS),
            "status": r[5],
            "status_color": _status_badge_color(r[5]),
            "updated_at": r[6].isoformat() if r[6] else None,
            "google_drive_link": r[7] or None,
            "doc_type": r[8] or None,
            "project_name": r[9] or None,
            "submitter_name": r[10] or None,
            "submitter_role": r[11] or None,
            "step_1_role": r[12] or None,
            "step_2_role": r[13] or None,
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
    current_user: TokenUser = Depends(require_reviewer),
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

    # ── Google Sheets update (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            google_sheets.update_approval_row(
                project_name=info[1] or "",
                file_name=_os.path.splitext(info[0] or "")[0],
                approver_name=current_user.email,
                status="Approved",
                comment=request.comment,
            )
    except Exception as exc:
        logger.warning("Sheets update failed after approve (%s): %s", workflow_id, exc)

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            completed_step = result.get("completed_step", 1)
            final_approved = result["status"] == "approved"

            if submitter_id:
                title = "Document Approved ✅" if final_approved else "Document Progressed"
                if final_approved:
                    msg = f"Project {project_name}: '{doc_title}' has been fully approved!"
                else:
                    msg = f"Project {project_name}: '{doc_title}' passed step {completed_step} review."
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title=title,
                    message=msg,
                    notif_type="approved",
                    doc_id=UUID(result["workflow_id"]) if False else None,
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()
    except Exception as exc:
        logger.warning("Notification failed after approve (%s): %s", workflow_id, exc)

    return result


@router.post("/{workflow_id}/reject")
async def reject_document(
    workflow_id: UUID,
    request: RejectionRequest,
    current_user: TokenUser = Depends(require_reviewer),
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

    # ── Google Sheets update (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            google_sheets.update_approval_row(
                project_name=info[1] or "",
                file_name=_os.path.splitext(info[0] or "")[0],
                approver_name=current_user.email,
                status="Rejected",
                comment=request.reason,
            )
    except Exception as exc:
        logger.warning("Sheets update failed after reject (%s): %s", workflow_id, exc)

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            if submitter_id:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title="Document Rejected",
                    message=f"Project {project_name}: '{doc_title}' was rejected. Reason: {request.reason}",
                    notif_type="rejected",
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()
    except Exception as exc:
        logger.warning("Notification failed after reject (%s): %s", workflow_id, exc)

    return result


@router.post("/{workflow_id}/return")
async def return_document(
    workflow_id: UUID,
    request: ReturnRequest,
    current_user: TokenUser = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    """Return a document for revision.

    Step 1 → returned_to_submitter (document status = returned)
    Step 2 → returned_to_step1 (resets to step 1)
    """
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

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            new_status = result["status"]

            if new_status == "returned_to_submitter" and submitter_id:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title="Document Returned",
                    message=(
                        f"Project {project_name}: '{doc_title}' has been returned "
                        f"for revision. Comment: {request.comment}"
                    ),
                    notif_type="returned",
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()

            elif new_status == "returned_to_step1":
                step_1_role = result.get("step_1_role") or "business_owner"
                wf_row = db.execute(
                    text("SELECT project_id FROM approval_workflows WHERE workflow_id = :wid"),
                    {"wid": str(workflow_id)},
                ).fetchone()
                if wf_row:
                    approver_ids = notif_svc.get_role_user_ids(
                        db=db,
                        project_id=UUID(str(wf_row[0])),
                        role=step_1_role,
                    )
                    for uid_str in approver_ids:
                        notif_svc.create_notification(
                            db=db,
                            user_id=UUID(uid_str),
                            title="Re-review Required",
                            message=(
                                f"Project {project_name}: '{doc_title}' has been "
                                f"returned to you for re-review. Comment: {request.comment}"
                            ),
                            notif_type="returned_to_step1",
                            workflow_id=workflow_id,
                            project_name=project_name or "",
                            doc_name=doc_title or "",
                        )
                    db.commit()
    except Exception as exc:
        logger.warning("Notification failed after return (%s): %s", workflow_id, exc)

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
        "status_color": _status_badge_color(workflow["status"]),
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
```

---

### File 8 — `backend/app/routers/documents.py` (COMPLETE REPLACEMENT)

```python
"""
Document management endpoints.

POST /upload            – Accept file + metadata, store to DB, upload to Drive, trigger pipeline
POST /{doc_id}/resubmit – Resubmit a returned document for re-review
GET  /{doc_id}/status   – Return current processing status + progress
"""
import hashlib
import logging
import mimetypes
import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile, File
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_ba, require_readonly
from app.services.db_service import get_db
from app.services import google_drive, google_sheets, elevenlabs, n8n_webhook
from app.services import notifications as notif_svc
from app.services.workflow import _resolve_dynamic_roles

logger = logging.getLogger(__name__)
router = APIRouter()

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
    project_folder_id: Optional[str] = None,
) -> None:
    """Background task: upload to Google Drive, trigger STT + n8n, update status."""
    db: Session = next(get_db())
    try:
        db.execute(
            text("UPDATE documents SET status = :s, updated_at = :t WHERE doc_id = :id"),
            {"s": STATUS_PROCESSING, "t": datetime.utcnow(), "id": doc_id},
        )
        db.commit()

        drive_url: Optional[str] = google_drive.upload_file(
            file_bytes, filename, mime_type, project_folder_id
        )
        if drive_url:
            db.execute(
                text(
                    "UPDATE documents SET google_drive_link = :url, updated_at = :t WHERE doc_id = :id"
                ),
                {"url": drive_url, "t": datetime.utcnow(), "id": doc_id},
            )
            db.commit()

        transcript: Optional[str] = None
        if elevenlabs.is_audio(mime_type):
            transcript = await elevenlabs.transcribe(file_bytes, filename, mime_type)
            if transcript:
                version_id = str(uuid.uuid4())
                db.execute(
                    text(
                        """INSERT INTO document_versions
                             (version_id, doc_id, version_number, content, approval_status, created_at)
                           VALUES (:vid, :did, 1, :content, 'pending', :ts)"""
                    ),
                    {
                        "vid": version_id,
                        "did": doc_id,
                        "content": transcript,
                        "ts": datetime.utcnow(),
                    },
                )
                db.commit()

        await n8n_webhook.trigger_document_workflow(
            workflow_id=workflow_id,
            document_id=doc_id,
            google_drive_url=drive_url,
            file_type=mime_type,
            filename=filename,
        )

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
    current_user: TokenUser = Depends(require_ba),
    db: Session = Depends(get_db),
):
    """
    Upload a document for processing.

    - Requires role: ba / pm / tech_lead / admin  (HTTP 403 otherwise)
    - Returns: {document_id, workflow_id, status: "PENDING"}
    """
    mime_type: str = file.content_type or ""
    if not mime_type or mime_type == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(file.filename or "")
        mime_type = guessed or "application/octet-stream"

    doc_title  = title or (file.filename or "Untitled")
    doc_id     = str(uuid.uuid4())
    workflow_id = str(uuid.uuid4())

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # ── 1. Insert document record ─────────────────────────────────────────
    try:
        db.execute(
            text(
                """INSERT INTO documents
                     (doc_id, project_id, title, doc_type, status, created_by, created_at, updated_at)
                   VALUES (:doc_id, :project_id, :title, :doc_type, :status, :created_by, :now, :now)"""
            ),
            {
                "doc_id":     doc_id,
                "project_id": project_id,
                "title":      doc_title,
                "doc_type":   mime_type,
                "status":     STATUS_PENDING,
                "created_by": current_user.user_id,
                "now":        datetime.utcnow(),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to insert document record: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to store document metadata")

    # ── 2. Determine dynamic roles ────────────────────────────────────────
    step_1_role, step_2_role = _resolve_dynamic_roles(current_user.role)
    auto_approve = current_user.role == "admin"
    initial_wf_status = "approved" if auto_approve else "in_progress"

    # ── 3. Create approval_workflow entry ─────────────────────────────────
    try:
        db.execute(
            text(
                """INSERT INTO approval_workflows
                     (workflow_id, doc_id, project_id, status, current_step, total_steps,
                      step_1_role, step_2_role, submitter_id, created_at, updated_at)
                   VALUES
                     (:wid, :did, :pid, :status, 1, 2,
                      :step_1_role, :step_2_role, :submitter_id, :now, :now)"""
            ),
            {
                "wid":          workflow_id,
                "did":          doc_id,
                "pid":          project_id,
                "status":       initial_wf_status,
                "step_1_role":  step_1_role,
                "step_2_role":  step_2_role,
                "submitter_id": str(current_user.user_id),
                "now":          datetime.utcnow(),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to create approval workflow entry: %s", exc)

    # ── 4. Fetch project Drive folder ─────────────────────────────────────
    project_folder_id: Optional[str] = None
    project_name: str = ""
    try:
        proj_row = db.execute(
            text("SELECT name, google_drive_folder_id FROM projects WHERE project_id = :pid"),
            {"pid": project_id},
        ).fetchone()
        if proj_row:
            project_name     = proj_row[0] or ""
            project_folder_id = proj_row[1] or None
            if project_folder_id is None:
                project_folder_id = google_drive.create_project_folder(project_name)
                if project_folder_id:
                    db.execute(
                        text(
                            "UPDATE projects SET google_drive_folder_id = :fid WHERE project_id = :pid"
                        ),
                        {"fid": project_folder_id, "pid": project_id},
                    )
                    db.commit()
    except Exception as exc:
        logger.warning("Could not fetch project Drive folder for %s: %s", project_id, exc)

    # ── 5. Append row to Google Sheets backlog (best-effort) ──────────────
    try:
        import os as _os
        file_name_no_ext = _os.path.splitext(doc_title)[0]
        google_sheets.append_upload_row(
            user_name=current_user.email,
            project_name=project_name,
            file_name=file_name_no_ext,
            upload_date=datetime.utcnow().strftime("%d-%b-%Y"),
        )
    except Exception as exc:
        logger.warning("Sheets append_upload_row failed for %s: %s", doc_id, exc)

    # ── 6. Notify step-1 approvers (best-effort) ──────────────────────────
    try:
        approver_ids = notif_svc.get_role_user_ids(
            db=db, project_id=UUID(project_id), role=step_1_role
        )
        for uid_str in approver_ids:
            notif_svc.create_notification(
                db=db,
                user_id=UUID(uid_str),
                title="New Review Request",
                message=f"Project {project_name}: '{doc_title}' needs your review.",
                notif_type="upload",
                workflow_id=UUID(workflow_id),
                project_name=project_name,
                doc_name=doc_title,
            )
        db.commit()
    except Exception as exc:
        logger.warning("Upload notification failed for %s: %s", doc_id, exc)

    # ── 7. Queue background processing ────────────────────────────────────
    background_tasks.add_task(
        _process_document,
        doc_id,
        workflow_id,
        file_bytes,
        file.filename or doc_title,
        mime_type,
        project_folder_id,
    )

    logger.info(
        "Document %s queued for processing by %s (workflow %s)",
        doc_id, current_user.email, workflow_id,
    )
    return {
        "document_id":  doc_id,
        "workflow_id":  workflow_id,
        "filename":     file.filename,
        "status":       STATUS_PENDING,
        "uploaded_by":  current_user.email,
        "step_1_role":  step_1_role,
        "step_2_role":  step_2_role,
    }


@router.post("/{doc_id}/resubmit")
async def resubmit_document(
    doc_id: str,
    current_user: TokenUser = Depends(require_ba),
    db: Session = Depends(get_db),
):
    """Resubmit a returned document for re-review (only the original submitter or admin)."""
    doc_row = db.execute(
        text(
            "SELECT doc_id, project_id, title, status, created_by FROM documents WHERE doc_id = :did"
        ),
        {"did": doc_id},
    ).fetchone()
    if doc_row is None:
        raise HTTPException(status_code=404, detail="document_not_found")

    if current_user.role != "admin" and str(doc_row[4]) != str(current_user.user_id):
        raise HTTPException(status_code=403, detail="Only the document submitter can resubmit")

    if doc_row[3] != "returned":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not in 'returned' status (current: {doc_row[3]})",
        )

    wf_row = db.execute(
        text(
            """
            SELECT workflow_id, step_1_role, step_2_role, project_id
            FROM approval_workflows
            WHERE doc_id = :did AND status = 'returned_to_submitter'
            ORDER BY updated_at DESC LIMIT 1
            """
        ),
        {"did": doc_id},
    ).fetchone()

    now = datetime.utcnow()

    # Create new document version
    prev = db.execute(
        text(
            "SELECT version_number, content FROM document_versions WHERE doc_id = :did ORDER BY version_number DESC LIMIT 1"
        ),
        {"did": doc_id},
    ).fetchone()
    new_version_num = (int(prev[0]) + 1) if prev else 1
    content = f"{prev[1] or ''}\n\n[resubmitted by {current_user.email}]".strip() if prev else "[resubmitted]"
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    version_id = str(uuid.uuid4())

    db.execute(
        text(
            """
            INSERT INTO document_versions
                (version_id, doc_id, version_number, content, content_hash,
                 created_by, approval_status, created_at)
            VALUES (:vid, :did, :vn, :content, :hash, :uid, 'pending', :ts)
            """
        ),
        {
            "vid": version_id, "did": doc_id, "vn": new_version_num,
            "content": content, "hash": content_hash,
            "uid": str(current_user.user_id), "ts": now,
        },
    )

    db.execute(
        text("UPDATE documents SET status = 'pending_approval', updated_at = :ts WHERE doc_id = :did"),
        {"ts": now, "did": doc_id},
    )

    wf_id_str: Optional[str] = None
    step_1_role = "business_owner"
    project_id_str = str(doc_row[1])

    if wf_row:
        wf_id_str   = str(wf_row[0])
        step_1_role = wf_row[1] or "business_owner"
        db.execute(
            text(
                "UPDATE approval_workflows SET status = 'in_progress', current_step = 1, updated_at = :ts WHERE workflow_id = :wid"
            ),
            {"ts": now, "wid": wf_id_str},
        )

    db.commit()

    # Notify step-1 approvers (best-effort)
    try:
        pname_row = db.execute(
            text("SELECT name FROM projects WHERE project_id = :pid"),
            {"pid": project_id_str},
        ).fetchone()
        pname = pname_row[0] if pname_row else ""
        approver_ids = notif_svc.get_role_user_ids(
            db=db, project_id=UUID(project_id_str), role=step_1_role
        )
        for uid_str in approver_ids:
            notif_svc.create_notification(
                db=db,
                user_id=UUID(uid_str),
                title="Document Resubmitted",
                message=f"Project {pname}: '{doc_row[2]}' has been revised and resubmitted.",
                notif_type="resubmit",
                workflow_id=UUID(wf_id_str) if wf_id_str else None,
                project_name=pname,
                doc_name=doc_row[2] or "",
            )
        db.commit()
    except Exception as exc:
        logger.warning("Resubmit notification failed for %s: %s", doc_id, exc)

    return {
        "document_id":    doc_id,
        "status":         "pending_approval",
        "version_id":     version_id,
        "resubmitted_by": current_user.email,
    }


@router.get("")
async def list_documents(
    project_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """List documents with optional project filter (auth required)."""
    safe_limit  = max(1, min(limit, 200))
    safe_offset = max(0, offset)

    if project_id:
        rows = db.execute(
            text(
                """SELECT doc_id, project_id, title, doc_type, status, updated_at
                   FROM documents WHERE project_id = :pid
                   ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"""
            ),
            {"pid": project_id, "limit": safe_limit, "offset": safe_offset},
        ).fetchall()
    else:
        rows = db.execute(
            text(
                """SELECT doc_id, project_id, title, doc_type, status, updated_at
                   FROM documents
                   ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"""
            ),
            {"limit": safe_limit, "offset": safe_offset},
        ).fetchall()

    return {
        "requested_by": current_user.email,
        "project_id": project_id,
        "total": len(rows),
        "documents": [
            {
                "doc_id":     str(r[0]),
                "project_id": str(r[1]),
                "title":      r[2],
                "doc_type":   r[3],
                "status":     r[4],
                "updated_at": r[5].isoformat() if r[5] else None,
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
    """Get the current processing status of a document."""
    try:
        row = db.execute(
            text(
                "SELECT doc_id, title, status, doc_type, google_drive_link, updated_at FROM documents WHERE doc_id = :id"
            ),
            {"id": doc_id},
        ).fetchone()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"db_error: {exc}")

    if row is None:
        raise HTTPException(status_code=404, detail="document_not_found")

    status = row[2]
    progress_map = {
        STATUS_PENDING:    10,
        STATUS_PROCESSING: 50,
        STATUS_COMPLETED:  100,
        STATUS_FAILED:     0,
    }

    # Build edit URL if Drive link exists
    edit_url: Optional[str] = None
    drive_link = row[4]
    if drive_link:
        file_id = google_drive.get_drive_file_id(drive_link)
        if file_id:
            edit_url = google_drive.get_edit_url(file_id, row[3] or "")

    return {
        "document_id":      str(row[0]),
        "title":            row[1],
        "status":           status,
        "progress":         progress_map.get(status, 0),
        "doc_type":         row[3],
        "google_drive_url": drive_link,
        "edit_url":         edit_url,
        "updated_at":       row[5].isoformat() if row[5] else None,
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
                "version_id":       str(r[0]),
                "version_number":   int(r[1]),
                "content_hash":     r[2],
                "approval_status":  r[3],
                "created_by":       str(r[4]) if r[4] else None,
                "created_at":       r[5].isoformat() if r[5] else None,
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
            SELECT version_id, version_number, content, content_hash, approval_status, created_by, created_at
            FROM document_versions
            WHERE doc_id = :doc_id AND version_id = :version_id
            """
        ),
        {"doc_id": doc_id, "version_id": version_id},
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="version_not_found")

    return {
        "version_id":       str(row[0]),
        "version_number":   int(row[1]),
        "content":          row[2],
        "content_hash":     row[3],
        "approval_status":  row[4],
        "created_by":       str(row[5]) if row[5] else None,
        "created_at":       row[6].isoformat() if row[6] else None,
    }
```

---

### File 9 — `backend/app/routers/notifications.py` (COMPLETE REPLACEMENT)

```python
"""Notification endpoints — Telegram + in-app DB notifications."""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_admin, require_readonly
from app.services.db_service import get_db
from app.services.notification import notification_service
from app.services.telegram_bot import telegram_bot_service
from app.services import notifications as notif_svc

router = APIRouter()


class NotificationSendRequest(BaseModel):
    message: str = Field(min_length=1)
    type: str = "info"
    project_id: Optional[UUID] = None
    metadata: Dict[str, Any] = {}


class TelegramUpdateRequest(BaseModel):
    update_id: Optional[int] = None
    message: Dict[str, Any] = {}


# ─── Telegram endpoints (unchanged) ──────────────────────────────────────────

@router.post("/send")
async def send_notification(
    request: NotificationSendRequest,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Send a notification through the configured Telegram bot."""
    result = await notification_service.dispatch_notification(
        db=db,
        message=request.message,
        notification_type=request.type,
        actor_user_id=UUID(str(current_user.user_id)),
        project_id=request.project_id,
        metadata=request.metadata,
    )
    db.commit()
    return result


@router.post("/telegram/webhook")
async def telegram_webhook(
    payload: TelegramUpdateRequest,
    db: Session = Depends(get_db),
):
    """Receive Telegram updates and reply to /status, /backlog, /help."""
    message = payload.message or {}
    command_text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id")) if chat.get("id") is not None else None

    if not command_text.startswith("/"):
        return {"ok": True, "handled": False}

    reply_text = notification_service.process_telegram_command(command_text, db)
    sent = await telegram_bot_service.send_message(reply_text, chat_id=chat_id)
    return {
        "ok": True,
        "handled": True,
        "command": command_text.split(" ")[0].lower(),
        "sent": sent,
    }


@router.post("/approval-reminders/run")
async def run_approval_reminders(
    current_user: TokenUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Manual trigger for approval reminders (used by n8n workflow E)."""
    result = await notification_service.send_approval_reminders(db)
    return {**result, "triggered_by": current_user.email}


# ─── In-app DB notifications ─────────────────────────────────────────────────

@router.get("")
async def get_notifications(
    limit: int = 20,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Get in-app notifications for the current user."""
    items = notif_svc.get_user_notifications(
        db=db, user_id=UUID(str(current_user.user_id)), limit=min(limit, 100)
    )
    unread = notif_svc.get_unread_count(db=db, user_id=UUID(str(current_user.user_id)))
    return {"notifications": items, "unread_count": unread}


@router.get("/unread-count")
async def get_unread_count(
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Return unread notification count for the current user."""
    count = notif_svc.get_unread_count(db=db, user_id=UUID(str(current_user.user_id)))
    return {"count": count}


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Mark a single notification as read."""
    updated = notif_svc.mark_as_read(
        db=db,
        notification_id=notification_id,
        user_id=UUID(str(current_user.user_id)),
    )
    db.commit()
    return {"notification_id": str(notification_id), "marked_read": updated}


@router.post("/read-all")
async def mark_all_read(
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Mark all notifications as read for the current user."""
    count = notif_svc.mark_all_as_read(db=db, user_id=UUID(str(current_user.user_id)))
    db.commit()
    return {"marked_count": count}
```

---

### File 10 — `backend/app/routers/webhooks.py` (NEW)

```python
"""Webhook receivers for external integrations (Google Drive change notifications)."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.db_service import get_db
from app.services import notifications as notif_svc

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/drive-changes")
async def drive_changes_webhook(
    request: Request,
    x_goog_resource_id: str = Header(None, alias="X-Goog-Resource-Id"),
    x_goog_channel_id: str = Header(None, alias="X-Goog-Channel-Id"),
    x_goog_resource_state: str = Header(None, alias="X-Goog-Resource-State"),
    db: Session = Depends(get_db),
):
    """Receive Google Drive push notifications for file changes.

    channel_id convention: "doc:{document_id}" (set during register_file_watch).
    """
    logger.info(
        "Drive webhook: channel=%s resource=%s state=%s",
        x_goog_channel_id, x_goog_resource_id, x_goog_resource_state,
    )

    if x_goog_resource_state == "sync":
        return {"ok": True, "type": "sync"}

    if x_goog_channel_id and x_goog_channel_id.startswith("doc:"):
        try:
            doc_id_str = x_goog_channel_id[4:]
            row = db.execute(
                text(
                    """
                    SELECT d.title, d.created_by, p.name
                    FROM documents d
                    JOIN projects p ON p.project_id = d.project_id
                    WHERE d.doc_id = :did
                    """
                ),
                {"did": doc_id_str},
            ).fetchone()
            if row and row[1]:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(row[1])),
                    title="Document Modified",
                    message=f"Your document '{row[0]}' in project '{row[2]}' was modified.",
                    notif_type="file_edited",
                    project_name=row[2] or "",
                    doc_name=row[0] or "",
                )
                db.commit()
        except Exception as exc:
            logger.warning("drive_changes_webhook notification failed: %s", exc)

    return {"ok": True, "type": x_goog_resource_state or "change"}
```

---

### File 11 — `backend/app/main.py` — add webhooks router

In [main.py](backend/app/main.py), add after the existing imports:

```python
from .routers import webhooks as webhooks_router
```

And add the router registration after the existing `app.include_router(notifications_router...)`:

```python
app.include_router(
    webhooks_router.router,
    prefix="/api/webhooks",
    tags=["webhooks"],
)
```

---

### File 12 — `frontend/src/services/documents.ts` — add to end of file

Append to the existing [documents.ts](frontend/src/services/documents.ts):

```typescript
export async function returnWorkflow(workflowId: string, comment: string): Promise<void> {
  await approvalsClient.post(`/${workflowId}/return`, { comment })
}

export async function resubmitDocument(docId: string): Promise<void> {
  const docsClient2 = axios.create({ baseURL: '/api/documents', withCredentials: true })
  await docsClient2.post(`/${docId}/resubmit`)
}

export interface ApprovalItemExtended extends PendingApprovalItem {
  project_name?: string | null
  submitter_name?: string | null
  submitter_role?: string | null
  doc_type?: string | null
  status_color?: string | null
  step_1_role?: string | null
  step_2_role?: string | null
}
```

---

### File 13 — `frontend/src/services/notifications.ts` (NEW)

```typescript
import axios from 'axios'

export interface NotificationItem {
  notification_id: string
  title: string
  message: string
  type: string
  is_read: boolean
  related_doc_id: string | null
  related_workflow_id: string | null
  project_name: string | null
  doc_name: string | null
  created_at: string | null
}

const client = axios.create({
  baseURL: '/api/notifications',
  withCredentials: true,
})

export async function getNotifications(limit = 20): Promise<{ notifications: NotificationItem[]; unread_count: number }> {
  const response = await client.get('', { params: { limit } })
  return response.data
}

export async function getUnreadCount(): Promise<number> {
  const response = await client.get('/unread-count')
  return (response.data as { count: number }).count
}

export async function markAsRead(notificationId: string): Promise<void> {
  await client.post(`/${notificationId}/read`)
}

export async function markAllAsRead(): Promise<void> {
  await client.post('/read-all')
}
```

---

### File 14 — `frontend/src/components/NotificationBell.tsx` (NEW)

```tsx
import React, { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/router'
import {
  getNotifications,
  getUnreadCount,
  markAllAsRead,
  markAsRead,
  type NotificationItem,
} from '@/services/notifications'

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} minute${mins > 1 ? 's' : ''} ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs} hour${hrs > 1 ? 's' : ''} ago`
  return `${Math.floor(hrs / 24)} day${Math.floor(hrs / 24) > 1 ? 's' : ''} ago`
}

export default function NotificationBell() {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<NotificationItem[]>([])
  const [unread, setUnread] = useState(0)
  const ref = useRef<HTMLDivElement>(null)

  const load = async () => {
    try {
      const { notifications, unread_count } = await getNotifications(20)
      setItems(notifications)
      setUnread(unread_count)
    } catch {
      // silent — not authenticated yet
    }
  }

  useEffect(() => {
    void load()
    const interval = setInterval(() => void load(), 30000)
    return () => clearInterval(interval)
  }, [])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleMarkAll = async () => {
    await markAllAsRead()
    setUnread(0)
    setItems((prev) => prev.map((n) => ({ ...n, is_read: true })))
  }

  const handleItemClick = async (item: NotificationItem) => {
    if (!item.is_read) {
      await markAsRead(item.notification_id)
      setItems((prev) =>
        prev.map((n) =>
          n.notification_id === item.notification_id ? { ...n, is_read: true } : n
        )
      )
      setUnread((c) => Math.max(0, c - 1))
    }
    if (item.related_workflow_id) {
      void router.push('/approvals')
    }
    setOpen(false)
  }

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        type="button"
        className="btn btn-link nav-link position-relative p-0 me-3"
        onClick={() => setOpen((o) => !o)}
        aria-label="Notifications"
        style={{ color: 'rgba(255,255,255,0.75)' }}
      >
        🔔
        {unread > 0 && (
          <span
            className="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger"
            style={{ fontSize: '0.65rem' }}
          >
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          className="card shadow"
          style={{
            position: 'absolute',
            right: 0,
            top: '2rem',
            width: '360px',
            maxHeight: '480px',
            overflowY: 'auto',
            zIndex: 1050,
          }}
        >
          <div className="card-header d-flex justify-content-between align-items-center py-2">
            <strong>Notifications</strong>
            {unread > 0 && (
              <button
                type="button"
                className="btn btn-link btn-sm p-0 text-muted"
                onClick={() => void handleMarkAll()}
              >
                Mark all as read
              </button>
            )}
          </div>

          {items.length === 0 ? (
            <div className="card-body text-muted small text-center py-4">No notifications</div>
          ) : (
            <ul className="list-group list-group-flush">
              {items.map((item) => (
                <li
                  key={item.notification_id}
                  className={`list-group-item list-group-item-action ${!item.is_read ? 'fw-bold' : ''}`}
                  style={{ cursor: 'pointer', backgroundColor: item.is_read ? '' : '#f0f7ff' }}
                  onClick={() => void handleItemClick(item)}
                >
                  <div className="d-flex justify-content-between">
                    <span className="small">{item.title}</span>
                    <span className="text-muted" style={{ fontSize: '0.7rem', whiteSpace: 'nowrap' }}>
                      {timeAgo(item.created_at)}
                    </span>
                  </div>
                  <div className="text-muted small" style={{ fontSize: '0.8rem' }}>
                    {(item.message || '').length > 80
                      ? `${item.message.slice(0, 80)}…`
                      : item.message}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
```

---

### File 15 — `frontend/src/components/Layout.tsx` (COMPLETE REPLACEMENT)

```tsx
/**
 * Main Layout Component
 */
import React from 'react'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/router'
import 'bootstrap/dist/css/bootstrap.min.css'
import styles from '@/styles/layout.module.css'
import { getCurrentUser, logout } from '@/services/auth'
import NotificationBell from '@/components/NotificationBell'

interface LayoutProps {
  children: React.ReactNode
}

export function Layout({ children }: LayoutProps) {
  const router = useRouter()
  const [isAuthenticated, setIsAuthenticated] = useState(false)

  useEffect(() => {
    const bootstrap = async () => {
      const user = await getCurrentUser()
      setIsAuthenticated(user !== null)
    }
    void bootstrap()
  }, [router.pathname])

  const handleLogout = async () => {
    await logout()
    router.push('/login')
  }

  return (
    <div className={styles.layout}>
      {isAuthenticated && (
        <nav className={`${styles.navbar} navbar navbar-expand-lg navbar-dark bg-dark`}>
          <div className="container-fluid">
            <Link href="/" className="navbar-brand">
              AI BA Agent
            </Link>
            <div className="collapse navbar-collapse">
              <ul className="navbar-nav ms-auto align-items-center">
                <li className="nav-item">
                  <Link href="/projects" className="nav-link">
                    Projects
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/documents" className="nav-link">
                    Documents
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/approvals" className="nav-link">
                    Approvals
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/knowledge-base" className="nav-link">
                    Knowledge Base
                  </Link>
                </li>
                <li className="nav-item d-flex align-items-center">
                  <NotificationBell />
                </li>
                <li className="nav-item">
                  <button
                    className="nav-link btn btn-link"
                    onClick={handleLogout}
                  >
                    Logout
                  </button>
                </li>
              </ul>
            </div>
          </div>
        </nav>
      )}

      
```


## License: unknown
https://github.com/RakanAji/SMARTPLANTMONITORING_KELOMPOK6/blob/ebf90229ddf582f567c06fafa486befebe2eab2d/src/components/Header.js

```
I now have a complete picture of the codebase. I'm in Ask mode so I cannot write files directly — I'll provide the complete, implementation-ready code for every file to create or modify. Apply them in order.

---

## Implementation

### File 1 — `infra/migrations/005_add_notifications.sql` (NEW)

```sql
-- 005: In-app notifications table
CREATE TABLE IF NOT EXISTS notifications (
  notification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(user_id),
  title VARCHAR(255) NOT NULL,
  message TEXT NOT NULL,
  type VARCHAR(50) NOT NULL DEFAULT 'info',
  is_read BOOLEAN DEFAULT false,
  related_doc_id UUID REFERENCES documents(doc_id),
  related_workflow_id UUID REFERENCES approval_workflows(workflow_id),
  project_name VARCHAR(255),
  doc_name VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_is_read  ON notifications(is_read);
```

---

### File 2 — `infra/migrations/006_add_workflow_roles.sql` (NEW)

```sql
-- 006: Per-workflow dynamic role assignment + submitter tracking
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS step_1_role   VARCHAR(50);
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS step_2_role   VARCHAR(50);
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS submitter_id  UUID REFERENCES users(user_id);
```

---

### File 3 — `backend/app/services/notifications.py` (NEW)

```python
"""DB-backed in-app notification service (distinct from notification.py which is Telegram)."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def create_notification(
    *,
    db: Session,
    user_id: UUID,
    title: str,
    message: str,
    notif_type: str = "info",
    doc_id: Optional[UUID] = None,
    workflow_id: Optional[UUID] = None,
    project_name: str = "",
    doc_name: str = "",
) -> Optional[str]:
    """Insert a notification row. Returns notification_id or None on failure."""
    try:
        nid = str(uuid4())
        db.execute(
            text(
                """
                INSERT INTO notifications
                    (notification_id, user_id, title, message, type, is_read,
                     related_doc_id, related_workflow_id, project_name, doc_name, created_at)
                VALUES
                    (:nid, :uid, :title, :msg, :type, false,
                     :doc_id, :wf_id, :pname, :dname, :ts)
                """
            ),
            {
                "nid": nid,
                "uid": str(user_id),
                "title": title,
                "msg": message,
                "type": notif_type,
                "doc_id": str(doc_id) if doc_id else None,
                "wf_id": str(workflow_id) if workflow_id else None,
                "pname": project_name,
                "dname": doc_name,
                "ts": datetime.utcnow(),
            },
        )
        return nid
    except Exception as exc:
        logger.error("create_notification failed: %s", exc)
        return None


def get_user_notifications(
    *, db: Session, user_id: UUID, limit: int = 20
) -> List[Dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT notification_id, title, message, type, is_read,
                   related_doc_id, related_workflow_id,
                   project_name, doc_name, created_at
            FROM notifications
            WHERE user_id = :uid
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"uid": str(user_id), "limit": limit},
    ).fetchall()
    return [
        {
            "notification_id": str(r[0]),
            "title": r[1],
            "message": r[2],
            "type": r[3],
            "is_read": bool(r[4]),
            "related_doc_id": str(r[5]) if r[5] else None,
            "related_workflow_id": str(r[6]) if r[6] else None,
            "project_name": r[7],
            "doc_name": r[8],
            "created_at": r[9].isoformat() if r[9] else None,
        }
        for r in rows
    ]


def mark_as_read(*, db: Session, notification_id: UUID, user_id: UUID) -> bool:
    result = db.execute(
        text(
            """
            UPDATE notifications
            SET is_read = true
            WHERE notification_id = :nid AND user_id = :uid
            """
        ),
        {"nid": str(notification_id), "uid": str(user_id)},
    )
    return (result.rowcount or 0) > 0


def mark_all_as_read(*, db: Session, user_id: UUID) -> int:
    result = db.execute(
        text(
            "UPDATE notifications SET is_read = true WHERE user_id = :uid AND is_read = false"
        ),
        {"uid": str(user_id)},
    )
    return result.rowcount or 0


def get_unread_count(*, db: Session, user_id: UUID) -> int:
    row = db.execute(
        text(
            "SELECT COUNT(*) FROM notifications WHERE user_id = :uid AND is_read = false"
        ),
        {"uid": str(user_id)},
    ).fetchone()
    return int(row[0] or 0)


def get_role_user_ids(
    *, db: Session, project_id: UUID, role: str
) -> List[str]:
    """Return user_ids that have the given role (system-wide or project-scoped)."""
    rows = db.execute(
        text(
            """
            SELECT DISTINCT u.user_id
            FROM users u
            LEFT JOIN user_projects up
                ON up.user_id = u.user_id AND up.project_id = :pid
            WHERE u.role = :role OR up.role = :role
            LIMIT 20
            """
        ),
        {"pid": str(project_id), "role": role},
    ).fetchall()
    return [str(r[0]) for r in rows]
```

---

### File 4 — `backend/app/services/workflow.py` (COMPLETE REPLACEMENT)

```python
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


# Fallback static step roles — used when a workflow pre-dates dynamic assignment
APPROVAL_STEPS = {
    1: "business_owner",
    2: "admin",
}


def _resolve_dynamic_roles(submitter_role: str) -> Tuple[str, str]:
    """Return (step_1_role, step_2_role) based on the submitter's role."""
    if submitter_role == "business_owner":
        return ("ba", "business_owner")
    if submitter_role in ("ba", "pm"):
        return ("business_owner", "ba")
    # tech_lead, legal, finance, viewer → default
    return ("business_owner", "admin")


def _get_expected_role(wf: Dict[str, Any]) -> str:
    """Return the role required for the current workflow step."""
    if wf["current_step"] == 1:
        return wf.get("step_1_role") or APPROVAL_STEPS.get(1, "business_owner")
    return wf.get("step_2_role") or APPROVAL_STEPS.get(2, "admin")


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
    step_1_role, step_2_role = _resolve_dynamic_roles(submitter_role)
    total_steps = len(APPROVAL_STEPS)

    if submitter_role == "admin":
        initial_status = "approved"
        doc_status = "approved"
    else:
        initial_status = "pending"
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
    step_2 = row[8] or APPROVAL_STEPS.get(2, "admin")

    return {
        "workflow_id": str(row[0]),
        "doc_id": str(row[1]),
        "project_id": str(row[2]),
        "current_step": int(row[3] or 1),
        "total_steps": len(APPROVAL_STEPS),
        "status": str(row[5] or "in_progress"),
        "version_id": str(row[6]) if row[6] else None,
        "step_1_role": step_1,
        "step_2_role": step_2,
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

    next_step = completed_step + 1
    final_step = len(APPROVAL_STEPS)
    new_status = "approved" if next_step > final_step else "in_progress"
    new_doc_status = "approved" if new_status == "approved" else "pending_approval"

    step_roles = {1: wf.get("step_1_role"), 2: wf.get("step_2_role")}
    next_required_role = step_roles.get(next_step) or APPROVAL_STEPS.get(next_step)

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
            SET current_step = :current_step,
                status       = :status,
                version_id   = :version_id,
                updated_at   = :updated_at
            WHERE workflow_id = :workflow_id
            """
        ),
        {
            "current_step": min(next_step, final_step),
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

    log_audit_event(
        db=db,
        project_id=UUID(wf["project_id"]),
        action="APPROVAL_APPROVED",
        entity_type="approval",
        entity_id=workflow_id,
        user_id=actor_user_id,
        old_values={"status": wf["status"], "current_step": completed_step},
        new_values={
            "status": new_status,
            "current_step": min(next_step, final_step),
            "version_id": str(version_id),
        },
        succeeded=True,
    )

    return {
        "workflow_id": wf["workflow_id"],
        "decision_id": str(decision_id),
        "status": new_status,
        "completed_step": completed_step,
        "current_step": min(next_step, final_step),
        "next_required_role": None if new_status == "approved" else next_required_role,
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
        reason=(
            f"Rejection at step {wf['current_step']}: {reason}"
            if reason
            else f"Rejection at step {wf['current_step']}"
        ),
        project_id=UUID(wf["project_id"]),
        workflow_id=workflow_id,
        db=db,
    )

    db.execute(
        text(
            """
            UPDATE approval_workflows
            SET status     = 'rejected',
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
    """Return a document for revision.

    Step 1 → sets status = returned_to_submitter, doc status = returned
    Step 2 → sets status = returned_to_step1, resets to step 1
    """
    wf = get_workflow(workflow_id, db)
    if wf is None:
        raise ValueError("Approval workflow not found")

    if wf["status"] in {"approved", "rejected"}:
        raise ValueError(f"Workflow already closed with status={wf['status']}")

    expected_role = _get_expected_role(wf)
    if actor_role != expected_role and actor_role != "admin":
        raise PermissionError(f"Current step requires role '{expected_role}'")

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
            "step_number": wf["current_step"],
            "approver_id": str(actor_user_id),
            "comments": comment,
            "created_at": now,
        },
    )

    from_step = wf["current_step"]
    if from_step == 1:
        new_wf_status = "returned_to_submitter"
        new_doc_status = "returned"
        audit_action = "APPROVAL_RETURNED_TO_SUBMITTER"
    else:
        new_wf_status = "returned_to_step1"
        new_doc_status = "pending_approval"
        audit_action = "APPROVAL_RETURNED_TO_STEP1"

    version_id = create_document_version(
        doc_id=UUID(wf["doc_id"]),
        created_by=actor_user_id,
        approval_status=new_wf_status,
        reason=f"Returned at step {from_step}: {comment}",
        project_id=UUID(wf["project_id"]),
        workflow_id=workflow_id,
        db=db,
    )

    db.execute(
        text(
            """
            UPDATE approval_workflows
            SET status       = :status,
                current_step = 1,
                version_id   = :version_id,
                updated_at   = :updated_at
            WHERE workflow_id = :workflow_id
            """
        ),
        {
            "status": new_wf_status,
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
        old_values={"status": wf["status"], "current_step": from_step},
        new_values={"status": new_wf_status, "comment": comment, "version_id": str(version_id)},
        succeeded=True,
    )

    return {
        "workflow_id": wf["workflow_id"],
        "decision_id": str(decision_id),
        "status": new_wf_status,
        "current_step": 1,
        "previous_step": from_step,
        "comment": comment,
        "version_id": str(version_id),
        "submitter_id": wf.get("submitter_id"),
        "step_1_role": wf.get("step_1_role"),
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
                (workflow_id, doc_id, project_id, current_step, total_steps, status,
                 submitter_id, created_at, updated_at)
            VALUES
                (:workflow_id, :doc_id, :project_id, 1, :total_steps,
                 'human_review_required', :submitter_id, :created_at, :updated_at)
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
        new_values={
            "status": "human_review_required",
            "doc_id": str(doc_id),
            "total_steps": len(APPROVAL_STEPS),
        },
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
        {"version_id": str(version_id), "updated_at": now, "workflow_id": str(workflow_id)},
    )
    db.execute(
        text(
            "UPDATE documents SET status = 'human_review_required', updated_at = :t WHERE doc_id = :id"
        ),
        {"t": now, "id": str(doc_id)},
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
                (version_id, doc_id, version_number, content, content_hash,
                 created_by, approval_status, created_at)
            VALUES
                (:version_id, :doc_id, :version_number, :content, :content_hash,
                 :created_by, :approval_status, :created_at)
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
```

---

### File 5 — `backend/app/services/google_drive.py` — append at bottom

Add these three functions to the end of the existing [google_drive.py](backend/app/services/google_drive.py):

```python
import re as _re

_MIME_EDIT_URLS = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        "https://docs.google.com/document/d/{id}/edit",
    "application/msword":
        "https://docs.google.com/document/d/{id}/edit",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
    "application/vnd.ms-excel":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
    "text/csv":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
}


def get_drive_file_id(drive_url: str) -> Optional[str]:
    """Extract the Drive file ID from a webViewLink URL."""
    match = _re.search(r"/(?:file/)?d/([a-zA-Z0-9_-]+)", drive_url or "")
    return match.group(1) if match else None


def get_edit_url(file_id: str, mime_type: str) -> str:
    """Return the correct Google Drive / Docs / Sheets URL for the given MIME type."""
    template = _MIME_EDIT_URLS.get(mime_type)
    if template:
        return template.format(id=file_id)
    return f"https://drive.google.com/file/d/{file_id}/view"


def register_file_watch(file_id: str, document_id: str) -> bool:
    """Register a Google Drive push-notification watch (requires verified HTTPS endpoint).

    This stub logs the intent.  In production, call files().watch() with your
    verified webhook URL and store the channel/resource IDs for later expiry renewal.
    """
    logger.info(
        "register_file_watch: file_id=%s doc_id=%s (stub – HTTPS endpoint required)",
        file_id,
        document_id,
    )
    return False
```

---

### File 6 — `backend/app/middleware/rbac.py` — append one line after `require_approver`

Add after `require_approver = ...`:

```python
# Broader reviewer set: includes BA and PM (needed for dynamic step approver assignment)
require_reviewer = make_require_role(["admin", "business_owner", "ba", "pm", "legal"])
```

---

### File 7 — `backend/app/routers/approvals.py` (COMPLETE REPLACEMENT)

```python
"""Approval workflow endpoints."""

from __future__ import annotations

import logging
import os as _os
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_ba, require_readonly, require_reviewer
from app.services.db_service import get_db
from app.services import google_sheets
from app.services import notifications as notif_svc
from app.services.workflow import (
    APPROVAL_STEPS,
    approve_step,
    create_approval_workflow,
    get_workflow,
    reject_step,
    return_step,
    trigger_hitl,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Statuses considered "active / pending" for the dashboard
_PENDING_STATUSES = (
    "in_progress",
    "human_review_required",
    "returned_to_submitter",
    "returned_to_step1",
)
_COMPLETED_STATUSES = ("approved", "rejected")


class ApprovalActionRequest(BaseModel):
    comment: str = ""


class ReturnRequest(BaseModel):
    comment: str = Field(min_length=1)


class CreateApprovalRequest(BaseModel):
    document_id: UUID
    project_id: UUID
    workflow_type: str = "approval"


class RejectionRequest(BaseModel):
    reason: str = Field(min_length=1)


class HitlTriggerRequest(BaseModel):
    document_id: UUID
    project_id: Optional[UUID] = None
    reason: str = Field(min_length=1)
    risk_flags: Dict[str, Any] = {}


# ─── helpers ─────────────────────────────────────────────────────────────────

def _get_doc_project_info(workflow_id: UUID, db: Session):
    """Return (doc_title, project_name, submitter_id) for a workflow."""
    return db.execute(
        text(
            """
            SELECT d.title, p.name, aw.submitter_id
            FROM approval_workflows aw
            JOIN documents d ON d.doc_id = aw.doc_id
            JOIN projects p ON p.project_id = aw.project_id
            WHERE aw.workflow_id = :wid
            """
        ),
        {"wid": str(workflow_id)},
    ).fetchone()


def _status_badge_color(status: str) -> str:
    colors = {
        "in_progress": "info",
        "approved": "success",
        "rejected": "danger",
        "returned_to_submitter": "warning",
        "returned_to_step1": "warning",
        "human_review_required": "secondary",
    }
    return colors.get(status, "secondary")


# ─── endpoints ───────────────────────────────────────────────────────────────

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
            submitter_role=current_user.role,
            db=db,
        )
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"create_workflow_failed: {exc}")


@router.get("")
async def list_approvals(
    project_id: UUID,
    status: str = Query("pending"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """List approvals by status for dashboard views."""
    normalized = status.lower()
    if normalized not in {"pending", "completed", "all"}:
        raise HTTPException(status_code=400, detail="status must be pending, completed, or all")

    pending_in = ", ".join(f"'{s}'" for s in _PENDING_STATUSES)
    completed_in = ", ".join(f"'{s}'" for s in _COMPLETED_STATUSES)

    if normalized == "pending":
        status_filter = f"aw.status IN ({pending_in})"
    elif normalized == "completed":
        status_filter = f"aw.status IN ({completed_in})"
    else:
        status_filter = f"aw.status IN ({pending_in}, {completed_in})"

    offset = (page - 1) * page_size

    rows = db.execute(
        text(
            f"""
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
                    d.doc_type,
                    p.name AS project_name,
                    COALESCE(u.full_name, u.email, '') AS submitter_name,
                    u.role AS submitter_role,
                    aw.step_1_role,
                    aw.step_2_role,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                LEFT JOIN documents d ON d.doc_id = aw.doc_id
                LEFT JOIN projects p ON p.project_id = aw.project_id
                LEFT JOIN users u ON u.user_id = aw.submitter_id
                WHERE aw.project_id = :project_id
                  AND {status_filter}
            )
            SELECT workflow_id, doc_id, doc_title, current_step, total_steps, status,
                   updated_at, google_drive_link, doc_type, project_name,
                   submitter_name, submitter_role, step_1_role, step_2_role
            FROM ranked
            WHERE rn = 1
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"project_id": str(project_id), "limit": page_size, "offset": offset},
    ).fetchall()

    count_row = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT aw.doc_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                WHERE aw.project_id = :project_id AND {status_filter}
            )
            SELECT COUNT(*) FROM ranked WHERE rn = 1
            """
        ),
        {"project_id": str(project_id)},
    ).fetchone()

    items = [
        {
            "workflow_id": str(r[0]),
            "doc_id": str(r[1]),
            "doc_title": r[2] or None,
            "current_step": int(r[3] or 1),
            "total_steps": len(APPROVAL_STEPS),
            "status": r[5],
            "status_color": _status_badge_color(r[5]),
            "updated_at": r[6].isoformat() if r[6] else None,
            "google_drive_link": r[7] or None,
            "doc_type": r[8] or None,
            "project_name": r[9] or None,
            "submitter_name": r[10] or None,
            "submitter_role": r[11] or None,
            "step_1_role": r[12] or None,
            "step_2_role": r[13] or None,
        }
        for r in rows
    ]

    return {
        "project_id": str(project_id),
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
    pending_in = ", ".join(f"'{s}'" for s in _PENDING_STATUSES)
    offset = (page - 1) * page_size

    rows = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT
                    aw.workflow_id, aw.doc_id,
                    COALESCE(d.title, '') AS doc_title,
                    aw.current_step, aw.total_steps, aw.status, aw.updated_at,
                    d.google_drive_link, d.doc_type, p.name AS project_name,
                    COALESCE(u.full_name, u.email, '') AS submitter_name,
                    u.role AS submitter_role, aw.step_1_role, aw.step_2_role,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                LEFT JOIN documents d ON d.doc_id = aw.doc_id
                LEFT JOIN projects p ON p.project_id = aw.project_id
                LEFT JOIN users u ON u.user_id = aw.submitter_id
                WHERE aw.project_id = :project_id
                  AND aw.status IN ({pending_in})
            )
            SELECT workflow_id, doc_id, doc_title, current_step, total_steps, status,
                   updated_at, google_drive_link, doc_type, project_name,
                   submitter_name, submitter_role, step_1_role, step_2_role
            FROM ranked
            WHERE rn = 1
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"project_id": str(project_id), "limit": page_size, "offset": offset},
    ).fetchall()

    count_row = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT aw.doc_id,
                    ROW_NUMBER() OVER (PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC) AS rn
                FROM approval_workflows aw
                WHERE aw.project_id = :project_id
                  AND aw.status IN ({pending_in})
            )
            SELECT COUNT(*) FROM ranked WHERE rn = 1
            """
        ),
        {"project_id": str(project_id)},
    ).fetchone()

    items = [
        {
            "workflow_id": str(r[0]),
            "doc_id": str(r[1]),
            "doc_title": r[2] or None,
            "current_step": int(r[3] or 1),
            "total_steps": len(APPROVAL_STEPS),
            "status": r[5],
            "status_color": _status_badge_color(r[5]),
            "updated_at": r[6].isoformat() if r[6] else None,
            "google_drive_link": r[7] or None,
            "doc_type": r[8] or None,
            "project_name": r[9] or None,
            "submitter_name": r[10] or None,
            "submitter_role": r[11] or None,
            "step_1_role": r[12] or None,
            "step_2_role": r[13] or None,
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
    current_user: TokenUser = Depends(require_reviewer),
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

    # ── Google Sheets update (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            google_sheets.update_approval_row(
                project_name=info[1] or "",
                file_name=_os.path.splitext(info[0] or "")[0],
                approver_name=current_user.email,
                status="Approved",
                comment=request.comment,
            )
    except Exception as exc:
        logger.warning("Sheets update failed after approve (%s): %s", workflow_id, exc)

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            completed_step = result.get("completed_step", 1)
            final_approved = result["status"] == "approved"

            if submitter_id:
                title = "Document Approved ✅" if final_approved else "Document Progressed"
                if final_approved:
                    msg = f"Project {project_name}: '{doc_title}' has been fully approved!"
                else:
                    msg = f"Project {project_name}: '{doc_title}' passed step {completed_step} review."
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title=title,
                    message=msg,
                    notif_type="approved",
                    doc_id=UUID(result["workflow_id"]) if False else None,
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()
    except Exception as exc:
        logger.warning("Notification failed after approve (%s): %s", workflow_id, exc)

    return result


@router.post("/{workflow_id}/reject")
async def reject_document(
    workflow_id: UUID,
    request: RejectionRequest,
    current_user: TokenUser = Depends(require_reviewer),
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

    # ── Google Sheets update (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            google_sheets.update_approval_row(
                project_name=info[1] or "",
                file_name=_os.path.splitext(info[0] or "")[0],
                approver_name=current_user.email,
                status="Rejected",
                comment=request.reason,
            )
    except Exception as exc:
        logger.warning("Sheets update failed after reject (%s): %s", workflow_id, exc)

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            if submitter_id:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title="Document Rejected",
                    message=f"Project {project_name}: '{doc_title}' was rejected. Reason: {request.reason}",
                    notif_type="rejected",
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()
    except Exception as exc:
        logger.warning("Notification failed after reject (%s): %s", workflow_id, exc)

    return result


@router.post("/{workflow_id}/return")
async def return_document(
    workflow_id: UUID,
    request: ReturnRequest,
    current_user: TokenUser = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    """Return a document for revision.

    Step 1 → returned_to_submitter (document status = returned)
    Step 2 → returned_to_step1 (resets to step 1)
    """
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

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            new_status = result["status"]

            if new_status == "returned_to_submitter" and submitter_id:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title="Document Returned",
                    message=(
                        f"Project {project_name}: '{doc_title}' has been returned "
                        f"for revision. Comment: {request.comment}"
                    ),
                    notif_type="returned",
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()

            elif new_status == "returned_to_step1":
                step_1_role = result.get("step_1_role") or "business_owner"
                wf_row = db.execute(
                    text("SELECT project_id FROM approval_workflows WHERE workflow_id = :wid"),
                    {"wid": str(workflow_id)},
                ).fetchone()
                if wf_row:
                    approver_ids = notif_svc.get_role_user_ids(
                        db=db,
                        project_id=UUID(str(wf_row[0])),
                        role=step_1_role,
                    )
                    for uid_str in approver_ids:
                        notif_svc.create_notification(
                            db=db,
                            user_id=UUID(uid_str),
                            title="Re-review Required",
                            message=(
                                f"Project {project_name}: '{doc_title}' has been "
                                f"returned to you for re-review. Comment: {request.comment}"
                            ),
                            notif_type="returned_to_step1",
                            workflow_id=workflow_id,
                            project_name=project_name or "",
                            doc_name=doc_title or "",
                        )
                    db.commit()
    except Exception as exc:
        logger.warning("Notification failed after return (%s): %s", workflow_id, exc)

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
        "status_color": _status_badge_color(workflow["status"]),
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
```

---

### File 8 — `backend/app/routers/documents.py` (COMPLETE REPLACEMENT)

```python
"""
Document management endpoints.

POST /upload            – Accept file + metadata, store to DB, upload to Drive, trigger pipeline
POST /{doc_id}/resubmit – Resubmit a returned document for re-review
GET  /{doc_id}/status   – Return current processing status + progress
"""
import hashlib
import logging
import mimetypes
import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile, File
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_ba, require_readonly
from app.services.db_service import get_db
from app.services import google_drive, google_sheets, elevenlabs, n8n_webhook
from app.services import notifications as notif_svc
from app.services.workflow import _resolve_dynamic_roles

logger = logging.getLogger(__name__)
router = APIRouter()

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
    project_folder_id: Optional[str] = None,
) -> None:
    """Background task: upload to Google Drive, trigger STT + n8n, update status."""
    db: Session = next(get_db())
    try:
        db.execute(
            text("UPDATE documents SET status = :s, updated_at = :t WHERE doc_id = :id"),
            {"s": STATUS_PROCESSING, "t": datetime.utcnow(), "id": doc_id},
        )
        db.commit()

        drive_url: Optional[str] = google_drive.upload_file(
            file_bytes, filename, mime_type, project_folder_id
        )
        if drive_url:
            db.execute(
                text(
                    "UPDATE documents SET google_drive_link = :url, updated_at = :t WHERE doc_id = :id"
                ),
                {"url": drive_url, "t": datetime.utcnow(), "id": doc_id},
            )
            db.commit()

        transcript: Optional[str] = None
        if elevenlabs.is_audio(mime_type):
            transcript = await elevenlabs.transcribe(file_bytes, filename, mime_type)
            if transcript:
                version_id = str(uuid.uuid4())
                db.execute(
                    text(
                        """INSERT INTO document_versions
                             (version_id, doc_id, version_number, content, approval_status, created_at)
                           VALUES (:vid, :did, 1, :content, 'pending', :ts)"""
                    ),
                    {
                        "vid": version_id,
                        "did": doc_id,
                        "content": transcript,
                        "ts": datetime.utcnow(),
                    },
                )
                db.commit()

        await n8n_webhook.trigger_document_workflow(
            workflow_id=workflow_id,
            document_id=doc_id,
            google_drive_url=drive_url,
            file_type=mime_type,
            filename=filename,
        )

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
    current_user: TokenUser = Depends(require_ba),
    db: Session = Depends(get_db),
):
    """
    Upload a document for processing.

    - Requires role: ba / pm / tech_lead / admin  (HTTP 403 otherwise)
    - Returns: {document_id, workflow_id, status: "PENDING"}
    """
    mime_type: str = file.content_type or ""
    if not mime_type or mime_type == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(file.filename or "")
        mime_type = guessed or "application/octet-stream"

    doc_title  = title or (file.filename or "Untitled")
    doc_id     = str(uuid.uuid4())
    workflow_id = str(uuid.uuid4())

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # ── 1. Insert document record ─────────────────────────────────────────
    try:
        db.execute(
            text(
                """INSERT INTO documents
                     (doc_id, project_id, title, doc_type, status, created_by, created_at, updated_at)
                   VALUES (:doc_id, :project_id, :title, :doc_type, :status, :created_by, :now, :now)"""
            ),
            {
                "doc_id":     doc_id,
                "project_id": project_id,
                "title":      doc_title,
                "doc_type":   mime_type,
                "status":     STATUS_PENDING,
                "created_by": current_user.user_id,
                "now":        datetime.utcnow(),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to insert document record: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to store document metadata")

    # ── 2. Determine dynamic roles ────────────────────────────────────────
    step_1_role, step_2_role = _resolve_dynamic_roles(current_user.role)
    auto_approve = current_user.role == "admin"
    initial_wf_status = "approved" if auto_approve else "in_progress"

    # ── 3. Create approval_workflow entry ─────────────────────────────────
    try:
        db.execute(
            text(
                """INSERT INTO approval_workflows
                     (workflow_id, doc_id, project_id, status, current_step, total_steps,
                      step_1_role, step_2_role, submitter_id, created_at, updated_at)
                   VALUES
                     (:wid, :did, :pid, :status, 1, 2,
                      :step_1_role, :step_2_role, :submitter_id, :now, :now)"""
            ),
            {
                "wid":          workflow_id,
                "did":          doc_id,
                "pid":          project_id,
                "status":       initial_wf_status,
                "step_1_role":  step_1_role,
                "step_2_role":  step_2_role,
                "submitter_id": str(current_user.user_id),
                "now":          datetime.utcnow(),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to create approval workflow entry: %s", exc)

    # ── 4. Fetch project Drive folder ─────────────────────────────────────
    project_folder_id: Optional[str] = None
    project_name: str = ""
    try:
        proj_row = db.execute(
            text("SELECT name, google_drive_folder_id FROM projects WHERE project_id = :pid"),
            {"pid": project_id},
        ).fetchone()
        if proj_row:
            project_name     = proj_row[0] or ""
            project_folder_id = proj_row[1] or None
            if project_folder_id is None:
                project_folder_id = google_drive.create_project_folder(project_name)
                if project_folder_id:
                    db.execute(
                        text(
                            "UPDATE projects SET google_drive_folder_id = :fid WHERE project_id = :pid"
                        ),
                        {"fid": project_folder_id, "pid": project_id},
                    )
                    db.commit()
    except Exception as exc:
        logger.warning("Could not fetch project Drive folder for %s: %s", project_id, exc)

    # ── 5. Append row to Google Sheets backlog (best-effort) ──────────────
    try:
        import os as _os
        file_name_no_ext = _os.path.splitext(doc_title)[0]
        google_sheets.append_upload_row(
            user_name=current_user.email,
            project_name=project_name,
            file_name=file_name_no_ext,
            upload_date=datetime.utcnow().strftime("%d-%b-%Y"),
        )
    except Exception as exc:
        logger.warning("Sheets append_upload_row failed for %s: %s", doc_id, exc)

    # ── 6. Notify step-1 approvers (best-effort) ──────────────────────────
    try:
        approver_ids = notif_svc.get_role_user_ids(
            db=db, project_id=UUID(project_id), role=step_1_role
        )
        for uid_str in approver_ids:
            notif_svc.create_notification(
                db=db,
                user_id=UUID(uid_str),
                title="New Review Request",
                message=f"Project {project_name}: '{doc_title}' needs your review.",
                notif_type="upload",
                workflow_id=UUID(workflow_id),
                project_name=project_name,
                doc_name=doc_title,
            )
        db.commit()
    except Exception as exc:
        logger.warning("Upload notification failed for %s: %s", doc_id, exc)

    # ── 7. Queue background processing ────────────────────────────────────
    background_tasks.add_task(
        _process_document,
        doc_id,
        workflow_id,
        file_bytes,
        file.filename or doc_title,
        mime_type,
        project_folder_id,
    )

    logger.info(
        "Document %s queued for processing by %s (workflow %s)",
        doc_id, current_user.email, workflow_id,
    )
    return {
        "document_id":  doc_id,
        "workflow_id":  workflow_id,
        "filename":     file.filename,
        "status":       STATUS_PENDING,
        "uploaded_by":  current_user.email,
        "step_1_role":  step_1_role,
        "step_2_role":  step_2_role,
    }


@router.post("/{doc_id}/resubmit")
async def resubmit_document(
    doc_id: str,
    current_user: TokenUser = Depends(require_ba),
    db: Session = Depends(get_db),
):
    """Resubmit a returned document for re-review (only the original submitter or admin)."""
    doc_row = db.execute(
        text(
            "SELECT doc_id, project_id, title, status, created_by FROM documents WHERE doc_id = :did"
        ),
        {"did": doc_id},
    ).fetchone()
    if doc_row is None:
        raise HTTPException(status_code=404, detail="document_not_found")

    if current_user.role != "admin" and str(doc_row[4]) != str(current_user.user_id):
        raise HTTPException(status_code=403, detail="Only the document submitter can resubmit")

    if doc_row[3] != "returned":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not in 'returned' status (current: {doc_row[3]})",
        )

    wf_row = db.execute(
        text(
            """
            SELECT workflow_id, step_1_role, step_2_role, project_id
            FROM approval_workflows
            WHERE doc_id = :did AND status = 'returned_to_submitter'
            ORDER BY updated_at DESC LIMIT 1
            """
        ),
        {"did": doc_id},
    ).fetchone()

    now = datetime.utcnow()

    # Create new document version
    prev = db.execute(
        text(
            "SELECT version_number, content FROM document_versions WHERE doc_id = :did ORDER BY version_number DESC LIMIT 1"
        ),
        {"did": doc_id},
    ).fetchone()
    new_version_num = (int(prev[0]) + 1) if prev else 1
    content = f"{prev[1] or ''}\n\n[resubmitted by {current_user.email}]".strip() if prev else "[resubmitted]"
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    version_id = str(uuid.uuid4())

    db.execute(
        text(
            """
            INSERT INTO document_versions
                (version_id, doc_id, version_number, content, content_hash,
                 created_by, approval_status, created_at)
            VALUES (:vid, :did, :vn, :content, :hash, :uid, 'pending', :ts)
            """
        ),
        {
            "vid": version_id, "did": doc_id, "vn": new_version_num,
            "content": content, "hash": content_hash,
            "uid": str(current_user.user_id), "ts": now,
        },
    )

    db.execute(
        text("UPDATE documents SET status = 'pending_approval', updated_at = :ts WHERE doc_id = :did"),
        {"ts": now, "did": doc_id},
    )

    wf_id_str: Optional[str] = None
    step_1_role = "business_owner"
    project_id_str = str(doc_row[1])

    if wf_row:
        wf_id_str   = str(wf_row[0])
        step_1_role = wf_row[1] or "business_owner"
        db.execute(
            text(
                "UPDATE approval_workflows SET status = 'in_progress', current_step = 1, updated_at = :ts WHERE workflow_id = :wid"
            ),
            {"ts": now, "wid": wf_id_str},
        )

    db.commit()

    # Notify step-1 approvers (best-effort)
    try:
        pname_row = db.execute(
            text("SELECT name FROM projects WHERE project_id = :pid"),
            {"pid": project_id_str},
        ).fetchone()
        pname = pname_row[0] if pname_row else ""
        approver_ids = notif_svc.get_role_user_ids(
            db=db, project_id=UUID(project_id_str), role=step_1_role
        )
        for uid_str in approver_ids:
            notif_svc.create_notification(
                db=db,
                user_id=UUID(uid_str),
                title="Document Resubmitted",
                message=f"Project {pname}: '{doc_row[2]}' has been revised and resubmitted.",
                notif_type="resubmit",
                workflow_id=UUID(wf_id_str) if wf_id_str else None,
                project_name=pname,
                doc_name=doc_row[2] or "",
            )
        db.commit()
    except Exception as exc:
        logger.warning("Resubmit notification failed for %s: %s", doc_id, exc)

    return {
        "document_id":    doc_id,
        "status":         "pending_approval",
        "version_id":     version_id,
        "resubmitted_by": current_user.email,
    }


@router.get("")
async def list_documents(
    project_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """List documents with optional project filter (auth required)."""
    safe_limit  = max(1, min(limit, 200))
    safe_offset = max(0, offset)

    if project_id:
        rows = db.execute(
            text(
                """SELECT doc_id, project_id, title, doc_type, status, updated_at
                   FROM documents WHERE project_id = :pid
                   ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"""
            ),
            {"pid": project_id, "limit": safe_limit, "offset": safe_offset},
        ).fetchall()
    else:
        rows = db.execute(
            text(
                """SELECT doc_id, project_id, title, doc_type, status, updated_at
                   FROM documents
                   ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"""
            ),
            {"limit": safe_limit, "offset": safe_offset},
        ).fetchall()

    return {
        "requested_by": current_user.email,
        "project_id": project_id,
        "total": len(rows),
        "documents": [
            {
                "doc_id":     str(r[0]),
                "project_id": str(r[1]),
                "title":      r[2],
                "doc_type":   r[3],
                "status":     r[4],
                "updated_at": r[5].isoformat() if r[5] else None,
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
    """Get the current processing status of a document."""
    try:
        row = db.execute(
            text(
                "SELECT doc_id, title, status, doc_type, google_drive_link, updated_at FROM documents WHERE doc_id = :id"
            ),
            {"id": doc_id},
        ).fetchone()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"db_error: {exc}")

    if row is None:
        raise HTTPException(status_code=404, detail="document_not_found")

    status = row[2]
    progress_map = {
        STATUS_PENDING:    10,
        STATUS_PROCESSING: 50,
        STATUS_COMPLETED:  100,
        STATUS_FAILED:     0,
    }

    # Build edit URL if Drive link exists
    edit_url: Optional[str] = None
    drive_link = row[4]
    if drive_link:
        file_id = google_drive.get_drive_file_id(drive_link)
        if file_id:
            edit_url = google_drive.get_edit_url(file_id, row[3] or "")

    return {
        "document_id":      str(row[0]),
        "title":            row[1],
        "status":           status,
        "progress":         progress_map.get(status, 0),
        "doc_type":         row[3],
        "google_drive_url": drive_link,
        "edit_url":         edit_url,
        "updated_at":       row[5].isoformat() if row[5] else None,
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
                "version_id":       str(r[0]),
                "version_number":   int(r[1]),
                "content_hash":     r[2],
                "approval_status":  r[3],
                "created_by":       str(r[4]) if r[4] else None,
                "created_at":       r[5].isoformat() if r[5] else None,
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
            SELECT version_id, version_number, content, content_hash, approval_status, created_by, created_at
            FROM document_versions
            WHERE doc_id = :doc_id AND version_id = :version_id
            """
        ),
        {"doc_id": doc_id, "version_id": version_id},
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="version_not_found")

    return {
        "version_id":       str(row[0]),
        "version_number":   int(row[1]),
        "content":          row[2],
        "content_hash":     row[3],
        "approval_status":  row[4],
        "created_by":       str(row[5]) if row[5] else None,
        "created_at":       row[6].isoformat() if row[6] else None,
    }
```

---

### File 9 — `backend/app/routers/notifications.py` (COMPLETE REPLACEMENT)

```python
"""Notification endpoints — Telegram + in-app DB notifications."""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_admin, require_readonly
from app.services.db_service import get_db
from app.services.notification import notification_service
from app.services.telegram_bot import telegram_bot_service
from app.services import notifications as notif_svc

router = APIRouter()


class NotificationSendRequest(BaseModel):
    message: str = Field(min_length=1)
    type: str = "info"
    project_id: Optional[UUID] = None
    metadata: Dict[str, Any] = {}


class TelegramUpdateRequest(BaseModel):
    update_id: Optional[int] = None
    message: Dict[str, Any] = {}


# ─── Telegram endpoints (unchanged) ──────────────────────────────────────────

@router.post("/send")
async def send_notification(
    request: NotificationSendRequest,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Send a notification through the configured Telegram bot."""
    result = await notification_service.dispatch_notification(
        db=db,
        message=request.message,
        notification_type=request.type,
        actor_user_id=UUID(str(current_user.user_id)),
        project_id=request.project_id,
        metadata=request.metadata,
    )
    db.commit()
    return result


@router.post("/telegram/webhook")
async def telegram_webhook(
    payload: TelegramUpdateRequest,
    db: Session = Depends(get_db),
):
    """Receive Telegram updates and reply to /status, /backlog, /help."""
    message = payload.message or {}
    command_text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id")) if chat.get("id") is not None else None

    if not command_text.startswith("/"):
        return {"ok": True, "handled": False}

    reply_text = notification_service.process_telegram_command(command_text, db)
    sent = await telegram_bot_service.send_message(reply_text, chat_id=chat_id)
    return {
        "ok": True,
        "handled": True,
        "command": command_text.split(" ")[0].lower(),
        "sent": sent,
    }


@router.post("/approval-reminders/run")
async def run_approval_reminders(
    current_user: TokenUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Manual trigger for approval reminders (used by n8n workflow E)."""
    result = await notification_service.send_approval_reminders(db)
    return {**result, "triggered_by": current_user.email}


# ─── In-app DB notifications ─────────────────────────────────────────────────

@router.get("")
async def get_notifications(
    limit: int = 20,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Get in-app notifications for the current user."""
    items = notif_svc.get_user_notifications(
        db=db, user_id=UUID(str(current_user.user_id)), limit=min(limit, 100)
    )
    unread = notif_svc.get_unread_count(db=db, user_id=UUID(str(current_user.user_id)))
    return {"notifications": items, "unread_count": unread}


@router.get("/unread-count")
async def get_unread_count(
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Return unread notification count for the current user."""
    count = notif_svc.get_unread_count(db=db, user_id=UUID(str(current_user.user_id)))
    return {"count": count}


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Mark a single notification as read."""
    updated = notif_svc.mark_as_read(
        db=db,
        notification_id=notification_id,
        user_id=UUID(str(current_user.user_id)),
    )
    db.commit()
    return {"notification_id": str(notification_id), "marked_read": updated}


@router.post("/read-all")
async def mark_all_read(
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Mark all notifications as read for the current user."""
    count = notif_svc.mark_all_as_read(db=db, user_id=UUID(str(current_user.user_id)))
    db.commit()
    return {"marked_count": count}
```

---

### File 10 — `backend/app/routers/webhooks.py` (NEW)

```python
"""Webhook receivers for external integrations (Google Drive change notifications)."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.db_service import get_db
from app.services import notifications as notif_svc

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/drive-changes")
async def drive_changes_webhook(
    request: Request,
    x_goog_resource_id: str = Header(None, alias="X-Goog-Resource-Id"),
    x_goog_channel_id: str = Header(None, alias="X-Goog-Channel-Id"),
    x_goog_resource_state: str = Header(None, alias="X-Goog-Resource-State"),
    db: Session = Depends(get_db),
):
    """Receive Google Drive push notifications for file changes.

    channel_id convention: "doc:{document_id}" (set during register_file_watch).
    """
    logger.info(
        "Drive webhook: channel=%s resource=%s state=%s",
        x_goog_channel_id, x_goog_resource_id, x_goog_resource_state,
    )

    if x_goog_resource_state == "sync":
        return {"ok": True, "type": "sync"}

    if x_goog_channel_id and x_goog_channel_id.startswith("doc:"):
        try:
            doc_id_str = x_goog_channel_id[4:]
            row = db.execute(
                text(
                    """
                    SELECT d.title, d.created_by, p.name
                    FROM documents d
                    JOIN projects p ON p.project_id = d.project_id
                    WHERE d.doc_id = :did
                    """
                ),
                {"did": doc_id_str},
            ).fetchone()
            if row and row[1]:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(row[1])),
                    title="Document Modified",
                    message=f"Your document '{row[0]}' in project '{row[2]}' was modified.",
                    notif_type="file_edited",
                    project_name=row[2] or "",
                    doc_name=row[0] or "",
                )
                db.commit()
        except Exception as exc:
            logger.warning("drive_changes_webhook notification failed: %s", exc)

    return {"ok": True, "type": x_goog_resource_state or "change"}
```

---

### File 11 — `backend/app/main.py` — add webhooks router

In [main.py](backend/app/main.py), add after the existing imports:

```python
from .routers import webhooks as webhooks_router
```

And add the router registration after the existing `app.include_router(notifications_router...)`:

```python
app.include_router(
    webhooks_router.router,
    prefix="/api/webhooks",
    tags=["webhooks"],
)
```

---

### File 12 — `frontend/src/services/documents.ts` — add to end of file

Append to the existing [documents.ts](frontend/src/services/documents.ts):

```typescript
export async function returnWorkflow(workflowId: string, comment: string): Promise<void> {
  await approvalsClient.post(`/${workflowId}/return`, { comment })
}

export async function resubmitDocument(docId: string): Promise<void> {
  const docsClient2 = axios.create({ baseURL: '/api/documents', withCredentials: true })
  await docsClient2.post(`/${docId}/resubmit`)
}

export interface ApprovalItemExtended extends PendingApprovalItem {
  project_name?: string | null
  submitter_name?: string | null
  submitter_role?: string | null
  doc_type?: string | null
  status_color?: string | null
  step_1_role?: string | null
  step_2_role?: string | null
}
```

---

### File 13 — `frontend/src/services/notifications.ts` (NEW)

```typescript
import axios from 'axios'

export interface NotificationItem {
  notification_id: string
  title: string
  message: string
  type: string
  is_read: boolean
  related_doc_id: string | null
  related_workflow_id: string | null
  project_name: string | null
  doc_name: string | null
  created_at: string | null
}

const client = axios.create({
  baseURL: '/api/notifications',
  withCredentials: true,
})

export async function getNotifications(limit = 20): Promise<{ notifications: NotificationItem[]; unread_count: number }> {
  const response = await client.get('', { params: { limit } })
  return response.data
}

export async function getUnreadCount(): Promise<number> {
  const response = await client.get('/unread-count')
  return (response.data as { count: number }).count
}

export async function markAsRead(notificationId: string): Promise<void> {
  await client.post(`/${notificationId}/read`)
}

export async function markAllAsRead(): Promise<void> {
  await client.post('/read-all')
}
```

---

### File 14 — `frontend/src/components/NotificationBell.tsx` (NEW)

```tsx
import React, { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/router'
import {
  getNotifications,
  getUnreadCount,
  markAllAsRead,
  markAsRead,
  type NotificationItem,
} from '@/services/notifications'

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} minute${mins > 1 ? 's' : ''} ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs} hour${hrs > 1 ? 's' : ''} ago`
  return `${Math.floor(hrs / 24)} day${Math.floor(hrs / 24) > 1 ? 's' : ''} ago`
}

export default function NotificationBell() {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<NotificationItem[]>([])
  const [unread, setUnread] = useState(0)
  const ref = useRef<HTMLDivElement>(null)

  const load = async () => {
    try {
      const { notifications, unread_count } = await getNotifications(20)
      setItems(notifications)
      setUnread(unread_count)
    } catch {
      // silent — not authenticated yet
    }
  }

  useEffect(() => {
    void load()
    const interval = setInterval(() => void load(), 30000)
    return () => clearInterval(interval)
  }, [])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleMarkAll = async () => {
    await markAllAsRead()
    setUnread(0)
    setItems((prev) => prev.map((n) => ({ ...n, is_read: true })))
  }

  const handleItemClick = async (item: NotificationItem) => {
    if (!item.is_read) {
      await markAsRead(item.notification_id)
      setItems((prev) =>
        prev.map((n) =>
          n.notification_id === item.notification_id ? { ...n, is_read: true } : n
        )
      )
      setUnread((c) => Math.max(0, c - 1))
    }
    if (item.related_workflow_id) {
      void router.push('/approvals')
    }
    setOpen(false)
  }

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        type="button"
        className="btn btn-link nav-link position-relative p-0 me-3"
        onClick={() => setOpen((o) => !o)}
        aria-label="Notifications"
        style={{ color: 'rgba(255,255,255,0.75)' }}
      >
        🔔
        {unread > 0 && (
          <span
            className="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger"
            style={{ fontSize: '0.65rem' }}
          >
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          className="card shadow"
          style={{
            position: 'absolute',
            right: 0,
            top: '2rem',
            width: '360px',
            maxHeight: '480px',
            overflowY: 'auto',
            zIndex: 1050,
          }}
        >
          <div className="card-header d-flex justify-content-between align-items-center py-2">
            <strong>Notifications</strong>
            {unread > 0 && (
              <button
                type="button"
                className="btn btn-link btn-sm p-0 text-muted"
                onClick={() => void handleMarkAll()}
              >
                Mark all as read
              </button>
            )}
          </div>

          {items.length === 0 ? (
            <div className="card-body text-muted small text-center py-4">No notifications</div>
          ) : (
            <ul className="list-group list-group-flush">
              {items.map((item) => (
                <li
                  key={item.notification_id}
                  className={`list-group-item list-group-item-action ${!item.is_read ? 'fw-bold' : ''}`}
                  style={{ cursor: 'pointer', backgroundColor: item.is_read ? '' : '#f0f7ff' }}
                  onClick={() => void handleItemClick(item)}
                >
                  <div className="d-flex justify-content-between">
                    <span className="small">{item.title}</span>
                    <span className="text-muted" style={{ fontSize: '0.7rem', whiteSpace: 'nowrap' }}>
                      {timeAgo(item.created_at)}
                    </span>
                  </div>
                  <div className="text-muted small" style={{ fontSize: '0.8rem' }}>
                    {(item.message || '').length > 80
                      ? `${item.message.slice(0, 80)}…`
                      : item.message}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
```

---

### File 15 — `frontend/src/components/Layout.tsx` (COMPLETE REPLACEMENT)

```tsx
/**
 * Main Layout Component
 */
import React from 'react'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/router'
import 'bootstrap/dist/css/bootstrap.min.css'
import styles from '@/styles/layout.module.css'
import { getCurrentUser, logout } from '@/services/auth'
import NotificationBell from '@/components/NotificationBell'

interface LayoutProps {
  children: React.ReactNode
}

export function Layout({ children }: LayoutProps) {
  const router = useRouter()
  const [isAuthenticated, setIsAuthenticated] = useState(false)

  useEffect(() => {
    const bootstrap = async () => {
      const user = await getCurrentUser()
      setIsAuthenticated(user !== null)
    }
    void bootstrap()
  }, [router.pathname])

  const handleLogout = async () => {
    await logout()
    router.push('/login')
  }

  return (
    <div className={styles.layout}>
      {isAuthenticated && (
        <nav className={`${styles.navbar} navbar navbar-expand-lg navbar-dark bg-dark`}>
          <div className="container-fluid">
            <Link href="/" className="navbar-brand">
              AI BA Agent
            </Link>
            <div className="collapse navbar-collapse">
              <ul className="navbar-nav ms-auto align-items-center">
                <li className="nav-item">
                  <Link href="/projects" className="nav-link">
                    Projects
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/documents" className="nav-link">
                    Documents
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/approvals" className="nav-link">
                    Approvals
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/knowledge-base" className="nav-link">
                    Knowledge Base
                  </Link>
                </li>
                <li className="nav-item d-flex align-items-center">
                  <NotificationBell />
                </li>
                <li className="nav-item">
                  <button
                    className="nav-link btn btn-link"
                    onClick={handleLogout}
                  >
                    Logout
                  </button>
                </li>
              </ul>
            </div>
          </div>
        </nav>
      )}

      
```


## License: unknown
https://github.com/RakanAji/SMARTPLANTMONITORING_KELOMPOK6/blob/ebf90229ddf582f567c06fafa486befebe2eab2d/src/components/Header.js

```
I now have a complete picture of the codebase. I'm in Ask mode so I cannot write files directly — I'll provide the complete, implementation-ready code for every file to create or modify. Apply them in order.

---

## Implementation

### File 1 — `infra/migrations/005_add_notifications.sql` (NEW)

```sql
-- 005: In-app notifications table
CREATE TABLE IF NOT EXISTS notifications (
  notification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(user_id),
  title VARCHAR(255) NOT NULL,
  message TEXT NOT NULL,
  type VARCHAR(50) NOT NULL DEFAULT 'info',
  is_read BOOLEAN DEFAULT false,
  related_doc_id UUID REFERENCES documents(doc_id),
  related_workflow_id UUID REFERENCES approval_workflows(workflow_id),
  project_name VARCHAR(255),
  doc_name VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_is_read  ON notifications(is_read);
```

---

### File 2 — `infra/migrations/006_add_workflow_roles.sql` (NEW)

```sql
-- 006: Per-workflow dynamic role assignment + submitter tracking
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS step_1_role   VARCHAR(50);
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS step_2_role   VARCHAR(50);
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS submitter_id  UUID REFERENCES users(user_id);
```

---

### File 3 — `backend/app/services/notifications.py` (NEW)

```python
"""DB-backed in-app notification service (distinct from notification.py which is Telegram)."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def create_notification(
    *,
    db: Session,
    user_id: UUID,
    title: str,
    message: str,
    notif_type: str = "info",
    doc_id: Optional[UUID] = None,
    workflow_id: Optional[UUID] = None,
    project_name: str = "",
    doc_name: str = "",
) -> Optional[str]:
    """Insert a notification row. Returns notification_id or None on failure."""
    try:
        nid = str(uuid4())
        db.execute(
            text(
                """
                INSERT INTO notifications
                    (notification_id, user_id, title, message, type, is_read,
                     related_doc_id, related_workflow_id, project_name, doc_name, created_at)
                VALUES
                    (:nid, :uid, :title, :msg, :type, false,
                     :doc_id, :wf_id, :pname, :dname, :ts)
                """
            ),
            {
                "nid": nid,
                "uid": str(user_id),
                "title": title,
                "msg": message,
                "type": notif_type,
                "doc_id": str(doc_id) if doc_id else None,
                "wf_id": str(workflow_id) if workflow_id else None,
                "pname": project_name,
                "dname": doc_name,
                "ts": datetime.utcnow(),
            },
        )
        return nid
    except Exception as exc:
        logger.error("create_notification failed: %s", exc)
        return None


def get_user_notifications(
    *, db: Session, user_id: UUID, limit: int = 20
) -> List[Dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT notification_id, title, message, type, is_read,
                   related_doc_id, related_workflow_id,
                   project_name, doc_name, created_at
            FROM notifications
            WHERE user_id = :uid
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"uid": str(user_id), "limit": limit},
    ).fetchall()
    return [
        {
            "notification_id": str(r[0]),
            "title": r[1],
            "message": r[2],
            "type": r[3],
            "is_read": bool(r[4]),
            "related_doc_id": str(r[5]) if r[5] else None,
            "related_workflow_id": str(r[6]) if r[6] else None,
            "project_name": r[7],
            "doc_name": r[8],
            "created_at": r[9].isoformat() if r[9] else None,
        }
        for r in rows
    ]


def mark_as_read(*, db: Session, notification_id: UUID, user_id: UUID) -> bool:
    result = db.execute(
        text(
            """
            UPDATE notifications
            SET is_read = true
            WHERE notification_id = :nid AND user_id = :uid
            """
        ),
        {"nid": str(notification_id), "uid": str(user_id)},
    )
    return (result.rowcount or 0) > 0


def mark_all_as_read(*, db: Session, user_id: UUID) -> int:
    result = db.execute(
        text(
            "UPDATE notifications SET is_read = true WHERE user_id = :uid AND is_read = false"
        ),
        {"uid": str(user_id)},
    )
    return result.rowcount or 0


def get_unread_count(*, db: Session, user_id: UUID) -> int:
    row = db.execute(
        text(
            "SELECT COUNT(*) FROM notifications WHERE user_id = :uid AND is_read = false"
        ),
        {"uid": str(user_id)},
    ).fetchone()
    return int(row[0] or 0)


def get_role_user_ids(
    *, db: Session, project_id: UUID, role: str
) -> List[str]:
    """Return user_ids that have the given role (system-wide or project-scoped)."""
    rows = db.execute(
        text(
            """
            SELECT DISTINCT u.user_id
            FROM users u
            LEFT JOIN user_projects up
                ON up.user_id = u.user_id AND up.project_id = :pid
            WHERE u.role = :role OR up.role = :role
            LIMIT 20
            """
        ),
        {"pid": str(project_id), "role": role},
    ).fetchall()
    return [str(r[0]) for r in rows]
```

---

### File 4 — `backend/app/services/workflow.py` (COMPLETE REPLACEMENT)

```python
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


# Fallback static step roles — used when a workflow pre-dates dynamic assignment
APPROVAL_STEPS = {
    1: "business_owner",
    2: "admin",
}


def _resolve_dynamic_roles(submitter_role: str) -> Tuple[str, str]:
    """Return (step_1_role, step_2_role) based on the submitter's role."""
    if submitter_role == "business_owner":
        return ("ba", "business_owner")
    if submitter_role in ("ba", "pm"):
        return ("business_owner", "ba")
    # tech_lead, legal, finance, viewer → default
    return ("business_owner", "admin")


def _get_expected_role(wf: Dict[str, Any]) -> str:
    """Return the role required for the current workflow step."""
    if wf["current_step"] == 1:
        return wf.get("step_1_role") or APPROVAL_STEPS.get(1, "business_owner")
    return wf.get("step_2_role") or APPROVAL_STEPS.get(2, "admin")


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
    step_1_role, step_2_role = _resolve_dynamic_roles(submitter_role)
    total_steps = len(APPROVAL_STEPS)

    if submitter_role == "admin":
        initial_status = "approved"
        doc_status = "approved"
    else:
        initial_status = "pending"
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
    step_2 = row[8] or APPROVAL_STEPS.get(2, "admin")

    return {
        "workflow_id": str(row[0]),
        "doc_id": str(row[1]),
        "project_id": str(row[2]),
        "current_step": int(row[3] or 1),
        "total_steps": len(APPROVAL_STEPS),
        "status": str(row[5] or "in_progress"),
        "version_id": str(row[6]) if row[6] else None,
        "step_1_role": step_1,
        "step_2_role": step_2,
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

    next_step = completed_step + 1
    final_step = len(APPROVAL_STEPS)
    new_status = "approved" if next_step > final_step else "in_progress"
    new_doc_status = "approved" if new_status == "approved" else "pending_approval"

    step_roles = {1: wf.get("step_1_role"), 2: wf.get("step_2_role")}
    next_required_role = step_roles.get(next_step) or APPROVAL_STEPS.get(next_step)

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
            SET current_step = :current_step,
                status       = :status,
                version_id   = :version_id,
                updated_at   = :updated_at
            WHERE workflow_id = :workflow_id
            """
        ),
        {
            "current_step": min(next_step, final_step),
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

    log_audit_event(
        db=db,
        project_id=UUID(wf["project_id"]),
        action="APPROVAL_APPROVED",
        entity_type="approval",
        entity_id=workflow_id,
        user_id=actor_user_id,
        old_values={"status": wf["status"], "current_step": completed_step},
        new_values={
            "status": new_status,
            "current_step": min(next_step, final_step),
            "version_id": str(version_id),
        },
        succeeded=True,
    )

    return {
        "workflow_id": wf["workflow_id"],
        "decision_id": str(decision_id),
        "status": new_status,
        "completed_step": completed_step,
        "current_step": min(next_step, final_step),
        "next_required_role": None if new_status == "approved" else next_required_role,
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
        reason=(
            f"Rejection at step {wf['current_step']}: {reason}"
            if reason
            else f"Rejection at step {wf['current_step']}"
        ),
        project_id=UUID(wf["project_id"]),
        workflow_id=workflow_id,
        db=db,
    )

    db.execute(
        text(
            """
            UPDATE approval_workflows
            SET status     = 'rejected',
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
    """Return a document for revision.

    Step 1 → sets status = returned_to_submitter, doc status = returned
    Step 2 → sets status = returned_to_step1, resets to step 1
    """
    wf = get_workflow(workflow_id, db)
    if wf is None:
        raise ValueError("Approval workflow not found")

    if wf["status"] in {"approved", "rejected"}:
        raise ValueError(f"Workflow already closed with status={wf['status']}")

    expected_role = _get_expected_role(wf)
    if actor_role != expected_role and actor_role != "admin":
        raise PermissionError(f"Current step requires role '{expected_role}'")

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
            "step_number": wf["current_step"],
            "approver_id": str(actor_user_id),
            "comments": comment,
            "created_at": now,
        },
    )

    from_step = wf["current_step"]
    if from_step == 1:
        new_wf_status = "returned_to_submitter"
        new_doc_status = "returned"
        audit_action = "APPROVAL_RETURNED_TO_SUBMITTER"
    else:
        new_wf_status = "returned_to_step1"
        new_doc_status = "pending_approval"
        audit_action = "APPROVAL_RETURNED_TO_STEP1"

    version_id = create_document_version(
        doc_id=UUID(wf["doc_id"]),
        created_by=actor_user_id,
        approval_status=new_wf_status,
        reason=f"Returned at step {from_step}: {comment}",
        project_id=UUID(wf["project_id"]),
        workflow_id=workflow_id,
        db=db,
    )

    db.execute(
        text(
            """
            UPDATE approval_workflows
            SET status       = :status,
                current_step = 1,
                version_id   = :version_id,
                updated_at   = :updated_at
            WHERE workflow_id = :workflow_id
            """
        ),
        {
            "status": new_wf_status,
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
        old_values={"status": wf["status"], "current_step": from_step},
        new_values={"status": new_wf_status, "comment": comment, "version_id": str(version_id)},
        succeeded=True,
    )

    return {
        "workflow_id": wf["workflow_id"],
        "decision_id": str(decision_id),
        "status": new_wf_status,
        "current_step": 1,
        "previous_step": from_step,
        "comment": comment,
        "version_id": str(version_id),
        "submitter_id": wf.get("submitter_id"),
        "step_1_role": wf.get("step_1_role"),
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
                (workflow_id, doc_id, project_id, current_step, total_steps, status,
                 submitter_id, created_at, updated_at)
            VALUES
                (:workflow_id, :doc_id, :project_id, 1, :total_steps,
                 'human_review_required', :submitter_id, :created_at, :updated_at)
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
        new_values={
            "status": "human_review_required",
            "doc_id": str(doc_id),
            "total_steps": len(APPROVAL_STEPS),
        },
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
        {"version_id": str(version_id), "updated_at": now, "workflow_id": str(workflow_id)},
    )
    db.execute(
        text(
            "UPDATE documents SET status = 'human_review_required', updated_at = :t WHERE doc_id = :id"
        ),
        {"t": now, "id": str(doc_id)},
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
                (version_id, doc_id, version_number, content, content_hash,
                 created_by, approval_status, created_at)
            VALUES
                (:version_id, :doc_id, :version_number, :content, :content_hash,
                 :created_by, :approval_status, :created_at)
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
```

---

### File 5 — `backend/app/services/google_drive.py` — append at bottom

Add these three functions to the end of the existing [google_drive.py](backend/app/services/google_drive.py):

```python
import re as _re

_MIME_EDIT_URLS = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        "https://docs.google.com/document/d/{id}/edit",
    "application/msword":
        "https://docs.google.com/document/d/{id}/edit",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
    "application/vnd.ms-excel":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
    "text/csv":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
}


def get_drive_file_id(drive_url: str) -> Optional[str]:
    """Extract the Drive file ID from a webViewLink URL."""
    match = _re.search(r"/(?:file/)?d/([a-zA-Z0-9_-]+)", drive_url or "")
    return match.group(1) if match else None


def get_edit_url(file_id: str, mime_type: str) -> str:
    """Return the correct Google Drive / Docs / Sheets URL for the given MIME type."""
    template = _MIME_EDIT_URLS.get(mime_type)
    if template:
        return template.format(id=file_id)
    return f"https://drive.google.com/file/d/{file_id}/view"


def register_file_watch(file_id: str, document_id: str) -> bool:
    """Register a Google Drive push-notification watch (requires verified HTTPS endpoint).

    This stub logs the intent.  In production, call files().watch() with your
    verified webhook URL and store the channel/resource IDs for later expiry renewal.
    """
    logger.info(
        "register_file_watch: file_id=%s doc_id=%s (stub – HTTPS endpoint required)",
        file_id,
        document_id,
    )
    return False
```

---

### File 6 — `backend/app/middleware/rbac.py` — append one line after `require_approver`

Add after `require_approver = ...`:

```python
# Broader reviewer set: includes BA and PM (needed for dynamic step approver assignment)
require_reviewer = make_require_role(["admin", "business_owner", "ba", "pm", "legal"])
```

---

### File 7 — `backend/app/routers/approvals.py` (COMPLETE REPLACEMENT)

```python
"""Approval workflow endpoints."""

from __future__ import annotations

import logging
import os as _os
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_ba, require_readonly, require_reviewer
from app.services.db_service import get_db
from app.services import google_sheets
from app.services import notifications as notif_svc
from app.services.workflow import (
    APPROVAL_STEPS,
    approve_step,
    create_approval_workflow,
    get_workflow,
    reject_step,
    return_step,
    trigger_hitl,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Statuses considered "active / pending" for the dashboard
_PENDING_STATUSES = (
    "in_progress",
    "human_review_required",
    "returned_to_submitter",
    "returned_to_step1",
)
_COMPLETED_STATUSES = ("approved", "rejected")


class ApprovalActionRequest(BaseModel):
    comment: str = ""


class ReturnRequest(BaseModel):
    comment: str = Field(min_length=1)


class CreateApprovalRequest(BaseModel):
    document_id: UUID
    project_id: UUID
    workflow_type: str = "approval"


class RejectionRequest(BaseModel):
    reason: str = Field(min_length=1)


class HitlTriggerRequest(BaseModel):
    document_id: UUID
    project_id: Optional[UUID] = None
    reason: str = Field(min_length=1)
    risk_flags: Dict[str, Any] = {}


# ─── helpers ─────────────────────────────────────────────────────────────────

def _get_doc_project_info(workflow_id: UUID, db: Session):
    """Return (doc_title, project_name, submitter_id) for a workflow."""
    return db.execute(
        text(
            """
            SELECT d.title, p.name, aw.submitter_id
            FROM approval_workflows aw
            JOIN documents d ON d.doc_id = aw.doc_id
            JOIN projects p ON p.project_id = aw.project_id
            WHERE aw.workflow_id = :wid
            """
        ),
        {"wid": str(workflow_id)},
    ).fetchone()


def _status_badge_color(status: str) -> str:
    colors = {
        "in_progress": "info",
        "approved": "success",
        "rejected": "danger",
        "returned_to_submitter": "warning",
        "returned_to_step1": "warning",
        "human_review_required": "secondary",
    }
    return colors.get(status, "secondary")


# ─── endpoints ───────────────────────────────────────────────────────────────

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
            submitter_role=current_user.role,
            db=db,
        )
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"create_workflow_failed: {exc}")


@router.get("")
async def list_approvals(
    project_id: UUID,
    status: str = Query("pending"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """List approvals by status for dashboard views."""
    normalized = status.lower()
    if normalized not in {"pending", "completed", "all"}:
        raise HTTPException(status_code=400, detail="status must be pending, completed, or all")

    pending_in = ", ".join(f"'{s}'" for s in _PENDING_STATUSES)
    completed_in = ", ".join(f"'{s}'" for s in _COMPLETED_STATUSES)

    if normalized == "pending":
        status_filter = f"aw.status IN ({pending_in})"
    elif normalized == "completed":
        status_filter = f"aw.status IN ({completed_in})"
    else:
        status_filter = f"aw.status IN ({pending_in}, {completed_in})"

    offset = (page - 1) * page_size

    rows = db.execute(
        text(
            f"""
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
                    d.doc_type,
                    p.name AS project_name,
                    COALESCE(u.full_name, u.email, '') AS submitter_name,
                    u.role AS submitter_role,
                    aw.step_1_role,
                    aw.step_2_role,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                LEFT JOIN documents d ON d.doc_id = aw.doc_id
                LEFT JOIN projects p ON p.project_id = aw.project_id
                LEFT JOIN users u ON u.user_id = aw.submitter_id
                WHERE aw.project_id = :project_id
                  AND {status_filter}
            )
            SELECT workflow_id, doc_id, doc_title, current_step, total_steps, status,
                   updated_at, google_drive_link, doc_type, project_name,
                   submitter_name, submitter_role, step_1_role, step_2_role
            FROM ranked
            WHERE rn = 1
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"project_id": str(project_id), "limit": page_size, "offset": offset},
    ).fetchall()

    count_row = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT aw.doc_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                WHERE aw.project_id = :project_id AND {status_filter}
            )
            SELECT COUNT(*) FROM ranked WHERE rn = 1
            """
        ),
        {"project_id": str(project_id)},
    ).fetchone()

    items = [
        {
            "workflow_id": str(r[0]),
            "doc_id": str(r[1]),
            "doc_title": r[2] or None,
            "current_step": int(r[3] or 1),
            "total_steps": len(APPROVAL_STEPS),
            "status": r[5],
            "status_color": _status_badge_color(r[5]),
            "updated_at": r[6].isoformat() if r[6] else None,
            "google_drive_link": r[7] or None,
            "doc_type": r[8] or None,
            "project_name": r[9] or None,
            "submitter_name": r[10] or None,
            "submitter_role": r[11] or None,
            "step_1_role": r[12] or None,
            "step_2_role": r[13] or None,
        }
        for r in rows
    ]

    return {
        "project_id": str(project_id),
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
    pending_in = ", ".join(f"'{s}'" for s in _PENDING_STATUSES)
    offset = (page - 1) * page_size

    rows = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT
                    aw.workflow_id, aw.doc_id,
                    COALESCE(d.title, '') AS doc_title,
                    aw.current_step, aw.total_steps, aw.status, aw.updated_at,
                    d.google_drive_link, d.doc_type, p.name AS project_name,
                    COALESCE(u.full_name, u.email, '') AS submitter_name,
                    u.role AS submitter_role, aw.step_1_role, aw.step_2_role,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                LEFT JOIN documents d ON d.doc_id = aw.doc_id
                LEFT JOIN projects p ON p.project_id = aw.project_id
                LEFT JOIN users u ON u.user_id = aw.submitter_id
                WHERE aw.project_id = :project_id
                  AND aw.status IN ({pending_in})
            )
            SELECT workflow_id, doc_id, doc_title, current_step, total_steps, status,
                   updated_at, google_drive_link, doc_type, project_name,
                   submitter_name, submitter_role, step_1_role, step_2_role
            FROM ranked
            WHERE rn = 1
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"project_id": str(project_id), "limit": page_size, "offset": offset},
    ).fetchall()

    count_row = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT aw.doc_id,
                    ROW_NUMBER() OVER (PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC) AS rn
                FROM approval_workflows aw
                WHERE aw.project_id = :project_id
                  AND aw.status IN ({pending_in})
            )
            SELECT COUNT(*) FROM ranked WHERE rn = 1
            """
        ),
        {"project_id": str(project_id)},
    ).fetchone()

    items = [
        {
            "workflow_id": str(r[0]),
            "doc_id": str(r[1]),
            "doc_title": r[2] or None,
            "current_step": int(r[3] or 1),
            "total_steps": len(APPROVAL_STEPS),
            "status": r[5],
            "status_color": _status_badge_color(r[5]),
            "updated_at": r[6].isoformat() if r[6] else None,
            "google_drive_link": r[7] or None,
            "doc_type": r[8] or None,
            "project_name": r[9] or None,
            "submitter_name": r[10] or None,
            "submitter_role": r[11] or None,
            "step_1_role": r[12] or None,
            "step_2_role": r[13] or None,
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
    current_user: TokenUser = Depends(require_reviewer),
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

    # ── Google Sheets update (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            google_sheets.update_approval_row(
                project_name=info[1] or "",
                file_name=_os.path.splitext(info[0] or "")[0],
                approver_name=current_user.email,
                status="Approved",
                comment=request.comment,
            )
    except Exception as exc:
        logger.warning("Sheets update failed after approve (%s): %s", workflow_id, exc)

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            completed_step = result.get("completed_step", 1)
            final_approved = result["status"] == "approved"

            if submitter_id:
                title = "Document Approved ✅" if final_approved else "Document Progressed"
                if final_approved:
                    msg = f"Project {project_name}: '{doc_title}' has been fully approved!"
                else:
                    msg = f"Project {project_name}: '{doc_title}' passed step {completed_step} review."
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title=title,
                    message=msg,
                    notif_type="approved",
                    doc_id=UUID(result["workflow_id"]) if False else None,
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()
    except Exception as exc:
        logger.warning("Notification failed after approve (%s): %s", workflow_id, exc)

    return result


@router.post("/{workflow_id}/reject")
async def reject_document(
    workflow_id: UUID,
    request: RejectionRequest,
    current_user: TokenUser = Depends(require_reviewer),
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

    # ── Google Sheets update (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            google_sheets.update_approval_row(
                project_name=info[1] or "",
                file_name=_os.path.splitext(info[0] or "")[0],
                approver_name=current_user.email,
                status="Rejected",
                comment=request.reason,
            )
    except Exception as exc:
        logger.warning("Sheets update failed after reject (%s): %s", workflow_id, exc)

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            if submitter_id:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title="Document Rejected",
                    message=f"Project {project_name}: '{doc_title}' was rejected. Reason: {request.reason}",
                    notif_type="rejected",
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()
    except Exception as exc:
        logger.warning("Notification failed after reject (%s): %s", workflow_id, exc)

    return result


@router.post("/{workflow_id}/return")
async def return_document(
    workflow_id: UUID,
    request: ReturnRequest,
    current_user: TokenUser = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    """Return a document for revision.

    Step 1 → returned_to_submitter (document status = returned)
    Step 2 → returned_to_step1 (resets to step 1)
    """
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

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            new_status = result["status"]

            if new_status == "returned_to_submitter" and submitter_id:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title="Document Returned",
                    message=(
                        f"Project {project_name}: '{doc_title}' has been returned "
                        f"for revision. Comment: {request.comment}"
                    ),
                    notif_type="returned",
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()

            elif new_status == "returned_to_step1":
                step_1_role = result.get("step_1_role") or "business_owner"
                wf_row = db.execute(
                    text("SELECT project_id FROM approval_workflows WHERE workflow_id = :wid"),
                    {"wid": str(workflow_id)},
                ).fetchone()
                if wf_row:
                    approver_ids = notif_svc.get_role_user_ids(
                        db=db,
                        project_id=UUID(str(wf_row[0])),
                        role=step_1_role,
                    )
                    for uid_str in approver_ids:
                        notif_svc.create_notification(
                            db=db,
                            user_id=UUID(uid_str),
                            title="Re-review Required",
                            message=(
                                f"Project {project_name}: '{doc_title}' has been "
                                f"returned to you for re-review. Comment: {request.comment}"
                            ),
                            notif_type="returned_to_step1",
                            workflow_id=workflow_id,
                            project_name=project_name or "",
                            doc_name=doc_title or "",
                        )
                    db.commit()
    except Exception as exc:
        logger.warning("Notification failed after return (%s): %s", workflow_id, exc)

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
        "status_color": _status_badge_color(workflow["status"]),
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
```

---

### File 8 — `backend/app/routers/documents.py` (COMPLETE REPLACEMENT)

```python
"""
Document management endpoints.

POST /upload            – Accept file + metadata, store to DB, upload to Drive, trigger pipeline
POST /{doc_id}/resubmit – Resubmit a returned document for re-review
GET  /{doc_id}/status   – Return current processing status + progress
"""
import hashlib
import logging
import mimetypes
import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile, File
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_ba, require_readonly
from app.services.db_service import get_db
from app.services import google_drive, google_sheets, elevenlabs, n8n_webhook
from app.services import notifications as notif_svc
from app.services.workflow import _resolve_dynamic_roles

logger = logging.getLogger(__name__)
router = APIRouter()

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
    project_folder_id: Optional[str] = None,
) -> None:
    """Background task: upload to Google Drive, trigger STT + n8n, update status."""
    db: Session = next(get_db())
    try:
        db.execute(
            text("UPDATE documents SET status = :s, updated_at = :t WHERE doc_id = :id"),
            {"s": STATUS_PROCESSING, "t": datetime.utcnow(), "id": doc_id},
        )
        db.commit()

        drive_url: Optional[str] = google_drive.upload_file(
            file_bytes, filename, mime_type, project_folder_id
        )
        if drive_url:
            db.execute(
                text(
                    "UPDATE documents SET google_drive_link = :url, updated_at = :t WHERE doc_id = :id"
                ),
                {"url": drive_url, "t": datetime.utcnow(), "id": doc_id},
            )
            db.commit()

        transcript: Optional[str] = None
        if elevenlabs.is_audio(mime_type):
            transcript = await elevenlabs.transcribe(file_bytes, filename, mime_type)
            if transcript:
                version_id = str(uuid.uuid4())
                db.execute(
                    text(
                        """INSERT INTO document_versions
                             (version_id, doc_id, version_number, content, approval_status, created_at)
                           VALUES (:vid, :did, 1, :content, 'pending', :ts)"""
                    ),
                    {
                        "vid": version_id,
                        "did": doc_id,
                        "content": transcript,
                        "ts": datetime.utcnow(),
                    },
                )
                db.commit()

        await n8n_webhook.trigger_document_workflow(
            workflow_id=workflow_id,
            document_id=doc_id,
            google_drive_url=drive_url,
            file_type=mime_type,
            filename=filename,
        )

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
    current_user: TokenUser = Depends(require_ba),
    db: Session = Depends(get_db),
):
    """
    Upload a document for processing.

    - Requires role: ba / pm / tech_lead / admin  (HTTP 403 otherwise)
    - Returns: {document_id, workflow_id, status: "PENDING"}
    """
    mime_type: str = file.content_type or ""
    if not mime_type or mime_type == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(file.filename or "")
        mime_type = guessed or "application/octet-stream"

    doc_title  = title or (file.filename or "Untitled")
    doc_id     = str(uuid.uuid4())
    workflow_id = str(uuid.uuid4())

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # ── 1. Insert document record ─────────────────────────────────────────
    try:
        db.execute(
            text(
                """INSERT INTO documents
                     (doc_id, project_id, title, doc_type, status, created_by, created_at, updated_at)
                   VALUES (:doc_id, :project_id, :title, :doc_type, :status, :created_by, :now, :now)"""
            ),
            {
                "doc_id":     doc_id,
                "project_id": project_id,
                "title":      doc_title,
                "doc_type":   mime_type,
                "status":     STATUS_PENDING,
                "created_by": current_user.user_id,
                "now":        datetime.utcnow(),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to insert document record: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to store document metadata")

    # ── 2. Determine dynamic roles ────────────────────────────────────────
    step_1_role, step_2_role = _resolve_dynamic_roles(current_user.role)
    auto_approve = current_user.role == "admin"
    initial_wf_status = "approved" if auto_approve else "in_progress"

    # ── 3. Create approval_workflow entry ─────────────────────────────────
    try:
        db.execute(
            text(
                """INSERT INTO approval_workflows
                     (workflow_id, doc_id, project_id, status, current_step, total_steps,
                      step_1_role, step_2_role, submitter_id, created_at, updated_at)
                   VALUES
                     (:wid, :did, :pid, :status, 1, 2,
                      :step_1_role, :step_2_role, :submitter_id, :now, :now)"""
            ),
            {
                "wid":          workflow_id,
                "did":          doc_id,
                "pid":          project_id,
                "status":       initial_wf_status,
                "step_1_role":  step_1_role,
                "step_2_role":  step_2_role,
                "submitter_id": str(current_user.user_id),
                "now":          datetime.utcnow(),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to create approval workflow entry: %s", exc)

    # ── 4. Fetch project Drive folder ─────────────────────────────────────
    project_folder_id: Optional[str] = None
    project_name: str = ""
    try:
        proj_row = db.execute(
            text("SELECT name, google_drive_folder_id FROM projects WHERE project_id = :pid"),
            {"pid": project_id},
        ).fetchone()
        if proj_row:
            project_name     = proj_row[0] or ""
            project_folder_id = proj_row[1] or None
            if project_folder_id is None:
                project_folder_id = google_drive.create_project_folder(project_name)
                if project_folder_id:
                    db.execute(
                        text(
                            "UPDATE projects SET google_drive_folder_id = :fid WHERE project_id = :pid"
                        ),
                        {"fid": project_folder_id, "pid": project_id},
                    )
                    db.commit()
    except Exception as exc:
        logger.warning("Could not fetch project Drive folder for %s: %s", project_id, exc)

    # ── 5. Append row to Google Sheets backlog (best-effort) ──────────────
    try:
        import os as _os
        file_name_no_ext = _os.path.splitext(doc_title)[0]
        google_sheets.append_upload_row(
            user_name=current_user.email,
            project_name=project_name,
            file_name=file_name_no_ext,
            upload_date=datetime.utcnow().strftime("%d-%b-%Y"),
        )
    except Exception as exc:
        logger.warning("Sheets append_upload_row failed for %s: %s", doc_id, exc)

    # ── 6. Notify step-1 approvers (best-effort) ──────────────────────────
    try:
        approver_ids = notif_svc.get_role_user_ids(
            db=db, project_id=UUID(project_id), role=step_1_role
        )
        for uid_str in approver_ids:
            notif_svc.create_notification(
                db=db,
                user_id=UUID(uid_str),
                title="New Review Request",
                message=f"Project {project_name}: '{doc_title}' needs your review.",
                notif_type="upload",
                workflow_id=UUID(workflow_id),
                project_name=project_name,
                doc_name=doc_title,
            )
        db.commit()
    except Exception as exc:
        logger.warning("Upload notification failed for %s: %s", doc_id, exc)

    # ── 7. Queue background processing ────────────────────────────────────
    background_tasks.add_task(
        _process_document,
        doc_id,
        workflow_id,
        file_bytes,
        file.filename or doc_title,
        mime_type,
        project_folder_id,
    )

    logger.info(
        "Document %s queued for processing by %s (workflow %s)",
        doc_id, current_user.email, workflow_id,
    )
    return {
        "document_id":  doc_id,
        "workflow_id":  workflow_id,
        "filename":     file.filename,
        "status":       STATUS_PENDING,
        "uploaded_by":  current_user.email,
        "step_1_role":  step_1_role,
        "step_2_role":  step_2_role,
    }


@router.post("/{doc_id}/resubmit")
async def resubmit_document(
    doc_id: str,
    current_user: TokenUser = Depends(require_ba),
    db: Session = Depends(get_db),
):
    """Resubmit a returned document for re-review (only the original submitter or admin)."""
    doc_row = db.execute(
        text(
            "SELECT doc_id, project_id, title, status, created_by FROM documents WHERE doc_id = :did"
        ),
        {"did": doc_id},
    ).fetchone()
    if doc_row is None:
        raise HTTPException(status_code=404, detail="document_not_found")

    if current_user.role != "admin" and str(doc_row[4]) != str(current_user.user_id):
        raise HTTPException(status_code=403, detail="Only the document submitter can resubmit")

    if doc_row[3] != "returned":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not in 'returned' status (current: {doc_row[3]})",
        )

    wf_row = db.execute(
        text(
            """
            SELECT workflow_id, step_1_role, step_2_role, project_id
            FROM approval_workflows
            WHERE doc_id = :did AND status = 'returned_to_submitter'
            ORDER BY updated_at DESC LIMIT 1
            """
        ),
        {"did": doc_id},
    ).fetchone()

    now = datetime.utcnow()

    # Create new document version
    prev = db.execute(
        text(
            "SELECT version_number, content FROM document_versions WHERE doc_id = :did ORDER BY version_number DESC LIMIT 1"
        ),
        {"did": doc_id},
    ).fetchone()
    new_version_num = (int(prev[0]) + 1) if prev else 1
    content = f"{prev[1] or ''}\n\n[resubmitted by {current_user.email}]".strip() if prev else "[resubmitted]"
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    version_id = str(uuid.uuid4())

    db.execute(
        text(
            """
            INSERT INTO document_versions
                (version_id, doc_id, version_number, content, content_hash,
                 created_by, approval_status, created_at)
            VALUES (:vid, :did, :vn, :content, :hash, :uid, 'pending', :ts)
            """
        ),
        {
            "vid": version_id, "did": doc_id, "vn": new_version_num,
            "content": content, "hash": content_hash,
            "uid": str(current_user.user_id), "ts": now,
        },
    )

    db.execute(
        text("UPDATE documents SET status = 'pending_approval', updated_at = :ts WHERE doc_id = :did"),
        {"ts": now, "did": doc_id},
    )

    wf_id_str: Optional[str] = None
    step_1_role = "business_owner"
    project_id_str = str(doc_row[1])

    if wf_row:
        wf_id_str   = str(wf_row[0])
        step_1_role = wf_row[1] or "business_owner"
        db.execute(
            text(
                "UPDATE approval_workflows SET status = 'in_progress', current_step = 1, updated_at = :ts WHERE workflow_id = :wid"
            ),
            {"ts": now, "wid": wf_id_str},
        )

    db.commit()

    # Notify step-1 approvers (best-effort)
    try:
        pname_row = db.execute(
            text("SELECT name FROM projects WHERE project_id = :pid"),
            {"pid": project_id_str},
        ).fetchone()
        pname = pname_row[0] if pname_row else ""
        approver_ids = notif_svc.get_role_user_ids(
            db=db, project_id=UUID(project_id_str), role=step_1_role
        )
        for uid_str in approver_ids:
            notif_svc.create_notification(
                db=db,
                user_id=UUID(uid_str),
                title="Document Resubmitted",
                message=f"Project {pname}: '{doc_row[2]}' has been revised and resubmitted.",
                notif_type="resubmit",
                workflow_id=UUID(wf_id_str) if wf_id_str else None,
                project_name=pname,
                doc_name=doc_row[2] or "",
            )
        db.commit()
    except Exception as exc:
        logger.warning("Resubmit notification failed for %s: %s", doc_id, exc)

    return {
        "document_id":    doc_id,
        "status":         "pending_approval",
        "version_id":     version_id,
        "resubmitted_by": current_user.email,
    }


@router.get("")
async def list_documents(
    project_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """List documents with optional project filter (auth required)."""
    safe_limit  = max(1, min(limit, 200))
    safe_offset = max(0, offset)

    if project_id:
        rows = db.execute(
            text(
                """SELECT doc_id, project_id, title, doc_type, status, updated_at
                   FROM documents WHERE project_id = :pid
                   ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"""
            ),
            {"pid": project_id, "limit": safe_limit, "offset": safe_offset},
        ).fetchall()
    else:
        rows = db.execute(
            text(
                """SELECT doc_id, project_id, title, doc_type, status, updated_at
                   FROM documents
                   ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"""
            ),
            {"limit": safe_limit, "offset": safe_offset},
        ).fetchall()

    return {
        "requested_by": current_user.email,
        "project_id": project_id,
        "total": len(rows),
        "documents": [
            {
                "doc_id":     str(r[0]),
                "project_id": str(r[1]),
                "title":      r[2],
                "doc_type":   r[3],
                "status":     r[4],
                "updated_at": r[5].isoformat() if r[5] else None,
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
    """Get the current processing status of a document."""
    try:
        row = db.execute(
            text(
                "SELECT doc_id, title, status, doc_type, google_drive_link, updated_at FROM documents WHERE doc_id = :id"
            ),
            {"id": doc_id},
        ).fetchone()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"db_error: {exc}")

    if row is None:
        raise HTTPException(status_code=404, detail="document_not_found")

    status = row[2]
    progress_map = {
        STATUS_PENDING:    10,
        STATUS_PROCESSING: 50,
        STATUS_COMPLETED:  100,
        STATUS_FAILED:     0,
    }

    # Build edit URL if Drive link exists
    edit_url: Optional[str] = None
    drive_link = row[4]
    if drive_link:
        file_id = google_drive.get_drive_file_id(drive_link)
        if file_id:
            edit_url = google_drive.get_edit_url(file_id, row[3] or "")

    return {
        "document_id":      str(row[0]),
        "title":            row[1],
        "status":           status,
        "progress":         progress_map.get(status, 0),
        "doc_type":         row[3],
        "google_drive_url": drive_link,
        "edit_url":         edit_url,
        "updated_at":       row[5].isoformat() if row[5] else None,
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
                "version_id":       str(r[0]),
                "version_number":   int(r[1]),
                "content_hash":     r[2],
                "approval_status":  r[3],
                "created_by":       str(r[4]) if r[4] else None,
                "created_at":       r[5].isoformat() if r[5] else None,
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
            SELECT version_id, version_number, content, content_hash, approval_status, created_by, created_at
            FROM document_versions
            WHERE doc_id = :doc_id AND version_id = :version_id
            """
        ),
        {"doc_id": doc_id, "version_id": version_id},
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="version_not_found")

    return {
        "version_id":       str(row[0]),
        "version_number":   int(row[1]),
        "content":          row[2],
        "content_hash":     row[3],
        "approval_status":  row[4],
        "created_by":       str(row[5]) if row[5] else None,
        "created_at":       row[6].isoformat() if row[6] else None,
    }
```

---

### File 9 — `backend/app/routers/notifications.py` (COMPLETE REPLACEMENT)

```python
"""Notification endpoints — Telegram + in-app DB notifications."""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_admin, require_readonly
from app.services.db_service import get_db
from app.services.notification import notification_service
from app.services.telegram_bot import telegram_bot_service
from app.services import notifications as notif_svc

router = APIRouter()


class NotificationSendRequest(BaseModel):
    message: str = Field(min_length=1)
    type: str = "info"
    project_id: Optional[UUID] = None
    metadata: Dict[str, Any] = {}


class TelegramUpdateRequest(BaseModel):
    update_id: Optional[int] = None
    message: Dict[str, Any] = {}


# ─── Telegram endpoints (unchanged) ──────────────────────────────────────────

@router.post("/send")
async def send_notification(
    request: NotificationSendRequest,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Send a notification through the configured Telegram bot."""
    result = await notification_service.dispatch_notification(
        db=db,
        message=request.message,
        notification_type=request.type,
        actor_user_id=UUID(str(current_user.user_id)),
        project_id=request.project_id,
        metadata=request.metadata,
    )
    db.commit()
    return result


@router.post("/telegram/webhook")
async def telegram_webhook(
    payload: TelegramUpdateRequest,
    db: Session = Depends(get_db),
):
    """Receive Telegram updates and reply to /status, /backlog, /help."""
    message = payload.message or {}
    command_text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id")) if chat.get("id") is not None else None

    if not command_text.startswith("/"):
        return {"ok": True, "handled": False}

    reply_text = notification_service.process_telegram_command(command_text, db)
    sent = await telegram_bot_service.send_message(reply_text, chat_id=chat_id)
    return {
        "ok": True,
        "handled": True,
        "command": command_text.split(" ")[0].lower(),
        "sent": sent,
    }


@router.post("/approval-reminders/run")
async def run_approval_reminders(
    current_user: TokenUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Manual trigger for approval reminders (used by n8n workflow E)."""
    result = await notification_service.send_approval_reminders(db)
    return {**result, "triggered_by": current_user.email}


# ─── In-app DB notifications ─────────────────────────────────────────────────

@router.get("")
async def get_notifications(
    limit: int = 20,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Get in-app notifications for the current user."""
    items = notif_svc.get_user_notifications(
        db=db, user_id=UUID(str(current_user.user_id)), limit=min(limit, 100)
    )
    unread = notif_svc.get_unread_count(db=db, user_id=UUID(str(current_user.user_id)))
    return {"notifications": items, "unread_count": unread}


@router.get("/unread-count")
async def get_unread_count(
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Return unread notification count for the current user."""
    count = notif_svc.get_unread_count(db=db, user_id=UUID(str(current_user.user_id)))
    return {"count": count}


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Mark a single notification as read."""
    updated = notif_svc.mark_as_read(
        db=db,
        notification_id=notification_id,
        user_id=UUID(str(current_user.user_id)),
    )
    db.commit()
    return {"notification_id": str(notification_id), "marked_read": updated}


@router.post("/read-all")
async def mark_all_read(
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Mark all notifications as read for the current user."""
    count = notif_svc.mark_all_as_read(db=db, user_id=UUID(str(current_user.user_id)))
    db.commit()
    return {"marked_count": count}
```

---

### File 10 — `backend/app/routers/webhooks.py` (NEW)

```python
"""Webhook receivers for external integrations (Google Drive change notifications)."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.db_service import get_db
from app.services import notifications as notif_svc

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/drive-changes")
async def drive_changes_webhook(
    request: Request,
    x_goog_resource_id: str = Header(None, alias="X-Goog-Resource-Id"),
    x_goog_channel_id: str = Header(None, alias="X-Goog-Channel-Id"),
    x_goog_resource_state: str = Header(None, alias="X-Goog-Resource-State"),
    db: Session = Depends(get_db),
):
    """Receive Google Drive push notifications for file changes.

    channel_id convention: "doc:{document_id}" (set during register_file_watch).
    """
    logger.info(
        "Drive webhook: channel=%s resource=%s state=%s",
        x_goog_channel_id, x_goog_resource_id, x_goog_resource_state,
    )

    if x_goog_resource_state == "sync":
        return {"ok": True, "type": "sync"}

    if x_goog_channel_id and x_goog_channel_id.startswith("doc:"):
        try:
            doc_id_str = x_goog_channel_id[4:]
            row = db.execute(
                text(
                    """
                    SELECT d.title, d.created_by, p.name
                    FROM documents d
                    JOIN projects p ON p.project_id = d.project_id
                    WHERE d.doc_id = :did
                    """
                ),
                {"did": doc_id_str},
            ).fetchone()
            if row and row[1]:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(row[1])),
                    title="Document Modified",
                    message=f"Your document '{row[0]}' in project '{row[2]}' was modified.",
                    notif_type="file_edited",
                    project_name=row[2] or "",
                    doc_name=row[0] or "",
                )
                db.commit()
        except Exception as exc:
            logger.warning("drive_changes_webhook notification failed: %s", exc)

    return {"ok": True, "type": x_goog_resource_state or "change"}
```

---

### File 11 — `backend/app/main.py` — add webhooks router

In [main.py](backend/app/main.py), add after the existing imports:

```python
from .routers import webhooks as webhooks_router
```

And add the router registration after the existing `app.include_router(notifications_router...)`:

```python
app.include_router(
    webhooks_router.router,
    prefix="/api/webhooks",
    tags=["webhooks"],
)
```

---

### File 12 — `frontend/src/services/documents.ts` — add to end of file

Append to the existing [documents.ts](frontend/src/services/documents.ts):

```typescript
export async function returnWorkflow(workflowId: string, comment: string): Promise<void> {
  await approvalsClient.post(`/${workflowId}/return`, { comment })
}

export async function resubmitDocument(docId: string): Promise<void> {
  const docsClient2 = axios.create({ baseURL: '/api/documents', withCredentials: true })
  await docsClient2.post(`/${docId}/resubmit`)
}

export interface ApprovalItemExtended extends PendingApprovalItem {
  project_name?: string | null
  submitter_name?: string | null
  submitter_role?: string | null
  doc_type?: string | null
  status_color?: string | null
  step_1_role?: string | null
  step_2_role?: string | null
}
```

---

### File 13 — `frontend/src/services/notifications.ts` (NEW)

```typescript
import axios from 'axios'

export interface NotificationItem {
  notification_id: string
  title: string
  message: string
  type: string
  is_read: boolean
  related_doc_id: string | null
  related_workflow_id: string | null
  project_name: string | null
  doc_name: string | null
  created_at: string | null
}

const client = axios.create({
  baseURL: '/api/notifications',
  withCredentials: true,
})

export async function getNotifications(limit = 20): Promise<{ notifications: NotificationItem[]; unread_count: number }> {
  const response = await client.get('', { params: { limit } })
  return response.data
}

export async function getUnreadCount(): Promise<number> {
  const response = await client.get('/unread-count')
  return (response.data as { count: number }).count
}

export async function markAsRead(notificationId: string): Promise<void> {
  await client.post(`/${notificationId}/read`)
}

export async function markAllAsRead(): Promise<void> {
  await client.post('/read-all')
}
```

---

### File 14 — `frontend/src/components/NotificationBell.tsx` (NEW)

```tsx
import React, { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/router'
import {
  getNotifications,
  getUnreadCount,
  markAllAsRead,
  markAsRead,
  type NotificationItem,
} from '@/services/notifications'

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} minute${mins > 1 ? 's' : ''} ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs} hour${hrs > 1 ? 's' : ''} ago`
  return `${Math.floor(hrs / 24)} day${Math.floor(hrs / 24) > 1 ? 's' : ''} ago`
}

export default function NotificationBell() {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<NotificationItem[]>([])
  const [unread, setUnread] = useState(0)
  const ref = useRef<HTMLDivElement>(null)

  const load = async () => {
    try {
      const { notifications, unread_count } = await getNotifications(20)
      setItems(notifications)
      setUnread(unread_count)
    } catch {
      // silent — not authenticated yet
    }
  }

  useEffect(() => {
    void load()
    const interval = setInterval(() => void load(), 30000)
    return () => clearInterval(interval)
  }, [])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleMarkAll = async () => {
    await markAllAsRead()
    setUnread(0)
    setItems((prev) => prev.map((n) => ({ ...n, is_read: true })))
  }

  const handleItemClick = async (item: NotificationItem) => {
    if (!item.is_read) {
      await markAsRead(item.notification_id)
      setItems((prev) =>
        prev.map((n) =>
          n.notification_id === item.notification_id ? { ...n, is_read: true } : n
        )
      )
      setUnread((c) => Math.max(0, c - 1))
    }
    if (item.related_workflow_id) {
      void router.push('/approvals')
    }
    setOpen(false)
  }

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        type="button"
        className="btn btn-link nav-link position-relative p-0 me-3"
        onClick={() => setOpen((o) => !o)}
        aria-label="Notifications"
        style={{ color: 'rgba(255,255,255,0.75)' }}
      >
        🔔
        {unread > 0 && (
          <span
            className="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger"
            style={{ fontSize: '0.65rem' }}
          >
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          className="card shadow"
          style={{
            position: 'absolute',
            right: 0,
            top: '2rem',
            width: '360px',
            maxHeight: '480px',
            overflowY: 'auto',
            zIndex: 1050,
          }}
        >
          <div className="card-header d-flex justify-content-between align-items-center py-2">
            <strong>Notifications</strong>
            {unread > 0 && (
              <button
                type="button"
                className="btn btn-link btn-sm p-0 text-muted"
                onClick={() => void handleMarkAll()}
              >
                Mark all as read
              </button>
            )}
          </div>

          {items.length === 0 ? (
            <div className="card-body text-muted small text-center py-4">No notifications</div>
          ) : (
            <ul className="list-group list-group-flush">
              {items.map((item) => (
                <li
                  key={item.notification_id}
                  className={`list-group-item list-group-item-action ${!item.is_read ? 'fw-bold' : ''}`}
                  style={{ cursor: 'pointer', backgroundColor: item.is_read ? '' : '#f0f7ff' }}
                  onClick={() => void handleItemClick(item)}
                >
                  <div className="d-flex justify-content-between">
                    <span className="small">{item.title}</span>
                    <span className="text-muted" style={{ fontSize: '0.7rem', whiteSpace: 'nowrap' }}>
                      {timeAgo(item.created_at)}
                    </span>
                  </div>
                  <div className="text-muted small" style={{ fontSize: '0.8rem' }}>
                    {(item.message || '').length > 80
                      ? `${item.message.slice(0, 80)}…`
                      : item.message}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
```

---

### File 15 — `frontend/src/components/Layout.tsx` (COMPLETE REPLACEMENT)

```tsx
/**
 * Main Layout Component
 */
import React from 'react'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/router'
import 'bootstrap/dist/css/bootstrap.min.css'
import styles from '@/styles/layout.module.css'
import { getCurrentUser, logout } from '@/services/auth'
import NotificationBell from '@/components/NotificationBell'

interface LayoutProps {
  children: React.ReactNode
}

export function Layout({ children }: LayoutProps) {
  const router = useRouter()
  const [isAuthenticated, setIsAuthenticated] = useState(false)

  useEffect(() => {
    const bootstrap = async () => {
      const user = await getCurrentUser()
      setIsAuthenticated(user !== null)
    }
    void bootstrap()
  }, [router.pathname])

  const handleLogout = async () => {
    await logout()
    router.push('/login')
  }

  return (
    <div className={styles.layout}>
      {isAuthenticated && (
        <nav className={`${styles.navbar} navbar navbar-expand-lg navbar-dark bg-dark`}>
          <div className="container-fluid">
            <Link href="/" className="navbar-brand">
              AI BA Agent
            </Link>
            <div className="collapse navbar-collapse">
              <ul className="navbar-nav ms-auto align-items-center">
                <li className="nav-item">
                  <Link href="/projects" className="nav-link">
                    Projects
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/documents" className="nav-link">
                    Documents
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/approvals" className="nav-link">
                    Approvals
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/knowledge-base" className="nav-link">
                    Knowledge Base
                  </Link>
                </li>
                <li className="nav-item d-flex align-items-center">
                  <NotificationBell />
                </li>
                <li className="nav-item">
                  <button
                    className="nav-link btn btn-link"
                    onClick={handleLogout}
                  >
                    Logout
                  </button>
                </li>
              </ul>
            </div>
          </div>
        </nav>
      )}

      
```


## License: unknown
https://github.com/RakanAji/SMARTPLANTMONITORING_KELOMPOK6/blob/ebf90229ddf582f567c06fafa486befebe2eab2d/src/components/Header.js

```
I now have a complete picture of the codebase. I'm in Ask mode so I cannot write files directly — I'll provide the complete, implementation-ready code for every file to create or modify. Apply them in order.

---

## Implementation

### File 1 — `infra/migrations/005_add_notifications.sql` (NEW)

```sql
-- 005: In-app notifications table
CREATE TABLE IF NOT EXISTS notifications (
  notification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(user_id),
  title VARCHAR(255) NOT NULL,
  message TEXT NOT NULL,
  type VARCHAR(50) NOT NULL DEFAULT 'info',
  is_read BOOLEAN DEFAULT false,
  related_doc_id UUID REFERENCES documents(doc_id),
  related_workflow_id UUID REFERENCES approval_workflows(workflow_id),
  project_name VARCHAR(255),
  doc_name VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_is_read  ON notifications(is_read);
```

---

### File 2 — `infra/migrations/006_add_workflow_roles.sql` (NEW)

```sql
-- 006: Per-workflow dynamic role assignment + submitter tracking
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS step_1_role   VARCHAR(50);
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS step_2_role   VARCHAR(50);
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS submitter_id  UUID REFERENCES users(user_id);
```

---

### File 3 — `backend/app/services/notifications.py` (NEW)

```python
"""DB-backed in-app notification service (distinct from notification.py which is Telegram)."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def create_notification(
    *,
    db: Session,
    user_id: UUID,
    title: str,
    message: str,
    notif_type: str = "info",
    doc_id: Optional[UUID] = None,
    workflow_id: Optional[UUID] = None,
    project_name: str = "",
    doc_name: str = "",
) -> Optional[str]:
    """Insert a notification row. Returns notification_id or None on failure."""
    try:
        nid = str(uuid4())
        db.execute(
            text(
                """
                INSERT INTO notifications
                    (notification_id, user_id, title, message, type, is_read,
                     related_doc_id, related_workflow_id, project_name, doc_name, created_at)
                VALUES
                    (:nid, :uid, :title, :msg, :type, false,
                     :doc_id, :wf_id, :pname, :dname, :ts)
                """
            ),
            {
                "nid": nid,
                "uid": str(user_id),
                "title": title,
                "msg": message,
                "type": notif_type,
                "doc_id": str(doc_id) if doc_id else None,
                "wf_id": str(workflow_id) if workflow_id else None,
                "pname": project_name,
                "dname": doc_name,
                "ts": datetime.utcnow(),
            },
        )
        return nid
    except Exception as exc:
        logger.error("create_notification failed: %s", exc)
        return None


def get_user_notifications(
    *, db: Session, user_id: UUID, limit: int = 20
) -> List[Dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT notification_id, title, message, type, is_read,
                   related_doc_id, related_workflow_id,
                   project_name, doc_name, created_at
            FROM notifications
            WHERE user_id = :uid
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"uid": str(user_id), "limit": limit},
    ).fetchall()
    return [
        {
            "notification_id": str(r[0]),
            "title": r[1],
            "message": r[2],
            "type": r[3],
            "is_read": bool(r[4]),
            "related_doc_id": str(r[5]) if r[5] else None,
            "related_workflow_id": str(r[6]) if r[6] else None,
            "project_name": r[7],
            "doc_name": r[8],
            "created_at": r[9].isoformat() if r[9] else None,
        }
        for r in rows
    ]


def mark_as_read(*, db: Session, notification_id: UUID, user_id: UUID) -> bool:
    result = db.execute(
        text(
            """
            UPDATE notifications
            SET is_read = true
            WHERE notification_id = :nid AND user_id = :uid
            """
        ),
        {"nid": str(notification_id), "uid": str(user_id)},
    )
    return (result.rowcount or 0) > 0


def mark_all_as_read(*, db: Session, user_id: UUID) -> int:
    result = db.execute(
        text(
            "UPDATE notifications SET is_read = true WHERE user_id = :uid AND is_read = false"
        ),
        {"uid": str(user_id)},
    )
    return result.rowcount or 0


def get_unread_count(*, db: Session, user_id: UUID) -> int:
    row = db.execute(
        text(
            "SELECT COUNT(*) FROM notifications WHERE user_id = :uid AND is_read = false"
        ),
        {"uid": str(user_id)},
    ).fetchone()
    return int(row[0] or 0)


def get_role_user_ids(
    *, db: Session, project_id: UUID, role: str
) -> List[str]:
    """Return user_ids that have the given role (system-wide or project-scoped)."""
    rows = db.execute(
        text(
            """
            SELECT DISTINCT u.user_id
            FROM users u
            LEFT JOIN user_projects up
                ON up.user_id = u.user_id AND up.project_id = :pid
            WHERE u.role = :role OR up.role = :role
            LIMIT 20
            """
        ),
        {"pid": str(project_id), "role": role},
    ).fetchall()
    return [str(r[0]) for r in rows]
```

---

### File 4 — `backend/app/services/workflow.py` (COMPLETE REPLACEMENT)

```python
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


# Fallback static step roles — used when a workflow pre-dates dynamic assignment
APPROVAL_STEPS = {
    1: "business_owner",
    2: "admin",
}


def _resolve_dynamic_roles(submitter_role: str) -> Tuple[str, str]:
    """Return (step_1_role, step_2_role) based on the submitter's role."""
    if submitter_role == "business_owner":
        return ("ba", "business_owner")
    if submitter_role in ("ba", "pm"):
        return ("business_owner", "ba")
    # tech_lead, legal, finance, viewer → default
    return ("business_owner", "admin")


def _get_expected_role(wf: Dict[str, Any]) -> str:
    """Return the role required for the current workflow step."""
    if wf["current_step"] == 1:
        return wf.get("step_1_role") or APPROVAL_STEPS.get(1, "business_owner")
    return wf.get("step_2_role") or APPROVAL_STEPS.get(2, "admin")


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
    step_1_role, step_2_role = _resolve_dynamic_roles(submitter_role)
    total_steps = len(APPROVAL_STEPS)

    if submitter_role == "admin":
        initial_status = "approved"
        doc_status = "approved"
    else:
        initial_status = "pending"
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
    step_2 = row[8] or APPROVAL_STEPS.get(2, "admin")

    return {
        "workflow_id": str(row[0]),
        "doc_id": str(row[1]),
        "project_id": str(row[2]),
        "current_step": int(row[3] or 1),
        "total_steps": len(APPROVAL_STEPS),
        "status": str(row[5] or "in_progress"),
        "version_id": str(row[6]) if row[6] else None,
        "step_1_role": step_1,
        "step_2_role": step_2,
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

    next_step = completed_step + 1
    final_step = len(APPROVAL_STEPS)
    new_status = "approved" if next_step > final_step else "in_progress"
    new_doc_status = "approved" if new_status == "approved" else "pending_approval"

    step_roles = {1: wf.get("step_1_role"), 2: wf.get("step_2_role")}
    next_required_role = step_roles.get(next_step) or APPROVAL_STEPS.get(next_step)

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
            SET current_step = :current_step,
                status       = :status,
                version_id   = :version_id,
                updated_at   = :updated_at
            WHERE workflow_id = :workflow_id
            """
        ),
        {
            "current_step": min(next_step, final_step),
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

    log_audit_event(
        db=db,
        project_id=UUID(wf["project_id"]),
        action="APPROVAL_APPROVED",
        entity_type="approval",
        entity_id=workflow_id,
        user_id=actor_user_id,
        old_values={"status": wf["status"], "current_step": completed_step},
        new_values={
            "status": new_status,
            "current_step": min(next_step, final_step),
            "version_id": str(version_id),
        },
        succeeded=True,
    )

    return {
        "workflow_id": wf["workflow_id"],
        "decision_id": str(decision_id),
        "status": new_status,
        "completed_step": completed_step,
        "current_step": min(next_step, final_step),
        "next_required_role": None if new_status == "approved" else next_required_role,
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
        reason=(
            f"Rejection at step {wf['current_step']}: {reason}"
            if reason
            else f"Rejection at step {wf['current_step']}"
        ),
        project_id=UUID(wf["project_id"]),
        workflow_id=workflow_id,
        db=db,
    )

    db.execute(
        text(
            """
            UPDATE approval_workflows
            SET status     = 'rejected',
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
    """Return a document for revision.

    Step 1 → sets status = returned_to_submitter, doc status = returned
    Step 2 → sets status = returned_to_step1, resets to step 1
    """
    wf = get_workflow(workflow_id, db)
    if wf is None:
        raise ValueError("Approval workflow not found")

    if wf["status"] in {"approved", "rejected"}:
        raise ValueError(f"Workflow already closed with status={wf['status']}")

    expected_role = _get_expected_role(wf)
    if actor_role != expected_role and actor_role != "admin":
        raise PermissionError(f"Current step requires role '{expected_role}'")

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
            "step_number": wf["current_step"],
            "approver_id": str(actor_user_id),
            "comments": comment,
            "created_at": now,
        },
    )

    from_step = wf["current_step"]
    if from_step == 1:
        new_wf_status = "returned_to_submitter"
        new_doc_status = "returned"
        audit_action = "APPROVAL_RETURNED_TO_SUBMITTER"
    else:
        new_wf_status = "returned_to_step1"
        new_doc_status = "pending_approval"
        audit_action = "APPROVAL_RETURNED_TO_STEP1"

    version_id = create_document_version(
        doc_id=UUID(wf["doc_id"]),
        created_by=actor_user_id,
        approval_status=new_wf_status,
        reason=f"Returned at step {from_step}: {comment}",
        project_id=UUID(wf["project_id"]),
        workflow_id=workflow_id,
        db=db,
    )

    db.execute(
        text(
            """
            UPDATE approval_workflows
            SET status       = :status,
                current_step = 1,
                version_id   = :version_id,
                updated_at   = :updated_at
            WHERE workflow_id = :workflow_id
            """
        ),
        {
            "status": new_wf_status,
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
        old_values={"status": wf["status"], "current_step": from_step},
        new_values={"status": new_wf_status, "comment": comment, "version_id": str(version_id)},
        succeeded=True,
    )

    return {
        "workflow_id": wf["workflow_id"],
        "decision_id": str(decision_id),
        "status": new_wf_status,
        "current_step": 1,
        "previous_step": from_step,
        "comment": comment,
        "version_id": str(version_id),
        "submitter_id": wf.get("submitter_id"),
        "step_1_role": wf.get("step_1_role"),
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
                (workflow_id, doc_id, project_id, current_step, total_steps, status,
                 submitter_id, created_at, updated_at)
            VALUES
                (:workflow_id, :doc_id, :project_id, 1, :total_steps,
                 'human_review_required', :submitter_id, :created_at, :updated_at)
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
        new_values={
            "status": "human_review_required",
            "doc_id": str(doc_id),
            "total_steps": len(APPROVAL_STEPS),
        },
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
        {"version_id": str(version_id), "updated_at": now, "workflow_id": str(workflow_id)},
    )
    db.execute(
        text(
            "UPDATE documents SET status = 'human_review_required', updated_at = :t WHERE doc_id = :id"
        ),
        {"t": now, "id": str(doc_id)},
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
                (version_id, doc_id, version_number, content, content_hash,
                 created_by, approval_status, created_at)
            VALUES
                (:version_id, :doc_id, :version_number, :content, :content_hash,
                 :created_by, :approval_status, :created_at)
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
```

---

### File 5 — `backend/app/services/google_drive.py` — append at bottom

Add these three functions to the end of the existing [google_drive.py](backend/app/services/google_drive.py):

```python
import re as _re

_MIME_EDIT_URLS = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        "https://docs.google.com/document/d/{id}/edit",
    "application/msword":
        "https://docs.google.com/document/d/{id}/edit",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
    "application/vnd.ms-excel":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
    "text/csv":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
}


def get_drive_file_id(drive_url: str) -> Optional[str]:
    """Extract the Drive file ID from a webViewLink URL."""
    match = _re.search(r"/(?:file/)?d/([a-zA-Z0-9_-]+)", drive_url or "")
    return match.group(1) if match else None


def get_edit_url(file_id: str, mime_type: str) -> str:
    """Return the correct Google Drive / Docs / Sheets URL for the given MIME type."""
    template = _MIME_EDIT_URLS.get(mime_type)
    if template:
        return template.format(id=file_id)
    return f"https://drive.google.com/file/d/{file_id}/view"


def register_file_watch(file_id: str, document_id: str) -> bool:
    """Register a Google Drive push-notification watch (requires verified HTTPS endpoint).

    This stub logs the intent.  In production, call files().watch() with your
    verified webhook URL and store the channel/resource IDs for later expiry renewal.
    """
    logger.info(
        "register_file_watch: file_id=%s doc_id=%s (stub – HTTPS endpoint required)",
        file_id,
        document_id,
    )
    return False
```

---

### File 6 — `backend/app/middleware/rbac.py` — append one line after `require_approver`

Add after `require_approver = ...`:

```python
# Broader reviewer set: includes BA and PM (needed for dynamic step approver assignment)
require_reviewer = make_require_role(["admin", "business_owner", "ba", "pm", "legal"])
```

---

### File 7 — `backend/app/routers/approvals.py` (COMPLETE REPLACEMENT)

```python
"""Approval workflow endpoints."""

from __future__ import annotations

import logging
import os as _os
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_ba, require_readonly, require_reviewer
from app.services.db_service import get_db
from app.services import google_sheets
from app.services import notifications as notif_svc
from app.services.workflow import (
    APPROVAL_STEPS,
    approve_step,
    create_approval_workflow,
    get_workflow,
    reject_step,
    return_step,
    trigger_hitl,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Statuses considered "active / pending" for the dashboard
_PENDING_STATUSES = (
    "in_progress",
    "human_review_required",
    "returned_to_submitter",
    "returned_to_step1",
)
_COMPLETED_STATUSES = ("approved", "rejected")


class ApprovalActionRequest(BaseModel):
    comment: str = ""


class ReturnRequest(BaseModel):
    comment: str = Field(min_length=1)


class CreateApprovalRequest(BaseModel):
    document_id: UUID
    project_id: UUID
    workflow_type: str = "approval"


class RejectionRequest(BaseModel):
    reason: str = Field(min_length=1)


class HitlTriggerRequest(BaseModel):
    document_id: UUID
    project_id: Optional[UUID] = None
    reason: str = Field(min_length=1)
    risk_flags: Dict[str, Any] = {}


# ─── helpers ─────────────────────────────────────────────────────────────────

def _get_doc_project_info(workflow_id: UUID, db: Session):
    """Return (doc_title, project_name, submitter_id) for a workflow."""
    return db.execute(
        text(
            """
            SELECT d.title, p.name, aw.submitter_id
            FROM approval_workflows aw
            JOIN documents d ON d.doc_id = aw.doc_id
            JOIN projects p ON p.project_id = aw.project_id
            WHERE aw.workflow_id = :wid
            """
        ),
        {"wid": str(workflow_id)},
    ).fetchone()


def _status_badge_color(status: str) -> str:
    colors = {
        "in_progress": "info",
        "approved": "success",
        "rejected": "danger",
        "returned_to_submitter": "warning",
        "returned_to_step1": "warning",
        "human_review_required": "secondary",
    }
    return colors.get(status, "secondary")


# ─── endpoints ───────────────────────────────────────────────────────────────

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
            submitter_role=current_user.role,
            db=db,
        )
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"create_workflow_failed: {exc}")


@router.get("")
async def list_approvals(
    project_id: UUID,
    status: str = Query("pending"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """List approvals by status for dashboard views."""
    normalized = status.lower()
    if normalized not in {"pending", "completed", "all"}:
        raise HTTPException(status_code=400, detail="status must be pending, completed, or all")

    pending_in = ", ".join(f"'{s}'" for s in _PENDING_STATUSES)
    completed_in = ", ".join(f"'{s}'" for s in _COMPLETED_STATUSES)

    if normalized == "pending":
        status_filter = f"aw.status IN ({pending_in})"
    elif normalized == "completed":
        status_filter = f"aw.status IN ({completed_in})"
    else:
        status_filter = f"aw.status IN ({pending_in}, {completed_in})"

    offset = (page - 1) * page_size

    rows = db.execute(
        text(
            f"""
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
                    d.doc_type,
                    p.name AS project_name,
                    COALESCE(u.full_name, u.email, '') AS submitter_name,
                    u.role AS submitter_role,
                    aw.step_1_role,
                    aw.step_2_role,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                LEFT JOIN documents d ON d.doc_id = aw.doc_id
                LEFT JOIN projects p ON p.project_id = aw.project_id
                LEFT JOIN users u ON u.user_id = aw.submitter_id
                WHERE aw.project_id = :project_id
                  AND {status_filter}
            )
            SELECT workflow_id, doc_id, doc_title, current_step, total_steps, status,
                   updated_at, google_drive_link, doc_type, project_name,
                   submitter_name, submitter_role, step_1_role, step_2_role
            FROM ranked
            WHERE rn = 1
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"project_id": str(project_id), "limit": page_size, "offset": offset},
    ).fetchall()

    count_row = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT aw.doc_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                WHERE aw.project_id = :project_id AND {status_filter}
            )
            SELECT COUNT(*) FROM ranked WHERE rn = 1
            """
        ),
        {"project_id": str(project_id)},
    ).fetchone()

    items = [
        {
            "workflow_id": str(r[0]),
            "doc_id": str(r[1]),
            "doc_title": r[2] or None,
            "current_step": int(r[3] or 1),
            "total_steps": len(APPROVAL_STEPS),
            "status": r[5],
            "status_color": _status_badge_color(r[5]),
            "updated_at": r[6].isoformat() if r[6] else None,
            "google_drive_link": r[7] or None,
            "doc_type": r[8] or None,
            "project_name": r[9] or None,
            "submitter_name": r[10] or None,
            "submitter_role": r[11] or None,
            "step_1_role": r[12] or None,
            "step_2_role": r[13] or None,
        }
        for r in rows
    ]

    return {
        "project_id": str(project_id),
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
    pending_in = ", ".join(f"'{s}'" for s in _PENDING_STATUSES)
    offset = (page - 1) * page_size

    rows = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT
                    aw.workflow_id, aw.doc_id,
                    COALESCE(d.title, '') AS doc_title,
                    aw.current_step, aw.total_steps, aw.status, aw.updated_at,
                    d.google_drive_link, d.doc_type, p.name AS project_name,
                    COALESCE(u.full_name, u.email, '') AS submitter_name,
                    u.role AS submitter_role, aw.step_1_role, aw.step_2_role,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                LEFT JOIN documents d ON d.doc_id = aw.doc_id
                LEFT JOIN projects p ON p.project_id = aw.project_id
                LEFT JOIN users u ON u.user_id = aw.submitter_id
                WHERE aw.project_id = :project_id
                  AND aw.status IN ({pending_in})
            )
            SELECT workflow_id, doc_id, doc_title, current_step, total_steps, status,
                   updated_at, google_drive_link, doc_type, project_name,
                   submitter_name, submitter_role, step_1_role, step_2_role
            FROM ranked
            WHERE rn = 1
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"project_id": str(project_id), "limit": page_size, "offset": offset},
    ).fetchall()

    count_row = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT aw.doc_id,
                    ROW_NUMBER() OVER (PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC) AS rn
                FROM approval_workflows aw
                WHERE aw.project_id = :project_id
                  AND aw.status IN ({pending_in})
            )
            SELECT COUNT(*) FROM ranked WHERE rn = 1
            """
        ),
        {"project_id": str(project_id)},
    ).fetchone()

    items = [
        {
            "workflow_id": str(r[0]),
            "doc_id": str(r[1]),
            "doc_title": r[2] or None,
            "current_step": int(r[3] or 1),
            "total_steps": len(APPROVAL_STEPS),
            "status": r[5],
            "status_color": _status_badge_color(r[5]),
            "updated_at": r[6].isoformat() if r[6] else None,
            "google_drive_link": r[7] or None,
            "doc_type": r[8] or None,
            "project_name": r[9] or None,
            "submitter_name": r[10] or None,
            "submitter_role": r[11] or None,
            "step_1_role": r[12] or None,
            "step_2_role": r[13] or None,
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
    current_user: TokenUser = Depends(require_reviewer),
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

    # ── Google Sheets update (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            google_sheets.update_approval_row(
                project_name=info[1] or "",
                file_name=_os.path.splitext(info[0] or "")[0],
                approver_name=current_user.email,
                status="Approved",
                comment=request.comment,
            )
    except Exception as exc:
        logger.warning("Sheets update failed after approve (%s): %s", workflow_id, exc)

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            completed_step = result.get("completed_step", 1)
            final_approved = result["status"] == "approved"

            if submitter_id:
                title = "Document Approved ✅" if final_approved else "Document Progressed"
                if final_approved:
                    msg = f"Project {project_name}: '{doc_title}' has been fully approved!"
                else:
                    msg = f"Project {project_name}: '{doc_title}' passed step {completed_step} review."
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title=title,
                    message=msg,
                    notif_type="approved",
                    doc_id=UUID(result["workflow_id"]) if False else None,
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()
    except Exception as exc:
        logger.warning("Notification failed after approve (%s): %s", workflow_id, exc)

    return result


@router.post("/{workflow_id}/reject")
async def reject_document(
    workflow_id: UUID,
    request: RejectionRequest,
    current_user: TokenUser = Depends(require_reviewer),
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

    # ── Google Sheets update (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            google_sheets.update_approval_row(
                project_name=info[1] or "",
                file_name=_os.path.splitext(info[0] or "")[0],
                approver_name=current_user.email,
                status="Rejected",
                comment=request.reason,
            )
    except Exception as exc:
        logger.warning("Sheets update failed after reject (%s): %s", workflow_id, exc)

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            if submitter_id:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title="Document Rejected",
                    message=f"Project {project_name}: '{doc_title}' was rejected. Reason: {request.reason}",
                    notif_type="rejected",
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()
    except Exception as exc:
        logger.warning("Notification failed after reject (%s): %s", workflow_id, exc)

    return result


@router.post("/{workflow_id}/return")
async def return_document(
    workflow_id: UUID,
    request: ReturnRequest,
    current_user: TokenUser = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    """Return a document for revision.

    Step 1 → returned_to_submitter (document status = returned)
    Step 2 → returned_to_step1 (resets to step 1)
    """
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

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            new_status = result["status"]

            if new_status == "returned_to_submitter" and submitter_id:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title="Document Returned",
                    message=(
                        f"Project {project_name}: '{doc_title}' has been returned "
                        f"for revision. Comment: {request.comment}"
                    ),
                    notif_type="returned",
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()

            elif new_status == "returned_to_step1":
                step_1_role = result.get("step_1_role") or "business_owner"
                wf_row = db.execute(
                    text("SELECT project_id FROM approval_workflows WHERE workflow_id = :wid"),
                    {"wid": str(workflow_id)},
                ).fetchone()
                if wf_row:
                    approver_ids = notif_svc.get_role_user_ids(
                        db=db,
                        project_id=UUID(str(wf_row[0])),
                        role=step_1_role,
                    )
                    for uid_str in approver_ids:
                        notif_svc.create_notification(
                            db=db,
                            user_id=UUID(uid_str),
                            title="Re-review Required",
                            message=(
                                f"Project {project_name}: '{doc_title}' has been "
                                f"returned to you for re-review. Comment: {request.comment}"
                            ),
                            notif_type="returned_to_step1",
                            workflow_id=workflow_id,
                            project_name=project_name or "",
                            doc_name=doc_title or "",
                        )
                    db.commit()
    except Exception as exc:
        logger.warning("Notification failed after return (%s): %s", workflow_id, exc)

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
        "status_color": _status_badge_color(workflow["status"]),
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
```

---

### File 8 — `backend/app/routers/documents.py` (COMPLETE REPLACEMENT)

```python
"""
Document management endpoints.

POST /upload            – Accept file + metadata, store to DB, upload to Drive, trigger pipeline
POST /{doc_id}/resubmit – Resubmit a returned document for re-review
GET  /{doc_id}/status   – Return current processing status + progress
"""
import hashlib
import logging
import mimetypes
import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile, File
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_ba, require_readonly
from app.services.db_service import get_db
from app.services import google_drive, google_sheets, elevenlabs, n8n_webhook
from app.services import notifications as notif_svc
from app.services.workflow import _resolve_dynamic_roles

logger = logging.getLogger(__name__)
router = APIRouter()

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
    project_folder_id: Optional[str] = None,
) -> None:
    """Background task: upload to Google Drive, trigger STT + n8n, update status."""
    db: Session = next(get_db())
    try:
        db.execute(
            text("UPDATE documents SET status = :s, updated_at = :t WHERE doc_id = :id"),
            {"s": STATUS_PROCESSING, "t": datetime.utcnow(), "id": doc_id},
        )
        db.commit()

        drive_url: Optional[str] = google_drive.upload_file(
            file_bytes, filename, mime_type, project_folder_id
        )
        if drive_url:
            db.execute(
                text(
                    "UPDATE documents SET google_drive_link = :url, updated_at = :t WHERE doc_id = :id"
                ),
                {"url": drive_url, "t": datetime.utcnow(), "id": doc_id},
            )
            db.commit()

        transcript: Optional[str] = None
        if elevenlabs.is_audio(mime_type):
            transcript = await elevenlabs.transcribe(file_bytes, filename, mime_type)
            if transcript:
                version_id = str(uuid.uuid4())
                db.execute(
                    text(
                        """INSERT INTO document_versions
                             (version_id, doc_id, version_number, content, approval_status, created_at)
                           VALUES (:vid, :did, 1, :content, 'pending', :ts)"""
                    ),
                    {
                        "vid": version_id,
                        "did": doc_id,
                        "content": transcript,
                        "ts": datetime.utcnow(),
                    },
                )
                db.commit()

        await n8n_webhook.trigger_document_workflow(
            workflow_id=workflow_id,
            document_id=doc_id,
            google_drive_url=drive_url,
            file_type=mime_type,
            filename=filename,
        )

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
    current_user: TokenUser = Depends(require_ba),
    db: Session = Depends(get_db),
):
    """
    Upload a document for processing.

    - Requires role: ba / pm / tech_lead / admin  (HTTP 403 otherwise)
    - Returns: {document_id, workflow_id, status: "PENDING"}
    """
    mime_type: str = file.content_type or ""
    if not mime_type or mime_type == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(file.filename or "")
        mime_type = guessed or "application/octet-stream"

    doc_title  = title or (file.filename or "Untitled")
    doc_id     = str(uuid.uuid4())
    workflow_id = str(uuid.uuid4())

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # ── 1. Insert document record ─────────────────────────────────────────
    try:
        db.execute(
            text(
                """INSERT INTO documents
                     (doc_id, project_id, title, doc_type, status, created_by, created_at, updated_at)
                   VALUES (:doc_id, :project_id, :title, :doc_type, :status, :created_by, :now, :now)"""
            ),
            {
                "doc_id":     doc_id,
                "project_id": project_id,
                "title":      doc_title,
                "doc_type":   mime_type,
                "status":     STATUS_PENDING,
                "created_by": current_user.user_id,
                "now":        datetime.utcnow(),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to insert document record: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to store document metadata")

    # ── 2. Determine dynamic roles ────────────────────────────────────────
    step_1_role, step_2_role = _resolve_dynamic_roles(current_user.role)
    auto_approve = current_user.role == "admin"
    initial_wf_status = "approved" if auto_approve else "in_progress"

    # ── 3. Create approval_workflow entry ─────────────────────────────────
    try:
        db.execute(
            text(
                """INSERT INTO approval_workflows
                     (workflow_id, doc_id, project_id, status, current_step, total_steps,
                      step_1_role, step_2_role, submitter_id, created_at, updated_at)
                   VALUES
                     (:wid, :did, :pid, :status, 1, 2,
                      :step_1_role, :step_2_role, :submitter_id, :now, :now)"""
            ),
            {
                "wid":          workflow_id,
                "did":          doc_id,
                "pid":          project_id,
                "status":       initial_wf_status,
                "step_1_role":  step_1_role,
                "step_2_role":  step_2_role,
                "submitter_id": str(current_user.user_id),
                "now":          datetime.utcnow(),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to create approval workflow entry: %s", exc)

    # ── 4. Fetch project Drive folder ─────────────────────────────────────
    project_folder_id: Optional[str] = None
    project_name: str = ""
    try:
        proj_row = db.execute(
            text("SELECT name, google_drive_folder_id FROM projects WHERE project_id = :pid"),
            {"pid": project_id},
        ).fetchone()
        if proj_row:
            project_name     = proj_row[0] or ""
            project_folder_id = proj_row[1] or None
            if project_folder_id is None:
                project_folder_id = google_drive.create_project_folder(project_name)
                if project_folder_id:
                    db.execute(
                        text(
                            "UPDATE projects SET google_drive_folder_id = :fid WHERE project_id = :pid"
                        ),
                        {"fid": project_folder_id, "pid": project_id},
                    )
                    db.commit()
    except Exception as exc:
        logger.warning("Could not fetch project Drive folder for %s: %s", project_id, exc)

    # ── 5. Append row to Google Sheets backlog (best-effort) ──────────────
    try:
        import os as _os
        file_name_no_ext = _os.path.splitext(doc_title)[0]
        google_sheets.append_upload_row(
            user_name=current_user.email,
            project_name=project_name,
            file_name=file_name_no_ext,
            upload_date=datetime.utcnow().strftime("%d-%b-%Y"),
        )
    except Exception as exc:
        logger.warning("Sheets append_upload_row failed for %s: %s", doc_id, exc)

    # ── 6. Notify step-1 approvers (best-effort) ──────────────────────────
    try:
        approver_ids = notif_svc.get_role_user_ids(
            db=db, project_id=UUID(project_id), role=step_1_role
        )
        for uid_str in approver_ids:
            notif_svc.create_notification(
                db=db,
                user_id=UUID(uid_str),
                title="New Review Request",
                message=f"Project {project_name}: '{doc_title}' needs your review.",
                notif_type="upload",
                workflow_id=UUID(workflow_id),
                project_name=project_name,
                doc_name=doc_title,
            )
        db.commit()
    except Exception as exc:
        logger.warning("Upload notification failed for %s: %s", doc_id, exc)

    # ── 7. Queue background processing ────────────────────────────────────
    background_tasks.add_task(
        _process_document,
        doc_id,
        workflow_id,
        file_bytes,
        file.filename or doc_title,
        mime_type,
        project_folder_id,
    )

    logger.info(
        "Document %s queued for processing by %s (workflow %s)",
        doc_id, current_user.email, workflow_id,
    )
    return {
        "document_id":  doc_id,
        "workflow_id":  workflow_id,
        "filename":     file.filename,
        "status":       STATUS_PENDING,
        "uploaded_by":  current_user.email,
        "step_1_role":  step_1_role,
        "step_2_role":  step_2_role,
    }


@router.post("/{doc_id}/resubmit")
async def resubmit_document(
    doc_id: str,
    current_user: TokenUser = Depends(require_ba),
    db: Session = Depends(get_db),
):
    """Resubmit a returned document for re-review (only the original submitter or admin)."""
    doc_row = db.execute(
        text(
            "SELECT doc_id, project_id, title, status, created_by FROM documents WHERE doc_id = :did"
        ),
        {"did": doc_id},
    ).fetchone()
    if doc_row is None:
        raise HTTPException(status_code=404, detail="document_not_found")

    if current_user.role != "admin" and str(doc_row[4]) != str(current_user.user_id):
        raise HTTPException(status_code=403, detail="Only the document submitter can resubmit")

    if doc_row[3] != "returned":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not in 'returned' status (current: {doc_row[3]})",
        )

    wf_row = db.execute(
        text(
            """
            SELECT workflow_id, step_1_role, step_2_role, project_id
            FROM approval_workflows
            WHERE doc_id = :did AND status = 'returned_to_submitter'
            ORDER BY updated_at DESC LIMIT 1
            """
        ),
        {"did": doc_id},
    ).fetchone()

    now = datetime.utcnow()

    # Create new document version
    prev = db.execute(
        text(
            "SELECT version_number, content FROM document_versions WHERE doc_id = :did ORDER BY version_number DESC LIMIT 1"
        ),
        {"did": doc_id},
    ).fetchone()
    new_version_num = (int(prev[0]) + 1) if prev else 1
    content = f"{prev[1] or ''}\n\n[resubmitted by {current_user.email}]".strip() if prev else "[resubmitted]"
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    version_id = str(uuid.uuid4())

    db.execute(
        text(
            """
            INSERT INTO document_versions
                (version_id, doc_id, version_number, content, content_hash,
                 created_by, approval_status, created_at)
            VALUES (:vid, :did, :vn, :content, :hash, :uid, 'pending', :ts)
            """
        ),
        {
            "vid": version_id, "did": doc_id, "vn": new_version_num,
            "content": content, "hash": content_hash,
            "uid": str(current_user.user_id), "ts": now,
        },
    )

    db.execute(
        text("UPDATE documents SET status = 'pending_approval', updated_at = :ts WHERE doc_id = :did"),
        {"ts": now, "did": doc_id},
    )

    wf_id_str: Optional[str] = None
    step_1_role = "business_owner"
    project_id_str = str(doc_row[1])

    if wf_row:
        wf_id_str   = str(wf_row[0])
        step_1_role = wf_row[1] or "business_owner"
        db.execute(
            text(
                "UPDATE approval_workflows SET status = 'in_progress', current_step = 1, updated_at = :ts WHERE workflow_id = :wid"
            ),
            {"ts": now, "wid": wf_id_str},
        )

    db.commit()

    # Notify step-1 approvers (best-effort)
    try:
        pname_row = db.execute(
            text("SELECT name FROM projects WHERE project_id = :pid"),
            {"pid": project_id_str},
        ).fetchone()
        pname = pname_row[0] if pname_row else ""
        approver_ids = notif_svc.get_role_user_ids(
            db=db, project_id=UUID(project_id_str), role=step_1_role
        )
        for uid_str in approver_ids:
            notif_svc.create_notification(
                db=db,
                user_id=UUID(uid_str),
                title="Document Resubmitted",
                message=f"Project {pname}: '{doc_row[2]}' has been revised and resubmitted.",
                notif_type="resubmit",
                workflow_id=UUID(wf_id_str) if wf_id_str else None,
                project_name=pname,
                doc_name=doc_row[2] or "",
            )
        db.commit()
    except Exception as exc:
        logger.warning("Resubmit notification failed for %s: %s", doc_id, exc)

    return {
        "document_id":    doc_id,
        "status":         "pending_approval",
        "version_id":     version_id,
        "resubmitted_by": current_user.email,
    }


@router.get("")
async def list_documents(
    project_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """List documents with optional project filter (auth required)."""
    safe_limit  = max(1, min(limit, 200))
    safe_offset = max(0, offset)

    if project_id:
        rows = db.execute(
            text(
                """SELECT doc_id, project_id, title, doc_type, status, updated_at
                   FROM documents WHERE project_id = :pid
                   ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"""
            ),
            {"pid": project_id, "limit": safe_limit, "offset": safe_offset},
        ).fetchall()
    else:
        rows = db.execute(
            text(
                """SELECT doc_id, project_id, title, doc_type, status, updated_at
                   FROM documents
                   ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"""
            ),
            {"limit": safe_limit, "offset": safe_offset},
        ).fetchall()

    return {
        "requested_by": current_user.email,
        "project_id": project_id,
        "total": len(rows),
        "documents": [
            {
                "doc_id":     str(r[0]),
                "project_id": str(r[1]),
                "title":      r[2],
                "doc_type":   r[3],
                "status":     r[4],
                "updated_at": r[5].isoformat() if r[5] else None,
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
    """Get the current processing status of a document."""
    try:
        row = db.execute(
            text(
                "SELECT doc_id, title, status, doc_type, google_drive_link, updated_at FROM documents WHERE doc_id = :id"
            ),
            {"id": doc_id},
        ).fetchone()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"db_error: {exc}")

    if row is None:
        raise HTTPException(status_code=404, detail="document_not_found")

    status = row[2]
    progress_map = {
        STATUS_PENDING:    10,
        STATUS_PROCESSING: 50,
        STATUS_COMPLETED:  100,
        STATUS_FAILED:     0,
    }

    # Build edit URL if Drive link exists
    edit_url: Optional[str] = None
    drive_link = row[4]
    if drive_link:
        file_id = google_drive.get_drive_file_id(drive_link)
        if file_id:
            edit_url = google_drive.get_edit_url(file_id, row[3] or "")

    return {
        "document_id":      str(row[0]),
        "title":            row[1],
        "status":           status,
        "progress":         progress_map.get(status, 0),
        "doc_type":         row[3],
        "google_drive_url": drive_link,
        "edit_url":         edit_url,
        "updated_at":       row[5].isoformat() if row[5] else None,
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
                "version_id":       str(r[0]),
                "version_number":   int(r[1]),
                "content_hash":     r[2],
                "approval_status":  r[3],
                "created_by":       str(r[4]) if r[4] else None,
                "created_at":       r[5].isoformat() if r[5] else None,
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
            SELECT version_id, version_number, content, content_hash, approval_status, created_by, created_at
            FROM document_versions
            WHERE doc_id = :doc_id AND version_id = :version_id
            """
        ),
        {"doc_id": doc_id, "version_id": version_id},
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="version_not_found")

    return {
        "version_id":       str(row[0]),
        "version_number":   int(row[1]),
        "content":          row[2],
        "content_hash":     row[3],
        "approval_status":  row[4],
        "created_by":       str(row[5]) if row[5] else None,
        "created_at":       row[6].isoformat() if row[6] else None,
    }
```

---

### File 9 — `backend/app/routers/notifications.py` (COMPLETE REPLACEMENT)

```python
"""Notification endpoints — Telegram + in-app DB notifications."""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_admin, require_readonly
from app.services.db_service import get_db
from app.services.notification import notification_service
from app.services.telegram_bot import telegram_bot_service
from app.services import notifications as notif_svc

router = APIRouter()


class NotificationSendRequest(BaseModel):
    message: str = Field(min_length=1)
    type: str = "info"
    project_id: Optional[UUID] = None
    metadata: Dict[str, Any] = {}


class TelegramUpdateRequest(BaseModel):
    update_id: Optional[int] = None
    message: Dict[str, Any] = {}


# ─── Telegram endpoints (unchanged) ──────────────────────────────────────────

@router.post("/send")
async def send_notification(
    request: NotificationSendRequest,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Send a notification through the configured Telegram bot."""
    result = await notification_service.dispatch_notification(
        db=db,
        message=request.message,
        notification_type=request.type,
        actor_user_id=UUID(str(current_user.user_id)),
        project_id=request.project_id,
        metadata=request.metadata,
    )
    db.commit()
    return result


@router.post("/telegram/webhook")
async def telegram_webhook(
    payload: TelegramUpdateRequest,
    db: Session = Depends(get_db),
):
    """Receive Telegram updates and reply to /status, /backlog, /help."""
    message = payload.message or {}
    command_text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id")) if chat.get("id") is not None else None

    if not command_text.startswith("/"):
        return {"ok": True, "handled": False}

    reply_text = notification_service.process_telegram_command(command_text, db)
    sent = await telegram_bot_service.send_message(reply_text, chat_id=chat_id)
    return {
        "ok": True,
        "handled": True,
        "command": command_text.split(" ")[0].lower(),
        "sent": sent,
    }


@router.post("/approval-reminders/run")
async def run_approval_reminders(
    current_user: TokenUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Manual trigger for approval reminders (used by n8n workflow E)."""
    result = await notification_service.send_approval_reminders(db)
    return {**result, "triggered_by": current_user.email}


# ─── In-app DB notifications ─────────────────────────────────────────────────

@router.get("")
async def get_notifications(
    limit: int = 20,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Get in-app notifications for the current user."""
    items = notif_svc.get_user_notifications(
        db=db, user_id=UUID(str(current_user.user_id)), limit=min(limit, 100)
    )
    unread = notif_svc.get_unread_count(db=db, user_id=UUID(str(current_user.user_id)))
    return {"notifications": items, "unread_count": unread}


@router.get("/unread-count")
async def get_unread_count(
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Return unread notification count for the current user."""
    count = notif_svc.get_unread_count(db=db, user_id=UUID(str(current_user.user_id)))
    return {"count": count}


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Mark a single notification as read."""
    updated = notif_svc.mark_as_read(
        db=db,
        notification_id=notification_id,
        user_id=UUID(str(current_user.user_id)),
    )
    db.commit()
    return {"notification_id": str(notification_id), "marked_read": updated}


@router.post("/read-all")
async def mark_all_read(
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Mark all notifications as read for the current user."""
    count = notif_svc.mark_all_as_read(db=db, user_id=UUID(str(current_user.user_id)))
    db.commit()
    return {"marked_count": count}
```

---

### File 10 — `backend/app/routers/webhooks.py` (NEW)

```python
"""Webhook receivers for external integrations (Google Drive change notifications)."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.db_service import get_db
from app.services import notifications as notif_svc

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/drive-changes")
async def drive_changes_webhook(
    request: Request,
    x_goog_resource_id: str = Header(None, alias="X-Goog-Resource-Id"),
    x_goog_channel_id: str = Header(None, alias="X-Goog-Channel-Id"),
    x_goog_resource_state: str = Header(None, alias="X-Goog-Resource-State"),
    db: Session = Depends(get_db),
):
    """Receive Google Drive push notifications for file changes.

    channel_id convention: "doc:{document_id}" (set during register_file_watch).
    """
    logger.info(
        "Drive webhook: channel=%s resource=%s state=%s",
        x_goog_channel_id, x_goog_resource_id, x_goog_resource_state,
    )

    if x_goog_resource_state == "sync":
        return {"ok": True, "type": "sync"}

    if x_goog_channel_id and x_goog_channel_id.startswith("doc:"):
        try:
            doc_id_str = x_goog_channel_id[4:]
            row = db.execute(
                text(
                    """
                    SELECT d.title, d.created_by, p.name
                    FROM documents d
                    JOIN projects p ON p.project_id = d.project_id
                    WHERE d.doc_id = :did
                    """
                ),
                {"did": doc_id_str},
            ).fetchone()
            if row and row[1]:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(row[1])),
                    title="Document Modified",
                    message=f"Your document '{row[0]}' in project '{row[2]}' was modified.",
                    notif_type="file_edited",
                    project_name=row[2] or "",
                    doc_name=row[0] or "",
                )
                db.commit()
        except Exception as exc:
            logger.warning("drive_changes_webhook notification failed: %s", exc)

    return {"ok": True, "type": x_goog_resource_state or "change"}
```

---

### File 11 — `backend/app/main.py` — add webhooks router

In [main.py](backend/app/main.py), add after the existing imports:

```python
from .routers import webhooks as webhooks_router
```

And add the router registration after the existing `app.include_router(notifications_router...)`:

```python
app.include_router(
    webhooks_router.router,
    prefix="/api/webhooks",
    tags=["webhooks"],
)
```

---

### File 12 — `frontend/src/services/documents.ts` — add to end of file

Append to the existing [documents.ts](frontend/src/services/documents.ts):

```typescript
export async function returnWorkflow(workflowId: string, comment: string): Promise<void> {
  await approvalsClient.post(`/${workflowId}/return`, { comment })
}

export async function resubmitDocument(docId: string): Promise<void> {
  const docsClient2 = axios.create({ baseURL: '/api/documents', withCredentials: true })
  await docsClient2.post(`/${docId}/resubmit`)
}

export interface ApprovalItemExtended extends PendingApprovalItem {
  project_name?: string | null
  submitter_name?: string | null
  submitter_role?: string | null
  doc_type?: string | null
  status_color?: string | null
  step_1_role?: string | null
  step_2_role?: string | null
}
```

---

### File 13 — `frontend/src/services/notifications.ts` (NEW)

```typescript
import axios from 'axios'

export interface NotificationItem {
  notification_id: string
  title: string
  message: string
  type: string
  is_read: boolean
  related_doc_id: string | null
  related_workflow_id: string | null
  project_name: string | null
  doc_name: string | null
  created_at: string | null
}

const client = axios.create({
  baseURL: '/api/notifications',
  withCredentials: true,
})

export async function getNotifications(limit = 20): Promise<{ notifications: NotificationItem[]; unread_count: number }> {
  const response = await client.get('', { params: { limit } })
  return response.data
}

export async function getUnreadCount(): Promise<number> {
  const response = await client.get('/unread-count')
  return (response.data as { count: number }).count
}

export async function markAsRead(notificationId: string): Promise<void> {
  await client.post(`/${notificationId}/read`)
}

export async function markAllAsRead(): Promise<void> {
  await client.post('/read-all')
}
```

---

### File 14 — `frontend/src/components/NotificationBell.tsx` (NEW)

```tsx
import React, { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/router'
import {
  getNotifications,
  getUnreadCount,
  markAllAsRead,
  markAsRead,
  type NotificationItem,
} from '@/services/notifications'

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} minute${mins > 1 ? 's' : ''} ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs} hour${hrs > 1 ? 's' : ''} ago`
  return `${Math.floor(hrs / 24)} day${Math.floor(hrs / 24) > 1 ? 's' : ''} ago`
}

export default function NotificationBell() {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<NotificationItem[]>([])
  const [unread, setUnread] = useState(0)
  const ref = useRef<HTMLDivElement>(null)

  const load = async () => {
    try {
      const { notifications, unread_count } = await getNotifications(20)
      setItems(notifications)
      setUnread(unread_count)
    } catch {
      // silent — not authenticated yet
    }
  }

  useEffect(() => {
    void load()
    const interval = setInterval(() => void load(), 30000)
    return () => clearInterval(interval)
  }, [])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleMarkAll = async () => {
    await markAllAsRead()
    setUnread(0)
    setItems((prev) => prev.map((n) => ({ ...n, is_read: true })))
  }

  const handleItemClick = async (item: NotificationItem) => {
    if (!item.is_read) {
      await markAsRead(item.notification_id)
      setItems((prev) =>
        prev.map((n) =>
          n.notification_id === item.notification_id ? { ...n, is_read: true } : n
        )
      )
      setUnread((c) => Math.max(0, c - 1))
    }
    if (item.related_workflow_id) {
      void router.push('/approvals')
    }
    setOpen(false)
  }

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        type="button"
        className="btn btn-link nav-link position-relative p-0 me-3"
        onClick={() => setOpen((o) => !o)}
        aria-label="Notifications"
        style={{ color: 'rgba(255,255,255,0.75)' }}
      >
        🔔
        {unread > 0 && (
          <span
            className="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger"
            style={{ fontSize: '0.65rem' }}
          >
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          className="card shadow"
          style={{
            position: 'absolute',
            right: 0,
            top: '2rem',
            width: '360px',
            maxHeight: '480px',
            overflowY: 'auto',
            zIndex: 1050,
          }}
        >
          <div className="card-header d-flex justify-content-between align-items-center py-2">
            <strong>Notifications</strong>
            {unread > 0 && (
              <button
                type="button"
                className="btn btn-link btn-sm p-0 text-muted"
                onClick={() => void handleMarkAll()}
              >
                Mark all as read
              </button>
            )}
          </div>

          {items.length === 0 ? (
            <div className="card-body text-muted small text-center py-4">No notifications</div>
          ) : (
            <ul className="list-group list-group-flush">
              {items.map((item) => (
                <li
                  key={item.notification_id}
                  className={`list-group-item list-group-item-action ${!item.is_read ? 'fw-bold' : ''}`}
                  style={{ cursor: 'pointer', backgroundColor: item.is_read ? '' : '#f0f7ff' }}
                  onClick={() => void handleItemClick(item)}
                >
                  <div className="d-flex justify-content-between">
                    <span className="small">{item.title}</span>
                    <span className="text-muted" style={{ fontSize: '0.7rem', whiteSpace: 'nowrap' }}>
                      {timeAgo(item.created_at)}
                    </span>
                  </div>
                  <div className="text-muted small" style={{ fontSize: '0.8rem' }}>
                    {(item.message || '').length > 80
                      ? `${item.message.slice(0, 80)}…`
                      : item.message}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
```

---

### File 15 — `frontend/src/components/Layout.tsx` (COMPLETE REPLACEMENT)

```tsx
/**
 * Main Layout Component
 */
import React from 'react'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/router'
import 'bootstrap/dist/css/bootstrap.min.css'
import styles from '@/styles/layout.module.css'
import { getCurrentUser, logout } from '@/services/auth'
import NotificationBell from '@/components/NotificationBell'

interface LayoutProps {
  children: React.ReactNode
}

export function Layout({ children }: LayoutProps) {
  const router = useRouter()
  const [isAuthenticated, setIsAuthenticated] = useState(false)

  useEffect(() => {
    const bootstrap = async () => {
      const user = await getCurrentUser()
      setIsAuthenticated(user !== null)
    }
    void bootstrap()
  }, [router.pathname])

  const handleLogout = async () => {
    await logout()
    router.push('/login')
  }

  return (
    <div className={styles.layout}>
      {isAuthenticated && (
        <nav className={`${styles.navbar} navbar navbar-expand-lg navbar-dark bg-dark`}>
          <div className="container-fluid">
            <Link href="/" className="navbar-brand">
              AI BA Agent
            </Link>
            <div className="collapse navbar-collapse">
              <ul className="navbar-nav ms-auto align-items-center">
                <li className="nav-item">
                  <Link href="/projects" className="nav-link">
                    Projects
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/documents" className="nav-link">
                    Documents
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/approvals" className="nav-link">
                    Approvals
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/knowledge-base" className="nav-link">
                    Knowledge Base
                  </Link>
                </li>
                <li className="nav-item d-flex align-items-center">
                  <NotificationBell />
                </li>
                <li className="nav-item">
                  <button
                    className="nav-link btn btn-link"
                    onClick={handleLogout}
                  >
                    Logout
                  </button>
                </li>
              </ul>
            </div>
          </div>
        </nav>
      )}

      
```


## License: unknown
https://github.com/RakanAji/SMARTPLANTMONITORING_KELOMPOK6/blob/ebf90229ddf582f567c06fafa486befebe2eab2d/src/components/Header.js

```
I now have a complete picture of the codebase. I'm in Ask mode so I cannot write files directly — I'll provide the complete, implementation-ready code for every file to create or modify. Apply them in order.

---

## Implementation

### File 1 — `infra/migrations/005_add_notifications.sql` (NEW)

```sql
-- 005: In-app notifications table
CREATE TABLE IF NOT EXISTS notifications (
  notification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(user_id),
  title VARCHAR(255) NOT NULL,
  message TEXT NOT NULL,
  type VARCHAR(50) NOT NULL DEFAULT 'info',
  is_read BOOLEAN DEFAULT false,
  related_doc_id UUID REFERENCES documents(doc_id),
  related_workflow_id UUID REFERENCES approval_workflows(workflow_id),
  project_name VARCHAR(255),
  doc_name VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_is_read  ON notifications(is_read);
```

---

### File 2 — `infra/migrations/006_add_workflow_roles.sql` (NEW)

```sql
-- 006: Per-workflow dynamic role assignment + submitter tracking
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS step_1_role   VARCHAR(50);
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS step_2_role   VARCHAR(50);
ALTER TABLE approval_workflows ADD COLUMN IF NOT EXISTS submitter_id  UUID REFERENCES users(user_id);
```

---

### File 3 — `backend/app/services/notifications.py` (NEW)

```python
"""DB-backed in-app notification service (distinct from notification.py which is Telegram)."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def create_notification(
    *,
    db: Session,
    user_id: UUID,
    title: str,
    message: str,
    notif_type: str = "info",
    doc_id: Optional[UUID] = None,
    workflow_id: Optional[UUID] = None,
    project_name: str = "",
    doc_name: str = "",
) -> Optional[str]:
    """Insert a notification row. Returns notification_id or None on failure."""
    try:
        nid = str(uuid4())
        db.execute(
            text(
                """
                INSERT INTO notifications
                    (notification_id, user_id, title, message, type, is_read,
                     related_doc_id, related_workflow_id, project_name, doc_name, created_at)
                VALUES
                    (:nid, :uid, :title, :msg, :type, false,
                     :doc_id, :wf_id, :pname, :dname, :ts)
                """
            ),
            {
                "nid": nid,
                "uid": str(user_id),
                "title": title,
                "msg": message,
                "type": notif_type,
                "doc_id": str(doc_id) if doc_id else None,
                "wf_id": str(workflow_id) if workflow_id else None,
                "pname": project_name,
                "dname": doc_name,
                "ts": datetime.utcnow(),
            },
        )
        return nid
    except Exception as exc:
        logger.error("create_notification failed: %s", exc)
        return None


def get_user_notifications(
    *, db: Session, user_id: UUID, limit: int = 20
) -> List[Dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT notification_id, title, message, type, is_read,
                   related_doc_id, related_workflow_id,
                   project_name, doc_name, created_at
            FROM notifications
            WHERE user_id = :uid
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"uid": str(user_id), "limit": limit},
    ).fetchall()
    return [
        {
            "notification_id": str(r[0]),
            "title": r[1],
            "message": r[2],
            "type": r[3],
            "is_read": bool(r[4]),
            "related_doc_id": str(r[5]) if r[5] else None,
            "related_workflow_id": str(r[6]) if r[6] else None,
            "project_name": r[7],
            "doc_name": r[8],
            "created_at": r[9].isoformat() if r[9] else None,
        }
        for r in rows
    ]


def mark_as_read(*, db: Session, notification_id: UUID, user_id: UUID) -> bool:
    result = db.execute(
        text(
            """
            UPDATE notifications
            SET is_read = true
            WHERE notification_id = :nid AND user_id = :uid
            """
        ),
        {"nid": str(notification_id), "uid": str(user_id)},
    )
    return (result.rowcount or 0) > 0


def mark_all_as_read(*, db: Session, user_id: UUID) -> int:
    result = db.execute(
        text(
            "UPDATE notifications SET is_read = true WHERE user_id = :uid AND is_read = false"
        ),
        {"uid": str(user_id)},
    )
    return result.rowcount or 0


def get_unread_count(*, db: Session, user_id: UUID) -> int:
    row = db.execute(
        text(
            "SELECT COUNT(*) FROM notifications WHERE user_id = :uid AND is_read = false"
        ),
        {"uid": str(user_id)},
    ).fetchone()
    return int(row[0] or 0)


def get_role_user_ids(
    *, db: Session, project_id: UUID, role: str
) -> List[str]:
    """Return user_ids that have the given role (system-wide or project-scoped)."""
    rows = db.execute(
        text(
            """
            SELECT DISTINCT u.user_id
            FROM users u
            LEFT JOIN user_projects up
                ON up.user_id = u.user_id AND up.project_id = :pid
            WHERE u.role = :role OR up.role = :role
            LIMIT 20
            """
        ),
        {"pid": str(project_id), "role": role},
    ).fetchall()
    return [str(r[0]) for r in rows]
```

---

### File 4 — `backend/app/services/workflow.py` (COMPLETE REPLACEMENT)

```python
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


# Fallback static step roles — used when a workflow pre-dates dynamic assignment
APPROVAL_STEPS = {
    1: "business_owner",
    2: "admin",
}


def _resolve_dynamic_roles(submitter_role: str) -> Tuple[str, str]:
    """Return (step_1_role, step_2_role) based on the submitter's role."""
    if submitter_role == "business_owner":
        return ("ba", "business_owner")
    if submitter_role in ("ba", "pm"):
        return ("business_owner", "ba")
    # tech_lead, legal, finance, viewer → default
    return ("business_owner", "admin")


def _get_expected_role(wf: Dict[str, Any]) -> str:
    """Return the role required for the current workflow step."""
    if wf["current_step"] == 1:
        return wf.get("step_1_role") or APPROVAL_STEPS.get(1, "business_owner")
    return wf.get("step_2_role") or APPROVAL_STEPS.get(2, "admin")


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
    step_1_role, step_2_role = _resolve_dynamic_roles(submitter_role)
    total_steps = len(APPROVAL_STEPS)

    if submitter_role == "admin":
        initial_status = "approved"
        doc_status = "approved"
    else:
        initial_status = "pending"
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
    step_2 = row[8] or APPROVAL_STEPS.get(2, "admin")

    return {
        "workflow_id": str(row[0]),
        "doc_id": str(row[1]),
        "project_id": str(row[2]),
        "current_step": int(row[3] or 1),
        "total_steps": len(APPROVAL_STEPS),
        "status": str(row[5] or "in_progress"),
        "version_id": str(row[6]) if row[6] else None,
        "step_1_role": step_1,
        "step_2_role": step_2,
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

    next_step = completed_step + 1
    final_step = len(APPROVAL_STEPS)
    new_status = "approved" if next_step > final_step else "in_progress"
    new_doc_status = "approved" if new_status == "approved" else "pending_approval"

    step_roles = {1: wf.get("step_1_role"), 2: wf.get("step_2_role")}
    next_required_role = step_roles.get(next_step) or APPROVAL_STEPS.get(next_step)

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
            SET current_step = :current_step,
                status       = :status,
                version_id   = :version_id,
                updated_at   = :updated_at
            WHERE workflow_id = :workflow_id
            """
        ),
        {
            "current_step": min(next_step, final_step),
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

    log_audit_event(
        db=db,
        project_id=UUID(wf["project_id"]),
        action="APPROVAL_APPROVED",
        entity_type="approval",
        entity_id=workflow_id,
        user_id=actor_user_id,
        old_values={"status": wf["status"], "current_step": completed_step},
        new_values={
            "status": new_status,
            "current_step": min(next_step, final_step),
            "version_id": str(version_id),
        },
        succeeded=True,
    )

    return {
        "workflow_id": wf["workflow_id"],
        "decision_id": str(decision_id),
        "status": new_status,
        "completed_step": completed_step,
        "current_step": min(next_step, final_step),
        "next_required_role": None if new_status == "approved" else next_required_role,
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
        reason=(
            f"Rejection at step {wf['current_step']}: {reason}"
            if reason
            else f"Rejection at step {wf['current_step']}"
        ),
        project_id=UUID(wf["project_id"]),
        workflow_id=workflow_id,
        db=db,
    )

    db.execute(
        text(
            """
            UPDATE approval_workflows
            SET status     = 'rejected',
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
    """Return a document for revision.

    Step 1 → sets status = returned_to_submitter, doc status = returned
    Step 2 → sets status = returned_to_step1, resets to step 1
    """
    wf = get_workflow(workflow_id, db)
    if wf is None:
        raise ValueError("Approval workflow not found")

    if wf["status"] in {"approved", "rejected"}:
        raise ValueError(f"Workflow already closed with status={wf['status']}")

    expected_role = _get_expected_role(wf)
    if actor_role != expected_role and actor_role != "admin":
        raise PermissionError(f"Current step requires role '{expected_role}'")

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
            "step_number": wf["current_step"],
            "approver_id": str(actor_user_id),
            "comments": comment,
            "created_at": now,
        },
    )

    from_step = wf["current_step"]
    if from_step == 1:
        new_wf_status = "returned_to_submitter"
        new_doc_status = "returned"
        audit_action = "APPROVAL_RETURNED_TO_SUBMITTER"
    else:
        new_wf_status = "returned_to_step1"
        new_doc_status = "pending_approval"
        audit_action = "APPROVAL_RETURNED_TO_STEP1"

    version_id = create_document_version(
        doc_id=UUID(wf["doc_id"]),
        created_by=actor_user_id,
        approval_status=new_wf_status,
        reason=f"Returned at step {from_step}: {comment}",
        project_id=UUID(wf["project_id"]),
        workflow_id=workflow_id,
        db=db,
    )

    db.execute(
        text(
            """
            UPDATE approval_workflows
            SET status       = :status,
                current_step = 1,
                version_id   = :version_id,
                updated_at   = :updated_at
            WHERE workflow_id = :workflow_id
            """
        ),
        {
            "status": new_wf_status,
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
        old_values={"status": wf["status"], "current_step": from_step},
        new_values={"status": new_wf_status, "comment": comment, "version_id": str(version_id)},
        succeeded=True,
    )

    return {
        "workflow_id": wf["workflow_id"],
        "decision_id": str(decision_id),
        "status": new_wf_status,
        "current_step": 1,
        "previous_step": from_step,
        "comment": comment,
        "version_id": str(version_id),
        "submitter_id": wf.get("submitter_id"),
        "step_1_role": wf.get("step_1_role"),
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
                (workflow_id, doc_id, project_id, current_step, total_steps, status,
                 submitter_id, created_at, updated_at)
            VALUES
                (:workflow_id, :doc_id, :project_id, 1, :total_steps,
                 'human_review_required', :submitter_id, :created_at, :updated_at)
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
        new_values={
            "status": "human_review_required",
            "doc_id": str(doc_id),
            "total_steps": len(APPROVAL_STEPS),
        },
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
        {"version_id": str(version_id), "updated_at": now, "workflow_id": str(workflow_id)},
    )
    db.execute(
        text(
            "UPDATE documents SET status = 'human_review_required', updated_at = :t WHERE doc_id = :id"
        ),
        {"t": now, "id": str(doc_id)},
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
                (version_id, doc_id, version_number, content, content_hash,
                 created_by, approval_status, created_at)
            VALUES
                (:version_id, :doc_id, :version_number, :content, :content_hash,
                 :created_by, :approval_status, :created_at)
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
```

---

### File 5 — `backend/app/services/google_drive.py` — append at bottom

Add these three functions to the end of the existing [google_drive.py](backend/app/services/google_drive.py):

```python
import re as _re

_MIME_EDIT_URLS = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        "https://docs.google.com/document/d/{id}/edit",
    "application/msword":
        "https://docs.google.com/document/d/{id}/edit",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
    "application/vnd.ms-excel":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
    "text/csv":
        "https://docs.google.com/spreadsheets/d/{id}/edit",
}


def get_drive_file_id(drive_url: str) -> Optional[str]:
    """Extract the Drive file ID from a webViewLink URL."""
    match = _re.search(r"/(?:file/)?d/([a-zA-Z0-9_-]+)", drive_url or "")
    return match.group(1) if match else None


def get_edit_url(file_id: str, mime_type: str) -> str:
    """Return the correct Google Drive / Docs / Sheets URL for the given MIME type."""
    template = _MIME_EDIT_URLS.get(mime_type)
    if template:
        return template.format(id=file_id)
    return f"https://drive.google.com/file/d/{file_id}/view"


def register_file_watch(file_id: str, document_id: str) -> bool:
    """Register a Google Drive push-notification watch (requires verified HTTPS endpoint).

    This stub logs the intent.  In production, call files().watch() with your
    verified webhook URL and store the channel/resource IDs for later expiry renewal.
    """
    logger.info(
        "register_file_watch: file_id=%s doc_id=%s (stub – HTTPS endpoint required)",
        file_id,
        document_id,
    )
    return False
```

---

### File 6 — `backend/app/middleware/rbac.py` — append one line after `require_approver`

Add after `require_approver = ...`:

```python
# Broader reviewer set: includes BA and PM (needed for dynamic step approver assignment)
require_reviewer = make_require_role(["admin", "business_owner", "ba", "pm", "legal"])
```

---

### File 7 — `backend/app/routers/approvals.py` (COMPLETE REPLACEMENT)

```python
"""Approval workflow endpoints."""

from __future__ import annotations

import logging
import os as _os
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_ba, require_readonly, require_reviewer
from app.services.db_service import get_db
from app.services import google_sheets
from app.services import notifications as notif_svc
from app.services.workflow import (
    APPROVAL_STEPS,
    approve_step,
    create_approval_workflow,
    get_workflow,
    reject_step,
    return_step,
    trigger_hitl,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Statuses considered "active / pending" for the dashboard
_PENDING_STATUSES = (
    "in_progress",
    "human_review_required",
    "returned_to_submitter",
    "returned_to_step1",
)
_COMPLETED_STATUSES = ("approved", "rejected")


class ApprovalActionRequest(BaseModel):
    comment: str = ""


class ReturnRequest(BaseModel):
    comment: str = Field(min_length=1)


class CreateApprovalRequest(BaseModel):
    document_id: UUID
    project_id: UUID
    workflow_type: str = "approval"


class RejectionRequest(BaseModel):
    reason: str = Field(min_length=1)


class HitlTriggerRequest(BaseModel):
    document_id: UUID
    project_id: Optional[UUID] = None
    reason: str = Field(min_length=1)
    risk_flags: Dict[str, Any] = {}


# ─── helpers ─────────────────────────────────────────────────────────────────

def _get_doc_project_info(workflow_id: UUID, db: Session):
    """Return (doc_title, project_name, submitter_id) for a workflow."""
    return db.execute(
        text(
            """
            SELECT d.title, p.name, aw.submitter_id
            FROM approval_workflows aw
            JOIN documents d ON d.doc_id = aw.doc_id
            JOIN projects p ON p.project_id = aw.project_id
            WHERE aw.workflow_id = :wid
            """
        ),
        {"wid": str(workflow_id)},
    ).fetchone()


def _status_badge_color(status: str) -> str:
    colors = {
        "in_progress": "info",
        "approved": "success",
        "rejected": "danger",
        "returned_to_submitter": "warning",
        "returned_to_step1": "warning",
        "human_review_required": "secondary",
    }
    return colors.get(status, "secondary")


# ─── endpoints ───────────────────────────────────────────────────────────────

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
            submitter_role=current_user.role,
            db=db,
        )
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"create_workflow_failed: {exc}")


@router.get("")
async def list_approvals(
    project_id: UUID,
    status: str = Query("pending"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """List approvals by status for dashboard views."""
    normalized = status.lower()
    if normalized not in {"pending", "completed", "all"}:
        raise HTTPException(status_code=400, detail="status must be pending, completed, or all")

    pending_in = ", ".join(f"'{s}'" for s in _PENDING_STATUSES)
    completed_in = ", ".join(f"'{s}'" for s in _COMPLETED_STATUSES)

    if normalized == "pending":
        status_filter = f"aw.status IN ({pending_in})"
    elif normalized == "completed":
        status_filter = f"aw.status IN ({completed_in})"
    else:
        status_filter = f"aw.status IN ({pending_in}, {completed_in})"

    offset = (page - 1) * page_size

    rows = db.execute(
        text(
            f"""
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
                    d.doc_type,
                    p.name AS project_name,
                    COALESCE(u.full_name, u.email, '') AS submitter_name,
                    u.role AS submitter_role,
                    aw.step_1_role,
                    aw.step_2_role,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                LEFT JOIN documents d ON d.doc_id = aw.doc_id
                LEFT JOIN projects p ON p.project_id = aw.project_id
                LEFT JOIN users u ON u.user_id = aw.submitter_id
                WHERE aw.project_id = :project_id
                  AND {status_filter}
            )
            SELECT workflow_id, doc_id, doc_title, current_step, total_steps, status,
                   updated_at, google_drive_link, doc_type, project_name,
                   submitter_name, submitter_role, step_1_role, step_2_role
            FROM ranked
            WHERE rn = 1
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"project_id": str(project_id), "limit": page_size, "offset": offset},
    ).fetchall()

    count_row = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT aw.doc_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                WHERE aw.project_id = :project_id AND {status_filter}
            )
            SELECT COUNT(*) FROM ranked WHERE rn = 1
            """
        ),
        {"project_id": str(project_id)},
    ).fetchone()

    items = [
        {
            "workflow_id": str(r[0]),
            "doc_id": str(r[1]),
            "doc_title": r[2] or None,
            "current_step": int(r[3] or 1),
            "total_steps": len(APPROVAL_STEPS),
            "status": r[5],
            "status_color": _status_badge_color(r[5]),
            "updated_at": r[6].isoformat() if r[6] else None,
            "google_drive_link": r[7] or None,
            "doc_type": r[8] or None,
            "project_name": r[9] or None,
            "submitter_name": r[10] or None,
            "submitter_role": r[11] or None,
            "step_1_role": r[12] or None,
            "step_2_role": r[13] or None,
        }
        for r in rows
    ]

    return {
        "project_id": str(project_id),
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
    pending_in = ", ".join(f"'{s}'" for s in _PENDING_STATUSES)
    offset = (page - 1) * page_size

    rows = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT
                    aw.workflow_id, aw.doc_id,
                    COALESCE(d.title, '') AS doc_title,
                    aw.current_step, aw.total_steps, aw.status, aw.updated_at,
                    d.google_drive_link, d.doc_type, p.name AS project_name,
                    COALESCE(u.full_name, u.email, '') AS submitter_name,
                    u.role AS submitter_role, aw.step_1_role, aw.step_2_role,
                    ROW_NUMBER() OVER (
                        PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC
                    ) AS rn
                FROM approval_workflows aw
                LEFT JOIN documents d ON d.doc_id = aw.doc_id
                LEFT JOIN projects p ON p.project_id = aw.project_id
                LEFT JOIN users u ON u.user_id = aw.submitter_id
                WHERE aw.project_id = :project_id
                  AND aw.status IN ({pending_in})
            )
            SELECT workflow_id, doc_id, doc_title, current_step, total_steps, status,
                   updated_at, google_drive_link, doc_type, project_name,
                   submitter_name, submitter_role, step_1_role, step_2_role
            FROM ranked
            WHERE rn = 1
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"project_id": str(project_id), "limit": page_size, "offset": offset},
    ).fetchall()

    count_row = db.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT aw.doc_id,
                    ROW_NUMBER() OVER (PARTITION BY aw.doc_id
                        ORDER BY aw.created_at DESC, aw.updated_at DESC, aw.workflow_id DESC) AS rn
                FROM approval_workflows aw
                WHERE aw.project_id = :project_id
                  AND aw.status IN ({pending_in})
            )
            SELECT COUNT(*) FROM ranked WHERE rn = 1
            """
        ),
        {"project_id": str(project_id)},
    ).fetchone()

    items = [
        {
            "workflow_id": str(r[0]),
            "doc_id": str(r[1]),
            "doc_title": r[2] or None,
            "current_step": int(r[3] or 1),
            "total_steps": len(APPROVAL_STEPS),
            "status": r[5],
            "status_color": _status_badge_color(r[5]),
            "updated_at": r[6].isoformat() if r[6] else None,
            "google_drive_link": r[7] or None,
            "doc_type": r[8] or None,
            "project_name": r[9] or None,
            "submitter_name": r[10] or None,
            "submitter_role": r[11] or None,
            "step_1_role": r[12] or None,
            "step_2_role": r[13] or None,
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
    current_user: TokenUser = Depends(require_reviewer),
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

    # ── Google Sheets update (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            google_sheets.update_approval_row(
                project_name=info[1] or "",
                file_name=_os.path.splitext(info[0] or "")[0],
                approver_name=current_user.email,
                status="Approved",
                comment=request.comment,
            )
    except Exception as exc:
        logger.warning("Sheets update failed after approve (%s): %s", workflow_id, exc)

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            completed_step = result.get("completed_step", 1)
            final_approved = result["status"] == "approved"

            if submitter_id:
                title = "Document Approved ✅" if final_approved else "Document Progressed"
                if final_approved:
                    msg = f"Project {project_name}: '{doc_title}' has been fully approved!"
                else:
                    msg = f"Project {project_name}: '{doc_title}' passed step {completed_step} review."
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title=title,
                    message=msg,
                    notif_type="approved",
                    doc_id=UUID(result["workflow_id"]) if False else None,
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()
    except Exception as exc:
        logger.warning("Notification failed after approve (%s): %s", workflow_id, exc)

    return result


@router.post("/{workflow_id}/reject")
async def reject_document(
    workflow_id: UUID,
    request: RejectionRequest,
    current_user: TokenUser = Depends(require_reviewer),
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

    # ── Google Sheets update (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            google_sheets.update_approval_row(
                project_name=info[1] or "",
                file_name=_os.path.splitext(info[0] or "")[0],
                approver_name=current_user.email,
                status="Rejected",
                comment=request.reason,
            )
    except Exception as exc:
        logger.warning("Sheets update failed after reject (%s): %s", workflow_id, exc)

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            if submitter_id:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title="Document Rejected",
                    message=f"Project {project_name}: '{doc_title}' was rejected. Reason: {request.reason}",
                    notif_type="rejected",
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()
    except Exception as exc:
        logger.warning("Notification failed after reject (%s): %s", workflow_id, exc)

    return result


@router.post("/{workflow_id}/return")
async def return_document(
    workflow_id: UUID,
    request: ReturnRequest,
    current_user: TokenUser = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    """Return a document for revision.

    Step 1 → returned_to_submitter (document status = returned)
    Step 2 → returned_to_step1 (resets to step 1)
    """
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

    # ── In-app notifications (best-effort) ────────────────────────────────
    try:
        info = _get_doc_project_info(workflow_id, db)
        if info:
            doc_title, project_name, submitter_id = info[0], info[1], info[2]
            new_status = result["status"]

            if new_status == "returned_to_submitter" and submitter_id:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(submitter_id)),
                    title="Document Returned",
                    message=(
                        f"Project {project_name}: '{doc_title}' has been returned "
                        f"for revision. Comment: {request.comment}"
                    ),
                    notif_type="returned",
                    workflow_id=workflow_id,
                    project_name=project_name or "",
                    doc_name=doc_title or "",
                )
                db.commit()

            elif new_status == "returned_to_step1":
                step_1_role = result.get("step_1_role") or "business_owner"
                wf_row = db.execute(
                    text("SELECT project_id FROM approval_workflows WHERE workflow_id = :wid"),
                    {"wid": str(workflow_id)},
                ).fetchone()
                if wf_row:
                    approver_ids = notif_svc.get_role_user_ids(
                        db=db,
                        project_id=UUID(str(wf_row[0])),
                        role=step_1_role,
                    )
                    for uid_str in approver_ids:
                        notif_svc.create_notification(
                            db=db,
                            user_id=UUID(uid_str),
                            title="Re-review Required",
                            message=(
                                f"Project {project_name}: '{doc_title}' has been "
                                f"returned to you for re-review. Comment: {request.comment}"
                            ),
                            notif_type="returned_to_step1",
                            workflow_id=workflow_id,
                            project_name=project_name or "",
                            doc_name=doc_title or "",
                        )
                    db.commit()
    except Exception as exc:
        logger.warning("Notification failed after return (%s): %s", workflow_id, exc)

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
        "status_color": _status_badge_color(workflow["status"]),
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
```

---

### File 8 — `backend/app/routers/documents.py` (COMPLETE REPLACEMENT)

```python
"""
Document management endpoints.

POST /upload            – Accept file + metadata, store to DB, upload to Drive, trigger pipeline
POST /{doc_id}/resubmit – Resubmit a returned document for re-review
GET  /{doc_id}/status   – Return current processing status + progress
"""
import hashlib
import logging
import mimetypes
import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile, File
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_ba, require_readonly
from app.services.db_service import get_db
from app.services import google_drive, google_sheets, elevenlabs, n8n_webhook
from app.services import notifications as notif_svc
from app.services.workflow import _resolve_dynamic_roles

logger = logging.getLogger(__name__)
router = APIRouter()

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
    project_folder_id: Optional[str] = None,
) -> None:
    """Background task: upload to Google Drive, trigger STT + n8n, update status."""
    db: Session = next(get_db())
    try:
        db.execute(
            text("UPDATE documents SET status = :s, updated_at = :t WHERE doc_id = :id"),
            {"s": STATUS_PROCESSING, "t": datetime.utcnow(), "id": doc_id},
        )
        db.commit()

        drive_url: Optional[str] = google_drive.upload_file(
            file_bytes, filename, mime_type, project_folder_id
        )
        if drive_url:
            db.execute(
                text(
                    "UPDATE documents SET google_drive_link = :url, updated_at = :t WHERE doc_id = :id"
                ),
                {"url": drive_url, "t": datetime.utcnow(), "id": doc_id},
            )
            db.commit()

        transcript: Optional[str] = None
        if elevenlabs.is_audio(mime_type):
            transcript = await elevenlabs.transcribe(file_bytes, filename, mime_type)
            if transcript:
                version_id = str(uuid.uuid4())
                db.execute(
                    text(
                        """INSERT INTO document_versions
                             (version_id, doc_id, version_number, content, approval_status, created_at)
                           VALUES (:vid, :did, 1, :content, 'pending', :ts)"""
                    ),
                    {
                        "vid": version_id,
                        "did": doc_id,
                        "content": transcript,
                        "ts": datetime.utcnow(),
                    },
                )
                db.commit()

        await n8n_webhook.trigger_document_workflow(
            workflow_id=workflow_id,
            document_id=doc_id,
            google_drive_url=drive_url,
            file_type=mime_type,
            filename=filename,
        )

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
    current_user: TokenUser = Depends(require_ba),
    db: Session = Depends(get_db),
):
    """
    Upload a document for processing.

    - Requires role: ba / pm / tech_lead / admin  (HTTP 403 otherwise)
    - Returns: {document_id, workflow_id, status: "PENDING"}
    """
    mime_type: str = file.content_type or ""
    if not mime_type or mime_type == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(file.filename or "")
        mime_type = guessed or "application/octet-stream"

    doc_title  = title or (file.filename or "Untitled")
    doc_id     = str(uuid.uuid4())
    workflow_id = str(uuid.uuid4())

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # ── 1. Insert document record ─────────────────────────────────────────
    try:
        db.execute(
            text(
                """INSERT INTO documents
                     (doc_id, project_id, title, doc_type, status, created_by, created_at, updated_at)
                   VALUES (:doc_id, :project_id, :title, :doc_type, :status, :created_by, :now, :now)"""
            ),
            {
                "doc_id":     doc_id,
                "project_id": project_id,
                "title":      doc_title,
                "doc_type":   mime_type,
                "status":     STATUS_PENDING,
                "created_by": current_user.user_id,
                "now":        datetime.utcnow(),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to insert document record: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to store document metadata")

    # ── 2. Determine dynamic roles ────────────────────────────────────────
    step_1_role, step_2_role = _resolve_dynamic_roles(current_user.role)
    auto_approve = current_user.role == "admin"
    initial_wf_status = "approved" if auto_approve else "in_progress"

    # ── 3. Create approval_workflow entry ─────────────────────────────────
    try:
        db.execute(
            text(
                """INSERT INTO approval_workflows
                     (workflow_id, doc_id, project_id, status, current_step, total_steps,
                      step_1_role, step_2_role, submitter_id, created_at, updated_at)
                   VALUES
                     (:wid, :did, :pid, :status, 1, 2,
                      :step_1_role, :step_2_role, :submitter_id, :now, :now)"""
            ),
            {
                "wid":          workflow_id,
                "did":          doc_id,
                "pid":          project_id,
                "status":       initial_wf_status,
                "step_1_role":  step_1_role,
                "step_2_role":  step_2_role,
                "submitter_id": str(current_user.user_id),
                "now":          datetime.utcnow(),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to create approval workflow entry: %s", exc)

    # ── 4. Fetch project Drive folder ─────────────────────────────────────
    project_folder_id: Optional[str] = None
    project_name: str = ""
    try:
        proj_row = db.execute(
            text("SELECT name, google_drive_folder_id FROM projects WHERE project_id = :pid"),
            {"pid": project_id},
        ).fetchone()
        if proj_row:
            project_name     = proj_row[0] or ""
            project_folder_id = proj_row[1] or None
            if project_folder_id is None:
                project_folder_id = google_drive.create_project_folder(project_name)
                if project_folder_id:
                    db.execute(
                        text(
                            "UPDATE projects SET google_drive_folder_id = :fid WHERE project_id = :pid"
                        ),
                        {"fid": project_folder_id, "pid": project_id},
                    )
                    db.commit()
    except Exception as exc:
        logger.warning("Could not fetch project Drive folder for %s: %s", project_id, exc)

    # ── 5. Append row to Google Sheets backlog (best-effort) ──────────────
    try:
        import os as _os
        file_name_no_ext = _os.path.splitext(doc_title)[0]
        google_sheets.append_upload_row(
            user_name=current_user.email,
            project_name=project_name,
            file_name=file_name_no_ext,
            upload_date=datetime.utcnow().strftime("%d-%b-%Y"),
        )
    except Exception as exc:
        logger.warning("Sheets append_upload_row failed for %s: %s", doc_id, exc)

    # ── 6. Notify step-1 approvers (best-effort) ──────────────────────────
    try:
        approver_ids = notif_svc.get_role_user_ids(
            db=db, project_id=UUID(project_id), role=step_1_role
        )
        for uid_str in approver_ids:
            notif_svc.create_notification(
                db=db,
                user_id=UUID(uid_str),
                title="New Review Request",
                message=f"Project {project_name}: '{doc_title}' needs your review.",
                notif_type="upload",
                workflow_id=UUID(workflow_id),
                project_name=project_name,
                doc_name=doc_title,
            )
        db.commit()
    except Exception as exc:
        logger.warning("Upload notification failed for %s: %s", doc_id, exc)

    # ── 7. Queue background processing ────────────────────────────────────
    background_tasks.add_task(
        _process_document,
        doc_id,
        workflow_id,
        file_bytes,
        file.filename or doc_title,
        mime_type,
        project_folder_id,
    )

    logger.info(
        "Document %s queued for processing by %s (workflow %s)",
        doc_id, current_user.email, workflow_id,
    )
    return {
        "document_id":  doc_id,
        "workflow_id":  workflow_id,
        "filename":     file.filename,
        "status":       STATUS_PENDING,
        "uploaded_by":  current_user.email,
        "step_1_role":  step_1_role,
        "step_2_role":  step_2_role,
    }


@router.post("/{doc_id}/resubmit")
async def resubmit_document(
    doc_id: str,
    current_user: TokenUser = Depends(require_ba),
    db: Session = Depends(get_db),
):
    """Resubmit a returned document for re-review (only the original submitter or admin)."""
    doc_row = db.execute(
        text(
            "SELECT doc_id, project_id, title, status, created_by FROM documents WHERE doc_id = :did"
        ),
        {"did": doc_id},
    ).fetchone()
    if doc_row is None:
        raise HTTPException(status_code=404, detail="document_not_found")

    if current_user.role != "admin" and str(doc_row[4]) != str(current_user.user_id):
        raise HTTPException(status_code=403, detail="Only the document submitter can resubmit")

    if doc_row[3] != "returned":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not in 'returned' status (current: {doc_row[3]})",
        )

    wf_row = db.execute(
        text(
            """
            SELECT workflow_id, step_1_role, step_2_role, project_id
            FROM approval_workflows
            WHERE doc_id = :did AND status = 'returned_to_submitter'
            ORDER BY updated_at DESC LIMIT 1
            """
        ),
        {"did": doc_id},
    ).fetchone()

    now = datetime.utcnow()

    # Create new document version
    prev = db.execute(
        text(
            "SELECT version_number, content FROM document_versions WHERE doc_id = :did ORDER BY version_number DESC LIMIT 1"
        ),
        {"did": doc_id},
    ).fetchone()
    new_version_num = (int(prev[0]) + 1) if prev else 1
    content = f"{prev[1] or ''}\n\n[resubmitted by {current_user.email}]".strip() if prev else "[resubmitted]"
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    version_id = str(uuid.uuid4())

    db.execute(
        text(
            """
            INSERT INTO document_versions
                (version_id, doc_id, version_number, content, content_hash,
                 created_by, approval_status, created_at)
            VALUES (:vid, :did, :vn, :content, :hash, :uid, 'pending', :ts)
            """
        ),
        {
            "vid": version_id, "did": doc_id, "vn": new_version_num,
            "content": content, "hash": content_hash,
            "uid": str(current_user.user_id), "ts": now,
        },
    )

    db.execute(
        text("UPDATE documents SET status = 'pending_approval', updated_at = :ts WHERE doc_id = :did"),
        {"ts": now, "did": doc_id},
    )

    wf_id_str: Optional[str] = None
    step_1_role = "business_owner"
    project_id_str = str(doc_row[1])

    if wf_row:
        wf_id_str   = str(wf_row[0])
        step_1_role = wf_row[1] or "business_owner"
        db.execute(
            text(
                "UPDATE approval_workflows SET status = 'in_progress', current_step = 1, updated_at = :ts WHERE workflow_id = :wid"
            ),
            {"ts": now, "wid": wf_id_str},
        )

    db.commit()

    # Notify step-1 approvers (best-effort)
    try:
        pname_row = db.execute(
            text("SELECT name FROM projects WHERE project_id = :pid"),
            {"pid": project_id_str},
        ).fetchone()
        pname = pname_row[0] if pname_row else ""
        approver_ids = notif_svc.get_role_user_ids(
            db=db, project_id=UUID(project_id_str), role=step_1_role
        )
        for uid_str in approver_ids:
            notif_svc.create_notification(
                db=db,
                user_id=UUID(uid_str),
                title="Document Resubmitted",
                message=f"Project {pname}: '{doc_row[2]}' has been revised and resubmitted.",
                notif_type="resubmit",
                workflow_id=UUID(wf_id_str) if wf_id_str else None,
                project_name=pname,
                doc_name=doc_row[2] or "",
            )
        db.commit()
    except Exception as exc:
        logger.warning("Resubmit notification failed for %s: %s", doc_id, exc)

    return {
        "document_id":    doc_id,
        "status":         "pending_approval",
        "version_id":     version_id,
        "resubmitted_by": current_user.email,
    }


@router.get("")
async def list_documents(
    project_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """List documents with optional project filter (auth required)."""
    safe_limit  = max(1, min(limit, 200))
    safe_offset = max(0, offset)

    if project_id:
        rows = db.execute(
            text(
                """SELECT doc_id, project_id, title, doc_type, status, updated_at
                   FROM documents WHERE project_id = :pid
                   ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"""
            ),
            {"pid": project_id, "limit": safe_limit, "offset": safe_offset},
        ).fetchall()
    else:
        rows = db.execute(
            text(
                """SELECT doc_id, project_id, title, doc_type, status, updated_at
                   FROM documents
                   ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"""
            ),
            {"limit": safe_limit, "offset": safe_offset},
        ).fetchall()

    return {
        "requested_by": current_user.email,
        "project_id": project_id,
        "total": len(rows),
        "documents": [
            {
                "doc_id":     str(r[0]),
                "project_id": str(r[1]),
                "title":      r[2],
                "doc_type":   r[3],
                "status":     r[4],
                "updated_at": r[5].isoformat() if r[5] else None,
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
    """Get the current processing status of a document."""
    try:
        row = db.execute(
            text(
                "SELECT doc_id, title, status, doc_type, google_drive_link, updated_at FROM documents WHERE doc_id = :id"
            ),
            {"id": doc_id},
        ).fetchone()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"db_error: {exc}")

    if row is None:
        raise HTTPException(status_code=404, detail="document_not_found")

    status = row[2]
    progress_map = {
        STATUS_PENDING:    10,
        STATUS_PROCESSING: 50,
        STATUS_COMPLETED:  100,
        STATUS_FAILED:     0,
    }

    # Build edit URL if Drive link exists
    edit_url: Optional[str] = None
    drive_link = row[4]
    if drive_link:
        file_id = google_drive.get_drive_file_id(drive_link)
        if file_id:
            edit_url = google_drive.get_edit_url(file_id, row[3] or "")

    return {
        "document_id":      str(row[0]),
        "title":            row[1],
        "status":           status,
        "progress":         progress_map.get(status, 0),
        "doc_type":         row[3],
        "google_drive_url": drive_link,
        "edit_url":         edit_url,
        "updated_at":       row[5].isoformat() if row[5] else None,
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
                "version_id":       str(r[0]),
                "version_number":   int(r[1]),
                "content_hash":     r[2],
                "approval_status":  r[3],
                "created_by":       str(r[4]) if r[4] else None,
                "created_at":       r[5].isoformat() if r[5] else None,
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
            SELECT version_id, version_number, content, content_hash, approval_status, created_by, created_at
            FROM document_versions
            WHERE doc_id = :doc_id AND version_id = :version_id
            """
        ),
        {"doc_id": doc_id, "version_id": version_id},
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="version_not_found")

    return {
        "version_id":       str(row[0]),
        "version_number":   int(row[1]),
        "content":          row[2],
        "content_hash":     row[3],
        "approval_status":  row[4],
        "created_by":       str(row[5]) if row[5] else None,
        "created_at":       row[6].isoformat() if row[6] else None,
    }
```

---

### File 9 — `backend/app/routers/notifications.py` (COMPLETE REPLACEMENT)

```python
"""Notification endpoints — Telegram + in-app DB notifications."""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.middleware.rbac import TokenUser, require_admin, require_readonly
from app.services.db_service import get_db
from app.services.notification import notification_service
from app.services.telegram_bot import telegram_bot_service
from app.services import notifications as notif_svc

router = APIRouter()


class NotificationSendRequest(BaseModel):
    message: str = Field(min_length=1)
    type: str = "info"
    project_id: Optional[UUID] = None
    metadata: Dict[str, Any] = {}


class TelegramUpdateRequest(BaseModel):
    update_id: Optional[int] = None
    message: Dict[str, Any] = {}


# ─── Telegram endpoints (unchanged) ──────────────────────────────────────────

@router.post("/send")
async def send_notification(
    request: NotificationSendRequest,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Send a notification through the configured Telegram bot."""
    result = await notification_service.dispatch_notification(
        db=db,
        message=request.message,
        notification_type=request.type,
        actor_user_id=UUID(str(current_user.user_id)),
        project_id=request.project_id,
        metadata=request.metadata,
    )
    db.commit()
    return result


@router.post("/telegram/webhook")
async def telegram_webhook(
    payload: TelegramUpdateRequest,
    db: Session = Depends(get_db),
):
    """Receive Telegram updates and reply to /status, /backlog, /help."""
    message = payload.message or {}
    command_text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id")) if chat.get("id") is not None else None

    if not command_text.startswith("/"):
        return {"ok": True, "handled": False}

    reply_text = notification_service.process_telegram_command(command_text, db)
    sent = await telegram_bot_service.send_message(reply_text, chat_id=chat_id)
    return {
        "ok": True,
        "handled": True,
        "command": command_text.split(" ")[0].lower(),
        "sent": sent,
    }


@router.post("/approval-reminders/run")
async def run_approval_reminders(
    current_user: TokenUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Manual trigger for approval reminders (used by n8n workflow E)."""
    result = await notification_service.send_approval_reminders(db)
    return {**result, "triggered_by": current_user.email}


# ─── In-app DB notifications ─────────────────────────────────────────────────

@router.get("")
async def get_notifications(
    limit: int = 20,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Get in-app notifications for the current user."""
    items = notif_svc.get_user_notifications(
        db=db, user_id=UUID(str(current_user.user_id)), limit=min(limit, 100)
    )
    unread = notif_svc.get_unread_count(db=db, user_id=UUID(str(current_user.user_id)))
    return {"notifications": items, "unread_count": unread}


@router.get("/unread-count")
async def get_unread_count(
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Return unread notification count for the current user."""
    count = notif_svc.get_unread_count(db=db, user_id=UUID(str(current_user.user_id)))
    return {"count": count}


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Mark a single notification as read."""
    updated = notif_svc.mark_as_read(
        db=db,
        notification_id=notification_id,
        user_id=UUID(str(current_user.user_id)),
    )
    db.commit()
    return {"notification_id": str(notification_id), "marked_read": updated}


@router.post("/read-all")
async def mark_all_read(
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Mark all notifications as read for the current user."""
    count = notif_svc.mark_all_as_read(db=db, user_id=UUID(str(current_user.user_id)))
    db.commit()
    return {"marked_count": count}
```

---

### File 10 — `backend/app/routers/webhooks.py` (NEW)

```python
"""Webhook receivers for external integrations (Google Drive change notifications)."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.db_service import get_db
from app.services import notifications as notif_svc

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/drive-changes")
async def drive_changes_webhook(
    request: Request,
    x_goog_resource_id: str = Header(None, alias="X-Goog-Resource-Id"),
    x_goog_channel_id: str = Header(None, alias="X-Goog-Channel-Id"),
    x_goog_resource_state: str = Header(None, alias="X-Goog-Resource-State"),
    db: Session = Depends(get_db),
):
    """Receive Google Drive push notifications for file changes.

    channel_id convention: "doc:{document_id}" (set during register_file_watch).
    """
    logger.info(
        "Drive webhook: channel=%s resource=%s state=%s",
        x_goog_channel_id, x_goog_resource_id, x_goog_resource_state,
    )

    if x_goog_resource_state == "sync":
        return {"ok": True, "type": "sync"}

    if x_goog_channel_id and x_goog_channel_id.startswith("doc:"):
        try:
            doc_id_str = x_goog_channel_id[4:]
            row = db.execute(
                text(
                    """
                    SELECT d.title, d.created_by, p.name
                    FROM documents d
                    JOIN projects p ON p.project_id = d.project_id
                    WHERE d.doc_id = :did
                    """
                ),
                {"did": doc_id_str},
            ).fetchone()
            if row and row[1]:
                notif_svc.create_notification(
                    db=db,
                    user_id=UUID(str(row[1])),
                    title="Document Modified",
                    message=f"Your document '{row[0]}' in project '{row[2]}' was modified.",
                    notif_type="file_edited",
                    project_name=row[2] or "",
                    doc_name=row[0] or "",
                )
                db.commit()
        except Exception as exc:
            logger.warning("drive_changes_webhook notification failed: %s", exc)

    return {"ok": True, "type": x_goog_resource_state or "change"}
```

---

### File 11 — `backend/app/main.py` — add webhooks router

In [main.py](backend/app/main.py), add after the existing imports:

```python
from .routers import webhooks as webhooks_router
```

And add the router registration after the existing `app.include_router(notifications_router...)`:

```python
app.include_router(
    webhooks_router.router,
    prefix="/api/webhooks",
    tags=["webhooks"],
)
```

---

### File 12 — `frontend/src/services/documents.ts` — add to end of file

Append to the existing [documents.ts](frontend/src/services/documents.ts):

```typescript
export async function returnWorkflow(workflowId: string, comment: string): Promise<void> {
  await approvalsClient.post(`/${workflowId}/return`, { comment })
}

export async function resubmitDocument(docId: string): Promise<void> {
  const docsClient2 = axios.create({ baseURL: '/api/documents', withCredentials: true })
  await docsClient2.post(`/${docId}/resubmit`)
}

export interface ApprovalItemExtended extends PendingApprovalItem {
  project_name?: string | null
  submitter_name?: string | null
  submitter_role?: string | null
  doc_type?: string | null
  status_color?: string | null
  step_1_role?: string | null
  step_2_role?: string | null
}
```

---

### File 13 — `frontend/src/services/notifications.ts` (NEW)

```typescript
import axios from 'axios'

export interface NotificationItem {
  notification_id: string
  title: string
  message: string
  type: string
  is_read: boolean
  related_doc_id: string | null
  related_workflow_id: string | null
  project_name: string | null
  doc_name: string | null
  created_at: string | null
}

const client = axios.create({
  baseURL: '/api/notifications',
  withCredentials: true,
})

export async function getNotifications(limit = 20): Promise<{ notifications: NotificationItem[]; unread_count: number }> {
  const response = await client.get('', { params: { limit } })
  return response.data
}

export async function getUnreadCount(): Promise<number> {
  const response = await client.get('/unread-count')
  return (response.data as { count: number }).count
}

export async function markAsRead(notificationId: string): Promise<void> {
  await client.post(`/${notificationId}/read`)
}

export async function markAllAsRead(): Promise<void> {
  await client.post('/read-all')
}
```

---

### File 14 — `frontend/src/components/NotificationBell.tsx` (NEW)

```tsx
import React, { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/router'
import {
  getNotifications,
  getUnreadCount,
  markAllAsRead,
  markAsRead,
  type NotificationItem,
} from '@/services/notifications'

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} minute${mins > 1 ? 's' : ''} ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs} hour${hrs > 1 ? 's' : ''} ago`
  return `${Math.floor(hrs / 24)} day${Math.floor(hrs / 24) > 1 ? 's' : ''} ago`
}

export default function NotificationBell() {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<NotificationItem[]>([])
  const [unread, setUnread] = useState(0)
  const ref = useRef<HTMLDivElement>(null)

  const load = async () => {
    try {
      const { notifications, unread_count } = await getNotifications(20)
      setItems(notifications)
      setUnread(unread_count)
    } catch {
      // silent — not authenticated yet
    }
  }

  useEffect(() => {
    void load()
    const interval = setInterval(() => void load(), 30000)
    return () => clearInterval(interval)
  }, [])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleMarkAll = async () => {
    await markAllAsRead()
    setUnread(0)
    setItems((prev) => prev.map((n) => ({ ...n, is_read: true })))
  }

  const handleItemClick = async (item: NotificationItem) => {
    if (!item.is_read) {
      await markAsRead(item.notification_id)
      setItems((prev) =>
        prev.map((n) =>
          n.notification_id === item.notification_id ? { ...n, is_read: true } : n
        )
      )
      setUnread((c) => Math.max(0, c - 1))
    }
    if (item.related_workflow_id) {
      void router.push('/approvals')
    }
    setOpen(false)
  }

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        type="button"
        className="btn btn-link nav-link position-relative p-0 me-3"
        onClick={() => setOpen((o) => !o)}
        aria-label="Notifications"
        style={{ color: 'rgba(255,255,255,0.75)' }}
      >
        🔔
        {unread > 0 && (
          <span
            className="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger"
            style={{ fontSize: '0.65rem' }}
          >
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          className="card shadow"
          style={{
            position: 'absolute',
            right: 0,
            top: '2rem',
            width: '360px',
            maxHeight: '480px',
            overflowY: 'auto',
            zIndex: 1050,
          }}
        >
          <div className="card-header d-flex justify-content-between align-items-center py-2">
            <strong>Notifications</strong>
            {unread > 0 && (
              <button
                type="button"
                className="btn btn-link btn-sm p-0 text-muted"
                onClick={() => void handleMarkAll()}
              >
                Mark all as read
              </button>
            )}
          </div>

          {items.length === 0 ? (
            <div className="card-body text-muted small text-center py-4">No notifications</div>
          ) : (
            <ul className="list-group list-group-flush">
              {items.map((item) => (
                <li
                  key={item.notification_id}
                  className={`list-group-item list-group-item-action ${!item.is_read ? 'fw-bold' : ''}`}
                  style={{ cursor: 'pointer', backgroundColor: item.is_read ? '' : '#f0f7ff' }}
                  onClick={() => void handleItemClick(item)}
                >
                  <div className="d-flex justify-content-between">
                    <span className="small">{item.title}</span>
                    <span className="text-muted" style={{ fontSize: '0.7rem', whiteSpace: 'nowrap' }}>
                      {timeAgo(item.created_at)}
                    </span>
                  </div>
                  <div className="text-muted small" style={{ fontSize: '0.8rem' }}>
                    {(item.message || '').length > 80
                      ? `${item.message.slice(0, 80)}…`
                      : item.message}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
```

---

### File 15 — `frontend/src/components/Layout.tsx` (COMPLETE REPLACEMENT)

```tsx
/**
 * Main Layout Component
 */
import React from 'react'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/router'
import 'bootstrap/dist/css/bootstrap.min.css'
import styles from '@/styles/layout.module.css'
import { getCurrentUser, logout } from '@/services/auth'
import NotificationBell from '@/components/NotificationBell'

interface LayoutProps {
  children: React.ReactNode
}

export function Layout({ children }: LayoutProps) {
  const router = useRouter()
  const [isAuthenticated, setIsAuthenticated] = useState(false)

  useEffect(() => {
    const bootstrap = async () => {
      const user = await getCurrentUser()
      setIsAuthenticated(user !== null)
    }
    void bootstrap()
  }, [router.pathname])

  const handleLogout = async () => {
    await logout()
    router.push('/login')
  }

  return (
    <div className={styles.layout}>
      {isAuthenticated && (
        <nav className={`${styles.navbar} navbar navbar-expand-lg navbar-dark bg-dark`}>
          <div className="container-fluid">
            <Link href="/" className="navbar-brand">
              AI BA Agent
            </Link>
            <div className="collapse navbar-collapse">
              <ul className="navbar-nav ms-auto align-items-center">
                <li className="nav-item">
                  <Link href="/projects" className="nav-link">
                    Projects
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/documents" className="nav-link">
                    Documents
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/approvals" className="nav-link">
                    Approvals
                  </Link>
                </li>
                <li className="nav-item">
                  <Link href="/knowledge-base" className="nav-link">
                    Knowledge Base
                  </Link>
                </li>
                <li className="nav-item d-flex align-items-center">
                  <NotificationBell />
                </li>
                <li className="nav-item">
                  <button
                    className="nav-link btn btn-link"
                    onClick={handleLogout}
                  >
                    Logout
                  </button>
                </li>
              </ul>
            </div>
          </div>
        </nav>
      )}

      
```

