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
    *, db: Session, user_id: UUID, limit: int = 20, unread_only: bool = False
) -> List[Dict[str, Any]]:
    unread_clause = "AND is_read = false" if unread_only else ""
    rows = db.execute(
        text(
            f"""
            SELECT notification_id, title, message, type, is_read,
                   related_doc_id, related_workflow_id,
                   project_name, doc_name, created_at
            FROM notifications
            WHERE user_id = :uid
            {unread_clause}
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
