#!/usr/bin/env python3
"""
Claims Investigation Agent

This agent uses MCP (Model Context Protocol) to make outbound Twilio calls
for investigating insurance claims, fraud verification, or customer follow-ups.

Features:
- Initiates calls via Twilio using MCP tools
- Retrieves call summaries and transcripts
- Lists recent investigation calls
- Makes decisions based on call outcomes
"""

import os
import logging
from pathlib import Path
from typing import Any, Dict, List

from langgraph.func import entrypoint
from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
    BaseMessage,
    ToolMessage,
)
from langchain_mcp_adapters.client import MultiServerMCPClient

# Import local tools
try:
    from . import tools as claims_tools
except Exception:
    import importlib.util as _ilu
    _dir = os.path.dirname(__file__)
    _tools_path = os.path.join(_dir, "tools.py")
    _spec = _ilu.spec_from_file_location("claims_tools", _tools_path)
    claims_tools = _ilu.module_from_spec(_spec)
    assert _spec and _spec.loader
    _spec.loader.exec_module(claims_tools)

# ---- Logger ----
logger = logging.getLogger("ClaimsInvestigationAgent")
if not logger.handlers:
    _stream = logging.StreamHandler()
    _stream.setLevel(logging.INFO)
    _fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    _stream.setFormatter(_fmt)
    logger.addHandler(_stream)
logger.setLevel(logging.INFO)

# ---- MCP Client Setup ----
# Initialize MCP client at module level to avoid recreating on each invocation
_MCP_CLIENT = None
_MCP_TOOLS = None


async def _get_mcp_tools():
    """Get MCP tools (singleton pattern)."""
    global _MCP_CLIENT, _MCP_TOOLS
    
    if _MCP_TOOLS is not None:
        return _MCP_TOOLS
    
    # Path to MCP server
    mcp_server_path = str(Path(__file__).parent / "mcp_server.py")
    
    logger.info(f"Initializing MCP client with server: {mcp_server_path}")
    
    # Prepare environment variables for MCP server subprocess
    import os
    mcp_env = {
        "TWILIO_ACCOUNT_SID": os.getenv("TWILIO_ACCOUNT_SID", ""),
        "TWILIO_AUTH_TOKEN": os.getenv("TWILIO_AUTH_TOKEN", ""),
        "TWILIO_PHONE_NUMBER": os.getenv("TWILIO_PHONE_NUMBER", ""),
        "SERVER_URL": os.getenv("SERVER_URL", "http://localhost:7861"),
        "DATABASE_URL": os.getenv("DATABASE_URL", ""),  # PostgreSQL connection string
    }
    
    logger.info(f"Passing environment to MCP server:")
    logger.info(f"  • TWILIO_ACCOUNT_SID: {'set' if mcp_env['TWILIO_ACCOUNT_SID'] else 'not set'}")
    logger.info(f"  • DATABASE_URL: {'set' if mcp_env['DATABASE_URL'] else 'not set'}")
    
    # Create MCP client with environment variables
    _MCP_CLIENT = MultiServerMCPClient({
        "twilio_voice": {
            "command": "python",
            "args": [mcp_server_path],
            "transport": "stdio",
            "env": mcp_env,  # ← Pass environment variables!
        }
    })
    
    # Get tools from MCP server
    _MCP_TOOLS = await _MCP_CLIENT.get_tools()
    logger.info(f"MCP tools loaded: {[t.name for t in _MCP_TOOLS]}")
    
    return _MCP_TOOLS


# Import logic functions for metadata building
try:
    from . import logic as claims_logic
except Exception:
    import importlib.util as _ilu
    _dir = os.path.dirname(__file__)
    _logic_path = os.path.join(_dir, "logic.py")
    _spec = _ilu.spec_from_file_location("claims_logic_main", _logic_path)
    claims_logic = _ilu.module_from_spec(_spec)
    assert _spec and _spec.loader
    _spec.loader.exec_module(claims_logic)

