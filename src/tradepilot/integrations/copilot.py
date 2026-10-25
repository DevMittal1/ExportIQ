"""CopilotKit and AG-UI (Agent-User Interface) protocol integration for TradePilot AI."""

from typing import Any, List, Optional
from fastapi import FastAPI
from copilotkit import CopilotKitRemoteEndpoint, LangGraphAGUIAgent, Action
from copilotkit.integrations.fastapi import add_fastapi_endpoint
from ..graph.workflow import create_tradepilot_graph


def _client_action_placeholder(**kwargs):
    """Placeholder handler for actions executed in the client browser."""
    return "Action dispatched to client."


FRONTEND_ACTIONS = [
    Action(
        name="render_market_chart",
        description="Generates and renders an interactive multi-dimensional market comparison chart (radar or bar) in the dossier panel.",
        handler=_client_action_placeholder
    ),
    Action(
        name="open_dossier_tab",
        description="Switches the active view in the dossier ledger between 'rankings', 'charts', 'tariffs', and 'buyers'.",
        handler=_client_action_placeholder
    ),
    Action(
        name="filter_buyers_directory",
        description="Filters and highlights commercial importer records in the buyers directory live in the user interface.",
        handler=_client_action_placeholder
    ),
    Action(
        name="apply_scoring_preset",
        description="Applies preset multi-criteria weights to the scoring sliders (e.g. 'low_tariffs', 'high_growth', 'low_risk').",
        handler=_client_action_placeholder
    ),
    Action(
        name="export_dossier_file",
        description="Exports the current trade dossier to a downloadable CSV or printable format.",
        handler=_client_action_placeholder
    ),
]


class TradePilotAGUIAgent(LangGraphAGUIAgent):
    """Custom LangGraphAGUIAgent that surfaces rich LangGraph interrupt payloads into AG-UI metadata."""

    def _interrupts_to_agui(self, lg_interrupts) -> List[Any]:
        agui_ints = super()._interrupts_to_agui(lg_interrupts)
        for agui_int, lg_int in zip(agui_ints, lg_interrupts):
            raw = getattr(lg_int, "value", {})
            if isinstance(raw, dict):
                agui_int.metadata.update(raw)
                if not agui_int.message and raw.get("message"):
                    agui_int.message = raw["message"]
        return agui_ints


def setup_copilotkit_agui(app: FastAPI, graph=None, prefix: str = "/copilotkit"):
    """Mount CopilotKit AG-UI middleware and remote endpoint to FastAPI app.
    
    This connects TradePilot AI's LangGraph engine with CopilotKit frontends and
    the open AG-UI (Agent-User Interaction) protocol standard.
    """
    compiled_graph = graph or create_tradepilot_graph()

    # Wrap the LangGraph workflow with the AG-UI compliant agents
    tradepilot_agent = TradePilotAGUIAgent(
        name="tradepilot_agent",
        description="TradePilot AI Market Access, Tariff Compliance & Global Trade Advisory Engine",
        graph=compiled_graph
    )
    trade_agent = TradePilotAGUIAgent(
        name="tradeAgent",
        description="TradePilot AI Trade & Export Agent (HITL & AG-UI ApprovalCard)",
        graph=compiled_graph
    )

    # Initialize CopilotKit Remote Endpoint with agents and registered frontend actions
    sdk = CopilotKitRemoteEndpoint(
        agents=[tradepilot_agent, trade_agent],
        actions=FRONTEND_ACTIONS
    )

    # Mount the AG-UI streaming endpoint to FastAPI
    add_fastapi_endpoint(app, sdk, prefix)
    return sdk

