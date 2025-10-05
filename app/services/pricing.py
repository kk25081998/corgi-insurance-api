"""
Pricing service for calculating insurance premiums.
"""

from typing import Dict, Any, Tuple
import json

def calculate_shipping_premium(
    request_data: Dict[str, Any],
    risk_multiplier: float,
    partner_markup_pct: float,
    pricing_curve: Dict[str, Any]
) -> Tuple[int, Dict[str, Any]]:
    """
    Calculate shipping insurance premium.
    
    Formula: premium = (declared_value/100) * base_rate * category_mult * dest_mult * service_mult * risk_multiplier
    
    Args:
        request_data: Shipping request data (declared_value in dollars)
        risk_multiplier: Risk multiplier from risk scoring
        partner_markup_pct: Partner markup percentage
        pricing_curve: Pricing curve data
        
    Returns:
        Tuple of (premium_cents, breakdown_dict)
    """
    declared_value_dollars = request_data.get("declared_value", 0)  # Already in dollars
    item_category = request_data.get("item_category", "standard")
    destination_risk = request_data.get("destination_risk", "low")
    service_level = request_data.get("service_level", "ground")
    
    # Get pricing multipliers from curve
    base_rate = pricing_curve.get("base_rate", 0.55)
    category_mult = pricing_curve.get("category_multiplier", {}).get(item_category, 
                pricing_curve.get("category_multipliers", {}).get(item_category, 1.0))
    dest_mult = pricing_curve.get("destination_multiplier", {}).get(destination_risk,
                pricing_curve.get("destination_multipliers", {}).get(destination_risk, 1.0))
    service_mult = pricing_curve.get("service_level_multiplier", {}).get(service_level,
                pricing_curve.get("service_multipliers", {}).get(service_level, 1.0))
    
    # Calculate base premium in dollars (before risk multiplier and markup)
    # Base = (declared_value/100) * base_rate * category_mult * dest_mult * service_mult
    base_premium_dollars = (declared_value_dollars / 100) * base_rate * category_mult * dest_mult * service_mult
    
    # Apply risk multiplier and partner markup
    total_premium_dollars = base_premium_dollars * risk_multiplier * (1 + partner_markup_pct)
    
    # Convert to cents
    base_premium_cents = int(round(base_premium_dollars * 100))
    total_premium_cents = int(round(total_premium_dollars * 100))
    
    # Create breakdown per requirements
    breakdown = {
        "base": base_premium_cents,
        "category_mult": category_mult,
        "dest_mult": dest_mult,
        "service_mult": service_mult,
        "risk_mult": risk_multiplier,
        "partner_markup_pct": partner_markup_pct
    }
    
    return total_premium_cents, breakdown