# ---- Configuration ----
# Hardcoded values for call_customer tool
# These are ALWAYS used, not from environment or LLM
LANGGRAPH_URL = "http://localhost:2024"
DEFAULT_ASSISTANT_NAME = "claim-verification-agent"  # Changed from fraud-notification-agent

logger.info(f"Claims Agent Configuration (HARDCODED):")
logger.info(f"  • LangGraph URL: {LANGGRAPH_URL}")
logger.info(f"  • Assistant Name: {DEFAULT_ASSISTANT_NAME}")

# ---- System Prompt ----
SYSTEM_PROMPT = """You are a professional healthcare claims investigation assistant for an insurance company.
Your role is to help investigators identify suspicious claims and make outbound verification calls to beneficiaries.

Available tools:

CLAIMS DATA TOOLS (use these first to find suspicious claims):
- get_suspicious_claims_tool: Get list of suspicious claims by risk score
- get_high_risk_claims_tool: Get urgent high-risk claims (score >= 75)
- get_claim_investigation_guidance_tool: Get detailed investigation plan for a specific claim
  (tells you if a call is needed, what questions to ask, what info to gather)
- get_claim_details_tool: Get complete details for a specific claim
- search_claims_by_beneficiary_tool: Find claims by beneficiary name

CALLING TOOLS (use these to make verification calls):
- call_customer: Initiate an outbound call to a beneficiary
- get_call_summary: Retrieve transcript and results from a completed call
- list_calls: View recent investigation calls

INVESTIGATION WORKFLOW:
1. When asked about suspicious claims: Use get_suspicious_claims_tool or get_high_risk_claims_tool
2. For specific claim investigation:
   a. Use get_claim_investigation_guidance_tool to understand what's suspicious
   b. Review the guidance - it tells you if a call is needed and what info to gather
   c. If call is needed: Use call_customer with the claim_id parameter
   d. Wait 2-3 minutes for call completion
   e. Use get_call_summary to get results
   f. Provide assessment based on call outcome

IMPORTANT - When calling call_customer:
- You MUST provide claim_id parameter (e.g., "CLM-011")
- The system will automatically build all required metadata from the claim data
- Do NOT try to provide phone_number or metadata manually - just provide claim_id
- Example: call_customer(claim_id="CLM-011")
- The system handles: phone number, beneficiary name, claim details, verification questions, etc.

When presenting results to the investigator:
- Summarize key findings clearly
- Highlight risk scores and suspicion reasons
- Recommend next actions (call, approve, deny, request more docs)

STYLE GUIDELINES:
- Keep messages concise and conversational (1-2 sentences when possible)
- Be professional yet friendly and empathetic
- Provide clear, actionable information

TTS SAFETY - CRITICAL:
Your output will be converted to speech using text-to-speech (TTS). 
You MUST follow these rules:
- Use ONLY plain text - no markdown, bullets, asterisks, or special formatting
- Do NOT use: ** for bold, * for italic, - for bullets, # for headers, ``` for code
- Do NOT use emojis or special typography
- Use only standard ASCII punctuation: periods, commas, question marks, exclamation points
- Use straight quotes ("text") not curly quotes
- Spell out abbreviations when first mentioned (e.g., "claim ID" not "CLM-ID")
- Use natural, conversational language that sounds good when spoken aloud
- For lists, use: "first, second, third" or "number one, number two" instead of bullet points

Examples of GOOD TTS output:
"I've initiated a call to the customer. The call ID is CA123456. I'll check the results in about 2 minutes."
"The investigation found three important points. First, the customer confirmed the transaction. Second, no fraud indicators were detected. Third, all details match our records."

Examples of BAD TTS output (DO NOT USE):
"I've initiated a call to the customer.\n- Call ID: CA123456\n- Status: **queued**\n- ETA: ~2-3 min" ❌
"Investigation results:\n* Customer verified ✓\n* No fraud detected\n* All details match" ❌

Be professional, thorough, and clear in your responses. 
Always explain what you're doing and why.
"""

# ---- LLM Setup ----
_MODEL_NAME = os.getenv("CLAIMS_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o"))
_LLM = ChatOpenAI(model=_MODEL_NAME, temperature=0.3)


