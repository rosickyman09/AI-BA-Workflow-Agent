"""Notification endpoints for Telegram and reminders."""

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
from app.services import notifications as in_app_notif

router = APIRouter()


class NotificationSendRequest(BaseModel):
    message: str = Field(min_length=1)
    type: str = "info"
    project_id: Optional[UUID] = None
    metadata: Dict[str, Any] = {}


class TelegramUpdateRequest(BaseModel):
    update_id: Optional[int] = None
    message: Dict[str, Any] = {}


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
    return {
        **result,
        "triggered_by": current_user.email,
    }


# ─── In-app notification endpoints ───────────────────────────────────────────

@router.get("/in-app")
async def get_in_app_notifications(
    unread_only: bool = False,
    limit: int = 50,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Return in-app notifications for the authenticated user."""
    items = in_app_notif.get_user_notifications(
        user_id=str(current_user.user_id),
        unread_only=unread_only,
        limit=limit,
        db=db,
    )
    return {"items": items, "total": len(items)}


@router.post("/in-app/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Mark a single in-app notification as read."""
    in_app_notif.mark_as_read(
        notification_id=str(notification_id),
        user_id=str(current_user.user_id),
        db=db,
    )
    db.commit()
    return {"ok": True}


@router.post("/in-app/read-all")
async def mark_all_notifications_read(
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Mark all in-app notifications as read for the authenticated user."""
    count = in_app_notif.mark_all_as_read(user_id=str(current_user.user_id), db=db)
    db.commit()
    return {"ok": True, "marked_count": count}


@router.get("/in-app/unread-count")
async def get_unread_notification_count(
    current_user: TokenUser = Depends(require_readonly),
    db: Session = Depends(get_db),
):
    """Return the unread in-app notification count for the authenticated user."""
    count = in_app_notif.get_unread_count(user_id=str(current_user.user_id), db=db)
    return {"unread_count": count}
