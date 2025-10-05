"""
Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# TODO: Implement all request/response schemas as per the specification

# Base schemas
class PolicyholderBase(BaseModel):
    """Base policyholder information."""
    name: str
    email: str
    state: str
    age: Optional[int] = None
    tenure_months: Optional[int] = None

# Request schemas - Flat structure per requirements
class QuoteRequest(BaseModel):
    """Quote request - supports both shipping and PPI."""
    product_code: str = Field(description="Product code: shipping or ppi")
    partner_id: str = Field(description="Partner identifier")
    
    # Shipping fields
    declared_value: Optional[float] = Field(None, gt=0, description="Declared value in dollars (shipping)")
    item_category: Optional[str] = Field(None, description="Item category (shipping)")
    destination_state: Optional[str] = Field(None, description="Destination state (shipping)")
    destination_risk: Optional[str] = Field(None, description="Destination risk level (shipping)")
    service_level: Optional[str] = Field(None, description="Service level (shipping)")
    
    # PPI fields
    order_value: Optional[float] = Field(None, gt=0, description="Order value in dollars (PPI)")
    term_months: Optional[int] = Field(None, gt=0, le=24, description="Term in months (PPI)")
    age: Optional[int] = Field(None, gt=0, description="Policyholder age (PPI)")
    tenure_months: Optional[int] = Field(None, gt=0, description="Job tenure in months (PPI)")
    job_category: Optional[str] = Field(None, description="Job category (PPI)")
    state: Optional[str] = Field(None, description="State (PPI)")

class BindingRequest(BaseModel):
    """Policy binding request."""
    quote_id: int
    policyholder: PolicyholderBase

class SimulationRequest(BaseModel):
    """Portfolio simulation request."""
    as_of_month: str = Field(description="Simulation month in YYYY-MM format")
    scenario_count: int = Field(gt=0, le=10000, description="Number of scenarios")
    retention_grid: List[float] = Field(description="Retention levels to test")
    reinsurance_params: Dict[str, float] = Field(description="Reinsurance parameters")

# Response schemas
class PriceBreakdown(BaseModel):
    """Price breakdown details per requirements."""
    base: int = Field(description="Base premium in cents")
    category_mult: Optional[float] = Field(None, description="Category multiplier (shipping)")
    dest_mult: Optional[float] = Field(None, description="Destination multiplier (shipping)")
    service_mult: Optional[float] = Field(None, description="Service level multiplier (shipping)")
    risk_mult: float = Field(description="Risk multiplier")
    partner_markup_pct: float = Field(description="Partner markup percentage")
    
    # PPI-specific multipliers
    age_mult: Optional[float] = Field(None, description="Age multiplier (PPI)")
    tenure_mult: Optional[float] = Field(None, description="Tenure multiplier (PPI)")
    job_mult: Optional[float] = Field(None, description="Job category multiplier (PPI)")

class ComplianceResult(BaseModel):
    """Compliance check result per requirements."""
    decision: str = Field(description="allow or block")
    disclosures: List[str]
    report_id: str = Field(description="Compliance report ID")

class QuoteResponse(BaseModel):
    """Quote response."""
    quote_id: int
    product_code: str
    premium_cents: int
    price_breakdown: PriceBreakdown
    risk_band: str
    risk_multiplier: float
    carrier_suggestion: Optional[str]
    router_rationale: Optional[str]
    compliance: ComplianceResult

class BindingResponse(BaseModel):
    """Policy binding response."""
    policy_id: int
    status: str
    premium_total_cents: int
    carrier_id: str
    effective_date: str

class PolicyResponse(BaseModel):
    """Policy details response."""
    policy_id: int
    quote_id: int
    product_code: str
    carrier_id: str
    premium_total_cents: int
    status: str
    effective_date: str
    policyholder: Dict[str, Any]
    risk_band: str
    risk_multiplier: float
    compliance_disclosures: List[str]
    ledger_total_cents: int

class SimulationResult(BaseModel):
    """Portfolio simulation result."""
    var95: float
    var99: float
    tailvar99: float
    retention_table: List[Dict[str, float]]
    recommended: Dict[str, Any]