def _system_messages() -> List[BaseMessage]:
    """Get system messages for the agent."""
    return [SystemMessage(content=SYSTEM_PROMPT)]


# ---- Agent Helper Functions ----

def _trim_messages(messages: List[BaseMessage], max_messages: int = 20) -> List[BaseMessage]:
    """Trim message history to prevent context overflow."""
    if len(messages) <= max_messages:
        return messages
    return messages[-max_messages:]


async def _call_llm_with_tools(messages: List[BaseMessage]) -> AIMessage:
    """Call LLM with tools bound (both MCP and local tools)."""
    # Get MCP tools (Twilio calling tools)
    mcp_tools = await _get_mcp_tools()
    
    # Get local tools (claims data tools)
    local_tools = [
        claims_tools.get_suspicious_claims_tool,
        claims_tools.get_claim_investigation_guidance_tool,
        claims_tools.search_claims_by_beneficiary_tool,
        claims_tools.get_claim_details_tool,
        claims_tools.get_high_risk_claims_tool,
    ]
    
    # Combine all tools
    all_tools = list(mcp_tools) + local_tools
    
    logger.debug(f"Tools available: MCP={len(mcp_tools)}, Local={len(local_tools)}, Total={len(all_tools)}")
    
    # Bind all tools to LLM
    llm_with_tools = _LLM.bind_tools(all_tools)
    
    # Invoke with system message + conversation (use ainvoke for async)
    response = await llm_with_tools.ainvoke(_system_messages() + messages)
    
    # Log response
    tool_calls = getattr(response, "tool_calls", None) or []
    if tool_calls:
        names = [tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None) for tc in tool_calls]
        logger.info(f"LLM tool calls: {names}")
    else:
        content = getattr(response, "content", "")
        if content:
            logger.info(f"LLM response: {content[:200]}...")
    
    return response


async def _execute_tool(tool_call: Any) -> ToolMessage:
    """Execute a tool call (MCP or local)."""
    # Get all tools
    mcp_tools = await _get_mcp_tools()
    local_tools = [
        claims_tools.get_suspicious_claims_tool,
        claims_tools.get_claim_investigation_guidance_tool,
        claims_tools.search_claims_by_beneficiary_tool,
        claims_tools.get_claim_details_tool,
        claims_tools.get_high_risk_claims_tool,
    ]
    all_tools = list(mcp_tools) + local_tools
    
    # Find the tool
    tool_name = tool_call.get("name") if isinstance(tool_call, dict) else getattr(tool_call, "name", None)
    tool_args = tool_call.get("args", {}) if isinstance(tool_call, dict) else getattr(tool_call, "args", {})
    tool_id = tool_call.get("id") if isinstance(tool_call, dict) else getattr(tool_call, "id", None)
    
    # Auto-inject configuration for call_customer tool (MCP tool)
    # ALWAYS override these values (don't trust LLM)
    if tool_name == "call_customer":
        # Check if claim_id is provided (Approach A)
        claim_id = tool_args.get("claim_id")
        
        if claim_id:
            # Build complete metadata from claim data
            logger.info(f"  📋 Building metadata for claim: {claim_id}")
            try:
                metadata = claims_logic.build_call_metadata(claim_id)
                tool_args["metadata"] = metadata
                logger.info(f"  ✅ Built metadata with {len(metadata.get('verification_tasks', []))} verification tasks")
                
                # Also set phone_number from claim (in case LLM didn't provide it)
                tool_args["phone_number"] = metadata["phone_number"]
            except Exception as e:
                logger.error(f"  ❌ Failed to build metadata for {claim_id}: {e}")
                # Fallback: use whatever LLM provided
        else:
            logger.warning(f"  ⚠️  No claim_id provided, using LLM-provided metadata")
        
        # ALWAYS force correct langgraph_url (hardcoded)
        tool_args["langgraph_url"] = LANGGRAPH_URL
        logger.info(f"  ✅ Forced langgraph_url: {LANGGRAPH_URL}")
        
        # ALWAYS force correct assistant_name (hardcoded)
        tool_args["assistant_name"] = DEFAULT_ASSISTANT_NAME
        logger.info(f"  ✅ Forced assistant_name: {DEFAULT_ASSISTANT_NAME}")
    
    logger.info(f"Executing tool: {tool_name} with args: {list(tool_args.keys())}")
    
    # Find matching tool (check both MCP and local)
    tool = None
    for t in all_tools:
        t_name = t.name if hasattr(t, 'name') else None
        if t_name == tool_name:
            tool = t
            break
    
    if not tool:
        error_msg = f"Tool {tool_name} not found"
        logger.error(error_msg)
        return ToolMessage(content=error_msg, tool_call_id=tool_id, name=tool_name)
    
    # Invoke the tool
    try:
        # Check if it's an MCP tool (has ainvoke) or local tool (has invoke)
        if hasattr(tool, 'ainvoke'):
            result = await tool.ainvoke(tool_args)
        else:
            # Local LangChain tool - use invoke
            result = tool.invoke(tool_args)
        
        # Convert result to string
        if isinstance(result, str):
            content = result
        elif isinstance(result, dict):
            import json
            content = json.dumps(result, indent=2)
        else:
            content = str(result)
        
        logger.info(f"Tool {tool_name} result: {content[:200]}...")
        
        return ToolMessage(content=content, tool_call_id=tool_id, name=tool_name)
    
    except Exception as e:
        error_msg = f"Error executing {tool_name}: {str(e)}"
        logger.error(error_msg)
        return ToolMessage(content=error_msg, tool_call_id=tool_id, name=tool_name)


