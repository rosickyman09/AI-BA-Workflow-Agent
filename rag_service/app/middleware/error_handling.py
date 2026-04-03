"""
RAG Service Error Handler
"""

from fastapi import Request
from fastapi.responses import JSONResponse
import logging
import json

logger = logging.getLogger(__name__)

async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    
    error_response = {
        "error": {
            "type": exc.__class__.__name__,
            "message": str(exc),
            "request_id": request_id
        }
    }
    
    log_data = {
        "error_type": exc.__class__.__name__,
        "message": str(exc),
        "request_id": request_id
    }
    
    logger.error(json.dumps(log_data))
    
    return JSONResponse(
        status_code=500,
        content=error_response
    )


