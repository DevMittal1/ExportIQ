"""FastAPI web and REST API entrypoint for TradePilot AI."""

from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uuid

from ..graph.workflow import create_tradepilot_graph, create_react_supervisor_graph
from langgraph.types import Command
from ..models.state import TradePilotState
from ..tools.registry import TOOL_REGISTRY
from ..middleware.authorization import SkillAccessMiddleware
from ..tools.meta_tools import read_skill
from ..subagents.orchestrator import supervisor, build_research_request, extract_findings, merge_evidence
from ..graph.nodes import deterministic_scoring_node, generate_report_node, validate_request_node

from pathlib import Path
from fastapi.responses import HTMLResponse
from ..middleware.tool_hooks import USAGE_TRACKER

from ..integrations import setup_copilotkit_agui
from ..db.postgres import (
    init_application_tables,
    db_save_thread,
    db_list_threads,
    db_get_thread_messages,
    db_save_message,
    db_save_dossier,
    db_delete_thread,
)

app = FastAPI(
    title="TradePilot AI API",
    version="0.2.0",
    description="Agentic Import/Export Intelligence & Regulatory Compliance Engine"
)

@app.on_event("startup")
async def startup_event():
    """Ensure PostgreSQL checkpointer and application tables are initialized."""
    try:
        init_application_tables()
    except Exception as e:
        import logging
        logging.getLogger("tradepilot").warning(f"PostgreSQL tables init deferred: {e}")

# Global graph instance
_graph = create_tradepilot_graph()

# Mount CopilotKit & AG-UI protocol remote endpoints
setup_copilotkit_agui(app, graph=_graph, prefix="/copilotkit")
setup_copilotkit_agui(app, graph=_graph, prefix="/ag-ui")

_INDEX_HTML_PATH = Path(__file__).parent / "index.html"
_DASHBOARD_HTML_PATH = Path(__file__).parent / "dashboard.html"
_TOKENS_CSS_PATH = Path(__file__).parent / "tokens.css"


_FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="6" fill="#1F4E46"/>
  <path d="M7 10h18M16 10v14M11 24h10" stroke="#F4F1EA" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="16" cy="17" r="2.5" fill="#D88E35"/>
