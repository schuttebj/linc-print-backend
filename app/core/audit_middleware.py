"""
Lightweight Audit Middleware for Madagascar License System
Captures API requests for system monitoring and analytics
Separate from detailed transaction audit logs for performance optimization
"""

import time
import json
import uuid
import logging
from typing import Optional
from fastapi import Request, Response
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import ApiRequestLog
from app.api.v1.endpoints.auth import get_current_user_from_token

logger = logging.getLogger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    """Lightweight middleware for API request logging and monitoring"""
    
    def __init__(self, app, exclude_paths: Optional[list] = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/static/",
            "/images/", 
            "/favicon.ico",
            "/health",
            "/ping",
            "/docs",
            "/openapi.json",
            "/redoc"
        ]
    
    async def dispatch(self, request: Request, call_next):
        # Skip logging for excluded paths
        if self._should_exclude_path(request.url.path):
            return await call_next(request)
        
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Extract user context (if available)
        user_id = None
        try:
            # Try to get user from Authorization header
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                user_id = await self._get_user_id_from_token(token)
        except Exception:
            # If we can't get user, continue without it
            pass
        
        # Process request
        response = None
        error_message = None
        
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            # Capture errors that occur during request processing
            error_message = str(e)
            status_code = 500
            # Re-raise the exception after logging
            raise
        finally:
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Log the request (async to avoid blocking)
            await self._log_request(
                request_id=request_id,
                request=request,
                status_code=status_code,
                duration_ms=duration_ms,
                user_id=user_id,
                error_message=error_message,
                response_size=self._get_response_size(response) if response else None
            )
        
        return response
    
    def _should_exclude_path(self, path: str) -> bool:
        """Check if path should be excluded from logging"""
        return any(excluded in path for excluded in self.exclude_paths)
    
    async def _get_user_id_from_token(self, token: str) -> Optional[str]:
        """Extract user ID from JWT token"""
        try:
            from app.core.security import decode_access_token
            payload = decode_access_token(token)
            return payload.get("sub")  # 'sub' contains user_id in JWT
        except Exception:
            return None
    
    def _get_response_size(self, response: Response) -> Optional[int]:
        """Get response size in bytes if available"""
        try:
            content_length = response.headers.get("content-length")
            if content_length:
                return int(content_length)
        except Exception:
            pass
        return None
    
    def _extract_query_params(self, request: Request) -> Optional[str]:
        """Extract and serialize query parameters"""
        try:
            if request.query_params:
                # Convert to dict and serialize as JSON
                params_dict = dict(request.query_params)
                return json.dumps(params_dict)
        except Exception:
            pass
        return None
    
    async def _log_request(
        self,
        request_id: str,
        request: Request,
        status_code: int,
        duration_ms: int,
        user_id: Optional[str],
        error_message: Optional[str] = None,
        response_size: Optional[int] = None
    ):
        """Log request to database (async to avoid blocking main request)"""
        try:
            # Get database session
            db = next(get_db())
            
            try:
                # Create log entry
                log_entry = ApiRequestLog(
                    request_id=request_id,
                    method=request.method,
                    endpoint=request.url.path,
                    query_params=self._extract_query_params(request),
                    user_id=uuid.UUID(user_id) if user_id else None,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                    status_code=status_code,
                    response_size_bytes=response_size,
                    duration_ms=duration_ms,
                    error_message=error_message,
                    # Location ID could be extracted from user context later
                    location_id=None
                )
                
                db.add(log_entry)
                db.commit()
                
            except Exception as e:
                logger.error(f"Failed to save API request log: {e}")
                db.rollback()
            finally:
                db.close()
                
        except Exception as e:
            # Don't let logging errors affect the main request
            logger.error(f"Failed to create API request log: {e}")


def setup_audit_middleware(app, exclude_paths: Optional[list] = None):
    """Setup audit middleware with optional path exclusions"""
    app.add_middleware(AuditMiddleware, exclude_paths=exclude_paths)
    logger.info("Audit middleware initialized")