def calculate_ppi_premium(
    request_data: Dict[str, Any],
    risk_multiplier: float,
    partner_markup_pct: float,
    pricing_curve: Dict[str, Any],
    risk_band: str = None
) -> Tuple[int, Dict[str, Any]]:
    """
    Calculate PPI insurance premium.
    
    Formula: premium = (order_value/100) * base_rate * term_mult * band_mult * risk_multiplier
    
    Args:
        request_data: PPI request data (order_value in dollars)
        risk_multiplier: Risk multiplier from risk scoring
        partner_markup_pct: Partner markup percentage
        pricing_curve: Pricing curve data
        risk_band: Risk band (A-E) for band_multiplier lookup
        
    Returns:
        Tuple of (premium_cents, breakdown_dict)
    """
    order_value_dollars = request_data.get("order_value", 0)  # Already in dollars
    term_months = request_data.get("term_months", 6)
    age = request_data.get("age", 30)
    tenure_months = request_data.get("tenure_months", 12)
    job_category = request_data.get("job_category", "full_time")
    
    # Get pricing multipliers from curve
    base_rate = pricing_curve.get("base_rate", 0.80)
    
    # Map term months to term multiplier ranges
    term_mult = 1.0
    if term_months <= 6:
        term_mult = pricing_curve.get("term_multiplier", {}).get("<=6", 
                    pricing_curve.get("term_multipliers", {}).get("6", 0.9))
    elif term_months <= 12:
        term_mult = pricing_curve.get("term_multiplier", {}).get("7-12", 
                    pricing_curve.get("term_multipliers", {}).get("12", 1.0))
    elif term_months <= 18:
        term_mult = pricing_curve.get("term_multiplier", {}).get("13-18", 
                    pricing_curve.get("term_multipliers", {}).get("18", 1.1))
    else:
        term_mult = pricing_curve.get("term_multiplier", {}).get("19-24", 
                    pricing_curve.get("term_multipliers", {}).get("24", 1.25))
    
    # Get band_multiplier from pricing curve (carrier-specific pricing by band)
    band_mult = 1.0
    if risk_band:
        band_mult = pricing_curve.get("band_multiplier", {}).get(risk_band, 1.0)
    
    # Calculate age multiplier (example logic - adjust as needed)
    age_mult = 1.0
    if age < 25:
        age_mult = 1.2
    elif age < 35:
        age_mult = 1.0
    elif age < 50:
        age_mult = 0.95
    else:
        age_mult = 1.1
    
    # Calculate tenure multiplier
    tenure_mult = 1.0
    if tenure_months < 6:
        tenure_mult = 1.3
    elif tenure_months < 12:
        tenure_mult = 1.1
    else:
        tenure_mult = 1.0
    
    # Calculate job category multiplier
    job_mult = 1.0
    job_categories = pricing_curve.get("job_category_multiplier", {})
    if not job_categories:
        job_categories = pricing_curve.get("job_multipliers", {})
    job_mult = job_categories.get(job_category, 1.0)
    
    # Calculate base premium in dollars (before risk multiplier and markup)
    base_premium_dollars = (order_value_dollars / 100) * base_rate * term_mult * band_mult * age_mult * tenure_mult * job_mult
    
    # Apply risk multiplier and partner markup
    total_premium_dollars = base_premium_dollars * risk_multiplier * (1 + partner_markup_pct)
    
    # Convert to cents
    base_premium_cents = int(round(base_premium_dollars * 100))
    total_premium_cents = int(round(total_premium_dollars * 100))
    
    # Create breakdown per requirements
    breakdown = {
        "base": base_premium_cents,
        "age_mult": age_mult,
        "tenure_mult": tenure_mult,
        "job_mult": job_mult,
        "risk_mult": risk_multiplier,
        "partner_markup_pct": partner_markup_pct
    }
    
    return total_premium_cents, breakdown

def calculate_premium(
    product_code: str,
    request_data: Dict[str, Any],
    risk_multiplier: float,
    partner_markup_pct: float,
    pricing_curve: Dict[str, Any],
    risk_band: str = None
) -> Tuple[int, Dict[str, Any]]:
    """
    Calculate premium for any product type.
    
    Args:
        product_code: Product code (shipping or ppi)
        request_data: Request data
        risk_multiplier: Risk multiplier from risk scoring
        partner_markup_pct: Partner markup percentage
        pricing_curve: Pricing curve data
        risk_band: Risk band (A-E), required for PPI band_multiplier
        
    Returns:
        Tuple of (premium_cents, breakdown_dict)
    """
    if product_code == "shipping":
        return calculate_shipping_premium(
            request_data, risk_multiplier, partner_markup_pct, pricing_curve
        )
    elif product_code == "ppi":
        return calculate_ppi_premium(
            request_data, risk_multiplier, partner_markup_pct, pricing_curve, risk_band
        )
    else:
        raise ValueError(f"Unknown product code: {product_code}")

def get_pricing_curve_for_carrier(
    carrier_id: str,
    product_code: str,
    seed_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Get pricing curve for a specific carrier and product.
    
    Args:
        carrier_id: Carrier ID
        product_code: Product code
        seed_data: Seed data containing pricing curves
        
    Returns:
        Pricing curve data
    """
    # Find carrier
    carriers = seed_data.get("carriers", [])
    carrier = next((c for c in carriers if c["id"] == carrier_id), None)
    
    if not carrier:
        raise ValueError(f"Carrier {carrier_id} not found")
    
    # Get pricing curve reference
    curve_ref = carrier.get("pricing_curve_ref")
    if not curve_ref:
        raise ValueError(f"No pricing curve reference for carrier {carrier_id}")
    
    # Get pricing curves
    pricing_curves = seed_data.get("pricing_curves", {})
    curve_data = pricing_curves.get(curve_ref)
    
    if not curve_data:
        raise ValueError(f"Pricing curve {curve_ref} not found")
    
    # Get product-specific curve
    product_curve = curve_data.get(product_code)
    if not product_curve:
        raise ValueError(f"No pricing curve for product {product_code} in curve {curve_ref}")
    
    return product_curve
