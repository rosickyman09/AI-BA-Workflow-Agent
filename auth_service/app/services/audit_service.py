"""
Audit logging service for security tracking
"""
from sqlalchemy.orm import Session
from sqlalchemy import insert
from ..models import AuditLog
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID


def log_action(
    db: Session,
    action: str,
    user_id: Optional[UUID] = None,
    project_id: Optional[UUID] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[UUID] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    succeeded: bool = True,
    error_message: Optional[str] = None,
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None
) -> AuditLog:
    """Log an action to the audit_logs table"""
    audit_log = AuditLog(
        action=action,
        user_id=user_id,
        project_id=project_id,
        entity_type=entity_type,
        entity_id=entity_id,
        ip_address=ip_address,
        user_agent=user_agent,
        succeeded=succeeded,
        error_message=error_message,
        old_values=old_values,
        new_values=new_values,
        created_at=datetime.utcnow()
    )
    
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)
    
    return audit_log


def log_login(
    db: Session,
    user_id: UUID,
    email: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    succeeded: bool = True,
    error_message: Optional[str] = None
) -> AuditLog:
    """Log a login attempt"""
    return log_action(
        db=db,
        action="login",
        user_id=user_id if succeeded else None,
        entity_type="user",
        entity_id=user_id if succeeded else None,
        ip_address=ip_address,
        user_agent=user_agent,
        succeeded=succeeded,
        error_message=error_message,
        new_values={"email": email, "timestamp": datetime.utcnow().isoformat()} if succeeded else None
    )


def log_logout(
    db: Session,
    user_id: UUID,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AuditLog:
    """Log a logout event"""
    return log_action(
        db=db,
        action="logout",
        user_id=user_id,
        entity_type="user",
        entity_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        succeeded=True
    )


def log_token_refresh(
    db: Session,
    user_id: UUID,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AuditLog:
    """Log a token refresh event"""
    return log_action(
        db=db,
        action="token_refresh",
        user_id=user_id,
        entity_type="auth",
        entity_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        succeeded=True
    )


def log_failed_login(
    db: Session,
    email: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    reason: str = "invalid_credentials"
) -> AuditLog:
    """Log a failed login attempt"""
    return log_action(
        db=db,
        action="failed_login",
        entity_type="auth",
        ip_address=ip_address,
        user_agent=user_agent,
        succeeded=False,
        error_message=reason,
        new_values={"email": email}
    )
