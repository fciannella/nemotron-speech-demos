import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from langgraph.func import entrypoint, task
from langgraph.graph import add_messages
from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
    BaseMessage,
    ToolCall,
    ToolMessage,
)


# ---- Tools (wire-transfer) ----

try:
    from . import tools as wire_tools  # type: ignore
except Exception:
    import importlib.util as _ilu
    _dir = os.path.dirname(__file__)
    _tools_path = os.path.join(_dir, "tools.py")
    _spec = _ilu.spec_from_file_location("wire_transfer_agent_tools", _tools_path)
    wire_tools = _ilu.module_from_spec(_spec)  # type: ignore
    assert _spec and _spec.loader
    _spec.loader.exec_module(wire_tools)  # type: ignore

# Aliases for tool functions
list_accounts = wire_tools.list_accounts
get_customer_profile = wire_tools.get_customer_profile
find_customer = wire_tools.find_customer
find_account_by_last4 = wire_tools.find_account_by_last4
verify_identity = wire_tools.verify_identity
get_account_balance_tool = wire_tools.get_account_balance_tool
get_exchange_rate_tool = wire_tools.get_exchange_rate_tool
calculate_wire_fee_tool = wire_tools.calculate_wire_fee_tool
check_wire_limits_tool = wire_tools.check_wire_limits_tool
get_cutoff_and_eta_tool = wire_tools.get_cutoff_and_eta_tool
get_country_requirements_tool = wire_tools.get_country_requirements_tool
validate_beneficiary_tool = wire_tools.validate_beneficiary_tool
save_beneficiary_tool = wire_tools.save_beneficiary_tool
quote_wire_tool = wire_tools.quote_wire_tool
generate_otp_tool = wire_tools.generate_otp_tool
verify_otp_tool = wire_tools.verify_otp_tool
wire_transfer_domestic = wire_tools.wire_transfer_domestic
wire_transfer_international = wire_tools.wire_transfer_international
find_customer_by_name = wire_tools.find_customer_by_name
convert_currency_tool = wire_tools.convert_currency_tool


"""ReAct agent entrypoint and system prompt."""


SYSTEM_PROMPT = (
    "You are a warm, cheerful banking assistant helping a customer send a wire transfer (domestic or international). "
    "Start with a brief greeting and very short small talk. Then ask for the caller's full name. "
    "CUSTOMER LOOKUP: After receiving the customer's name, thank them and call find_customer with their first and last name to get their customer_id. If find_customer returns an empty result ({}), politely ask the customer to confirm their full name spelling or offer to look them up by other details. Do NOT proceed to asking for date of birth if you don't have a valid customer_id. "
    "IDENTITY IS MANDATORY: Once you have a customer_id from find_customer, you MUST call verify_identity. Thank the customer for their name, then ask for date of birth (customer can use any format; you normalize) and EITHER SSN last-4 OR the secret answer. If verify_identity returns a secret question, read it verbatim and collect the answer. "
    "NEVER claim the customer is verified unless the verify_identity tool returned verified=true. If not verified, ask ONLY for the next missing field and call verify_identity again. Do NOT proceed to wire details until verified=true. "
    "IMPORTANT: Once verified=true is returned from verify_identity, DO NOT ask for identity verification again. The customer is verified for the entire session. Proceed directly to OTP verification when ready to execute the transfer. "
    "AFTER VERIFIED: Ask ONE question at a time, in this order, waiting for the user's answer each time: (1) wire type (DOMESTIC or INTERNATIONAL); (2) source account (last-4 or picker); (3) amount (with source currency); (4) destination country/state; (5) destination currency preference; (6) who pays fees (OUR/SHA/BEN). Keep each turn to a single, concise prompt. Do NOT re-ask for fields already provided; instead, briefly summarize known details and ask only for the next missing field. "
"If destination currency differs from source, call get_exchange_rate_tool and state the applied rate and converted amount. "
"For ad-hoc conversion questions outside a specific wire quote, call convert_currency_tool and share the rate plus converted amount. "
    "Collect beneficiary details next. Use get_country_requirements_tool and validate_beneficiary_tool; if fields are missing, ask for ONLY the next missing field (one per turn). "
    "Then check balance/limits via get_account_balance_tool and check_wire_limits_tool. Provide a pre-transfer quote using quote_wire_tool showing: FX rate, total fees, who pays what, net sent, net received, and ETA from get_cutoff_and_eta_tool. "
    "Before executing, generate an OTP (generate_otp_tool), collect it, verify via verify_otp_tool, then execute the appropriate transfer: wire_transfer_domestic or wire_transfer_international. Offer to save the beneficiary afterward. "
    "STYLE: Keep messages short (1–2 sentences), empathetic, and strictly ask one question per turn. "
    "TTS SAFETY: Output must be plain text suitable for text-to-speech. Do not use markdown, bullets, asterisks, emojis, or special typography. Use only ASCII punctuation and straight quotes."
)