</svg>"""


@app.get("/favicon.ico")
async def serve_favicon():
    """Serve TradePilot customs ledger SVG favicon."""
    from fastapi.responses import Response
    return Response(content=_FAVICON_SVG, media_type="image/svg+xml")


@app.get("/tokens.css")
@app.get("/static/tokens.css")
async def serve_tokens():
    """Serve centralized Trade Desk CSS design tokens."""
    if _TOKENS_CSS_PATH.exists():
        from fastapi.responses import Response
        return Response(content=_TOKENS_CSS_PATH.read_text(encoding="utf-8"), media_type="text/css")
    return Response(content="/* tokens not found */", status_code=404, media_type="text/css")



@app.get("/", response_class=HTMLResponse)
@app.get("/app", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the interactive TradePilot AI Copilot frontend application."""
    if _INDEX_HTML_PATH.exists():
        return HTMLResponse(content=_INDEX_HTML_PATH.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>TradePilot Frontend not found</h1>", status_code=404)


class BudgetUpdateRequest(BaseModel):
    tool_name: str = Field(..., description="Target tool name to cap or update")
    max_calls: int = Field(..., description="Maximum allowed invocations (0 or negative to remove)")


@app.get("/dashboard", response_class=HTMLResponse)
@app.get("/admin", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the interactive API usage monitoring and budget control dashboard."""
    if _DASHBOARD_HTML_PATH.exists():
        return HTMLResponse(content=_DASHBOARD_HTML_PATH.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Dashboard UI not found</h1>", status_code=404)


@app.get("/api/v1/metrics/api-usage")
async def get_api_usage_metrics():
    """Retrieve live API tool usage counts, latencies, and budget controls from persistent DB."""
    return USAGE_TRACKER.get_summary()


@app.get("/api/v1/metrics/logs")
async def get_tool_execution_logs(
    limit: int = 50,
    offset: int = 0,
    tool_name: Optional[str] = None,
    status: Optional[str] = None
):
    """Retrieve historical tool invocation logs stored in persistent SQLite."""
    logs = USAGE_TRACKER.get_logs(limit=limit, offset=offset, tool_name=tool_name, status=status)
    return {"logs": logs, "count": len(logs), "offset": offset, "limit": limit}


@app.post("/api/v1/metrics/budget")
async def update_tool_budget(req: BudgetUpdateRequest):
    """Set or update quota budget cap for a specific tool in memory and persistent SQLite."""
    if req.max_calls <= 0:
        USAGE_TRACKER.remove_budget(req.tool_name)
        return {"status": "success", "message": f"Budget limit removed for '{req.tool_name}'"}
    USAGE_TRACKER.set_budget(req.tool_name, req.max_calls)
    return {
        "status": "success",
        "message": f"Budget limit set to {req.max_calls} for '{req.tool_name}'",
        "tool_name": req.tool_name,
        "max_calls": req.max_calls
    }


@app.post("/api/v1/metrics/reset")
async def reset_metrics():
    """Purge execution logs and reset metrics and budgets."""
    USAGE_TRACKER.reset()
    return {"status": "success", "message": "All execution logs and metrics reset successfully."}


@app.get("/api/v1/threads")
async def get_threads(limit: int = 50):
    """Retrieve persistent conversation threads from PostgreSQL."""
    return {"threads": db_list_threads(limit=limit)}


@app.get("/api/v1/threads/{thread_id}/messages")
async def get_thread_messages(thread_id: str):
    """Retrieve full conversation message history and HITL actions for a thread."""
    messages = db_get_thread_messages(thread_id)
    return {"thread_id": thread_id, "messages": messages}


@app.delete("/api/v1/threads/{thread_id}")
async def delete_thread(thread_id: str):
    """Delete a conversation thread and its message history from PostgreSQL."""
    success = db_delete_thread(thread_id)
    return {"status": "success" if success else "failed", "thread_id": thread_id}



class ResearchRequest(BaseModel):
    thread_id: Optional[str] = Field(default=None, description="Conversational thread/session ID for multi-turn state continuity")
    query: Optional[str] = Field(default=None, description="Natural language question, trade prompt, or research instruction")
    product_query: Optional[str] = Field(default=None, description="Product name or category (optional if in query)")
    hs_code: Optional[str] = Field(default=None, description="HS 6-digit classification code")
    origin_country: Optional[str] = Field(default=None, description="Country name or ISO-3 code of exporting origin")
    candidate_destinations: Optional[List[str]] = Field(default=None, description="Target candidate markets (auto-discovered if omitted)")
    reference_years: List[int] = Field(default=[2021, 2022, 2023], description="Historical trade periods")
    enable_hitl: bool = Field(default=False, description="Enable human-in-the-loop review before final dossier generation")
    scoring_weights: Optional[Dict[str, float]] = Field(default=None, description="Custom criteria weights for ranking")


class ResumeRequest(BaseModel):
    thread_id: str = Field(..., description="Conversational thread/session ID to resume")
    action: str = Field(default="approve", description="'clarify', 'approve_plan', 'approve', 'reject', or 'adjust_weights'")
    approved: Optional[bool] = Field(default=None, description="Direct boolean approval for AG-UI / CopilotKit ApprovalCard resolution")
    decision: Optional[Dict[str, Any]] = Field(default=None, description="Arbitrary AG-UI resolve decision payload")
    origin_country: Optional[str] = Field(default=None, description="Export origin country (for clarification checkpoint)")
    product_query: Optional[str] = Field(default=None, description="Product query (for clarification checkpoint)")
    selected_destinations: Optional[List[str]] = Field(default=None, description="Selected destination markets (for plan approval checkpoint)")
    weights: Optional[Dict[str, float]] = Field(default=None, description="Updated criteria weights (for dossier review checkpoint)")


class ResearchResponse(BaseModel):
    run_id: str
    thread_id: Optional[str] = None
    status: str
    checkpoint: Optional[str] = None
    direct_answer: Optional[str] = None
    report_markdown: Optional[str] = None
    rankings: List[Dict[str, Any]] = []
    evidence_count: int = 0
    subagents_dispatched: List[str] = []
    query_intent: Optional[str] = None
    scoring_weights: Optional[Dict[str, float]] = None
    interrupt_data: Optional[Dict[str, Any]] = None
    errors: List[str] = []
    steps: List[Dict[str, Any]] = Field(default_factory=list, description="Dynamic execution workflow steps generated by the agent")
    ui_actions: List[Dict[str, Any]] = Field(default_factory=list, description="Client-side UI action directives emitted by the agent")


@app.get("/api/v1/health")
async def health_check():
    """Health status and registered components."""
    return {
        "status": "healthy",
        "registered_tools_count": len(TOOL_REGISTRY),
        "available_tools": list(TOOL_REGISTRY.keys()),
        "approved_skills": SkillAccessMiddleware.APPROVED_SKILLS
    }


@app.get("/api/v1/skills")
async def list_skills():
    """List approved skills with their descriptions."""
    skills = []
    for s_name in SkillAccessMiddleware.APPROVED_SKILLS:
        res = read_skill(s_name)
        skills.append({
            "name": s_name,
            "status": res.get("status"),
            "preview": res.get("instructions", "")[:200] + "..."
        })
    return {"skills": skills}


def generate_agent_execution_steps(
    state: TradePilotState,
    status: str,
    checkpoint: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Dynamically generate the agent execution steps based on actual workflow, tools, and state."""
    steps: List[Dict[str, Any]] = []
    
    # 1. Validation & Intent Classification Step
    intent = state.get("query_intent") or "comprehensive_feasibility"
    product = state.get("product_query")
    origin = state.get("origin_country")
    destinations = list(state.get("shortlisted_destinations") or state.get("candidate_destinations") or [])
    
    intent_labels = {
        "trade_advisory": "Trade Advisory & Regulatory Guidance",
        "market_access": "Market Access & Applied Tariffs",
        "buyer_discovery": "Commercial Buyer Discovery",
        "comprehensive_feasibility": "Multi-Destination Feasibility Study",
        "general_advisory": "International Trade Advisory"
    }
    
    route_desc = f"{origin} ➔ {', '.join(destinations)}" if origin and destinations else (f"Origin: {origin}" if origin else "Global Policy")
    steps.append({
        "id": "step_validate",
        "name": "validate_request",
        "label": "Inquiry Intent & Route Auditing",
        "description": f"Verified request parameters. Intent classified as '{intent_labels.get(intent, intent)}'.",
        "status": "done",
        "details": f"Product: {product or 'General Trade Inquiry'} | Route: {route_desc}",
        "badge": "validate"
    })
    
    # Check if paused at clarification checkpoint or if clarification was performed
    if status == "awaiting_human_review" and checkpoint == "clarification":
        steps.append({
            "id": "step_clarification",
            "name": "human_clarification",
            "label": "Human Clarification Checkpoint",
            "description": "Agent identified incomplete parameters (e.g. Origin nation or product specification).",
            "status": "running",
            "details": "Awaiting exporter clarification before tool dispatch.",
            "badge": "HITL"
        })
        return steps
    elif state.get("human_clarification_completed") and origin and product:
        steps.append({
            "id": "step_clarification",
            "name": "human_clarification",
            "label": "Human Clarification Checkpoint",
            "description": f"Export parameters verified (Origin: {origin}).",
            "status": "done",
            "details": "Parameters confirmed by user.",
            "badge": "HITL"
        })
        
    # 2. Dynamic Specialist Subagent Steps (Rendered per actual specialist dispatched by the agent!)
    findings = state.get("subagent_findings", [])
    dispatched_agents = list(dict.fromkeys(f.get("agent_name") for f in findings if f.get("agent_name")))
    
    agent_configs = {
        "TradeResearchAgent": {
            "label": "Trade Research Specialist (UN Comtrade)",
            "desc": "Queried international trade flow datasets and calculated historical CAGR demand trends.",
            "badge": "comtrade"
        },
        "MarketAccessAgent": {
            "label": "Market Access Specialist (WTO & USITC/TARIC)",
            "desc": "Audited bilateral MFN tariffs, bound commitments, and non-tariff SPS/TBT regulatory measures.",
            "badge": "wto/customs"
        },
        "BuyerDiscoveryAgent": {
            "label": "Buyer Discovery Specialist (OpenCorporates & Exa)",
            "desc": "Discovered corporate commercial importers and verified active corporate registry profiles.",
            "badge": "buyers"
        },
        "TradeAdvisoryAgent": {
            "label": "Trade Advisory Specialist (Rules of Origin & Incoterms)",
            "desc": "Analyzed preferential trade rules, Incoterm liability, and trade finance requirements.",
            "badge": "advisory"
        },
        "EvidenceVerificationAgent": {
            "label": "Evidence Auditor (Conflict Resolution)",
            "desc": "Audited multi-source statistical claims and resolved discrepancies across national customs.",
            "badge": "audit"
        }
    }
    
    if dispatched_agents:
        for ag in dispatched_agents:
            cfg = agent_configs.get(ag, {
                "label": f"{ag.replace('Agent', '')} Specialist",
                "desc": "Specialist subagent conducted targeted empirical research.",
                "badge": ag.replace("Agent", "").lower()
            })
            f_item = next((f for f in findings if f.get("agent_name") == ag), {})
            ev_count = len(f_item.get("evidence", []))
            custom_summary = f_item.get("summary") or cfg["desc"]
            
            steps.append({
                "id": f"step_{ag.lower()}",
                "name": ag,
                "label": cfg["label"],
                "description": custom_summary,
                "status": "done",
                "details": f"Audited {ev_count} evidence records." if ev_count else "Empirical analysis completed.",
                "badge": cfg["badge"]
            })
    else:
        steps.append({
            "id": "step_supervisor",
            "name": "react_supervisor",
            "label": "Dynamic Supervisor Orchestration",
            "description": "Supervisor coordinated ReAct reasoning loop across regulatory documentation.",
            "status": "done",
            "details": "Synthesis completed.",
            "badge": "supervisor"
        })
        
    # Check if paused at plan_approval checkpoint
    if status == "awaiting_human_review" and checkpoint == "plan_approval":
        steps.append({
            "id": "step_plan_approval",
            "name": "human_plan_approval",
            "label": "Strategic Market Authorization",
            "description": f"Shortlisted potential destination markets ({', '.join(destinations) if destinations else 'Candidates'}).",
            "status": "running",
            "details": "Awaiting exporter authorization before deep quantitative scoring.",
            "badge": "HITL"
        })
        return steps
    elif state.get("human_plan_approved") and destinations and state.get("enable_hitl"):
        steps.append({
            "id": "step_plan_approval",
            "name": "human_plan_approval",
            "label": "Strategic Market Authorization",
            "description": f"Target destination markets approved: {', '.join(destinations)}.",
            "status": "done",
            "details": "Market scope authorized by exporter.",
            "badge": "HITL"
        })
        
    # 3. Deterministic Scoring Step (if executed)
    rankings = state.get("market_rankings", [])
    if rankings:
        top_dest = rankings[0].get("country_name") or rankings[0].get("country", "Top Destination")
        top_score = rankings[0].get("composite_score", 0.0)
        steps.append({
            "id": "step_scoring",
            "name": "deterministic_scoring",
            "label": "Empirical Multi-Criteria Market Scoring",
            "description": f"Deterministically evaluated {len(rankings)} target markets using applied tariffs, demand CAGR, and HHI market friction.",
            "status": "done",
            "details": f"Leading destination: {top_dest} ({top_score:.1f}/100 composite score).",
            "badge": "scoring"
        })
    elif intent in ["comprehensive_feasibility", "market_access"] and destinations:
        steps.append({
            "id": "step_scoring",
            "name": "deterministic_scoring",
            "label": "Market Scoring & Assessment",
            "description": "Computed comparative market access and trade metrics.",
            "status": "done",
            "details": "Bilateral tariffs and non-tariff trade barriers evaluated.",
            "badge": "scoring"
        })
        
    # Check if paused at dossier_review checkpoint
    if status == "awaiting_human_review" and checkpoint in ["dossier_review", "weight_tuning"]:
        steps.append({
            "id": "step_dossier_review",
            "name": "human_dossier_review",
            "label": "Human Oversight: Weight Tuning & Approval",
            "description": "Quantitative rankings computed. Paused for trade director weight customization and final sign-off.",
            "status": "running",
            "details": "Adjust criteria sliders or authorize final report synthesis below.",
            "badge": "HITL"
        })
        return steps
    elif state.get("human_review_completed") and rankings:
        steps.append({
            "id": "step_dossier_review",
            "name": "human_dossier_review",
            "label": "Human Oversight & Weight Tuning",
            "description": "Custom criteria weights approved and locked by user.",
            "status": "done",
            "details": "Strategic weights finalized.",
            "badge": "HITL"
        })
        
    # 4. Final Dossier Synthesis Step
    evidence_count = len(state.get("evidence_pool", []))
    if status == "completed":
        steps.append({
            "id": "step_report",
            "name": "generate_report",
            "label": "Intelligence Synthesis & Evidence Audit",
            "description": f"Synthesized verified intelligence dossier with {evidence_count} audited empirical evidence records.",
            "status": "done",
            "details": "Complete export feasibility dossier generated.",
            "badge": "dossier"
        })
    else:
        steps.append({
            "id": "step_report",
            "name": "generate_report",
            "label": "Intelligence Synthesis",
            "description": "Pending final report compilation.",
            "status": "pending",
            "details": "Awaiting prior stages.",
            "badge": "dossier"
        })
        
    return steps


def build_ui_actions(state: TradePilotState) -> List[Dict[str, Any]]:
    """Build list of client-side UI action directives for the CopilotKit frontend."""
    actions = list(state.get("ui_actions") or [])
    rankings = state.get("market_rankings") or []
    if rankings:
        actions.append({
            "name": "render_market_chart",
            "parameters": {
                "chart_type": "radar",
                "countries": [r.get("country") for r in rankings],
                "rankings": rankings
            }
        })
        actions.append({
            "name": "open_dossier_tab",
            "parameters": {
                "tab": "rankings"
            }
        })
    return actions


@app.post("/api/v1/research", response_model=ResearchResponse)
async def run_export_research(req: ResearchRequest):
    """Run an end-to-end export study, market discovery, or trade advisory inquiry."""
    run_id = str(uuid.uuid4())
    thread_id = req.thread_id or run_id
    config = {"configurable": {"thread_id": thread_id}}
    
    # If only query is provided, use it; if product_query provided, maintain backward compatibility
    effective_query = req.query or req.product_query or ""

    # Record thread and user prompt in persistent PostgreSQL
    session_title = (effective_query or "Trade Inquiry")[:60]
    db_save_thread(thread_id, title=session_title, metadata={"product": req.product_query or ""})
    db_save_message(str(uuid.uuid4()), thread_id, "user", effective_query)
    
    # Check if previous state exists for this thread in the LangGraph checkpointer
    existing_state = await _graph.aget_state(config)
    if existing_state and existing_state.values:
        initial_state: TradePilotState = {
            "query": effective_query,
            "current_stage": "initialized",
            "user_interrupt_needed": False,
            "user_interrupt_prompt": None,
            "enable_hitl": req.enable_hitl,
            "scoring_weights": req.scoring_weights or existing_state.values.get("scoring_weights"),
            "human_clarification_completed": False,
            "human_plan_approved": False,
            "human_review_completed": False
        }
        if req.product_query:
            initial_state["product_query"] = req.product_query
        if req.origin_country:
            initial_state["origin_country"] = req.origin_country
        if req.candidate_destinations:
            initial_state["candidate_destinations"] = req.candidate_destinations
        if req.hs_code:
            initial_state["hs_code"] = req.hs_code
    else:
        initial_state: TradePilotState = {
            "query": effective_query,
            "product_query": req.product_query,
            "hs_code": req.hs_code,
            "origin_country": req.origin_country,
            "candidate_destinations": req.candidate_destinations or [],
            "reference_years": req.reference_years,
            "query_intent": None,
            "active_skills": [],
            "execution_plan": [],
            "current_stage": "initialized",
            "follow_up_count": 0,
            "critical_gaps": [],
            "user_interrupt_needed": False,
            "user_interrupt_prompt": None,
            "enable_hitl": req.enable_hitl,
            "scoring_weights": req.scoring_weights,
            "human_clarification_completed": False,
            "human_plan_approved": False,
            "human_review_completed": False,
            "market_metrics_cache": [],
            "evidence_pool": [],
            "subagent_findings": [],
            "direct_answer": None,
            "shortlisted_destinations": [],
            "market_rankings": [],
            "final_report_markdown": None
        }
    
    try:
        final_state = await _graph.ainvoke(initial_state, config=config)
        
        if final_state.get("user_interrupt_needed"):
            return ResearchResponse(
                run_id=run_id,
                thread_id=thread_id,
                status="interrupted",
                errors=final_state.get("critical_gaps", ["User clarification required."])
            )
            
        # Check for LangGraph interrupt (HITL checkpoints)
        state_snapshot = await _graph.aget_state(config)
        tasks_with_interrupts = [t.interrupts for t in state_snapshot.tasks if t.interrupts]
        
        if tasks_with_interrupts or final_state.get("__interrupt__"):
            interrupt_info = tasks_with_interrupts[0][0].value if tasks_with_interrupts else final_state["__interrupt__"][0].value
            findings = final_state.get("subagent_findings", [])
            dispatched = list(dict.fromkeys(f.get("agent_name") for f in findings if f.get("agent_name")))
            checkpoint = interrupt_info.get("checkpoint") if isinstance(interrupt_info, dict) else None
            msg_text = interrupt_info.get("message") if isinstance(interrupt_info, dict) else "Human review required"
            db_save_message(str(uuid.uuid4()), thread_id, "assistant", msg_text, hitl_action=interrupt_info if isinstance(interrupt_info, dict) else None)
            return ResearchResponse(
                run_id=run_id,
                thread_id=thread_id,
                status="awaiting_human_review",
                checkpoint=checkpoint,
                direct_answer=msg_text,
                rankings=final_state.get("market_rankings", []),
                evidence_count=len(final_state.get("evidence_pool", [])),
                subagents_dispatched=dispatched,
                query_intent=final_state.get("query_intent") or "comprehensive_feasibility",
                scoring_weights=interrupt_info.get("weights") if isinstance(interrupt_info, dict) else None,
                interrupt_data=interrupt_info if isinstance(interrupt_info, dict) else None,
                steps=generate_agent_execution_steps(final_state, status="awaiting_human_review", checkpoint=checkpoint),
                ui_actions=build_ui_actions(final_state)
            )
            
        findings = final_state.get("subagent_findings", [])
        dispatched = list(dict.fromkeys(f.get("agent_name") for f in findings if f.get("agent_name")))
        intent = final_state.get("query_intent") or ("comprehensive_feasibility" if final_state.get("market_rankings") else "trade_advisory")
        ans_text = final_state.get("direct_answer") or final_state.get("final_report_markdown") or "Analysis completed."
        db_save_message(str(uuid.uuid4()), thread_id, "assistant", ans_text)
        if final_state.get("final_report_markdown") or final_state.get("market_rankings"):
            db_save_dossier(
                str(uuid.uuid4()),
                thread_id,
                final_state.get("product_query") or "Commodity",
                {
                    "report_markdown": final_state.get("final_report_markdown"),
                    "rankings": final_state.get("market_rankings", []),
                    "evidence_count": len(final_state.get("evidence_pool", []))
                }
            )

        return ResearchResponse(
            run_id=run_id,
            thread_id=thread_id,
            status="completed",
            direct_answer=final_state.get("direct_answer"),
            report_markdown=final_state.get("final_report_markdown"),
            rankings=final_state.get("market_rankings", []),
            evidence_count=len(final_state.get("evidence_pool", [])),
            subagents_dispatched=dispatched,
            query_intent=intent,
            scoring_weights=final_state.get("scoring_weights"),
            steps=generate_agent_execution_steps(final_state, status="completed"),
            ui_actions=build_ui_actions(final_state)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")


@app.post("/api/v1/research/resume", response_model=ResearchResponse)
async def resume_export_research(req: ResumeRequest):
    """Resume an interrupted LangGraph execution with human review input, clarification, or plan approval."""
    run_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": req.thread_id}}
    
    state_snapshot = await _graph.aget_state(config)
    if not state_snapshot or not state_snapshot.values:
        raise HTTPException(status_code=404, detail=f"No active session found for thread_id '{req.thread_id}'")
        
    resume_payload: Dict[str, Any] = {
        "action": req.action,
        "approved": req.approved if req.approved is not None else (req.action != "reject"),
        "origin_country": req.origin_country,
        "product_query": req.product_query,
        "selected_destinations": req.selected_destinations,
        "weights": req.weights
    }
    if req.decision and isinstance(req.decision, dict):
        resume_payload.update(req.decision)
    
    # Record resume step in PostgreSQL
    action_note = f"Action: {req.action}"
    if req.origin_country:
        action_note += f" (Origin: {req.origin_country})"
    if req.selected_destinations:
        action_note += f" (Destinations: {', '.join(req.selected_destinations)})"
    db_save_message(str(uuid.uuid4()), req.thread_id, "user", action_note)

    try:
        final_state = await _graph.ainvoke(Command(resume=resume_payload), config=config)
        
        # Check if paused at subsequent HITL checkpoint
        post_snapshot = await _graph.aget_state(config)
        tasks_with_interrupts = [t.interrupts for t in post_snapshot.tasks if t.interrupts]
        
        if tasks_with_interrupts or final_state.get("__interrupt__"):
            interrupt_info = tasks_with_interrupts[0][0].value if tasks_with_interrupts else final_state["__interrupt__"][0].value
            findings = final_state.get("subagent_findings", [])
            dispatched = list(dict.fromkeys(f.get("agent_name") for f in findings if f.get("agent_name")))
            checkpoint = interrupt_info.get("checkpoint") if isinstance(interrupt_info, dict) else None
            msg_text = interrupt_info.get("message") if isinstance(interrupt_info, dict) else "Human review required"
            db_save_message(str(uuid.uuid4()), req.thread_id, "assistant", msg_text, hitl_action=interrupt_info if isinstance(interrupt_info, dict) else None)
            return ResearchResponse(
                run_id=run_id,
                thread_id=req.thread_id,
                status="awaiting_human_review",
                checkpoint=checkpoint,
                direct_answer=msg_text,
                rankings=final_state.get("market_rankings", []),
                evidence_count=len(final_state.get("evidence_pool", [])),
                subagents_dispatched=dispatched,
                query_intent=final_state.get("query_intent") or "comprehensive_feasibility",
                scoring_weights=interrupt_info.get("weights") if isinstance(interrupt_info, dict) else None,
                interrupt_data=interrupt_info if isinstance(interrupt_info, dict) else None,
                steps=generate_agent_execution_steps(final_state, status="awaiting_human_review", checkpoint=checkpoint),
                ui_actions=build_ui_actions(final_state)
            )
        
        findings = final_state.get("subagent_findings", [])
        dispatched = list(dict.fromkeys(f.get("agent_name") for f in findings if f.get("agent_name")))
        intent = final_state.get("query_intent") or ("comprehensive_feasibility" if final_state.get("market_rankings") else "trade_advisory")
        ans_text = final_state.get("direct_answer") or final_state.get("final_report_markdown") or "Analysis completed."
        db_save_message(str(uuid.uuid4()), req.thread_id, "assistant", ans_text)
        if final_state.get("final_report_markdown") or final_state.get("market_rankings"):
            db_save_dossier(
                str(uuid.uuid4()),
                req.thread_id,
                final_state.get("product_query") or "Commodity",
                {
                    "report_markdown": final_state.get("final_report_markdown"),
                    "rankings": final_state.get("market_rankings", []),
                    "evidence_count": len(final_state.get("evidence_pool", []))
                }
            )

        return ResearchResponse(
            run_id=run_id,
            thread_id=req.thread_id,
            status="completed",
            direct_answer=final_state.get("direct_answer"),
            report_markdown=final_state.get("final_report_markdown"),
            rankings=final_state.get("market_rankings", []),
            evidence_count=len(final_state.get("evidence_pool", [])),
            subagents_dispatched=dispatched,
            query_intent=intent,
            scoring_weights=final_state.get("scoring_weights"),
            steps=generate_agent_execution_steps(final_state, status="completed"),
            ui_actions=build_ui_actions(final_state)
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error resuming graph execution: {str(exc)}")


async def execute_react_supervisor_research(req: ResearchRequest) -> Dict[str, Any]:
    """Execute dynamic ReAct supervisor loop with deterministic scoring and report finalization."""
    run_id = str(uuid.uuid4())
    thread_id = req.thread_id or run_id
    effective_query = req.query or req.product_query or ""
    
    state: TradePilotState = {
        "query": effective_query,
        "product_query": req.product_query,
        "hs_code": req.hs_code,
        "origin_country": req.origin_country,
        "candidate_destinations": req.candidate_destinations or [],
        "reference_years": req.reference_years or [2021, 2022, 2023],
        "query_intent": None,
        "active_skills": [],
        "execution_plan": [],
        "current_stage": "initialized",
        "follow_up_count": 0,
        "critical_gaps": [],
        "user_interrupt_needed": False,
        "user_interrupt_prompt": None,
        "evidence_pool": [],
        "subagent_findings": [],
        "direct_answer": None,
        "shortlisted_destinations": req.candidate_destinations or [],
        "market_rankings": [],
        "final_report_markdown": None
    }
    
    # 1. Pre-validation
    val_res = await validate_request_node(state)
    if val_res.get("user_interrupt_needed"):
        return {
            "run_id": run_id,
            "thread_id": thread_id,
            "status": "interrupted",
            "errors": val_res.get("critical_gaps", ["Input validation error"])
        }
        
    # 2. Dynamic model -> tool -> observation loop
    result = await supervisor.ainvoke(
        {
            "messages": [{
                "role": "user",
                "content": build_research_request(state)
            }]
        },
        config={
            "recursion_limit": 50,
            "configurable": {"thread_id": thread_id}
        }
    )
    findings = extract_findings(result)
    state["subagent_findings"] = findings
    state["evidence_pool"] = merge_evidence(findings)
    
    # Extract direct supervisor synthesized response
    direct_answer = None
    messages = result.get("messages", []) if isinstance(result, dict) else []
    if messages:
        last_msg = messages[-1]
        content = getattr(last_msg, "content", None) or (last_msg.get("content") if isinstance(last_msg, dict) else None)
        if isinstance(content, list):
            content = "\n".join(
                b.get("text", "") if isinstance(b, dict) else str(b)
                for b in content
                if not (isinstance(b, dict) and b.get("type") != "text")
            )
        if content and isinstance(content, str) and content.strip():
            direct_answer = content.strip()
    state["direct_answer"] = direct_answer
        
    # 3. Deterministic Finalization: Scoring and Report Generation
    score_update = await deterministic_scoring_node(state)
    state["market_rankings"] = score_update.get("market_rankings", [])
    
    report_update = await generate_report_node(state)
    state["final_report_markdown"] = report_update.get("final_report_markdown")
    
    findings = state["subagent_findings"]
    dispatched = list(dict.fromkeys(f.get("agent_name") for f in findings if f.get("agent_name")))
    intent = state.get("query_intent") or ("comprehensive_feasibility" if state.get("market_rankings") else "trade_advisory")

    return {
        "run_id": run_id,
        "thread_id": thread_id,
        "status": "completed",
        "direct_answer": state.get("direct_answer"),
        "report_markdown": state["final_report_markdown"],
        "rankings": state["market_rankings"],
        "evidence_count": len(state["evidence_pool"]),
        "subagents_dispatched": dispatched,
        "query_intent": intent,
        "subagent_findings_count": len(state["subagent_findings"])
    }


@app.post("/api/v1/research/react", response_model=ResearchResponse)
async def run_react_supervisor_endpoint(req: ResearchRequest):
    """Run an end-to-end export research study driven directly by the ReAct supervisor."""
    try:
        res = await execute_react_supervisor_research(req)
        return ResearchResponse(
            run_id=res["run_id"],
            thread_id=res.get("thread_id"),
            status=res["status"],
            direct_answer=res.get("direct_answer"),
            report_markdown=res.get("report_markdown"),
            rankings=res.get("rankings", []),
            evidence_count=res.get("evidence_count", 0),
            subagents_dispatched=res.get("subagents_dispatched", []),
            query_intent=res.get("query_intent"),
            errors=res.get("errors", [])
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ReAct supervisor error: {str(exc)}")
