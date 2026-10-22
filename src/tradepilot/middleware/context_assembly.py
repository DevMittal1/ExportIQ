"""Context assembly and context budget compression middlewares."""

from typing import Any, Dict, List
from ..tools.meta_tools import read_skill


class ContextAssemblyMiddleware:
    """Assembles isolated, high-leverage context for each subagent."""
    
    @staticmethod
    def assemble_prompt(
        agent_name: str,
        system_persona: str,
        active_skills: List[str],
        task_objective: str,
        task_inputs: Dict[str, Any]
    ) -> str:
        """Compose system context containing persona, relevant skills, and objective."""
        skill_texts = []
        for s in active_skills:
            res = read_skill(s)
            if res.get("status") == "success":
                skill_texts.append(f"### Skill Handbook: {s}\n{res.get('instructions')}")
                
        skills_block = "\n\n".join(skill_texts) if skill_texts else "No specialized skill handbooks loaded."
        
        prompt = (
            f"# Agent Role: {agent_name}\n"
            f"{system_persona}\n\n"
            f"## Loaded Active Skills\n{skills_block}\n\n"
            f"## Operational Task Assignment\n"
            f"Objective: {task_objective}\n"
            f"Inputs: {task_inputs}\n"
        )
        return prompt


class ContextBudgetMiddleware:
    """Monitors token footprint and summarizes large tool observations."""
    
    MAX_TOKENS = 12000
    
    @classmethod
    def compress_tool_observations(cls, observations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """If tool responses are excessively large, compress to essential claim statements."""
        compressed = []
        for obs in observations:
            if "evidence_records" in obs and len(obs["evidence_records"]) > 10:
                # Retain only key claims
                compressed_obs = {
                    "status": obs.get("status"),
                    "summary_claims": [r.get("claim") for r in obs["evidence_records"][:5]],
                    "total_records_count": len(obs["evidence_records"])
                }
                compressed.append(compressed_obs)
            else:
                compressed.append(obs)
        return compressed