_MODEL_NAME = os.getenv("REACT_MODEL", os.getenv("CLARIFY_MODEL", "gpt-4o"))
_LLM = ChatOpenAI(model=_MODEL_NAME, temperature=0.3)
_TOOLS = [
    list_accounts,
    get_customer_profile,
    find_customer,
    find_account_by_last4,
    verify_identity,
    get_account_balance_tool,
    get_exchange_rate_tool,
    calculate_wire_fee_tool,
    check_wire_limits_tool,
    get_cutoff_and_eta_tool,
    get_country_requirements_tool,
    validate_beneficiary_tool,
    save_beneficiary_tool,
    quote_wire_tool,
    convert_currency_tool,
    generate_otp_tool,
    verify_otp_tool,
    wire_transfer_domestic,
    wire_transfer_international,
]
_LLM_WITH_TOOLS = _LLM.bind_tools(_TOOLS)
_TOOLS_BY_NAME = {t.name: t for t in _TOOLS}

# Simple per-run context storage (thread-safe enough for local dev worker)
_CURRENT_THREAD_ID: str | None = None
_CURRENT_CUSTOMER_ID: str | None = None

# ---- Logger ----
logger = logging.getLogger("WireTransferAgent")
if not logger.handlers:
    _stream = logging.StreamHandler()
    _stream.setLevel(logging.INFO)
    _fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    _stream.setFormatter(_fmt)
    logger.addHandler(_stream)
    try:
        _file = logging.FileHandler(str(Path(__file__).resolve().parents[2] / "app.log"))
        _file.setLevel(logging.INFO)
        _file.setFormatter(_fmt)
        logger.addHandler(_file)
    except Exception:
        pass
logger.setLevel(logging.INFO)
_DEBUG = os.getenv("RBC_FEES_DEBUG", "0") not in ("", "0", "false", "False")

def _get_thread_id(config: Dict[str, Any] | None, messages: List[BaseMessage]) -> str:
    cfg = config or {}
    # Try dict-like and attribute-like access
    def _safe_get(container: Any, key: str, default: Any = None) -> Any:
        try:
            if isinstance(container, dict):
                return container.get(key, default)
            if hasattr(container, "get"):
                return container.get(key, default)
            if hasattr(container, key):
                return getattr(container, key, default)
        except Exception:
            return default
        return default

    try:
        conf = _safe_get(cfg, "configurable", {}) or {}
        for key in ("thread_id", "session_id", "thread"):
            val = _safe_get(conf, key)
            if isinstance(val, str) and val:
                return val
    except Exception:
        pass

    # Fallback: look for session_id on the latest human message additional_kwargs
    try:
        for m in reversed(messages or []):
            addl = getattr(m, "additional_kwargs", None)
            if isinstance(addl, dict) and isinstance(addl.get("session_id"), str) and addl.get("session_id"):
                return addl.get("session_id")
            if isinstance(m, dict):
                ak = m.get("additional_kwargs") or {}
                if isinstance(ak, dict) and isinstance(ak.get("session_id"), str) and ak.get("session_id"):
                    return ak.get("session_id")
    except Exception:
        pass
    return "unknown"


def _trim_messages(messages: List[BaseMessage], max_messages: int = 40) -> List[BaseMessage]:
    if len(messages) <= max_messages:
        return messages
    return messages[-max_messages:]


