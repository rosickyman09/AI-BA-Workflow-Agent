"""Audit logging helper for backend actions."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def log_audit_event(
    *,
    db: Session,
    project_id: Optional[UUID],
    action: str,
    entity_type: str,
    entity_id: Optional[UUID],
    user_id: Optional[UUID],
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    succeeded: bool = True,
    error_message: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO audit_logs
                (project_id, action, entity_type, entity_id, user_id,
                 old_values, new_values, ip_address, user_agent,
                 succeeded, error_message, created_at)
            VALUES
                (:project_id, :action, :entity_type, :entity_id, :user_id,
                 CAST(:old_values AS jsonb), CAST(:new_values AS jsonb), :ip_address, :user_agent,
                 :succeeded, :error_message, :created_at)
            """
        ),
        {
            "project_id": str(project_id) if project_id else None,
            "action": action,
            "entity_type": entity_type,
            "entity_id": str(entity_id) if entity_id else None,
            "user_id": str(user_id) if user_id else None,
            "old_values": json.dumps(old_values or {}),
            "new_values": json.dumps(new_values or {}),
            "ip_address": ip_address,
            "user_agent": user_agent,
            "succeeded": succeeded,
            "error_message": error_message,
            "created_at": datetime.utcnow(),
        },
    )