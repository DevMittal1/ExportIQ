"""Request validation middleware to enforce ISO standards and input integrity."""

import re
from typing import Any, Dict, List, Tuple


class RequestValidationMiddleware:
    """Validates user requests and graph state inputs prior to planning."""
    
    @staticmethod
    def validate_initial_inputs(state: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate presence and format of core research inputs."""
        errors: List[str] = []
        
        # Check product query
        product = state.get("product_query", "").strip()
        if not product:
            errors.append("Product description or query cannot be empty.")
            
        # Check HS Code format if provided
        hs_code = state.get("hs_code")
        if hs_code:
            clean_hs = re.sub(r"[^0-9]", "", str(hs_code))
            if len(clean_hs) < 2 or len(clean_hs) > 10:
                errors.append(f"Invalid HS code format '{hs_code}'. Expected between 2 and 10 digits.")
                
        # Check origin country
        origin = state.get("origin_country", "").strip().upper()
        if not origin:
            errors.append("Origin country must be specified as an ISO-3 alpha code.")
        elif len(origin) != 3 or not origin.isalpha():
            errors.append(f"Origin country '{origin}' must be a 3-letter ISO code (e.g. 'IND', 'USA', 'DEU').")
            
        # Check candidate destinations
        destinations = state.get("candidate_destinations", [])
        if not destinations:
            errors.append("At least one candidate destination country must be provided.")
        else:
            for d in destinations:
                d_clean = str(d).strip().upper()
                if len(d_clean) != 3 or not d_clean.isalpha():
                    errors.append(f"Destination '{d}' is not a valid 3-letter ISO country code.")
                    
        return (len(errors) == 0, errors)
