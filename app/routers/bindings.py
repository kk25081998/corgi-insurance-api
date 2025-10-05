"""
Bindings router for handling policy binding requests.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session
from typing import Dict, Any
import json
from datetime import datetime, date

from app.schemas import BindingRequest, BindingResponse
from app.deps import get_current_partner, check_idempotency_key, store_idempotency_response, generate_request_hash
from app.db import get_session
from app.models import Quote, Policy, Carrier
from app.services.compliance import compliance_engine
from app.services.ledger import write_premium_to_ledger
from app.services.routing import decrement_carrier_capacity

router = APIRouter()

@router.post("/bindings", response_model=BindingResponse)
async def create_binding(
    request: BindingRequest,
    request_obj: Request,
    partner: Dict[str, Any] = Depends(get_current_partner),
    session: Session = Depends(get_session)
):
    """
    Bind a quote to create a policy.
    
    This endpoint:
    1. Validates the binding request
    2. Re-runs compliance checks with policyholder data
    3. Creates the policy
    4. Writes to ledger
    5. Decrements carrier capacity
    6. Returns binding response
    """
    # Check idempotency
    cached_response = await check_idempotency_key(request_obj, session)
    if cached_response:
        return cached_response
    
    # Get the quote
    quote = session.query(Quote).filter(Quote.id == request.quote_id).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    # Validate quote belongs to partner (optional security check)
    # In a real system, you might want to track which partner created the quote
    
    # Extract request data from quote
    request_data = json.loads(quote.request_json)
    
    # Re-run compliance check with actual policyholder data
    compliance_result = compliance_engine.evaluate_rules(
        quote.product_code,
        request_data,
        request.policyholder.dict()
    )
    
    # Block if compliance fails
    if compliance_result["decision"] == "block":
        raise HTTPException(
            status_code=400,
            detail=f"Binding blocked by compliance: {', '.join(compliance_result['rules_applied'])}"
        )
    
    # Get the carrier
    carrier = session.query(Carrier).filter(Carrier.id == quote.carrier_suggestion).first()
    if not carrier:
        raise HTTPException(status_code=500, detail="Carrier not found")
    
    # Check carrier capacity
    current_month = datetime.now().strftime("%Y-%m")
    capacity_decremented = decrement_carrier_capacity(
        quote.carrier_suggestion,
        current_month,
        session
    )
    
    if not capacity_decremented:
        raise HTTPException(
            status_code=400,
            detail="No carrier capacity available for binding"
        )
    
    # Create policy
    policy = Policy(
        quote_id=quote.id,
        product_code=quote.product_code,
        carrier_id=quote.carrier_suggestion,
        premium_total_cents=quote.premium_cents,
        status="active",
        effective_date=date.today().strftime("%Y-%m-%d"),
        policyholder_json=json.dumps(request.policyholder.dict())
    )
    
    session.add(policy)
    session.commit()
    session.refresh(policy)
    
    # Write to ledger
    ledger_entry = write_premium_to_ledger(
        policy.id,
        policy.premium_total_cents,
        session
    )
    
    # Prepare response
    response_data = BindingResponse(
        policy_id=policy.id,
        status=policy.status,
        premium_total_cents=policy.premium_total_cents,
        carrier_id=policy.carrier_id,
        effective_date=policy.effective_date
    )
    
    # Store idempotency response if key provided
    idempotency_key = request_obj.headers.get("X-Idempotency-Key")
    if idempotency_key:
        request_hash = generate_request_hash(request.dict())
        store_idempotency_response(
            idempotency_key,
            request_obj.method,
            request_obj.url.path,
            request_hash,
            response_data.dict(),
            session
        )
    
    return response_data
