"""
Ledger service for tracking written premiums and capacity management.
"""

from typing import Dict, Any, Optional
from datetime import datetime, date
import json

def write_premium_to_ledger(
    policy_id: int,
    premium_cents: int,
    db_session,
    written_at: datetime = None
) -> Dict[str, Any]:
    """
    Write premium to ledger.
    
    Args:
        policy_id: Policy ID
        premium_cents: Premium amount in cents
        db_session: Database session
        written_at: Write timestamp (defaults to now)
        
    Returns:
        Ledger entry data
    """
    from app.models import Ledger
    
    if written_at is None:
        written_at = datetime.utcnow()
    
    # Create ledger entry
    ledger_entry = Ledger(
        policy_id=policy_id,
        written_premium_cents=premium_cents,
        written_at=written_at
    )
    
    db_session.add(ledger_entry)
    db_session.commit()
    
    return {
        "id": ledger_entry.id,
        "policy_id": policy_id,
        "written_premium_cents": premium_cents,
        "written_at": written_at.isoformat()
    }

def get_ledger_totals(
    policy_id: Optional[int] = None,
    as_of_month: Optional[str] = None,
    db_session = None
) -> Dict[str, Any]:
    """
    Get ledger totals for policies or a specific month.
    
    Args:
        policy_id: Optional policy ID to filter by
        as_of_month: Optional month in YYYY-MM format
        db_session: Database session
        
    Returns:
        Ledger totals summary
    """
    from app.models import Ledger
    from sqlalchemy import func
    
    query = db_session.query(Ledger)
    
    # Filter by policy if specified
    if policy_id:
        query = query.filter(Ledger.policy_id == policy_id)
    
    # Filter by month if specified
    if as_of_month:
        year, month = as_of_month.split('-')
        query = query.filter(
            func.extract('year', Ledger.written_at) == int(year),
            func.extract('month', Ledger.written_at) == int(month)
        )
    
    # Calculate totals
    total_written_premium = query.with_entities(
        func.sum(Ledger.written_premium_cents)
    ).scalar() or 0
    
    total_policies = query.with_entities(
        func.count(func.distinct(Ledger.policy_id))
    ).scalar() or 0
    
    total_entries = query.count()
    
    return {
        "total_written_premium_cents": total_written_premium,
        "total_written_premium_dollars": total_written_premium / 100,
        "total_policies": total_policies,
        "total_entries": total_entries,
        "as_of_month": as_of_month,
        "policy_id": policy_id
    }

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
    from app.services.routing import decrement_carrier_capacity as routing_decrement
    
    # Delegate to routing service which has the database logic
    return routing_decrement(carrier_id, as_of_month, db_session)

def calculate_pro_rata_cancel(
    premium_cents: int,
    effective_date: str,
    cancel_date: str
) -> int:
    """
    Calculate pro-rata cancellation refund using 30/360 method.
    
    This is optional functionality as mentioned in the spec.
    
    Args:
        premium_cents: Original premium in cents
        effective_date: Policy effective date (YYYY-MM-DD)
        cancel_date: Cancellation date (YYYY-MM-DD)
        
    Returns:
        Refund amount in cents
    """
    try:
        # Parse dates
        eff_date = datetime.strptime(effective_date, "%Y-%m-%d").date()
        cancel_date_obj = datetime.strptime(cancel_date, "%Y-%m-%d").date()
        
        # Calculate days using 30/360 method
        eff_year, eff_month, eff_day = eff_date.year, eff_date.month, eff_date.day
        cancel_year, cancel_month, cancel_day = cancel_date_obj.year, cancel_date_obj.month, cancel_date_obj.day
        
        # Adjust days to 30 for 30/360
        if eff_day == 31:
            eff_day = 30
        if cancel_day == 31:
            cancel_day = 30
        
        # Calculate total days in policy period (assuming 12 months)
        total_days = 360  # 30 days * 12 months
        
        # Calculate days used
        days_used = (
            (cancel_year - eff_year) * 360 +
            (cancel_month - eff_month) * 30 +
            (cancel_day - eff_day)
        )
        
        # Ensure days_used is positive
        days_used = max(0, days_used)
        
        # Calculate refund
        refund_ratio = max(0, (total_days - days_used) / total_days)
        refund_cents = int(premium_cents * refund_ratio)
        
        return refund_cents
        
    except (ValueError, TypeError) as e:
        print(f"Error calculating pro-rata refund: {e}")
        return 0

def get_policy_ledger_summary(
    policy_id: int,
    db_session
) -> Dict[str, Any]:
    """
    Get ledger summary for a specific policy.
    
    Args:
        policy_id: Policy ID
        db_session: Database session
        
    Returns:
        Policy ledger summary
    """
    from app.models import Ledger, Policy
    
    # Get policy details
    policy = db_session.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        return {"error": "Policy not found"}
    
    # Get ledger entries for this policy
    ledger_entries = db_session.query(Ledger).filter(
        Ledger.policy_id == policy_id
    ).all()
    
    total_written = sum(entry.written_premium_cents for entry in ledger_entries)
    
    return {
        "policy_id": policy_id,
        "policy_status": policy.status,
        "premium_total_cents": policy.premium_total_cents,
        "total_written_premium_cents": total_written,
        "ledger_entries": [
            {
                "id": entry.id,
                "written_premium_cents": entry.written_premium_cents,
                "written_at": entry.written_at.isoformat()
            }
            for entry in ledger_entries
        ],
        "entries_count": len(ledger_entries)
    }
