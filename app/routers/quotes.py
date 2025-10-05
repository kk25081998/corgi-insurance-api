"""
Quotes router for handling insurance quote requests.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session
from typing import Dict, Any
import json
from datetime import datetime

from app.schemas import QuoteRequest, QuoteResponse, PriceBreakdown, ComplianceResult
from app.deps import get_current_partner, check_idempotency_key, store_idempotency_response, generate_request_hash
from app.db import get_session
from app.models import Quote, Carrier
from app.services.compliance import compliance_engine
from app.services.risk import calculate_risk_assessment
from app.services.pricing import calculate_premium
from app.services.routing import route_to_carrier, get_carrier_capacities_for_month, get_routing_summary
from app.cache import config_cache
import logging

logger = logging.getLogger("embedded_insurance")

router = APIRouter()

@router.post("/quotes", response_model=QuoteResponse)
async def create_quote(
    request: QuoteRequest,
    request_obj: Request,
    partner: Dict[str, Any] = Depends(get_current_partner),
    session: Session = Depends(get_session)
):
    """
    Create a new insurance quote.
    
    This endpoint:
    1. Validates the request
    2. Runs compliance checks
    3. Calculates risk score and band
    4. Computes pricing with breakdown
    5. Routes to appropriate carrier
    6. Returns quote response
    """
    # Get request ID from middleware
    request_id = getattr(request_obj.state, "request_id", "unknown")
    logger.info(f"Processing quote request | request_id={request_id} | product={request.product_code}")
    
    # Check idempotency
    cached_response = await check_idempotency_key(request_obj, session)
    if cached_response:
        logger.info(f"Returning cached response | request_id={request_id}")
        return cached_response
    
    # Validate product code
    if request.product_code not in partner["products"]:
        raise HTTPException(
            status_code=400,
            detail=f"Product {request.product_code} not available for this partner"
        )
    
    # Extract request data based on product type (now flat structure)
    request_data = {}
    if request.product_code == "shipping":
        # Validate required shipping fields
        if not request.declared_value:
            raise HTTPException(status_code=400, detail="declared_value required for shipping quotes")
        if not request.item_category:
            raise HTTPException(status_code=400, detail="item_category required for shipping quotes")
        if not request.destination_state:
            raise HTTPException(status_code=400, detail="destination_state required for shipping quotes")
        if not request.destination_risk:
            raise HTTPException(status_code=400, detail="destination_risk required for shipping quotes")
        if not request.service_level:
            raise HTTPException(status_code=400, detail="service_level required for shipping quotes")
        
        request_data = {
            "declared_value": request.declared_value,
            "item_category": request.item_category,
            "destination_state": request.destination_state,
            "destination_risk": request.destination_risk,
            "service_level": request.service_level
        }
        # Policyholder defaults for shipping (used in compliance/risk)
        policyholder = {
            "state": request.destination_state,
            "age": 30,
            "tenure_months": 12
        }
    elif request.product_code == "ppi":
        # Validate required PPI fields
        if not request.order_value:
            raise HTTPException(status_code=400, detail="order_value required for PPI quotes")
        if not request.term_months:
            raise HTTPException(status_code=400, detail="term_months required for PPI quotes")
        if not request.age:
            raise HTTPException(status_code=400, detail="age required for PPI quotes")
        if not request.tenure_months:
            raise HTTPException(status_code=400, detail="tenure_months required for PPI quotes")
        if not request.job_category:
            raise HTTPException(status_code=400, detail="job_category required for PPI quotes")
        if not request.state:
            raise HTTPException(status_code=400, detail="state required for PPI quotes")
        
        request_data = {
            "order_value": request.order_value,
            "term_months": request.term_months,
            "age": request.age,
            "tenure_months": request.tenure_months,
            "job_category": request.job_category
        }
        # Policyholder data for PPI
        policyholder = {
            "state": request.state,
            "age": request.age,
            "tenure_months": request.tenure_months
        }
    else:
        raise HTTPException(status_code=400, detail="Invalid product code")
    
    # Run compliance check
    compliance_result = compliance_engine.evaluate_rules(
        request.product_code,
        request_data,
        policyholder
    )
    
    # Block if compliance fails
    if compliance_result["decision"] == "block":
        logger.warning(
            f"Quote blocked by compliance | request_id={request_id} | "
            f"rules={', '.join(compliance_result['rules_applied'])}"
        )
        raise HTTPException(
            status_code=400,
            detail=f"Quote blocked by compliance: {', '.join(compliance_result['rules_applied'])}"
        )
    
    # Calculate risk assessment
    risk_assessment = calculate_risk_assessment(
        request.product_code,
        request_data,
        policyholder
    )
    
    # Get carriers and their capacities
    carriers = session.query(Carrier).all()
    carrier_list = [{"id": c.id, "name": c.name, "appetite_json": c.appetite_json, 
                    "capacity_monthly_limit": c.capacity_monthly_limit, 
                    "pricing_curve_ref": c.pricing_curve_ref} for c in carriers]
    
    current_month = datetime.now().strftime("%Y-%m")
    carrier_capacities = get_carrier_capacities_for_month(carrier_list, current_month, session)
    
    # Calculate pricing and margins for each carrier, checking appetite and capacity
    # Per assignment: "Choose the highest margin among accepted; tie-break: lower premium"
    eligible_carrier_evaluations = []
    
    # Add risk_band to request_data for appetite checking
    request_data_with_band = {**request_data, "risk_band": risk_assessment["risk_band"]}
    
    for carrier in carrier_list:
        try:
            # Parse appetite configuration
            appetite = json.loads(carrier["appetite_json"]) if isinstance(carrier["appetite_json"], str) else carrier["appetite_json"]
            
            # Get product-specific appetite
            product_appetite = appetite.get(request.product_code, {})
            
            # Check appetite constraints
            appetite_ok = True
            rejection_reason = None
            
            # Check excluded states
            if policyholder.get("state") in product_appetite.get("excluded_states", []):
                appetite_ok = False
                rejection_reason = f"State {policyholder.get('state')} excluded"
            
            # Check excluded categories (shipping)
            if request.product_code == "shipping":
                if request_data.get("item_category") in product_appetite.get("excluded_categories", []):
                    appetite_ok = False
                    rejection_reason = f"Category {request_data.get('item_category')} excluded"
                
                # Check max declared value
                max_value = product_appetite.get("max_declared_value", float('inf'))
                if request_data.get("declared_value", 0) > max_value:
                    appetite_ok = False
                    rejection_reason = f"Declared value exceeds max ${max_value}"
            
            # Check PPI constraints
            if request.product_code == "ppi":
                # Check max term
                max_term = product_appetite.get("max_term_months", float('inf'))
                if request_data.get("term_months", 0) > max_term:
                    appetite_ok = False
                    rejection_reason = f"Term exceeds max {max_term} months"
                
                # Check max risk band
                max_risk_band = product_appetite.get("max_risk_band")
                if max_risk_band:
                    band_order = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5}
                    if band_order.get(risk_assessment["risk_band"], 5) > band_order.get(max_risk_band, 5):
                        appetite_ok = False
                        rejection_reason = f"Risk band {risk_assessment['risk_band']} exceeds max {max_risk_band}"
                
                # Check excluded job categories
                if request_data.get("job_category") in product_appetite.get("excluded_job_categories", []):
                    appetite_ok = False
                    rejection_reason = f"Job category {request_data.get('job_category')} excluded"
            
            # Check capacity
            current_capacity = carrier_capacities.get(carrier["id"], 0)
            if current_capacity <= 0:
                appetite_ok = False
                rejection_reason = "No capacity available"
            
            if not appetite_ok:
                logger.debug(f"Carrier {carrier['id']} rejected: {rejection_reason}")
                continue
            
            # Get pricing curve for this carrier from cache (avoids disk I/O)
            pricing_curve = config_cache.get_pricing_curve_for_carrier(
                carrier["id"], 
                request.product_code
            )
            
            # Calculate premium
            premium_cents, breakdown = calculate_premium(
                request.product_code,
                request_data,
                risk_assessment["risk_multiplier"],
                partner["markup_pct"],
                pricing_curve,
                risk_assessment["risk_band"]
            )
            
            # Calculate expected margin per assignment formula
            # margin = premium - (premium * 0.60 * risk_multiplier)
            expected_margin = premium_cents - (premium_cents * 0.60 * risk_assessment["risk_multiplier"])
            
            eligible_carrier_evaluations.append({
                "carrier_id": carrier["id"],
                "carrier_name": carrier["name"],
                "premium_cents": premium_cents,
                "breakdown": breakdown,
                "expected_margin": expected_margin,
                "capacity": current_capacity
            })
                
        except Exception as e:
            # Skip carriers with pricing issues
            logger.warning(f"Skipping carrier {carrier['id']} due to error: {e}")
            continue
    
    if not eligible_carrier_evaluations:
        logger.error(f"No eligible carriers found | request_id={request_id}")
        raise HTTPException(
            status_code=500,
            detail="No eligible carriers found for this quote"
        )
    
    # Sort by highest margin, then by lowest premium (tie-breaker)
    eligible_carrier_evaluations.sort(key=lambda x: (-x["expected_margin"], x["premium_cents"]))
    
    # Select best carrier based on margin
    selected_carrier = eligible_carrier_evaluations[0]
    carrier_suggestion = selected_carrier["carrier_id"]
    best_premium = selected_carrier["premium_cents"]
    best_breakdown = selected_carrier["breakdown"]
    best_margin = selected_carrier["expected_margin"]
    
    # Create rationale
    router_rationale = (
        f"Selected {carrier_suggestion} with margin ${best_margin/100:.2f} "
        f"(premium: ${best_premium/100:.2f}, capacity: {selected_carrier['capacity']})"
    )
    
    # Log other candidates for debugging
    if len(eligible_carrier_evaluations) > 1:
        other_carriers = [f"{c['carrier_id']} (margin: ${c['expected_margin']/100:.2f})" 
                         for c in eligible_carrier_evaluations[1:]]
        logger.debug(f"Other eligible carriers: {', '.join(other_carriers)}")
    
    # Create quote record
    quote = Quote(
        product_code=request.product_code,
        request_json=json.dumps(request_data),
        risk_band=risk_assessment["risk_band"],
        risk_multiplier=risk_assessment["risk_multiplier"],
        price_breakdown_json=json.dumps(best_breakdown),
        carrier_suggestion=carrier_suggestion,
        router_rationale=router_rationale,
        compliance_json=json.dumps(compliance_result),
        premium_cents=best_premium
    )
    
    session.add(quote)
    session.commit()
    session.refresh(quote)
    
    logger.info(
        f"Quote created | request_id={request_id} | quote_id={quote.id} | "
        f"carrier={carrier_suggestion} | premium_cents={quote.premium_cents} | "
        f"risk_band={quote.risk_band}"
    )
    
    # Prepare response with new breakdown format
    response_data = QuoteResponse(
        quote_id=quote.id,
        product_code=quote.product_code,
        premium_cents=quote.premium_cents,
        price_breakdown=PriceBreakdown(**best_breakdown),
        risk_band=quote.risk_band,
        risk_multiplier=quote.risk_multiplier,
        carrier_suggestion=quote.carrier_suggestion,
        router_rationale=quote.router_rationale,
        compliance=ComplianceResult(
            decision=compliance_result["decision"],
            disclosures=compliance_result["disclosures"],
            report_id=compliance_result["report_id"]
        )
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
