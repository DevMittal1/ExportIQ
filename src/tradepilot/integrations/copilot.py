"""CopilotKit and AG-UI (Agent-User Interface) protocol integration for TradePilot AI."""

from typing import Optional
from fastapi import FastAPI
from copilotkit import CopilotKitRemoteEndpoint, LangGraphAGUIAgent
from copilotkit.integrations.fastapi import add_fastapi_endpoint
from ..graph.workflow import create_tradepilot_graph


def setup_copilotkit_agui(app: FastAPI, graph=None, prefix: str = "/copilotkit"):
    """Mount CopilotKit AG-UI middleware and remote endpoint to FastAPI app.
    
    This connects TradePilot AI's LangGraph engine with CopilotKit frontends and
    the open AG-UI (Agent-User Interaction) protocol standard.
    """
    compiled_graph = graph or create_tradepilot_graph()

    # Wrap the LangGraph workflow with the AG-UI compliant agent
    agui_agent = LangGraphAGUIAgent(
        name="tradepilot_agent",
        description="TradePilot AI Market Access, Tariff Compliance & Global Trade Advisory Engine",
        graph=compiled_graph
    )

    # Initialize CopilotKit Remote Endpoint
    sdk = CopilotKitRemoteEndpoint(agents=[agui_agent])

    # Mount the AG-UI streaming endpoint to FastAPI
    add_fastapi_endpoint(app, sdk, prefix)
    return sdk
