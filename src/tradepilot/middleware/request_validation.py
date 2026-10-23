"""Request validation middleware to enforce payload integrity and basic sanity."""

import re
from typing import Any, Dict, List, Tuple


class RequestValidationMiddleware:
    """Validates structural presence and format of core requests prior to agent planning."""
    
    @staticmethod
    def validate_initial_inputs(state: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate input payload sanity without restricting natural language queries."""
        errors: List[str] = []
        
        query = (state.get("query") or "").strip()
        product = (state.get("product_query") or "").strip()
        
        # At least one query or product description must be provided
        if not query and not product:
            errors.append("User query or product description cannot be empty.")
            
        # Check HS Code format if explicitly provided
        hs_code = state.get("hs_code")
        if hs_code:
            clean_hs = re.sub(r"[^0-9]", "", str(hs_code))
            if len(clean_hs) < 2 or len(clean_hs) > 10:
                errors.append(f"Invalid HS code format '{hs_code}'. Expected between 2 and 10 digits.")
                
        # Check origin country format if explicitly provided
        origin = state.get("origin_country")
        if origin:
            origin_str = str(origin).strip()
            # If provided, must be a 3-letter ISO code
            if len(origin_str) != 3 or not origin_str.isalpha():
                errors.append(f"Origin country '{origin}' must be a 3-letter ISO code (e.g. 'IND', 'USA', 'DEU').")
                
        # Check candidate destinations format if explicitly provided
        destinations = state.get("candidate_destinations")
        if destinations:
            for d in destinations:
                d_str = str(d).strip()
                if len(d_str) != 3 or not d_str.isalpha():
                    errors.append(f"Destination '{d}' is not a valid 3-letter ISO country code.")
                    
        return (len(errors) == 0, errors)
