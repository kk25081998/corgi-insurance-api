"""
Middleware for performance monitoring and observability.
"""

import time
import uuid
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("embedded_insurance")

class PerformanceMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track request performance and add request IDs.
    
    Features:
    - Adds X-Request-ID header (uses provided value or generates ULID-like UUID)
    - Tracks request duration
    - Logs request/response details
    - Includes idempotency key if provided
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            # Use idempotency key if provided, otherwise generate UUID
            request_id = request.headers.get("X-Idempotency-Key")
            if not request_id:
                request_id = str(uuid.uuid4())
        
        # Store request ID in request state for access by endpoints
        request.state.request_id = request_id
        
        # Start timing
        start_time = time.time()
        
        # Log request start
        logger.info(
            f"Request started | "
            f"request_id={request_id} | "
            f"method={request.method} | "
            f"path={request.url.path} | "
            f"client={request.client.host if request.client else 'unknown'}"
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log response
            logger.info(
                f"Request completed | "
                f"request_id={request_id} | "
                f"method={request.method} | "
                f"path={request.url.path} | "
                f"status={response.status_code} | "
                f"duration_ms={duration_ms:.2f}"
            )
            
            # Add headers to response
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"
            
            # Log performance warnings
            if duration_ms > 250 and request.url.path == "/v1/quotes":
                logger.warning(
                    f"Slow quote request | "
                    f"request_id={request_id} | "
                    f"duration_ms={duration_ms:.2f} | "
                    f"threshold_ms=250"
                )
            
            return response
            
        except Exception as e:
            # Calculate duration even for errors
            duration_ms = (time.time() - start_time) * 1000
            
            # Log error
            logger.error(
                f"Request failed | "
                f"request_id={request_id} | "
                f"method={request.method} | "
                f"path={request.url.path} | "
                f"duration_ms={duration_ms:.2f} | "
                f"error={str(e)}"
            )
            raise


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to inject request context into logs.
    
    Makes request_id available to all downstream handlers.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Ensure request_id is available
        if not hasattr(request.state, "request_id"):
            request.state.request_id = request.headers.get(
                "X-Request-ID", 
                str(uuid.uuid4())
            )
        
        response = await call_next(request)
        return response

