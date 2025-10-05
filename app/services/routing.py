"""
Routing service for carrier selection and capacity management.
"""

from typing import Dict, Any, List, Optional, Tuple
import json

def route_to_carrier(
    product_code: str,
    request_data: Dict[str, Any],
    policyholder: Dict[str, Any],
    premium_cents: int,
    risk_multiplier: float,
    carriers: List[Dict[str, Any]],
    carrier_capacities: Dict[str, int]
) -> Tuple[Optional[str], str]:
    """
    Route quote to appropriate carrier based on appetite, capacity, and margin.
    
    Args:
        product_code: Product code (shipping or ppi)
        request_data: Request data
        policyholder: Policyholder information
        premium_cents: Calculated premium in cents
        risk_multiplier: Risk multiplier
        carriers: List of available carriers
        carrier_capacities: Current carrier capacities
        
    Returns:
        Tuple of (carrier_id, rationale)
    """
    eligible_carriers = []
    
    for carrier in carriers:
        carrier_id = carrier["id"]
        appetite = json.loads(carrier["appetite_json"]) if isinstance(carrier["appetite_json"], str) else carrier["appetite_json"]
        
        # Check appetite constraints
        appetite_check, appetite_reason = _check_appetite(
            product_code, request_data, policyholder, appetite
        )
        if not appetite_check:
            continue
            
        # Check capacity
        current_capacity = carrier_capacities.get(carrier_id, 0)
        if current_capacity <= 0:
            continue
            
        # Calculate expected margin: premium - (premium * 0.60 * risk_multiplier)
        expected_margin = premium_cents - (premium_cents * 0.60 * risk_multiplier)
        
        eligible_carriers.append({
            "carrier_id": carrier_id,
            "expected_margin": expected_margin,
            "premium": premium_cents,
            "capacity": current_capacity,
            "appetite_reason": appetite_reason
        })
    
    if not eligible_carriers:
        return None, "No carriers available - appetite or capacity constraints"
    
    # Sort by highest margin, then by lowest premium (tie-breaker)
    eligible_carriers.sort(key=lambda x: (-x["expected_margin"], x["premium"]))
    
    selected = eligible_carriers[0]
    rationale = (
        f"Selected {selected['carrier_id']} with margin ${selected['expected_margin']/100:.2f} "
        f"(premium: ${selected['premium']/100:.2f}, capacity: {selected['capacity']})"
    )
    
    return selected["carrier_id"], rationale

def _check_appetite(
    product_code: str,
    request_data: Dict[str, Any],
    policyholder: Dict[str, Any],
    appetite: Dict[str, Any]
) -> Tuple[bool, str]:
    """
    Check if request meets carrier appetite requirements.
    
    Args:
        product_code: Product code
        request_data: Request data
        policyholder: Policyholder information
        appetite: Carrier appetite configuration
        
    Returns:
        Tuple of (meets_appetite, reason)
    """
    # Check excluded states
    state = policyholder.get("state")
    excluded_states = appetite.get("excluded_states", [])
    if state in excluded_states:
        return False, f"State {state} excluded by carrier"
    
    # Check excluded risk bands
    risk_band = request_data.get("risk_band")
    excluded_risk_bands = appetite.get("excluded_risk_bands", [])
    if risk_band in excluded_risk_bands:
        return False, f"Risk band {risk_band} excluded by carrier"
    
    if product_code == "shipping":
        # Check excluded categories
        item_category = request_data.get("item_category")
        excluded_categories = appetite.get("excluded_categories", [])
        if item_category in excluded_categories:
            return False, f"Category {item_category} excluded by carrier"
        
        # Check max declared value
        declared_value = request_data.get("declared_value", 0)
        max_value = appetite.get("max_declared_value", float('inf'))
        if declared_value > max_value:
            return False, f"Declared value ${declared_value} exceeds max ${max_value}"
    
    elif product_code == "ppi":
        # Check max term
        term_months = request_data.get("term_months", 0)
        max_term = appetite.get("max_term_months", float('inf'))
        if term_months > max_term:
            return False, f"Term {term_months} months exceeds max {max_term}"
    
    return True, "Meets all appetite requirements"

