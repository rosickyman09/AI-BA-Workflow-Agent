"""
Logging middleware - Structured JSON logging
"""

from fastapi import Request
import json
import logging
import time
from uuid import uuid4

logger = logging.getLogger(__name__)

class LoggingMiddleware:
    """Structured logging middleware"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, request: Request, call_next):
        # Request ID for tracing
        request_id = str(uuid4())
        request.state.request_id = request_id
        
        # Start timer
        start_time = time.time()
        
        # Call next middleware
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Log structured format
        log_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "process_time_ms": round(process_time * 1000, 2),
            "timestamp": time.time()
        }
        
        logger.info(json.dumps(log_data))
        
        return response
