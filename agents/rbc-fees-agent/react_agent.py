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


# ---- Tools (wrap existing logic/fixtures) ----

try:
    from .tools import (
        get_customer_profile,
        find_account_by_last4,
        parse_date_range,
        find_customer,
        check_upgrade_options,
        verify_identity,
        list_accounts,
        fetch_activity,
        detect_fees,
        explain_fee,
        check_dispute_eligibility,
        create_dispute,
    )
except ImportError:
    import sys
    sys.path.append(os.path.dirname(__file__))
    from tools import (  # type: ignore
        get_customer_profile,
        find_account_by_last4,
        parse_date_range,
        find_customer,
        check_upgrade_options,
        verify_identity,
        list_accounts,
        fetch_activity,
        detect_fees,
        explain_fee,
        check_dispute_eligibility,
        create_dispute,
    )

# Also import a direct finder for name→customer_id in case the LLM doesn't call the tool before verification
try:
    from .logic import find_customer_by_name  # type: ignore
except Exception:
    try:
        import sys as _sys, os as _os
        _sys.path.append(os.path.dirname(__file__))
        from logic import find_customer_by_name  # type: ignore
    except Exception:
        find_customer_by_name = None  # type: ignore


"""ReAct agent entrypoint and system prompt."""


SYSTEM_PROMPT = (
    "You are a warm, cheerful banking assistant on a phone call. "
    "Start with a brief greeting and small talk. If the caller's identity is unknown, politely ask for their full name (first and last). If they provide only a single given name, ask for their last name next. "
    "Before any account lookups or actions, you MUST verify the caller's identity using the verify_identity tool. "
    "Ask for date of birth (do not specify a format) and either last-4 of account or a secret answer. If the tool returns a secret question, read it back verbatim and ask for the answer. "
    "Normalize any provided DOB to YYYY-MM-DD before calling verify_identity. "
    "If the user provides first and last name, FIRST call find_customer to resolve customer_id and then include that customer_id in subsequent tool calls. "
    "Only after verified=true, re-use the authenticated account if the customer confirms it's the same; "
    "otherwise, ask for the last 4 of the other account and use find_account_by_last4. "
    "Then ASK THE CUSTOMER for the specific fee date or a date range (e.g., last 30/90 days). Do not assume a default window. "
    "After the customer provides a timeframe, first call parse_date_range. If it returns an error, ask for clarification and DO NOT proceed. Then call detect_fees. If detect_fees returns an error (invalid/future/no_fees), ask for clarification or suggest a wider range (e.g., last 90 days) and DO NOT invent a fee. Only once there are fee events, continue. FIRST, explain the relevant fee clearly (what it is and why it happened) using simple language. Do not mention your training data cutoff; rely on the provided tools and fixtures to answer. "
    "SECOND, confirm understanding or offer a brief clarification if needed. If the customer asks about a refund or relief, call check_dispute_eligibility; if eligible, ask permission and then call create_dispute; otherwise, suggest preventive tips. "
    "THIRD, ONLY AFTER explanation and any refund/relief handling, you MUST proactively consider upgrades: call check_upgrade_options with the recent fee events and propose ONE concise package (the highest estimated net benefit) even if the user doesn't ask. If net benefit is positive, emphasize savings; if not, present as optional convenience. "
    "Keep messages short (1–3 sentences), empathetic, and helpful. "
    "TTS SAFETY: Output must be plain text suitable for text-to-speech. Do not use markdown, bullets, asterisks, emojis, or special typography. Use only ASCII punctuation and straight quotes."
)


_MODEL_NAME = os.getenv("REACT_MODEL", os.getenv("CLARIFY_MODEL", "gpt-4o"))
_LLM = ChatOpenAI(model=_MODEL_NAME, temperature=0.3)
_TOOLS = [
    get_customer_profile,
    find_account_by_last4,
    parse_date_range,
    find_customer,
    check_upgrade_options,
    verify_identity,
    list_accounts,
    fetch_activity,
    detect_fees,
    explain_fee,
    check_dispute_eligibility,
    create_dispute,
]
_LLM_WITH_TOOLS = _LLM.bind_tools(_TOOLS)
_TOOLS_BY_NAME = {t.name: t for t in _TOOLS}

# Simple per-run context storage (thread-safe enough for local dev worker)
_CURRENT_THREAD_ID: str | None = None
_CURRENT_CUSTOMER_ID: str | None = None

# ---- Logger ----
logger = logging.getLogger("RBC_ReActFeesAgent")
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
    return [
        SystemMessage(content=SYSTEM_PROMPT),
        SystemMessage(content=(
            f"Today is {today} (UTC). When the user mentions any date or timeframe, first call parse_date_range. "
            "Do not claim a date is in the future unless it is strictly after today. "
            "Rely on tools/fixtures and do not mention training data cutoffs."
        )),
    ]


@task()
def call_llm(messages: List[BaseMessage]) -> AIMessage:
    """LLM decides whether to call a tool or not."""
    if _DEBUG:
        try:
            preview = [f"{getattr(m,'type', getattr(m,'role',''))}:{str(getattr(m,'content', m))[:80]}" for m in messages[-6:]]
            logger.info("call_llm: messages_count=%s preview=%s", len(messages), preview)
        except Exception:
            logger.info("call_llm: messages_count=%s", len(messages))
    return _LLM_WITH_TOOLS.invoke(_system_messages() + messages)


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
    if _DEBUG:
        try:
            logger.info("call_tool: name=%s args_keys=%s", tool.name, list(args.keys()))
        except Exception:
            logger.info("call_tool: name=%s", tool.name)
    result = tool.invoke(args)
    # Ensure string content
    content = result if isinstance(result, str) else json.dumps(result)
    return ToolMessage(content=content, tool_call_id=tool_call["id"], name=tool.name)


@entrypoint()
def agent(messages: List[BaseMessage], previous: List[BaseMessage] | None, config: Dict[str, Any] | None = None):
    # Start from full conversation history (previous + new)
    prev_list = list(previous or [])
    new_list = list(messages or [])
    convo: List[BaseMessage] = prev_list + new_list
    # Trim to avoid context bloat
    convo = _trim_messages(convo, max_messages=int(os.getenv("RBC_FEES_MAX_MSGS", "40")))
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
    ai = AIMessage(content=final_text if isinstance(final_text, str) else str(final_text))
    logger.info("agent done: thread_id=%s total_messages=%s final_len=%s", thread_id, len(convo), len(ai.content))
    # Save only the merged conversation (avoid duplicating previous)
    return entrypoint.final(value=ai, save=convo)


