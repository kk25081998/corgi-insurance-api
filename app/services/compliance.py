"""
Compliance service for YAML-based rules engine.
"""

from typing import Dict, Any, List
import yaml
import os
import re
import json
import uuid

class ComplianceEngine:
    """Compliance rules engine with proper condition evaluation."""
    
    def __init__(self):
        self.rules = []
        self._load_rules()
    
    def _load_rules(self):
        """Load compliance rules from YAML file."""
        config_path = os.path.join(os.path.dirname(__file__), "..", "config", "compliance.yaml")
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                self.rules = config.get("rules", [])
        except FileNotFoundError:
            print(f"Warning: Compliance config not found at {config_path}")
            self.rules = []
    
    def evaluate_rules(
        self,
        product_code: str,
        request_data: Dict[str, Any],
        policyholder: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Evaluate compliance rules for a request.
        
        Args:
            product_code: Product code (shipping or ppi)
            request_data: Request data
            policyholder: Policyholder information (optional for quotes)
            
        Returns:
            Compliance result with decision, disclosures, and rules applied
        """
        disclosures = []
        rules_applied = []
        decision = "allow"
        
        # Create evaluation context
        context = {
            "product_code": product_code,
            **request_data
        }
        
        # Add policyholder data if available
        if policyholder:
            context.update(policyholder)
        
        # Evaluate each rule
        for rule in self.rules:
            if rule.get("applies_to") != product_code:
                continue
            
            # Check if rule has criteria
            has_criteria = "criteria" in rule and rule["criteria"]
            
            # If no criteria, rule always applies (for general disclosures)
            # If has criteria, evaluate them
            if not has_criteria or self._evaluate_criteria(rule["criteria"], context):
                rules_applied.append(rule["id"])
                
                # Handle disclosures
                if rule.get("type") == "disclosure":
                    disclosures.append(rule.get("message", ""))
                
                # Block decision overrides allow
                if rule.get("type") == "block":
                    decision = "block"
                    # Also add message to disclosures for block rules
                    disclosures.append(rule.get("message", ""))
        
        # Generate compliance report ID
        report_id = f"cr_{uuid.uuid4().hex[:8]}"
        
        return {
            "decision": decision,
            "disclosures": disclosures,
            "report_id": report_id,
            # Keep these for internal use but they won't be in API response
            "rules_applied": rules_applied,
            "version": "1.0"
        }
    
    def _evaluate_criteria(self, criteria: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        Evaluate criteria dictionary against context.
        Uses AND logic: ALL criteria must be met for rule to apply.
        
        Args:
            criteria: Criteria dictionary (e.g., {"state_in": ["GA", "VT"]})
            context: Evaluation context
            
        Returns:
            True if ALL criteria are met
        """
        if not criteria:
            return False
        
        try:
            # Collect all criteria results - ALL must be True
            results = []
            
            # Handle state_in criteria
            if "state_in" in criteria:
                state = context.get("state")
                excluded_states = criteria["state_in"]
                results.append(state in excluded_states)
            
            # Handle item_category_in criteria
            if "item_category_in" in criteria:
                item_category = context.get("item_category")
                excluded_categories = criteria["item_category_in"]
                results.append(item_category in excluded_categories)
            
            # Handle min_age criteria
            if "min_age" in criteria:
                age = context.get("age", 0)
                min_age = criteria["min_age"]
                results.append(age < min_age)
            
            # Handle min_tenure_months criteria
            if "min_tenure_months" in criteria:
                tenure_months = context.get("tenure_months", 0)
                min_tenure = criteria["min_tenure_months"]
                results.append(tenure_months < min_tenure)
            
            # Handle declared_value_greater_than criteria
            if "declared_value_greater_than" in criteria:
                declared_value = context.get("declared_value", 0)
                threshold = criteria["declared_value_greater_than"]
                results.append(declared_value > threshold)
            
            # Handle age_less_than criteria
            if "age_less_than" in criteria:
                age = context.get("age", 0)
                threshold = criteria["age_less_than"]
                results.append(age < threshold)
            
            # Handle tenure_months_less_than criteria
            if "tenure_months_less_than" in criteria:
                tenure_months = context.get("tenure_months", 0)
                threshold = criteria["tenure_months_less_than"]
                results.append(tenure_months < threshold)
            
            # Handle term_months_greater_than criteria
            if "term_months_greater_than" in criteria:
                term_months = context.get("term_months", 0)
                threshold = criteria["term_months_greater_than"]
                results.append(term_months > threshold)
            
            # Return True only if ALL criteria are met
            return len(results) > 0 and all(results)
            
        except (ValueError, TypeError, AttributeError) as e:
            print(f"Error evaluating criteria '{criteria}': {e}")
            return False

    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """
        Evaluate a condition string against context using proper parsing.
        
        Args:
            condition: Condition string (e.g., "state == 'GA'", "declared_value > 10000")
            context: Evaluation context
            
        Returns:
            True if condition is met
        """
        if not condition:
            return False
        
        try:
            # Handle string equality comparisons
            if " == " in condition:
                parts = condition.split(" == ")
                if len(parts) == 2:
                    field = parts[0].strip()
                    value = parts[1].strip().strip("'\"")
                    return context.get(field) == value
            
            # Handle numeric comparisons
            elif " > " in condition:
                parts = condition.split(" > ")
                if len(parts) == 2:
                    field = parts[0].strip()
                    threshold = float(parts[1].strip())
                    field_value = context.get(field, 0)
                    return float(field_value) > threshold
            
            elif " < " in condition:
                parts = condition.split(" < ")
                if len(parts) == 2:
                    field = parts[0].strip()
                    threshold = float(parts[1].strip())
                    field_value = context.get(field, 0)
                    return float(field_value) < threshold
            
            elif " >= " in condition:
                parts = condition.split(" >= ")
                if len(parts) == 2:
                    field = parts[0].strip()
                    threshold = float(parts[1].strip())
                    field_value = context.get(field, 0)
                    return float(field_value) >= threshold
            
            elif " <= " in condition:
                parts = condition.split(" <= ")
                if len(parts) == 2:
                    field = parts[0].strip()
                    threshold = float(parts[1].strip())
                    field_value = context.get(field, 0)
                    return float(field_value) <= threshold
            
            # Handle string contains
            elif " in " in condition:
                parts = condition.split(" in ")
                if len(parts) == 2:
                    field = parts[0].strip()
                    value = parts[1].strip().strip("'\"")
                    field_value = context.get(field, "")
                    return value in str(field_value)
            
            # Handle boolean field checks
            elif condition in context:
                return bool(context.get(condition))
            
            # Fallback to simple string matching for known patterns
            return self._fallback_evaluation(condition, context)
            
        except (ValueError, TypeError, AttributeError) as e:
            print(f"Error evaluating condition '{condition}': {e}")
            return False
    
    def _fallback_evaluation(self, condition: str, context: Dict[str, Any]) -> bool:
        """Fallback evaluation for known condition patterns."""
        # Known patterns from compliance.yaml
        if "state == 'GA'" in condition:
            return context.get("state") == "GA"
        elif "declared_value > 10000" in condition:
            return context.get("declared_value", 0) > 10000
        elif "age < 25" in condition:
            return context.get("age", 30) < 25
        elif "tenure_months < 6" in condition:
            return context.get("tenure_months", 12) < 6
        elif "item_category == 'electronics_high_value'" in condition:
            return context.get("item_category") == "electronics_high_value"
        elif "term_months > 24" in condition:
            return context.get("term_months", 6) > 24
        elif "declared_value > 100000" in condition:
            return context.get("declared_value", 0) > 100000
        
        return False

# Global compliance engine instance
compliance_engine = ComplianceEngine()
