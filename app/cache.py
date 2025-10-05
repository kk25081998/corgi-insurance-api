"""
Config cache module for performance optimization.

This module provides in-memory caching of configuration files
to avoid repeated disk I/O on every request.
"""

import json
import os
from typing import Dict, Any, Optional
from threading import Lock

class ConfigCache:
    """Thread-safe configuration cache."""
    
    def __init__(self):
        self._seed_data: Optional[Dict[str, Any]] = None
        self._carriers_cache: Optional[Dict[str, Any]] = None
        self._partners_cache: Optional[Dict[str, Any]] = None
        self._pricing_curves_cache: Optional[Dict[str, Any]] = None
        self._lock = Lock()
    
    def get_seed_data(self) -> Dict[str, Any]:
        """Get cached seed data, loading from disk if not cached."""
        if self._seed_data is None:
            with self._lock:
                if self._seed_data is None:  # Double-check locking
                    seed_file = os.path.join(
                        os.path.dirname(__file__), 
                        "config", 
                        "seed.json"
                    )
                    with open(seed_file, 'r') as f:
                        self._seed_data = json.load(f)
        return self._seed_data
    
    def get_carriers(self) -> list:
        """Get cached carriers list."""
        if self._carriers_cache is None:
            seed_data = self.get_seed_data()
            self._carriers_cache = seed_data.get("carriers", [])
        return self._carriers_cache
    
    def get_partners(self) -> list:
        """Get cached partners list."""
        if self._partners_cache is None:
            seed_data = self.get_seed_data()
            self._partners_cache = seed_data.get("partners", [])
        return self._partners_cache
    
    def get_pricing_curves(self) -> Dict[str, Any]:
        """Get cached pricing curves."""
        if self._pricing_curves_cache is None:
            seed_data = self.get_seed_data()
            self._pricing_curves_cache = seed_data.get("pricing", {})
        return self._pricing_curves_cache
    
    def get_pricing_curve_for_carrier(
        self, 
        carrier_id: str, 
        product_code: str
    ) -> Dict[str, Any]:
        """
        Get pricing curve for a specific carrier and product.
        
        Args:
            carrier_id: Carrier ID
            product_code: Product code
            
        Returns:
            Pricing curve data
        """
        # Find carrier
        carriers = self.get_carriers()
        carrier = next((c for c in carriers if c["id"] == carrier_id), None)
        
        if not carrier:
            raise ValueError(f"Carrier {carrier_id} not found")
        
        # Get pricing curve reference
        curve_ref = carrier.get("pricing_curve_ref")
        if not curve_ref:
            raise ValueError(f"No pricing curve reference for carrier {carrier_id}")
        
        # Get pricing data
        pricing_data = self.get_pricing_curves()
        product_pricing = pricing_data.get(product_code, {})
        
        if not product_pricing:
            raise ValueError(f"No pricing data for product {product_code}")
        
        # Build pricing curve for this carrier
        pricing_curve = {}
        
        # Get base rate for this carrier
        base_rates = product_pricing.get("base_rate_per_100_value", {})
        carrier_base_rate = base_rates.get(curve_ref, 0.55)  # Use carrier-specific rate
        pricing_curve["base_rate"] = carrier_base_rate
        
        # Copy other multipliers
        if product_code == "shipping":
            pricing_curve["category_multiplier"] = product_pricing.get("category_multiplier", {})
            pricing_curve["destination_multiplier"] = product_pricing.get("destination_multiplier", {})
            pricing_curve["service_level_multiplier"] = product_pricing.get("service_level_multiplier", {})
        elif product_code == "ppi":
            pricing_curve["term_multiplier"] = product_pricing.get("term_multiplier", {})
            pricing_curve["band_multiplier"] = product_pricing.get("band_multiplier", {})
        
        return pricing_curve
    
    def clear_cache(self):
        """Clear all cached data (useful for testing)."""
        with self._lock:
            self._seed_data = None
            self._carriers_cache = None
            self._partners_cache = None
            self._pricing_curves_cache = None

# Global cache instance
config_cache = ConfigCache()

