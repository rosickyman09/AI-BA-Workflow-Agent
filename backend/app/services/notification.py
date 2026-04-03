"""Notification dispatcher service for Telegram and workflow reminders."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.audit import log_audit_event
from app.services.telegram_bot import telegram_bot_service


class NotificationService:
    """Business logic for notification dispatch and Telegram commands."""

    def get_pending_approval_count(self, db: Session, project_id: Optional[UUID] = None) -> int:
        if project_id:
            row = db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM approval_workflows
                    WHERE status IN ('in_progress', 'human_review_required')
                      AND project_id = :project_id
                    """
                ),
                {"project_id": str(project_id)},
            ).fetchone()
        else:
            row = db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM approval_workflows
                    WHERE status IN ('in_progress', 'human_review_required')
                    """
                )
            ).fetchone()
        return int(row[0] or 0)

    def get_overdue_backlog_items(self, db: Session, limit: int = 10) -> List[Dict[str, Any]]:
        rows = db.execute(
            text(
                """
                SELECT
                    aw.workflow_id,
                    d.title,
                    aw.created_at,
                    COALESCE(u.full_name, u.email, 'Unassigned') AS owner_name
                FROM approval_workflows aw
                JOIN documents d ON d.doc_id = aw.doc_id
                LEFT JOIN users u ON u.user_id = d.created_by
                WHERE aw.status IN ('in_progress', 'human_review_required')
                  AND aw.created_at < NOW() - INTERVAL '2 days'
                ORDER BY aw.created_at ASC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).fetchall()

        items: List[Dict[str, Any]] = []
        for row in rows:
            items.append(
                {
                    "workflow_id": str(row[0]),
                    "title": row[1],
                    "created_at": row[2],
                    "owner": row[3],
                }
            )
        return items

    def _help_message(self) -> str:
        return (
            "Available commands:\n"
            "/status - show pending approvals count\n"
            "/backlog - show overdue items (pending > 2 days)\n"
            "/help - show this help message"
        )

    def _status_message(self, db: Session) -> str:
        pending = self.get_pending_approval_count(db)
        return f"Approval status: {pending} pending workflow(s)."

    def _backlog_message(self, db: Session) -> str:
        items = self.get_overdue_backlog_items(db)
        if not items:
            return "Backlog status: no overdue items today."

        lines = [f"Backlog overdue items ({len(items)}):"]
        for item in items:
            created_at = item["created_at"]
            pending_since = created_at.strftime("%Y-%m-%d") if created_at else "unknown"
            lines.append(f"- {item['title']} | owner: {item['owner']} | pending since: {pending_since}")
        return "\n".join(lines)

    def process_telegram_command(self, command_text: str, db: Session) -> str:
        command = (command_text or "").strip().split(" ")[0].lower()
        if command == "/status":
            return self._status_message(db)
        if command == "/backlog":
            return self._backlog_message(db)
        if command == "/help":
            return self._help_message()
        return "Unknown command. Use /help to see supported commands."

    async def dispatch_notification(
        self,
        *,
        db: Session,
        message: str,
        notification_type: str,
        actor_user_id: Optional[UUID],
        project_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        sent = await telegram_bot_service.send_message(message)

        log_audit_event(
            db=db,
            project_id=project_id,
            action="NOTIFICATION_SENT" if sent else "NOTIFICATION_FAILED",
            entity_type="notification",
            entity_id=None,
            user_id=actor_user_id,
            old_values=None,
            new_values={
                "type": notification_type,
                "message": message,
                "metadata": metadata or {},
                "sent": sent,
            },
        )

        return {
            "sent": sent,
            "type": notification_type,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def send_approval_reminders(self, db: Session) -> Dict[str, Any]:
        rows = db.execute(
            text(
                """
                SELECT
                    aw.workflow_id,
                    d.title,
                    aw.created_at,
                    COALESCE(u.full_name, u.email, 'Approver') AS approver_name
                FROM approval_workflows aw
                JOIN documents d ON d.doc_id = aw.doc_id
                LEFT JOIN users u ON u.user_id = d.created_by
                WHERE aw.status IN ('in_progress', 'human_review_required')
                  AND aw.created_at < NOW() - INTERVAL '2 days'
                ORDER BY aw.created_at ASC
                """
            )
        ).fetchall()

        sent_count = 0
        for row in rows:
            workflow_id = str(row[0])
            title = row[1]
            pending_since = row[2].strftime("%Y-%m-%d") if row[2] else "unknown"
            approver_name = row[3]
            message = (
                "Approval Reminder\n"
                f"Document: {title}\n"
                f"Pending since: {pending_since}\n"
                f"Approver: {approver_name}\n"
                f"Workflow: {workflow_id}"
            )
            if await telegram_bot_service.send_message(message):
                sent_count += 1

        return {
            "sent": sent_count > 0,
            "total_alerts": sent_count,
            "total_candidates": len(rows),
            "timestamp": datetime.utcnow().isoformat(),
        }


notification_service = NotificationService()