def get_carrier_capacities_for_month(
    carriers: List[Dict[str, Any]],
    as_of_month: str,
    db_session
) -> Dict[str, int]:
    """
    Get current carrier capacities for a specific month.
    
    Args:
        carriers: List of carriers
        as_of_month: Month in YYYY-MM format
        db_session: Database session
        
    Returns:
        Dictionary mapping carrier_id to remaining capacity
    """
    from app.models import CarrierCapacity
    
    capacities = {}
    
    for carrier in carriers:
        carrier_id = carrier["id"]
        
        # Query current capacity for this month
        capacity_record = db_session.query(CarrierCapacity).filter(
            CarrierCapacity.carrier_id == carrier_id,
            CarrierCapacity.as_of_month == as_of_month
        ).first()
        
        if capacity_record:
            capacities[carrier_id] = capacity_record.remaining_count
        else:
            # If no record exists, use the monthly limit
            capacities[carrier_id] = carrier["capacity_monthly_limit"]
    
    return capacities

def decrement_carrier_capacity(
    carrier_id: str,
    as_of_month: str,
    db_session
) -> bool:
    """
    Decrement carrier capacity for the month.
    
    Args:
        carrier_id: Carrier ID
        as_of_month: Month in YYYY-MM format
        db_session: Database session
        
    Returns:
        True if capacity was decremented successfully
    """
    from app.models import CarrierCapacity
    from datetime import datetime
    
    # Find or create capacity record
    capacity_record = db_session.query(CarrierCapacity).filter(
        CarrierCapacity.carrier_id == carrier_id,
        CarrierCapacity.as_of_month == as_of_month
    ).first()
    
    if not capacity_record:
        # Create new record with default capacity
        from app.models import Carrier
        carrier = db_session.query(Carrier).filter(Carrier.id == carrier_id).first()
        if not carrier:
            return False
        
        capacity_record = CarrierCapacity(
            carrier_id=carrier_id,
            as_of_month=as_of_month,
            remaining_count=carrier.capacity_monthly_limit - 1
        )
        db_session.add(capacity_record)
    else:
        # Decrement existing capacity
        if capacity_record.remaining_count > 0:
            capacity_record.remaining_count -= 1
        else:
            return False  # No capacity available
    
    db_session.commit()
    return True

def get_routing_summary(
    product_code: str,
    request_data: Dict[str, Any],
    policyholder: Dict[str, Any],
    premium_cents: int,
    risk_multiplier: float,
    carriers: List[Dict[str, Any]],
    carrier_capacities: Dict[str, int]
) -> Dict[str, Any]:
    """
    Get detailed routing analysis for all carriers.
    
    Args:
        product_code: Product code
        request_data: Request data
        policyholder: Policyholder information
        premium_cents: Calculated premium in cents
        risk_multiplier: Risk multiplier
        carriers: List of available carriers
        carrier_capacities: Current carrier capacities
        
    Returns:
        Routing summary with all carrier evaluations
    """
    carrier_evaluations = []
    
    for carrier in carriers:
        carrier_id = carrier["id"]
        appetite = json.loads(carrier["appetite_json"]) if isinstance(carrier["appetite_json"], str) else carrier["appetite_json"]
        
        # Check appetite
        appetite_check, appetite_reason = _check_appetite(
            product_code, request_data, policyholder, appetite
        )
        
        # Check capacity
        current_capacity = carrier_capacities.get(carrier_id, 0)
        capacity_available = current_capacity > 0
        
        # Calculate margin
        expected_margin = premium_cents - (premium_cents * 0.60 * risk_multiplier)
        
        carrier_evaluations.append({
            "carrier_id": carrier_id,
            "carrier_name": carrier["name"],
            "appetite_check": appetite_check,
            "appetite_reason": appetite_reason,
            "capacity_available": capacity_available,
            "current_capacity": current_capacity,
            "expected_margin_cents": expected_margin,
            "expected_margin_dollars": expected_margin / 100,
            "eligible": appetite_check and capacity_available
        })
    
    # Sort by eligibility and margin
    carrier_evaluations.sort(key=lambda x: (not x["eligible"], -x["expected_margin_cents"]))
    
    return {
        "carrier_evaluations": carrier_evaluations,
        "selected_carrier": carrier_evaluations[0]["carrier_id"] if carrier_evaluations and carrier_evaluations[0]["eligible"] else None,
        "total_eligible": sum(1 for c in carrier_evaluations if c["eligible"])
    }
