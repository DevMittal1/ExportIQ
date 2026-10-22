"""Evidence provenance and source validation middleware."""

from typing import Any, Dict, List
from ..models.evidence import EvidenceRecord


class EvidenceProvenanceMiddleware:
    """Ensures returned observations retain source provider, period, and retrieval metadata."""
    
    @staticmethod
    def validate_provenance(record: Dict[str, Any]) -> bool:
        """Verify that record has complete provenance fields."""
        source = record.get("source")
        if not source or not isinstance(source, dict):
            return False
        has_provider = bool(source.get("provider"))
        has_url = bool(source.get("url"))
        has_period = bool(record.get("period"))
        return has_provider and has_url and has_period
