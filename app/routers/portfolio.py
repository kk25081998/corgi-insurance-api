"""
Portfolio router for handling portfolio simulation requests.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session
from typing import Dict, Any
import json

from app.schemas import SimulationRequest, SimulationResult
from app.deps import get_current_partner, check_idempotency_key, store_idempotency_response, generate_request_hash
from app.db import get_session
from app.services.simulate import run_portfolio_simulation

router = APIRouter()

@router.post("/portfolio/simulate", response_model=SimulationResult)
async def simulate_portfolio(
    request: SimulationRequest,
    request_obj: Request,
    partner: Dict[str, Any] = Depends(get_current_partner),
    session: Session = Depends(get_session)
):
    """
    Run portfolio simulation with Monte Carlo analysis.
    
    This endpoint:
    1. Validates simulation parameters
    2. Runs Monte Carlo simulation
    3. Calculates VaR(95), VaR(99), TailVaR(99)
    4. Generates retention table
    5. Recommends optimal retention
    6. Returns simulation results
    """
    # Check idempotency
    cached_response = await check_idempotency_key(request_obj, session)
    if cached_response:
        return cached_response
    
    # Validate simulation parameters
    if request.scenario_count > 10000:
        raise HTTPException(
            status_code=400,
            detail="Maximum scenario count is 10,000"
        )
    
    if not request.retention_grid:
        raise HTTPException(
            status_code=400,
            detail="Retention grid cannot be empty"
        )
    
    # Validate retention values are positive
    if any(r <= 0 for r in request.retention_grid):
        raise HTTPException(
            status_code=400,
            detail="All retention values must be positive"
        )
    
    # Validate reinsurance parameters
    required_params = ["rate_on_line", "load"]
    for param in required_params:
        if param not in request.reinsurance_params:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required reinsurance parameter: {param}"
            )
    
    rate_on_line = request.reinsurance_params["rate_on_line"]
    load = request.reinsurance_params["load"]
    
    if rate_on_line <= 0 or rate_on_line > 1:
        raise HTTPException(
            status_code=400,
            detail="Rate on line must be between 0 and 1"
        )
    
    if load < 0 or load > 1:
        raise HTTPException(
            status_code=400,
            detail="Load must be between 0 and 1"
        )
    
    try:
        # Run the simulation
        simulation_results = run_portfolio_simulation(
            as_of_month=request.as_of_month,
            scenario_count=request.scenario_count,
            retention_grid=request.retention_grid,
            reinsurance_params=request.reinsurance_params,
            db_session=session
        )
        
        # Prepare response
        response_data = SimulationResult(
            var95=simulation_results["var95"],
            var99=simulation_results["var99"],
            tailvar99=simulation_results["tailvar99"],
            retention_table=simulation_results["retention_table"],
            recommended=simulation_results["recommended"]
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
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Simulation failed: {str(e)}"
        )
