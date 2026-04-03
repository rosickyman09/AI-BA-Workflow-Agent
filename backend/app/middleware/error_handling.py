"""
Global exception handler middleware
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
import logging
import json

logger = logging.getLogger(__name__)

async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    
    request_id = getattr(request.state, "request_id", "unknown")
    
    # Standard error response
    error_response = {
        "error": {
            "type": exc.__class__.__name__,
            "message": str(exc),
            "request_id": request_id
        }
    }
    
    # Log error in structured format
    log_data = {
        "error_type": exc.__class__.__name__,
        "message": str(exc),
        "request_id": request_id,
        "path": request.url.path,
        "method": request.method
    }
    
    logger.error(json.dumps(log_data))
    
    # HTTP exceptions
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response
        )
    
    # Generic 500 error
    return JSONResponse(
        status_code=500,
        content=error_response
    )
