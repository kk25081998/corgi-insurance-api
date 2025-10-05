"""
Simulation service for portfolio analysis and Monte Carlo simulations.
"""

from typing import Dict, Any, List
import numpy as np
import random
import statistics

def run_portfolio_simulation(
    as_of_month: str,
    scenario_count: int,
    retention_grid: List[float],
    reinsurance_params: Dict[str, float],
    db_session = None
) -> Dict[str, Any]:
    """
    Run Monte Carlo portfolio simulation.
    
    Args:
        as_of_month: Simulation month in YYYY-MM format
        scenario_count: Number of scenarios to run
        retention_grid: Retention levels to test
        reinsurance_params: Reinsurance parameters (rate_on_line, load)
        db_session: Database session for historical data
        
    Returns:
        Simulation results with VaR, TailVaR, and retention analysis
    """
    # Set fixed seed for deterministic results
    np.random.seed(42)
    random.seed(42)
    
    # Generate loss scenarios based on historical data
    scenarios = _generate_scenarios(scenario_count, as_of_month, db_session)
    
    # Calculate VaR metrics
    var95 = _calculate_var(scenarios, 0.95)
    var99 = _calculate_var(scenarios, 0.99)
    tailvar99 = _calculate_tail_var(scenarios, 0.99)
    
    # Calculate retention table
    retention_table = _calculate_retention_table(
        scenarios, retention_grid, reinsurance_params
    )
    
    # Find recommended retention
    recommended = _find_recommended_retention(retention_table)
    
    return {
        "as_of_month": as_of_month,
        "scenario_count": scenario_count,
        "var95": var95,
        "var99": var99,
        "tailvar99": tailvar99,
        "retention_table": retention_table,
        "recommended": recommended,
        "scenario_statistics": {
            "mean": statistics.mean(scenarios),
            "median": statistics.median(scenarios),
            "std_dev": statistics.stdev(scenarios) if len(scenarios) > 1 else 0,
            "min": min(scenarios),
            "max": max(scenarios)
        }
    }

def _generate_scenarios(scenario_count: int, as_of_month: str, db_session = None) -> List[float]:
    """Generate loss scenarios for simulation."""
    if db_session:
        # Use historical data if available
        scenarios = _generate_scenarios_from_history(scenario_count, as_of_month, db_session)
    else:
        # Generate synthetic scenarios
        scenarios = _generate_synthetic_scenarios(scenario_count)
    
    return scenarios

def _generate_scenarios_from_history(scenario_count: int, as_of_month: str, db_session) -> List[float]:
    """Generate scenarios based on historical policy data."""
    from app.models import Policy, Ledger
    from sqlalchemy import func
    
    try:
        # Get historical premiums and claims data
        # For this simulation, we'll use premiums as proxy for potential losses
        historical_premiums = db_session.query(Policy.premium_total_cents).all()
        
        if not historical_premiums:
            # Fallback to synthetic if no data
            return _generate_synthetic_scenarios(scenario_count)
        
        premiums = [p[0] for p in historical_premiums]
        
        # Fit a distribution to historical data
        mean_premium = statistics.mean(premiums)
        std_premium = statistics.stdev(premiums) if len(premiums) > 1 else mean_premium * 0.3
        
        # Generate scenarios using normal distribution with some skew
        base_scenarios = np.random.normal(mean_premium, std_premium, scenario_count)
        
        # Add some extreme events (fat tail)
        extreme_probability = 0.05  # 5% chance of extreme event
        extreme_multiplier = 3.0
        
        scenarios = []
        for scenario in base_scenarios:
            if random.random() < extreme_probability:
                # Extreme event
                scenarios.append(scenario * extreme_multiplier)
            else:
                scenarios.append(max(0, scenario))  # Ensure non-negative
        
        return scenarios
        
    except Exception as e:
        print(f"Error generating scenarios from history: {e}")
        return _generate_synthetic_scenarios(scenario_count)

def _generate_synthetic_scenarios(scenario_count: int) -> List[float]:
    """Generate synthetic loss scenarios."""
    # Use exponential distribution for insurance losses
    # Mean loss of $1000 with some variation
    base_scenarios = np.random.exponential(1000, scenario_count)
    
    # Add some extreme events
    extreme_probability = 0.02  # 2% chance of extreme event
    extreme_multiplier = 10.0
    
    scenarios = []
    for scenario in base_scenarios:
        if random.random() < extreme_probability:
            # Extreme event
            scenarios.append(scenario * extreme_multiplier)
        else:
            scenarios.append(scenario)
    
    return scenarios

