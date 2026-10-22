"""Security guardrails: Prompt injection prevention and human-in-the-loop approval."""

import re
from typing import Any, Dict, List, Optional


class PromptInjectionGuard:
    """Sanitizes untrusted external web text and company directory snippets."""
    
    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
        r"you\s+are\s+now\s+a",
        r"system\s*prompt",
        r"disregard\s+the\s+above",
        r"<script.*?>.*?</script>",
        r"!\[.*?\]\(.*?\)"  # Markdown image injection
    ]
    
    @classmethod
    def sanitize_untrusted_text(cls, text: str) -> str:
        """Strip dangerous injection patterns from external content."""
        if not text:
            return ""
        sanitized = text
        for pattern in cls.INJECTION_PATTERNS:
            sanitized = re.sub(pattern, "[FILTERED_SECURITY_STRING]", sanitized, flags=re.IGNORECASE | re.DOTALL)
        return sanitized


class HumanApprovalMiddleware:
    """Enforces human-in-the-loop verification before external side-effects."""
    
    @staticmethod
    def requires_approval(action_type: str, details: Dict[str, Any]) -> bool:
        """Determine whether an action requires explicit human confirmation."""
        consequential_actions = [
            "commercial_buyer_outreach",
            "paid_credit_manifest_query",
            "dispatch_automated_email"
        ]
        return action_type in consequential_actions
