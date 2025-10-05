"""
SQLModel database models for the insurance API.
"""

from sqlmodel import SQLModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

# TODO: Implement all database models as per the specification

class Partner(SQLModel, table=True):
    """Partner model for API authentication and configuration."""
    id: str = Field(primary_key=True)
    api_key: str = Field(unique=True, index=True)
    markup_pct: float
    regions: str  # JSON string
    products: str  # JSON string
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Carrier(SQLModel, table=True):
    """Carrier model for insurance providers."""
    id: str = Field(primary_key=True)
    name: str
    appetite_json: str  # JSON string
    capacity_monthly_limit: int
    pricing_curve_ref: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CarrierCapacity(SQLModel, table=True):
    """Carrier capacity tracking per month."""
    id: Optional[int] = Field(default=None, primary_key=True)
    carrier_id: str = Field(foreign_key="carrier.id")
    as_of_month: str  # YYYY-MM format
    remaining_count: int
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Quote(SQLModel, table=True):
    """Quote model for insurance quotes."""
    id: Optional[int] = Field(default=None, primary_key=True)
    product_code: str
    request_json: str  # JSON string
    risk_band: str
    risk_multiplier: float
    price_breakdown_json: str  # JSON string
    carrier_suggestion: Optional[str]
    router_rationale: Optional[str]
    compliance_json: str  # JSON string
    premium_cents: int
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Policy(SQLModel, table=True):
    """Policy model for bound insurance policies."""
    id: Optional[int] = Field(default=None, primary_key=True)
    quote_id: int = Field(foreign_key="quote.id")
    product_code: str
    carrier_id: str = Field(foreign_key="carrier.id")
    premium_total_cents: int
    status: str
    effective_date: str
    policyholder_json: str  # JSON string
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Ledger(SQLModel, table=True):
    """Ledger model for tracking written premiums."""
    id: Optional[int] = Field(default=None, primary_key=True)
    policy_id: int = Field(foreign_key="policy.id")
    written_premium_cents: int
    written_at: datetime = Field(default_factory=datetime.utcnow)

class IdempotencyKey(SQLModel, table=True):
    """Idempotency key model for preventing duplicate requests."""
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True)
    method: str
    path: str
    request_hash: str
    response_json: str  # JSON string
    created_at: datetime = Field(default_factory=datetime.utcnow)