def _calculate_var(scenarios: List[float], confidence_level: float) -> float:
    """Calculate Value at Risk.
    
    VaR at confidence level X is the loss value such that there's a (1-X) 
    probability of exceeding it. For example, VaR95 means 5% chance of exceeding.
    """
    if not scenarios:
        return 0.0
    
    sorted_scenarios = sorted(scenarios)
    # VaR should be at the high end (worst losses)
    # For 95% confidence, we want the 95th percentile (index at 95% of length)
    index = int(confidence_level * len(sorted_scenarios))
    index = max(0, min(index, len(sorted_scenarios) - 1))
    return sorted_scenarios[index]

def _calculate_tail_var(scenarios: List[float], confidence_level: float) -> float:
    """Calculate Tail Value at Risk (Expected Shortfall)."""
    if not scenarios:
        return 0.0
    
    var = _calculate_var(scenarios, confidence_level)
    tail_scenarios = [s for s in scenarios if s >= var]
    
    if not tail_scenarios:
        return var
    
    return statistics.mean(tail_scenarios)

def _calculate_retention_table(
    scenarios: List[float],
    retention_grid: List[float],
    reinsurance_params: Dict[str, float]
) -> List[Dict[str, float]]:
    """Calculate retention analysis table."""
    table = []
    
    rate_on_line = reinsurance_params.get("rate_on_line", 0.1)
    load = reinsurance_params.get("load", 0.2)
    
    for retention in retention_grid:
        # Calculate expected retained loss
        expected_loss = sum(min(s, retention) for s in scenarios) / len(scenarios)
        
        # Calculate expected ceded loss
        expected_ceded = sum(max(0, s - retention) for s in scenarios) / len(scenarios)
        
        # Calculate reinsurance premium
        reinsurance_premium = expected_ceded * rate_on_line * (1 + load)
        
        # Calculate expected net cost
        expected_net = expected_loss + reinsurance_premium
        
        # Calculate cost efficiency (lower is better)
        cost_efficiency = expected_net / max(expected_loss, 0.01)
        
        table.append({
            "retention": retention,
            "expected_loss": round(expected_loss, 2),
            "expected_ceded": round(expected_ceded, 2),
            "reinsurance_premium": round(reinsurance_premium, 2),
            "expected_net": round(expected_net, 2),
            "cost_efficiency": round(cost_efficiency, 3)
        })
    
    return table

def _find_recommended_retention(retention_table: List[Dict[str, float]]) -> Dict[str, float]:
    """Find recommended retention with optimal cost efficiency."""
    if not retention_table:
        return {}
    
    # Find retention with minimum expected net cost
    best_retention = min(retention_table, key=lambda x: x["expected_net"])
    
    return {
        "retention": best_retention["retention"],
        "expected_net": best_retention["expected_net"],
        "expected_loss": best_retention["expected_loss"],
        "reinsurance_premium": best_retention["reinsurance_premium"],
        "cost_efficiency": best_retention["cost_efficiency"],
        "rationale": f"Minimum expected net cost of ${best_retention['expected_net']:.2f}"
    }

def run_sensitivity_analysis(
    base_scenarios: List[float],
    retention_levels: List[float],
    reinsurance_params: Dict[str, float]
) -> Dict[str, Any]:
    """
    Run sensitivity analysis on key parameters.
    
    Args:
        base_scenarios: Base loss scenarios
        retention_levels: Retention levels to test
        reinsurance_params: Base reinsurance parameters
        
    Returns:
        Sensitivity analysis results
    """
    # Test different rate on line values
    rate_variations = [0.05, 0.10, 0.15, 0.20]
    rate_sensitivity = []
    
    for rate in rate_variations:
        params = reinsurance_params.copy()
        params["rate_on_line"] = rate
        
        table = _calculate_retention_table(base_scenarios, retention_levels, params)
        recommended = _find_recommended_retention(table)
        
        rate_sensitivity.append({
            "rate_on_line": rate,
            "recommended_retention": recommended.get("retention", 0),
            "expected_net": recommended.get("expected_net", 0)
        })
    
    # Test different load factors
    load_variations = [0.1, 0.2, 0.3, 0.4]
    load_sensitivity = []
    
    for load in load_variations:
        params = reinsurance_params.copy()
        params["load"] = load
        
        table = _calculate_retention_table(base_scenarios, retention_levels, params)
        recommended = _find_recommended_retention(table)
        
        load_sensitivity.append({
            "load": load,
            "recommended_retention": recommended.get("retention", 0),
            "expected_net": recommended.get("expected_net", 0)
        })
    
    return {
        "rate_on_line_sensitivity": rate_sensitivity,
        "load_sensitivity": load_sensitivity,
        "base_scenario_count": len(base_scenarios),
        "retention_levels_tested": len(retention_levels)
    }
