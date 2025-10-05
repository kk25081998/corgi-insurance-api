"""
Policies router for retrieving policy information.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import Dict, Any
import json

from app.schemas import PolicyResponse
from app.deps import get_current_partner
from app.db import get_session
from app.models import Policy, Quote, Carrier
from app.services.ledger import get_ledger_totals

router = APIRouter()

@router.get("/policies/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: int,
    partner: Dict[str, Any] = Depends(get_current_partner),
    session: Session = Depends(get_session)
):
    """
    Retrieve policy details by ID.
    
    This endpoint:
    1. Looks up the policy by ID
    2. Retrieves associated quote and carrier info
    3. Calculates ledger totals
    4. Returns comprehensive policy response
    """
    # Get the policy
    policy = session.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    # Get the associated quote
    quote = session.query(Quote).filter(Quote.id == policy.quote_id).first()
    if not quote:
        raise HTTPException(status_code=500, detail="Associated quote not found")
    
    # Get the carrier
    carrier = session.query(Carrier).filter(Carrier.id == policy.carrier_id).first()
    if not carrier:
        raise HTTPException(status_code=500, detail="Associated carrier not found")
    
    # Get policyholder data
    policyholder = json.loads(policy.policyholder_json)
    
    # Get compliance data from quote
    compliance_data = json.loads(quote.compliance_json)
    
    # Get ledger totals for this policy
    ledger_totals = get_ledger_totals(policy_id=policy.id, db_session=session)
    
    # Prepare response
    response = PolicyResponse(
        policy_id=policy.id,
        quote_id=policy.quote_id,
        product_code=policy.product_code,
        carrier_id=policy.carrier_id,
        premium_total_cents=policy.premium_total_cents,
        status=policy.status,
        effective_date=policy.effective_date,
        policyholder=policyholder,
        risk_band=quote.risk_band,
        risk_multiplier=quote.risk_multiplier,
        compliance_disclosures=compliance_data.get("disclosures", []),
        ledger_total_cents=ledger_totals["total_written_premium_cents"]
    )
    
    return response
