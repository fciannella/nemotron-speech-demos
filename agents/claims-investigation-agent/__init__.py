"""Claims Investigation Agent

This package contains a LangGraph agent that uses MCP (Model Context Protocol)
to make outbound Twilio calls for investigating insurance claims, fraud verification,
or customer follow-ups.
"""

from .claims_agent import agent  # noqa: F401

__all__ = ["agent"]

