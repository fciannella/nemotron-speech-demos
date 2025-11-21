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
        
        config = {"configurable": {"user_email": self.user_email}}
        # Attempt to ensure thread; OK if None (threadless run)
        await self._ensure_thread()
        
        logger.info(f"[LangGraph] Thread ensured: {self._thread_id}")
        
        # Get conversation history from thread state and append new message
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

        try:
            logger.info(f"[LangGraph] Starting SDK stream...")
            async for chunk in self._client.runs.stream(
                self._thread_id,
                self.assistant,
                input=input_messages,  # Send full conversation history!
                stream_mode=self.stream_mode,
                config=config,
            ):
                data = getattr(chunk, "data", None)
                event = getattr(chunk, "event", "") or ""
                
                # ALWAYS log first to see if we're getting chunks
                logger.info(f"[LangGraph] Received chunk: event='{event}', data_type={type(data).__name__}")

                if self.debug_stream:
                    try:
                        # Short, structured debugging output
                        dtype = type(data).__name__
                        preview = ""
                        if hasattr(data, "content") and isinstance(getattr(data, "content"), str):
                            c = getattr(data, "content")
                            preview = c[:120]
                        elif isinstance(data, dict):
                            preview = ",".join(list(data.keys())[:6])
                        logger.debug(f"[LangGraph stream] event={event} data={dtype}:{preview}")
                    except Exception:  # noqa: BLE001
                        logger.debug(f"[LangGraph stream] event={event}")

                # Token streaming events (LangChain chat model streaming)
                if "on_chat_model_stream" in event or event.endswith(".on_chat_model_stream"):
                    part_text = ""
                    d = data
                    if isinstance(d, dict):
                        if "chunk" in d:
                            ch = d["chunk"]
                            part_text = getattr(ch, "content", None) or ""
                            if not isinstance(part_text, str):
                                part_text = str(part_text)
                        elif "delta" in d:
                            delta = d["delta"]
                            part_text = getattr(delta, "content", None) or ""
                            if not isinstance(part_text, str):
                                part_text = str(part_text)
                        elif "content" in d and isinstance(d["content"], str):
                            part_text = d["content"]
                    else:
                        part_text = getattr(d, "content", "")

                    if part_text:
                        if not self._outer_open:
                            await self.push_frame(LLMFullResponseStartFrame())
                            self._outer_open = True
                            self._emitted_texts.clear()
                        if part_text not in self._emitted_texts:
                            self._emitted_texts.add(part_text)
                            await self.push_frame(LLMTextFrame(_tts_sanitize(part_text)))

                # Final value-style events (values mode)
                if event == "values":
                    # For Functional API entrypoints, data is the return value
                    # Our simple_agent returns {"messages": [...]}
                    logger.info(f"[LangGraph] Processing 'values' event, data: {type(data).__name__}")
                    final_text = ""
                    if isinstance(data, dict):
                        logger.info(f"[LangGraph] Dict keys: {list(data.keys())}")
                        # Check if it's our agent's response format
                        msgs = data.get("messages")
                        if isinstance(msgs, list) and msgs:
                            logger.info(f"[LangGraph] Found {len(msgs)} messages")
                            # Get the last assistant message
                            last_msg = msgs[-1]
                            if isinstance(last_msg, dict):
                                content = last_msg.get("content", "")
                                logger.info(f"[LangGraph] Last message content: '{content[:100]}...'")
                                if isinstance(content, str):
                                    final_text = content
                        # Fallback: direct content field
                        if not final_text:
                            c = data.get("content")
                            if isinstance(c, str):
                                final_text = c
                    elif hasattr(data, "content") and isinstance(getattr(data, "content"), str):
                        final_text = getattr(data, "content")
                    
                    logger.info(f"[LangGraph] Extracted final_text: '{final_text[:100] if final_text else None}...'")
                    if final_text:
                        # Close backchannel utterance if open
                        if self._outer_open:
                            await self.push_frame(LLMFullResponseEndFrame())
                            self._outer_open = False
                            self._emitted_texts.clear()
                        # Emit final explanation as its own message
                        await self.push_frame(LLMFullResponseStartFrame())
                        await self.push_frame(LLMTextFrame(_tts_sanitize(final_text)))
                        await self.push_frame(LLMFullResponseEndFrame())

                # Messages mode: look for an array of messages
                if event == "messages" or event.endswith(":messages"):
                    try:
                        msgs = None
                        if isinstance(data, dict):
                            msgs = data.get("messages") or data.get("result") or data.get("value")
                        elif hasattr(data, "messages"):
                            msgs = getattr(data, "messages")
                        if isinstance(msgs, list) and msgs:
                            last = msgs[-1]
                            content = getattr(last, "content", None)
                            if content is None and isinstance(last, dict):
                                content = last.get("content")
                            if isinstance(content, str) and content:
                                if not self._outer_open:
                                    await self.push_frame(LLMFullResponseStartFrame())
                                    self._outer_open = True
                                    self._emitted_texts.clear()
                                if content not in self._emitted_texts:
                                    self._emitted_texts.add(content)
                                    await self.push_frame(LLMTextFrame(_tts_sanitize(content)))
                    except Exception as exc:  # noqa: BLE001
                        logger.debug(f"LangGraph messages parsing error: {exc}")
                # If payload is a plain string, emit it
                if isinstance(data, str):
                    txt = data.strip()
                    if txt:
                        if not self._outer_open:
                            await self.push_frame(LLMFullResponseStartFrame())
                            self._outer_open = True
                            self._emitted_texts.clear()
                        if txt not in self._emitted_texts:
                            self._emitted_texts.add(txt)
                            await self.push_frame(LLMTextFrame(_tts_sanitize(txt)))
        except Exception as exc:  # noqa: BLE001
            logger.error(f"LangGraph stream error: {exc}", exc_info=True)
        
        logger.info(f"[LangGraph] Stream completed")

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