# ---- Main Agent Entrypoint ----

@entrypoint()
async def agent(messages: List[BaseMessage], previous: List[BaseMessage] | None, config: Dict[str, Any] | None = None):
    """
    Claims Investigation Agent entrypoint.
    
    This agent can:
    - Initiate customer calls for claim verification
    - Retrieve call transcripts and summaries
    - List recent investigation calls
    - Make decisions based on call outcomes
    
    Args:
        messages: New messages in this turn
        previous: Previous conversation history
        config: Configuration (thread_id, etc.)
    
    Returns:
        Final AI message with full conversation history
    """
    # Build full conversation
    prev_list = list(previous or [])
    new_list = list(messages or [])
    convo = prev_list + new_list
    
    # Trim to avoid context overflow
    convo = _trim_messages(convo, max_messages=20)
    
    # Extract thread ID for logging
    thread_id = "unknown"
    try:
        conf = (config or {}).get("configurable", {}) if isinstance(config, dict) else {}
        thread_id = conf.get("thread_id") or conf.get("session_id") or "unknown"
    except:
        pass
    
    logger.info(f"Claims agent start: thread_id={thread_id}, messages={len(convo)}")
    
    # Call LLM with tools
    llm_response = await _call_llm_with_tools(convo)
    
    # ReAct loop: Execute tools until no more tool calls
    max_iterations = 10  # Prevent infinite loops
    iteration = 0
    
    while iteration < max_iterations:
        tool_calls = getattr(llm_response, "tool_calls", None) or []
        
        if not tool_calls:
            # No more tools to call, we're done
            break
        
        iteration += 1
        logger.info(f"ReAct iteration {iteration}: {len(tool_calls)} tool(s) to execute")
        
        # Execute all tool calls
        tool_results = []
        for tc in tool_calls:
            result = await _execute_tool(tc)
            tool_results.append(result)
        
        # Add assistant message (with tool calls) and tool results to conversation
        convo.append(llm_response)
        convo.extend(tool_results)
        
        # Get next LLM response
        llm_response = await _call_llm_with_tools(convo)
    
    # Final response (no more tool calls)
    convo.append(llm_response)
    
    # Extract final text
    final_text = getattr(llm_response, "content", "") or ""
    
    logger.info(f"Claims agent done: thread_id={thread_id}, iterations={iteration}, final_len={len(final_text)}")
    
    # Return final message with full conversation saved
    ai_message = AIMessage(content=final_text if isinstance(final_text, str) else str(final_text))
    
    return entrypoint.final(value=ai_message, save=convo)