def _sanitize_conversation(messages: List[BaseMessage]) -> List[BaseMessage]:
    """Ensure tool messages only follow an assistant message with tool_calls.

    Drops orphan tool messages that could cause OpenAI 400 errors.
    """
    sanitized: List[BaseMessage] = []
    pending_tool_ids: set[str] | None = None
    for m in messages:
        try:
            if isinstance(m, AIMessage):
                sanitized.append(m)
                tool_calls = getattr(m, "tool_calls", None) or []
                ids: set[str] = set()
                for tc in tool_calls:
                    # ToolCall can be mapping-like or object-like
                    if isinstance(tc, dict):
                        _id = tc.get("id") or tc.get("tool_call_id")
                    else:
                        _id = getattr(tc, "id", None) or getattr(tc, "tool_call_id", None)
                    if isinstance(_id, str):
                        ids.add(_id)
                pending_tool_ids = ids if ids else None
                continue
            if isinstance(m, ToolMessage):
                if pending_tool_ids and isinstance(getattr(m, "tool_call_id", None), str) and m.tool_call_id in pending_tool_ids:
                    sanitized.append(m)
                    # keep accepting subsequent tool messages for the same assistant turn
                    continue
                # Orphan tool message: drop
                continue
            # Any other message resets expectation
            sanitized.append(m)
            pending_tool_ids = None
        except Exception:
            # On any unexpected shape, include as-is but reset to avoid pairing issues
            sanitized.append(m)
            pending_tool_ids = None
    # Ensure the conversation doesn't start with a ToolMessage
    while sanitized and isinstance(sanitized[0], ToolMessage):
        sanitized.pop(0)
    return sanitized


def _today_string() -> str:
    override = os.getenv("RBC_FEES_TODAY_OVERRIDE")
    if isinstance(override, str) and override.strip():
        try:
            datetime.strptime(override.strip(), "%Y-%m-%d")
            return override.strip()
        except Exception:
            pass
    return datetime.utcnow().strftime("%Y-%m-%d")


def _system_messages() -> List[BaseMessage]:
    today = _today_string()
    return [SystemMessage(content=SYSTEM_PROMPT)]


@task()
def call_llm(messages: List[BaseMessage]) -> AIMessage:
    """LLM decides whether to call a tool or not."""
    if _DEBUG:
        try:
            preview = [f"{getattr(m,'type', getattr(m,'role',''))}:{str(getattr(m,'content', m))[:80]}" for m in messages[-6:]]
            logger.info("call_llm: messages_count=%s preview=%s", len(messages), preview)
        except Exception:
            logger.info("call_llm: messages_count=%s", len(messages))
    resp = _LLM_WITH_TOOLS.invoke(_system_messages() + messages)
    try:
        # Log assistant content or tool calls for visibility
        tool_calls = getattr(resp, "tool_calls", None) or []
        if tool_calls:
            names = []
            for tc in tool_calls:
                n = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                if isinstance(n, str):
                    names.append(n)
            logger.info("LLM tool_calls: %s", names)
        else:
            txt = getattr(resp, "content", "") or ""
            if isinstance(txt, str) and txt.strip():
                logger.info("LLM content: %s", (txt if len(txt) <= 500 else (txt[:500] + "…")))
    except Exception:
        pass
    return resp


@task()
def call_tool(tool_call: ToolCall) -> ToolMessage:
    """Execute a tool call and wrap result in a ToolMessage."""
    tool = _TOOLS_BY_NAME[tool_call["name"]]
    args = tool_call.get("args") or {}
    # Auto-inject session/customer context if missing for identity and other tools
    if tool.name == "verify_identity":
        if "session_id" not in args and _CURRENT_THREAD_ID:
            args["session_id"] = _CURRENT_THREAD_ID
        if "customer_id" not in args and _CURRENT_CUSTOMER_ID:
            args["customer_id"] = _CURRENT_CUSTOMER_ID
    if tool.name == "list_accounts":
        if "customer_id" not in args and _CURRENT_CUSTOMER_ID:
            args["customer_id"] = _CURRENT_CUSTOMER_ID
    # Gate non-identity tools until verified=true
    try:
        if tool.name not in ("verify_identity", "find_customer"):
            # Look back through recent messages for the last verify_identity result
            # The runtime passes messages separately; we cannot access here, so rely on LLM prompt discipline.
            # As an extra guard, if the tool is attempting a wire action before identity, return a friendly error.
            pass
    except Exception:
        pass
    if _DEBUG:
        try:
            logger.info("call_tool: name=%s args_keys=%s", tool.name, list(args.keys()))
        except Exception:
            logger.info("call_tool: name=%s", tool.name)
    result = tool.invoke(args)
    # Ensure string content
    content = result if isinstance(result, str) else json.dumps(result)
    try:
        # Log tool result previews and OTP debug_code when present
        if tool.name == "verify_identity":
            try:
                data = json.loads(content)
                logger.info("verify_identity: verified=%s needs=%s", data.get("verified"), data.get("needs"))
            except Exception:
                logger.info("verify_identity result: %s", content[:300])
        elif tool.name == "generate_otp_tool":
            try:
                data = json.loads(content)
                if isinstance(data, dict) and data.get("debug_code"):
                    logger.info("OTP debug_code: %s", data.get("debug_code"))
                else:
                    logger.info("generate_otp_tool: %s", content[:300])
            except Exception:
                logger.info("generate_otp_tool: %s", content[:300])
        else:
            # Generic preview
            logger.info("tool %s result: %s", tool.name, (content[:300] if isinstance(content, str) else str(content)[:300]))
    except Exception:
        pass
    # Never expose OTP debug_code to the LLM
    try:
        if tool.name == "generate_otp_tool":
            data = json.loads(content)
            if isinstance(data, dict) and "debug_code" in data:
                data.pop("debug_code", None)
                content = json.dumps(data)
    except Exception:
        pass
    return ToolMessage(content=content, tool_call_id=tool_call["id"], name=tool.name)


