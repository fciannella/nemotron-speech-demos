"""LangGraph-backed LLM service for Pipecat pipelines.

This service adapts a running LangGraph agent (accessed via langgraph-sdk)
to Pipecat's frame-based processing model. It consumes `OpenAILLMContextFrame`
or `LLMMessagesFrame` inputs, extracts the latest user message (using the
LangGraph server's thread to persist history), and streams assistant tokens
back as `LLMTextFrame` until completion.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional
import os
from dotenv import load_dotenv

from langgraph_sdk import get_client
from langchain_core.messages import HumanMessage
from loguru import logger
from pipecat.frames.frames import (
    Frame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMMessagesFrame,
    LLMTextFrame,
    InterruptionFrame,
    UserImageRawFrame,
)
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext, OpenAILLMContextFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.openai.llm import OpenAILLMService


load_dotenv()

# TTS sanitize helper: normalize curly quotes/dashes and non-breaking spaces to ASCII
def _tts_sanitize(text: str) -> str:
    try:
        if not isinstance(text, str):
            text = str(text)
        replacements = {
            "\u2018": "'",  # left single quote
            "\u2019": "'",  # right single quote / apostrophe
            "\u201C": '"',   # left double quote
            "\u201D": '"',   # right double quote
            "\u00AB": '"',   # left angle quote
            "\u00BB": '"',   # right angle quote
            "\u2013": "-",  # en dash
            "\u2014": "-",  # em dash
            "\u2026": "...",# ellipsis
            "\u00A0": " ",  # non-breaking space
            "\u202F": " ",  # narrow no-break space
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        return text
    except Exception:
        return text

class LangGraphLLMService(OpenAILLMService):
    """Pipecat LLM service that delegates responses to a LangGraph agent.

    Attributes:
        base_url: LangGraph API base URL, e.g. "http://127.0.0.1:2024".
        assistant: Assistant name or id registered with the LangGraph server.
        user_email: Value for `configurable.user_email` (routing / personalization).
        stream_mode: SDK stream mode ("updates", "values", "messages", "events").
        debug_stream: When True, logs raw stream events for troubleshooting.
    """

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:2024",
        assistant: str = "ace-base-agent",
        user_email: str = "test@example.com",
        stream_mode: str = "values",
        debug_stream: bool = False,
        thread_id: Optional[str] = None,
        auth_token: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        # Initialize base class; OpenAI settings unused but required by parent
        super().__init__(api_key="", **kwargs)
        self.base_url = base_url
        self.assistant = assistant
        self.user_email = user_email
        self.stream_mode = stream_mode
        self.debug_stream = debug_stream

        # Optional auth header
        token = (
            auth_token
            or os.getenv("LANGGRAPH_AUTH_TOKEN")
            or os.getenv("AUTH0_ACCESS_TOKEN")
            or os.getenv("AUTH_BEARER_TOKEN")
        )

        headers = {"Authorization": f"Bearer {token}"} if isinstance(token, str) and token else None
        self._client = get_client(url=self.base_url, headers=headers) if headers else get_client(url=self.base_url)
        self._thread_id: Optional[str] = thread_id
        self._current_task: Optional[asyncio.Task] = None
        self._outer_open: bool = False
        self._emitted_texts: set[str] = set()
        self._runtime_config: Optional[dict] = None  # Runtime configuration for agent
        self._last_content: str = ""  # Track last content to detect changes
        self._tools_seen: set[str] = set()  # Track tools to detect when we hit final response

    def set_runtime_config(self, config: dict) -> None:
        """Set runtime configuration for the agent.
        
        Args:
            config: Configuration dict with 'configurable' and optional 'metadata' keys.
                   Example: {
                       "configurable": {"book_id": "123", "agent_voice": "author"},
                       "metadata": {"user_id": "user@example.com"}
                   }
        """
        self._runtime_config = config
        logger.info(f"[LangGraph] Runtime config set: {config}")
    
    def get_runtime_config(self) -> Optional[dict]:
        """Get the current runtime configuration."""
        return self._runtime_config
    
    def _build_config(self) -> dict:
        """Build the configuration for LangGraph runs, merging base + runtime config.
        
        Returns:
            Merged configuration dict
        """
        # Start with base config
        config: dict = {
            "configurable": {
                "user_email": self.user_email
            }
        }
        
        # Merge runtime config if present
        if self._runtime_config:
            # Merge configurable section
            if "configurable" in self._runtime_config:
                config["configurable"].update(self._runtime_config["configurable"])
            
            # Add metadata section if present
            if "metadata" in self._runtime_config:
                config["metadata"] = self._runtime_config["metadata"]
        
        return config

    async def _ensure_thread(self) -> Optional[str]:
        if self._thread_id:
            return self._thread_id
        try:
            thread = await self._client.threads.create()
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"LangGraph: failed to create thread; proceeding threadless. Error: {exc}")
            self._thread_id = None
            return None

        thread_id = getattr(thread, "thread_id", None)
        if thread_id is None and isinstance(thread, dict):
            thread_id = thread.get("thread_id") or thread.get("id")
        if thread_id is None:
            thread_id = getattr(thread, "id", None)
        if isinstance(thread_id, str) and thread_id:
            self._thread_id = thread_id
        else:
            logger.warning("LangGraph: could not determine thread id; proceeding threadless.")
            self._thread_id = None
        return self._thread_id

    @staticmethod
    def _extract_latest_user_text(context: OpenAILLMContext) -> str:
        """Return the latest user (or fallback system) message content.

        The LangGraph server maintains history via threads, so we only need to
        send the current turn text. Prefer the latest user message; if absent,
        fall back to the latest system message so system-only kickoffs can work.
        """
        messages = context.get_messages() or []
        for msg in reversed(messages):
            try:
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    return content if isinstance(content, str) else str(content)
            except Exception:  # Defensive against unexpected shapes
                continue
        # Fallback: use the most recent system message if no user message exists
        for msg in reversed(messages):
            try:
                if msg.get("role") == "system":
                    content = msg.get("content", "")
                    return content if isinstance(content, str) else str(content)
            except Exception:
                continue
        return ""

    async def _stream_langgraph(self, text: str) -> None:
        logger.info(f"[LangGraph] Starting stream for text: '{text[:50]}...'")
        logger.info(f"[LangGraph] Config: assistant={self.assistant}, stream_mode={self.stream_mode}, thread_id={self._thread_id}")
        
        # Clear previous state
        self._last_content = ""
        self._tools_seen.clear()
        self._outer_open = False
        self._emitted_texts.clear()
        
        # Build config with runtime parameters
        config = self._build_config()
        logger.info(f"[LangGraph] Using config: {config}")
        
        # Attempt to ensure thread; OK if None (threadless run)
        await self._ensure_thread()
        
        logger.info(f"[LangGraph] Thread ensured: {self._thread_id}")
        
        # Get conversation history from thread state
        input_messages = []
        if self._thread_id:
            try:
                state = await self._client.threads.get_state(thread_id=self._thread_id)
                if state and state.get("values"):
                    existing_msgs = state["values"].get("messages", [])
                    if existing_msgs:
                        input_messages = existing_msgs
                        logger.info(f"[LangGraph] Loaded {len(existing_msgs)} existing messages from thread")
            except Exception as e:
                logger.debug(f"[LangGraph] Could not load thread state: {e}")
        
        # Append the new user message
        input_messages.append({"role": "user", "content": text})
        logger.info(f"[LangGraph] Sending {len(input_messages)} total messages to agent")
        logger.info(f"[LangGraph] Latest user message: '{text[:100]}...'")

        # For Functional API, send messages as a plain list (not wrapped in dict)
        # simple_agent(messages: list) expects the list directly
        
        try:
            logger.info(f"[LangGraph] Starting SDK stream with mode: {self.stream_mode}...")
            async for chunk in self._client.runs.stream(
                self._thread_id,
                self.assistant,
                input=input_messages,  # Send as plain list for Functional API
                stream_mode=self.stream_mode,  # Use string, not list
                config=config,
            ):
                data = getattr(chunk, "data", None)
                event = getattr(chunk, "event", "") or ""
                
                logger.info(f"[LangGraph] 📦 Chunk: event='{event}', data_type={type(data).__name__}")
                
                # Log data structure for debugging
                if isinstance(data, dict):
                    logger.debug(f"[LangGraph]    Data keys: {list(data.keys())}")
                elif isinstance(data, str):
                    logger.debug(f"[LangGraph]    Data string: '{data[:100]}...'")
                elif hasattr(data, 'content'):
                    logger.debug(f"[LangGraph]    Data content: '{getattr(data, 'content', '')[:100]}...'")

                # Handle messages/partial events for token-by-token streaming
                # This gives us incremental content as tokens arrive
                # Also handle plain "messages" events which contain the message list
                if (event == "messages/partial" or event == "messages") and data is not None:
                    # Extract messages from data
                    messages = []
                    if isinstance(data, (list, tuple)):
                        messages = list(data)
                    elif isinstance(data, dict) and "messages" in data:
                        messages = data.get("messages", [])
                    
                    logger.info(f"[LangGraph] 📧 Processing {event}: found {len(messages)} message(s)")
                    
                    if messages and len(messages) > 0:
                        # Track tool calls to know when we've moved past internal processing
                        for msg in messages:
                            msg_type = getattr(msg, "type", None) or getattr(msg, "role", None)
                            if isinstance(msg, dict):
                                msg_type = msg.get("type") or msg.get("role")

                            # Track tools
                            if msg_type == "ai" or msg_type == "assistant":
                                tool_calls = getattr(msg, "tool_calls", None) if hasattr(msg, "tool_calls") else (msg.get("tool_calls") if isinstance(msg, dict) else None)
                                if tool_calls and isinstance(tool_calls, list):
                                    for tool_call in tool_calls:
                                        tool_name = getattr(tool_call, "name", None) if hasattr(tool_call, "name") else (tool_call.get("name") if isinstance(tool_call, dict) else None)
                                        if tool_name:
                                            self._tools_seen.add(tool_name)
                                            logger.debug(f"[LangGraph] Tool call detected: {tool_name}")
                        
                        # Get the last message
                        last_msg = messages[-1]
                        msg_type = getattr(last_msg, "type", None) or getattr(last_msg, "role", None)
                        if isinstance(last_msg, dict):
                            msg_type = last_msg.get("type") or last_msg.get("role")
                        
                        # Only stream if it's an assistant message with actual content
                        if msg_type in ("ai", "assistant"):
                            content = getattr(last_msg, "content", "") if hasattr(last_msg, "content") else (last_msg.get("content", "") if isinstance(last_msg, dict) else "")
                            
                            if isinstance(content, str) and content.strip():
                                # Skip internal processing messages (ones with tool calls or short status messages)
                                tool_calls = getattr(last_msg, "tool_calls", None) if hasattr(last_msg, "tool_calls") else (last_msg.get("tool_calls") if isinstance(last_msg, dict) else None)
                                has_tool_calls = tool_calls and isinstance(tool_calls, list) and len(tool_calls) > 0
                                
                                # Only stream if:
                                # 1. No active tool calls (we're past internal processing)
                                # 2. Content has changed
                                # 3. We've seen tools (so we're past initial processing) OR content is substantial
                                is_substantial = len(content) > 20 or len(self._tools_seen) > 0
                                
                                logger.debug(f"[LangGraph] Checking: has_tool_calls={has_tool_calls}, content_len={len(content)}, is_substantial={is_substantial}, changed={content != self._last_content}")

                                if not has_tool_calls and content != self._last_content and is_substantial:
                                    # Open response if not already open
                                    if not self._outer_open:
                                        logger.info(f"[LangGraph] ✅ Starting to stream final response...")
                                        await self.push_frame(LLMFullResponseStartFrame())
                                        self._outer_open = True
                                        self._emitted_texts.clear()
                                        self._last_content = ""
                                    
                                    # Calculate delta (only new text since last update)
                                    if len(content) > len(self._last_content):
                                        delta = content[len(self._last_content):]
                                        self._last_content = content
                                        
                                        # Emit only the NEW text (delta)
                                        await self.push_frame(LLMTextFrame(_tts_sanitize(delta)))
                                        logger.info(f"[LangGraph] 📝 Streamed delta ({len(delta)} chars): '{delta[:80]}...'")

                # Fallback: Handle 'values' mode for non-streaming responses
                if event == "values":
                    logger.info(f"[LangGraph] 📦 Processing 'values' event, data type: {type(data).__name__}")
                    content_to_emit = None
                    
                    if isinstance(data, dict):
                        logger.info(f"[LangGraph] Dict keys: {list(data.keys())}")
                        
                        # Pattern 1: Functional API - data is {"messages": [...]}
                        msgs = data.get("messages")
                        if isinstance(msgs, list) and msgs:
                            logger.info(f"[LangGraph] Functional API pattern - found {len(msgs)} messages")
                            last_msg = msgs[-1]
                            if isinstance(last_msg, dict):
                                role = last_msg.get("role") or last_msg.get("type")
                                content = last_msg.get("content", "")
                                if role in ("assistant", "ai") and isinstance(content, str) and content.strip():
                                    content_to_emit = content
                                    logger.info(f"[LangGraph] Extracted content from Functional API: '{content[:100]}...'")
                        
                        # Pattern 2: React API - data is an AIMessage object (dict with 'content' key)
                        elif "content" in data and "type" in data:
                            msg_type = data.get("type")
                            content = data.get("content", "")
                            logger.info(f"[LangGraph] React API pattern - type={msg_type}, content_len={len(content) if isinstance(content, str) else 'N/A'}")
                            if msg_type in ("ai", "AIMessage") and isinstance(content, str) and content.strip():
                                content_to_emit = content
                                logger.info(f"[LangGraph] Extracted content from React API: '{content[:100]}...'")
                    
                    # Emit the content if we found any
                    if content_to_emit and content_to_emit != self._last_content:
                        self._last_content = content_to_emit
                        logger.info(f"[LangGraph] 🎯 Emitting response via frames...")
                        await self.push_frame(LLMFullResponseStartFrame())
                        await self.push_frame(LLMTextFrame(_tts_sanitize(content_to_emit)))
                        await self.push_frame(LLMFullResponseEndFrame())
                        logger.info(f"[LangGraph] ✅ Emitted final response (values mode, {len(content_to_emit)} chars)")
                    elif content_to_emit == self._last_content:
                        logger.info(f"[LangGraph] ⚠️ Skipping emission: already sent this content")
                    else:
                        logger.info(f"[LangGraph] ⚠️ No content extracted from values event")

                # Handle plain string responses (edge case)
                if isinstance(data, str) and data.strip():
                    txt = data.strip()
                    if txt != self._last_content:
                        self._last_content = txt
                        if not self._outer_open:
                            await self.push_frame(LLMFullResponseStartFrame())
                            self._outer_open = True
                            await self.push_frame(LLMTextFrame(_tts_sanitize(txt)))
        except Exception as exc:  # noqa: BLE001
            logger.error(f"LangGraph stream error: {exc}", exc_info=True)
        finally:
            # Close the response if it was opened
            if self._outer_open:
                await self.push_frame(LLMFullResponseEndFrame())
                self._outer_open = False
                logger.info(f"[LangGraph] Stream completed, emitted {len(self._last_content)} total chars")

    async def _process_context_and_frames(self, context: OpenAILLMContext) -> None:
        """Adapter entrypoint: push start/end frames and stream tokens."""
        try:
            # Defer opening until backchannels arrive; final will be emitted separately
            user_text = self._extract_latest_user_text(context)
            logger.info(f"[LangGraph] _process_context_and_frames called with user_text: '{user_text[:50] if user_text else None}...'")
            if not user_text:
                logger.warning("LangGraph: no user text in context; skipping run.")
                return
            self._outer_open = False
            self._emitted_texts.clear()
            await self._stream_langgraph(user_text)
        finally:
            if self._outer_open:
                await self.push_frame(LLMFullResponseEndFrame())
                self._outer_open = False

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process pipeline frames, handling interruptions and context inputs."""
        context: Optional[OpenAILLMContext] = None

        if isinstance(frame, OpenAILLMContextFrame):
            context = frame.context
        elif isinstance(frame, LLMMessagesFrame):
            context = OpenAILLMContext.from_messages(frame.messages)
        elif isinstance(frame, UserImageRawFrame):
            # Not implemented for LangGraph adapter; ignore images
            context = None
        elif isinstance(frame, InterruptionFrame):
            # Relay interruption downstream and cancel any active run
            await self._start_interruption()
            await self.stop_all_metrics()
            await self.push_frame(frame, direction)
            if self._current_task is not None and not self._current_task.done():
                await self.cancel_task(self._current_task)
                self._current_task = None
            return
        else:
            await super().process_frame(frame, direction)

        if context is not None:
            if self._current_task is not None and not self._current_task.done():
                await self.cancel_task(self._current_task)
                self._current_task = None
                logger.debug("LangGraph LLM: canceled previous task")

            self._current_task = self.create_task(self._process_context_and_frames(context))
            self._current_task.add_done_callback(lambda _: setattr(self, "_current_task", None))


