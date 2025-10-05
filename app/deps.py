"""
Dependencies and middleware for authentication and idempotency.
"""

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any
import hashlib
import json
from sqlmodel import Session
from app.db import get_session
from app.models import Partner, IdempotencyKey

security = HTTPBearer()

async def get_current_partner(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_session)
) -> Dict[str, Any]:
    """
    Extract and validate partner API key from Authorization header.
    Returns partner information for use in endpoints.
    """
    api_key = credentials.credentials
    
    # Look up partner in database
    partner = session.query(Partner).filter(Partner.api_key == api_key).first()
    
    if not partner:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    return {
        "id": partner.id,
        "api_key": partner.api_key,
        "markup_pct": partner.markup_pct,
        "regions": json.loads(partner.regions),
        "products": json.loads(partner.products)
    }

async def check_idempotency_key(
    request: Request,
    session: Session = Depends(get_session)
) -> Optional[Dict[str, Any]]:
    """
    Check idempotency key for duplicate requests.
    Returns None if new request, or cached response if duplicate.
    """
    idempotency_key = request.headers.get("X-Idempotency-Key")
    
    if not idempotency_key:
        return None
    
    # Check if we have a cached response for this key
    cached_response = session.query(IdempotencyKey).filter(
        IdempotencyKey.key == idempotency_key,
        IdempotencyKey.method == request.method,
        IdempotencyKey.path == request.url.path
    ).first()
    
    if cached_response:
        return json.loads(cached_response.response_json)
    
    return None

def store_idempotency_response(
    idempotency_key: str,
    method: str,
    path: str,
    request_hash: str,
    response_data: Dict[str, Any],
    session: Session
) -> None:
    """
    Store response for idempotency key to prevent duplicate processing.
    """
    if not idempotency_key:
        return
    
    # Store the response
    idempotency_record = IdempotencyKey(
        key=idempotency_key,
        method=method,
        path=path,
        request_hash=request_hash,
        response_json=json.dumps(response_data)
    )
    
    session.add(idempotency_record)
    session.commit()

def generate_request_hash(request_body: Dict[str, Any]) -> str:
    """Generate a hash for request body to detect duplicates."""
    # Sort keys to ensure consistent hashing
    sorted_body = json.dumps(request_body, sort_keys=True)
    return hashlib.sha256(sorted_body.encode()).hexdigest()
