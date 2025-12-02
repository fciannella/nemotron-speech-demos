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


# ---- Tools (telco) ----

try:
    from . import tools as telco_tools  # type: ignore
except Exception:
    import importlib.util as _ilu
    _dir = os.path.dirname(__file__)
    _tools_path = os.path.join(_dir, "tools.py")
    _spec = _ilu.spec_from_file_location("telco_agent_tools", _tools_path)
    telco_tools = _ilu.module_from_spec(_spec)  # type: ignore
    assert _spec and _spec.loader
    _spec.loader.exec_module(telco_tools)  # type: ignore

# Aliases for tool functions
start_login_tool = telco_tools.start_login_tool
verify_login_tool = telco_tools.verify_login_tool
get_current_package_tool = telco_tools.get_current_package_tool
get_data_balance_tool = telco_tools.get_data_balance_tool
list_available_packages_tool = telco_tools.list_available_packages_tool
recommend_packages_tool = telco_tools.recommend_packages_tool
get_roaming_info_tool = telco_tools.get_roaming_info_tool
close_contract_tool = telco_tools.close_contract_tool
list_addons_tool = telco_tools.list_addons_tool
purchase_roaming_pass_tool = telco_tools.purchase_roaming_pass_tool
change_package_tool = telco_tools.change_package_tool
get_billing_summary_tool = telco_tools.get_billing_summary_tool
set_data_alerts_tool = telco_tools.set_data_alerts_tool


"""ReAct agent entrypoint and system prompt for Telco assistant."""


SYSTEM_PROMPT = (
    "You are a warm, helpful mobile operator assistant. Greet briefly, then ask for the caller's mobile number (MSISDN). "
    "IDENTITY IS MANDATORY: After collecting the number, call start_login_tool to send a one-time code via SMS, then ask for the 6-digit code. "
    "Call verify_login_tool with the code. Do NOT proceed unless verified=true. If not verified, ask ONLY for the next missing item and retry. "
    "AFTER VERIFIED: Support these tasks and ask one question per turn: "
    "(1) Show current package and contract; (2) Check current data balance; (3) Explain roaming in a country and available passes; (4) Recommend packages with costs based on usage/preferences; (5) Close contract (require explicit yes/no confirmation). "
    "When recommending, include monthly fees and key features, and keep answers concise. When closing contracts, summarize any early termination fee before asking for confirmation. "
    "STYLE: Concise (1–2 sentences), friendly, and action-oriented. "
    "TTS SAFETY: Output must be plain text suitable for text-to-speech. Do not use markdown, bullets, asterisks, emojis, or special typography. Use only ASCII punctuation and straight quotes."
)


_MODEL_NAME = os.getenv("REACT_MODEL", os.getenv("CLARIFY_MODEL", "gpt-4o"))
_LLM = ChatOpenAI(model=_MODEL_NAME, temperature=0.3)
_TOOLS = [
    start_login_tool,
    verify_login_tool,
    get_current_package_tool,
    get_data_balance_tool,
    list_available_packages_tool,
    recommend_packages_tool,
    get_roaming_info_tool,
    close_contract_tool,
    list_addons_tool,
    purchase_roaming_pass_tool,
    change_package_tool,
    get_billing_summary_tool,
    set_data_alerts_tool,
]
_LLM_WITH_TOOLS = _LLM.bind_tools(_TOOLS)
_TOOLS_BY_NAME = {t.name: t for t in _TOOLS}

# Simple per-run context storage (thread-safe enough for local dev worker)
_CURRENT_THREAD_ID: str | None = None
_CURRENT_MSISDN: str | None = None

# ---- Logger ----
logger = logging.getLogger("TelcoAgent")
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
_DEBUG = os.getenv("TELCO_DEBUG", "0") not in ("", "0", "false", "False")

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
    global _CURRENT_MSISDN
    tool = _TOOLS_BY_NAME[tool_call["name"]]
    args = tool_call.get("args") or {}
    # Auto-inject session context and remembered msisdn
    if tool.name in ("start_login_tool", "verify_login_tool"):
        if "session_id" not in args and _CURRENT_THREAD_ID:
            args["session_id"] = _CURRENT_THREAD_ID
    if "msisdn" not in args and _CURRENT_MSISDN:
        args["msisdn"] = _CURRENT_MSISDN
    # If the LLM passes msisdn, remember it for subsequent calls
    try:
        if isinstance(args.get("msisdn"), str) and args.get("msisdn").strip():
            _CURRENT_MSISDN = args.get("msisdn")
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
        if tool.name == "verify_login_tool":
            try:
                data = json.loads(content)
                logger.info("verify_login: verified=%s", data.get("verified"))
            except Exception:
                logger.info("verify_login result: %s", content[:300])
        elif tool.name == "start_login_tool":
            try:
                data = json.loads(content)
                logger.info("start_login_tool: sent=%s", data.get("sent"))
            except Exception:
                logger.info("start_login_tool: %s", content[:300])
        else:
            # Generic preview
            logger.info("tool %s result: %s", tool.name, (content[:300] if isinstance(content, str) else str(content)[:300]))
    except Exception:
        pass
    # Never expose OTP debug_code to the LLM
    try:
        if tool.name == "start_login_tool":
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
    # Trim to avoid context bloat
    convo = _trim_messages(convo, max_messages=int(os.getenv("RBC_FEES_MAX_MSGS", "40")))
    # Sanitize to avoid orphan tool messages after trimming
    convo = _sanitize_conversation(convo)
    thread_id = _get_thread_id(config, new_list)
    logger.info("agent start: thread_id=%s total_in=%s (prev=%s, new=%s)", thread_id, len(convo), len(prev_list), len(new_list))
    # Establish default session context
    conf = (config or {}).get("configurable", {}) if isinstance(config, dict) else {}
    default_msisdn = conf.get("msisdn") or conf.get("phone_number")

    # Update module context
    global _CURRENT_THREAD_ID, _CURRENT_MSISDN
    _CURRENT_THREAD_ID = thread_id
    _CURRENT_MSISDN = default_msisdn

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


