"""Telco Assistant Agent (ReAct)

This package contains a LangGraph ReAct-based assistant for a mobile operator.
It verifies callers via SMS OTP, can review current plans and data usage,
answer roaming questions, recommend packages, and close contracts (mock).
"""

from .react_agent import agent  # noqa: F401


