"""Authorization middlewares enforcing tool boundaries and secure skill access."""

from typing import List
from ..models.subagent import AGENT_REGISTRY


class ToolAuthorizationMiddleware:
    """Enforces per-agent tool execution permissions."""
    
    @staticmethod
    def is_authorized(agent_key: str, tool_name: str) -> bool:
        """Check whether the agent is permitted to execute the tool."""
        # Orchestrator allowed meta and scoring tools
        if agent_key in ["orchestrator", "TradePilotOrchestrator"]:
            return tool_name in ["research.delegate", "skills.read_skill", "analytics.score_export_markets"]
            
        agent_spec = AGENT_REGISTRY.get(agent_key)
        if not agent_spec:
            return False
            
        permitted_tools = agent_spec.get("tools", [])
        return tool_name in permitted_tools


class SkillAccessMiddleware:
    """Restricts skill loading strictly to approved identifiers and prevents traversal."""
    
    APPROVED_SKILLS: List[str] = [
        "hs-classification",
        "trade-data-analysis",
        "tariff-market-access",
        "buyer-qualification",
        "trade-evidence-verification",
        "market-scoring"
    ]
    
    @classmethod
    def validate_skill_identifier(cls, skill_name: str) -> bool:
        """Verify skill against whitelist and block path traversal."""
        if ".." in skill_name or "/" in skill_name or "\\" in skill_name:
            return False
        return skill_name in cls.APPROVED_SKILLS
