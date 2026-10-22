"""Meta tools for on-demand skill reading and bounded task delegation."""

from pathlib import Path
from typing import Any, Dict, Optional
from .registry import register_tool
from ..config import settings
from ..models.subagent import AGENT_REGISTRY, SubagentFinding


@register_tool(
    name="skills.read_skill",
    description=(
        "Read an approved skill's instructions when the current task requires that specialized procedure. "
        "CANNOT be used to read arbitrary filesystem paths."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "skill_name": {
                "type": "string",
                "enum": [
                    "hs-classification",
                    "trade-data-analysis",
                    "tariff-market-access",
                    "buyer-qualification",
                    "trade-evidence-verification",
                    "market-scoring"
                ],
                "description": "Identifier of the approved domain skill handbook"
            }
        },
        "required": ["skill_name"]
    }
)
def read_skill(skill_name: str) -> Dict[str, Any]:
    """Read the full SKILL.md handbook for an approved canonical skill."""
    approved_skills = [
        "hs-classification",
        "trade-data-analysis",
        "tariff-market-access",
        "buyer-qualification",
        "trade-evidence-verification",
        "market-scoring"
    ]
    if skill_name not in approved_skills:
        return {
            "status": "error",
            "message": f"Skill '{skill_name}' is not an approved skill. Approved: {approved_skills}"
        }
        
    skill_path = settings.SKILLS_DIR / skill_name / "SKILL.md"
    if not skill_path.exists():
        return {
            "status": "error",
            "message": f"Skill file not found at expected path: {skill_path}"
        }
        
    content = skill_path.read_text(encoding="utf-8")
    return {
        "status": "success",
        "skill_name": skill_name,
        "instructions": content
    }


@register_tool(
    name="research.delegate",
    description=(
        "Delegate a bounded research task to an authorized specialist agent. "
        "Validates agent registration, permitted tools, and execution budget."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "agent_name": {
                "type": "string",
                "enum": ["trade_research", "market_access", "buyer_discovery", "evidence_verification"],
                "description": "Authorized target subagent"
            },
            "objective": {"type": "string", "description": "Concise operational goal for the task"},
            "inputs": {"type": "object", "description": "Key-value input parameters"},
            "constraints": {"type": "object", "description": "Execution budget and limits"}
        },
        "required": ["agent_name", "objective", "inputs"]
    }
)
async def delegate(
    agent_name: str,
    objective: str,
    inputs: Dict[str, Any],
    constraints: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Delegate a task to a registered subagent."""
    if agent_name not in AGENT_REGISTRY:
        return {
            "status": "error",
            "message": f"Agent '{agent_name}' is not in AGENT_REGISTRY."
        }
        
    # Lazy import to prevent circular dependency
    from ..subagents.base import dispatch_subagent
    finding = await dispatch_subagent(
        agent_key=agent_name,
        objective=objective,
        inputs=inputs,
        constraints=constraints or {}
    )
    return finding.model_dump()
