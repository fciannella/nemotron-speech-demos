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


# ---- Tools (healthcare) ----

try:
    from . import tools as hc_tools  # type: ignore
    from . import prompts as hc_prompts  # type: ignore
except Exception:
    import importlib.util as _ilu
    _dir = os.path.dirname(__file__)
    _tools_path = os.path.join(_dir, "tools.py")
    _spec = _ilu.spec_from_file_location("healthcare_agent_tools", _tools_path)
    hc_tools = _ilu.module_from_spec(_spec)  # type: ignore
    assert _spec and _spec.loader
    _spec.loader.exec_module(hc_tools)  # type: ignore
    _prompts_path = os.path.join(_dir, "prompts.py")
    _spec_prompts = _ilu.spec_from_file_location("healthcare_agent_prompts", _prompts_path)
    hc_prompts = _ilu.module_from_spec(_spec_prompts)  # type: ignore
    assert _spec_prompts and _spec_prompts.loader
    _spec_prompts.loader.exec_module(hc_prompts)  # type: ignore

# Aliases for tool functions
find_patient = hc_tools.find_patient
get_patient_profile_tool = hc_tools.get_patient_profile_tool
verify_identity = hc_tools.verify_identity
get_preferred_pharmacy_tool = hc_tools.get_preferred_pharmacy_tool
list_providers_tool = hc_tools.list_providers_tool
get_provider_slots_tool = hc_tools.get_provider_slots_tool
schedule_appointment_tool = hc_tools.schedule_appointment_tool
triage_symptoms_tool = hc_tools.triage_symptoms_tool
log_call_tool = hc_tools.log_call_tool

find_customer_by_name = None  # not used


"""ReAct agent entrypoint and system prompt."""

# Import system prompt from prompts module
SYSTEM_PROMPT = hc_prompts.HEALTHCARE_SYSTEM_PROMPT


_MODEL_NAME = os.getenv("REACT_MODEL", os.getenv("CLARIFY_MODEL", "gpt-4o"))
_OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
_LLM = ChatOpenAI(model=_MODEL_NAME, temperature=0.3, base_url=_OPENAI_BASE_URL, api_key=_OPENAI_API_KEY)
_TOOLS = [
    find_patient,
    get_patient_profile_tool,
    verify_identity,
    triage_symptoms_tool,
    list_providers_tool,
    get_provider_slots_tool,
    schedule_appointment_tool,
    get_preferred_pharmacy_tool,
    log_call_tool,
]
_LLM_WITH_TOOLS = _LLM.bind_tools(_TOOLS)
_TOOLS_BY_NAME = {t.name: t for t in _TOOLS}

# Simple per-run context storage (thread-safe enough for local dev worker)
_CURRENT_THREAD_ID: str | None = None
_CURRENT_PATIENT_ID: str | None = None

# ---- Logger ----
logger = logging.getLogger("HealthcareAgent")
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
_DEBUG = os.getenv("HC_DEBUG", "0") not in ("", "0", "false", "False")

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
    # Auto-inject session/patient context for identity and profile tools
    if tool.name == "verify_identity":
        if "session_id" not in args and _CURRENT_THREAD_ID:
            args["session_id"] = _CURRENT_THREAD_ID
        if "patient_id" not in args and _CURRENT_PATIENT_ID:
            args["patient_id"] = _CURRENT_PATIENT_ID
    if tool.name in ("get_patient_profile_tool", "get_preferred_pharmacy_tool"):
        if "patient_id" not in args and _CURRENT_PATIENT_ID:
            args["patient_id"] = _CURRENT_PATIENT_ID
    if tool.name == "triage_symptoms_tool":
        if "patient_id" not in args:
            args["patient_id"] = _CURRENT_PATIENT_ID
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
    # Trim to avoid context bloat
    convo = _trim_messages(convo, max_messages=int(os.getenv("RBC_FEES_MAX_MSGS", "40")))
    # Sanitize to avoid orphan tool messages after trimming
    convo = _sanitize_conversation(convo)
    thread_id = _get_thread_id(config, new_list)
    logger.info("agent start: thread_id=%s total_in=%s (prev=%s, new=%s)", thread_id, len(convo), len(prev_list), len(new_list))
    # Establish default patient from config (or fallback to pt_jmarshall)
    conf = (config or {}).get("configurable", {}) if isinstance(config, dict) else {}
    default_patient = conf.get("patient_id") or conf.get("user_email") or "pt_jmarshall"

    # Heuristic: infer patient_id from latest human name if provided (e.g., "I am John Marshall")
    inferred_patient: str | None = None
    try:
        recent_humans = [m for m in reversed(new_list) if (getattr(m, "type", None) == "human" or getattr(m, "role", None) == "user" or (isinstance(m, dict) and m.get("type") == "human"))]
        text = None
        for m in recent_humans[:3]:
            text = (getattr(m, "content", None) if not isinstance(m, dict) else m.get("content")) or ""
            if isinstance(text, str) and text.strip():
                break
        if isinstance(text, str):
            tokens = [t for t in text.replace(',', ' ').split() if t.isalpha()]
            if len(tokens) >= 2 and False:
                pass
    except Exception:
        pass

    # Update module context
    global _CURRENT_THREAD_ID, _CURRENT_PATIENT_ID
    _CURRENT_THREAD_ID = thread_id
    _CURRENT_PATIENT_ID = inferred_patient or default_patient

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


