"""
n8n webhook trigger service.

POSTs document metadata to an n8n workflow webhook after a file is uploaded.
Gracefully degrades (returns False) when N8N_WEBHOOK_URL is not configured.
"""
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_N8N_WEBHOOK_URL: str = os.environ.get("N8N_WEBHOOK_URL", "")


async def trigger_document_workflow(
    workflow_id: str,
    document_id: str,
    google_drive_url: Optional[str],
    file_type: str,
    filename: str,
) -> bool:
    """
    POST a document-upload event to the configured n8n webhook.

    Payload:
        workflow_id      – UUID of the approval workflow
        document_id      – UUID of the document record
        google_drive_url – Public view URL (may be None if Drive not set up)
        file_type        – MIME type of the uploaded file
        filename         – Original filename

    Returns True on success, False when n8n is not configured or the call fails.
    """
    if not _N8N_WEBHOOK_URL:
        logger.info("N8N_WEBHOOK_URL not configured — skipping n8n trigger")
        return False

    payload = {
        "workflow_id": workflow_id,
        "document_id": document_id,
        "google_drive_url": google_drive_url,
        "file_type": file_type,
        "filename": filename,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(_N8N_WEBHOOK_URL, json=payload)
            response.raise_for_status()
            logger.info("n8n webhook triggered for workflow %s", workflow_id)
            return True
    except Exception as exc:
        logger.warning("n8n webhook failed for workflow %s: %s", workflow_id, exc)
        return False
