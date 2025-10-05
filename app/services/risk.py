"""
Risk scoring service for deterministic risk assessment.
"""

from typing import Dict, Any, Tuple
import math

def calculate_shipping_risk_score(request_data: Dict[str, Any]) -> float:
    """
    Calculate shipping insurance risk score.
    
    Formula: s = 0.02*(declared_value/1000) + risk(dest_risk) + svc(service_level) + cat_hi(item_category)
    
    Where:
    - risk(dest_risk): low=0, medium=0.5, high=1.0
    - svc(service_level): ground=0.2, expedited=0.1, overnight=0
    - cat_hi(item_category): electronics_high_value/jewelry_high_value=0.3, others=0
    
    Args:
        request_data: Shipping request data
        
    Returns:
        Risk score as float
    """
    declared_value = request_data.get("declared_value", 0)
    dest_risk = request_data.get("destination_risk", "low")
    service_level = request_data.get("service_level", "ground")
    item_category = request_data.get("item_category", "standard")
    
    # Base score: 0.02 * (declared_value / 1000)
    base_score = 0.02 * (declared_value / 1000)
    
    # Destination risk multiplier
    dest_risk_multipliers = {
        "low": 0.0,
        "medium": 0.5,
        "high": 1.0
    }
    dest_risk_score = dest_risk_multipliers.get(dest_risk, 0.0)
    
    # Service level multiplier
    service_multipliers = {
        "ground": 0.2,
        "expedited": 0.1,
        "overnight": 0.0
    }
    service_score = service_multipliers.get(service_level, 0.2)
    
    # Category high-value multiplier
    high_value_categories = ["electronics_high_value", "jewelry_high_value"]
    category_score = 0.3 if item_category in high_value_categories else 0.0
    
    total_score = base_score + dest_risk_score + service_score + category_score
    
    return round(total_score, 4)

def calculate_ppi_risk_score(request_data: Dict[str, Any], policyholder: Dict[str, Any]) -> float:
    """
    Calculate PPI insurance risk score.
    
    Formula: s = 0.02*(order_value/100) + 0.1*(term_months/6) + (age<25?0.3:0) + (tenure_months<6?0.3:0)
    
    Args:
        request_data: PPI request data
        policyholder: Policyholder information
        
    Returns:
        Risk score as float
    """
    order_value = request_data.get("order_value", 0)
    term_months = request_data.get("term_months", 6)
    age = policyholder.get("age", 30)
    tenure_months = policyholder.get("tenure_months", 12)
    
    # Base score: 0.02 * (order_value / 100)
    base_score = 0.02 * (order_value / 100)
    
    # Term score: 0.1 * (term_months / 6)
    term_score = 0.1 * (term_months / 6)
    
    # Age penalty: 0.3 if age < 25, else 0
    age_score = 0.3 if age < 25 else 0.0
    
    # Tenure penalty: 0.3 if tenure_months < 6, else 0
    tenure_score = 0.3 if tenure_months < 6 else 0.0
    
    total_score = base_score + term_score + age_score + tenure_score
    
    return round(total_score, 4)

def map_risk_score_to_band(score: float) -> Tuple[str, float]:
    """
    Map risk score to risk band and multiplier.
    
    Bands:
    - A: <0.4 → 0.90
    - B: <0.8 → 1.00
    - C: <1.2 → 1.10
    - D: <1.6 → 1.25
    - E: else → 1.40
    
    Args:
        score: Risk score
        
    Returns:
        Tuple of (band, multiplier)
    """
    if score < 0.4:
        return "A", 0.90
    elif score < 0.8:
        return "B", 1.00
    elif score < 1.2:
        return "C", 1.10
    elif score < 1.6:
        return "D", 1.25
    else:
        return "E", 1.40

def calculate_risk_assessment(
    product_code: str,
    request_data: Dict[str, Any],
    policyholder: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Calculate complete risk assessment for a product.
    
    Args:
        product_code: Product code (shipping or ppi)
        request_data: Request data
        policyholder: Policyholder information (required for PPI)
        
    Returns:
        Risk assessment with score, band, and multiplier
    """
    if product_code == "shipping":
        score = calculate_shipping_risk_score(request_data)
    elif product_code == "ppi":
        if not policyholder:
            raise ValueError("Policyholder data required for PPI risk assessment")
        score = calculate_ppi_risk_score(request_data, policyholder)
    else:
        raise ValueError(f"Unknown product code: {product_code}")
    
    band, multiplier = map_risk_score_to_band(score)
    
    return {
        "risk_score": score,
        "risk_band": band,
        "risk_multiplier": multiplier,
        "product_code": product_code
    }
