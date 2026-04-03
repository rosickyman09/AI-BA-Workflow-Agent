"""Google Drive push-notification webhook endpoint."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Header, Request
from sqlalchemy.orm import Session

from app.services.db_service import get_db
from fastapi import Depends

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/drive")
async def drive_webhook(
    request: Request,
    x_goog_channel_id: str = Header(default=""),
    x_goog_resource_id: str = Header(default=""),
    x_goog_resource_state: str = Header(default=""),
    x_goog_changed: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """
    Receive Google Drive push notifications.

    Drive sends a POST with headers such as:
      X-Goog-Channel-Id, X-Goog-Resource-Id, X-Goog-Resource-State, X-Goog-Changed

    Resource states:
      sync   — initial handshake (no action required)
      change — file was updated/renamed/trashed
    """
    if x_goog_resource_state == "sync":
        logger.info("Drive webhook sync event received for channel %s", x_goog_channel_id)
        return {"ok": True, "state": "sync"}

    logger.info(
        "Drive change event: channel=%s resource=%s state=%s changed=%s",
        x_goog_channel_id,
        x_goog_resource_id,
        x_goog_resource_state,
        x_goog_changed,
    )

    # Look up whether any workflow is associated with this Drive resource
    row = db.execute(
        __import__("sqlalchemy").text(
            """
            SELECT aw.workflow_id, d.title, aw.project_id
            FROM approval_workflows aw
            JOIN documents d ON d.doc_id = aw.doc_id
            WHERE d.google_drive_link LIKE :resource_pattern
              AND aw.status IN ('in_progress', 'returned_to_step1')
            LIMIT 1
            """
        ),
        {"resource_pattern": f"%{x_goog_resource_id}%"},
    ).fetchone()

    if row:
        logger.info(
            "Drive file updated for workflow %s (doc: %s)",
            row[0], row[1],
        )
        # Future: trigger re-analysis or send notification to reviewers
    else:
        logger.debug("No active workflow found for resource %s", x_goog_resource_id)

    return {"ok": True, "state": x_goog_resource_state}