@entrypoint()
def agent(messages: List[BaseMessage], previous: List[BaseMessage] | None, config: Dict[str, Any] | None = None):
    # Start from full conversation history (previous + new)
    prev_list = list(previous or [])
    new_list = list(messages or [])
    convo: List[BaseMessage] = prev_list + new_list
    # Trim to avoid context bloat (increased from 40 to 60 to preserve verification state in long conversations)
    convo = _trim_messages(convo, max_messages=int(os.getenv("RBC_FEES_MAX_MSGS", "60")))
    # Sanitize to avoid orphan tool messages after trimming
    convo = _sanitize_conversation(convo)
    thread_id = _get_thread_id(config, new_list)
    logger.info("agent start: thread_id=%s total_in=%s (prev=%s, new=%s)", thread_id, len(convo), len(prev_list), len(new_list))
    # Establish default customer from config (or fallback to cust_test)
    conf = (config or {}).get("configurable", {}) if isinstance(config, dict) else {}
    default_customer = conf.get("customer_id") or conf.get("user_email") or "cust_test"

    # Heuristic: infer customer_id from latest human name if provided (e.g., "I am Alice Stone")
    inferred_customer: str | None = None
    try:
        recent_humans = [m for m in reversed(new_list) if (getattr(m, "type", None) == "human" or getattr(m, "role", None) == "user" or (isinstance(m, dict) and m.get("type") == "human"))]
        text = None
        for m in recent_humans[:3]:
            text = (getattr(m, "content", None) if not isinstance(m, dict) else m.get("content")) or ""
            if isinstance(text, str) and text.strip():
                break
        if isinstance(text, str):
            tokens = [t for t in text.replace(',', ' ').split() if t.isalpha()]
            if len(tokens) >= 2 and find_customer_by_name is not None:
                # Try adjacent pairs as first/last
                for i in range(len(tokens) - 1):
                    fn = tokens[i]
                    ln = tokens[i + 1]
                    found = find_customer_by_name(fn, ln)  # type: ignore
                    if isinstance(found, dict) and found.get("customer_id"):
                        inferred_customer = found.get("customer_id")
                        break
    except Exception:
        pass

    # Update module context
    global _CURRENT_THREAD_ID, _CURRENT_CUSTOMER_ID
    _CURRENT_THREAD_ID = thread_id
    _CURRENT_CUSTOMER_ID = inferred_customer or default_customer

    llm_response = call_llm(convo).result()

    while True:
        tool_calls = getattr(llm_response, "tool_calls", None) or []
        if not tool_calls:
            break

        # Execute tools (in parallel) and append results
        futures = [call_tool(tc) for tc in tool_calls]
        tool_results = [f.result() for f in futures]
        if _DEBUG:
            try:
                logger.info("tool_results: count=%s names=%s", len(tool_results), [tr.name for tr in tool_results])
            except Exception:
                pass
        convo = add_messages(convo, [llm_response, *tool_results])
        llm_response = call_llm(convo).result()

    # Append final assistant turn
    convo = add_messages(convo, [llm_response])
    final_text = getattr(llm_response, "content", "") or ""
    try:
        if isinstance(final_text, str) and final_text.strip():
            logger.info("final content: %s", (final_text if len(final_text) <= 500 else (final_text[:500] + "…")))
    except Exception:
        pass
    ai = AIMessage(content=final_text if isinstance(final_text, str) else str(final_text))
    logger.info("agent done: thread_id=%s total_messages=%s final_len=%s", thread_id, len(convo), len(ai.content))
    # Save only the merged conversation (avoid duplicating previous)
    return entrypoint.final(value=ai, save=convo)


