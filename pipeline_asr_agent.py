#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2024-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: BSD 2-Clause License

"""ASR + Agent Pipeline with Text-Only Output (No TTS).

This pipeline provides:
- Voice input via WebRTC
- NVIDIA Riva STT for speech recognition
- LangGraph agent for intelligent responses
- Text-only output (no speech synthesis)
- Support for interruptions during agent text streaming
- Agent-specific configuration via 'config' parameter

Perfect for:
- Voice-controlled chatbots with text display
- Fast agent responses without TTS latency
- Scenarios where text output is preferred over speech
- Mobile apps with text UI but voice input

Agent Configuration:
-------------------
Pass agent-specific configuration in the request body under the 'config' key.

Example request to /api/offer:
    POST /api/offer
    {
        "pc_id": "unique-id",
        "sdp": "...",
        "type": "offer",
        "assistant": "motivator",
        "language": "en-US",
        "config": {
            "configurable": {
                "book_id": "6c3dba595fff66efae64fecbfd1c9ce8",
                "agent_voice": "author",
                "motivation_style": "balanced",
                "user_goal": "Build a daily reading habit"
            },
            "metadata": {
                "user_id": "user@example.com",
                "session_source": "mobile_app"
            }
        }
    }

Example for claims agent:
    {
        "assistant": "claims-investigation-agent",
        "config": {
            "configurable": {
                "claim_id": "CLM-2024-001",
                "policy_number": "POL-12345"
            }
        }
    }

The 'config' parameter is passed directly to LangGraph's run API, allowing
agents to access these values in their graph logic.
"""

import argparse
import asyncio
import base64
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from loguru import logger
from pipecat_ai_small_webrtc_prebuilt.frontend import SmallWebRTCPrebuiltUI

from pipecat.frames.frames import (
    Frame,
    TranscriptionFrame,
    InterimTranscriptionFrame,
    TextFrame,
    EndFrame
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.processors.frameworks.rtvi import RTVIProcessor, RTVIObserver
from pipecat.services.riva.stt import RivaSTTService
from pipecat.transcriptions.language import Language
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.smallwebrtc.connection import (
    IceServer,
    SmallWebRTCConnection,
)
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams

# Use the ASR-agent specific version that wraps input in {"messages": [...]} dict
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location("langgraph_llm_service_asr", 
    Path(__file__).parent / "langgraph_llm_service-asr-agent.py")
langgraph_llm_service_asr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(langgraph_llm_service_asr)
LangGraphLLMService = langgraph_llm_service_asr.LangGraphLLMService

load_dotenv(override=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store connections, contexts, and configs by pc_id
pcs_map: dict[str, SmallWebRTCConnection] = {}
contexts_map: dict[str, OpenAILLMContext] = {}
configs_map: dict[str, dict] = {}  # Store agent-specific config per session
llm_services_map: dict[str, LangGraphLLMService] = {}  # Store LLM service instance per session


def get_language_from_string(lang_str: str):
    """Convert language string to Language enum.
    
    Args:
        lang_str: Language code like "en-US", "es-ES", "multi"
        
    Returns:
        Language enum value, or "multi" for auto-detection
    """
    if lang_str.lower() == "multi":
        return "multi"
    
    mapping = {
        "en-US": Language.EN_US,
        "en-GB": Language.EN_GB,
        "es-ES": Language.ES,
        "es-US": Language.ES_US,
        "fr-FR": Language.FR,
        "de-DE": Language.DE,
        "it-IT": Language.IT,
        "pt-BR": Language.PT_BR,
        "ja-JP": Language.JA,
        "ko-KR": Language.KO,
        "zh-CN": Language.ZH,
    }
    return mapping.get(lang_str, Language.EN_US)


def build_client_ice_servers() -> list[dict]:
    """Build ICE servers for client (browser) using Twilio or env vars.
    
    Returns:
        List of ICE server configurations for browser
    """
    # Try Twilio dynamic TURN credentials
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token_auth = os.getenv("TWILIO_AUTH_TOKEN")
    
    if sid and token_auth:
        try:
            from twilio.rest import Client
            
            client = Client(sid, token_auth)
            token = client.tokens.create()
            servers: list[dict] = []
            
            for s in getattr(token, "ice_servers", []) or []:
                url_val = s.get("urls") if isinstance(s, dict) else getattr(s, "urls", None)
                if not url_val:
                    url_val = s.get("url") if isinstance(s, dict) else getattr(s, "url", None)
                
                entry: dict = {"urls": url_val}
                u = s.get("username") if isinstance(s, dict) else getattr(s, "username", None)
                c = s.get("credential") if isinstance(s, dict) else getattr(s, "credential", None)
                
                if u:
                    entry["username"] = u
                if c:
                    entry["credential"] = c
                if entry.get("urls"):
                    servers.append(entry)
            
            # Always include public STUN fallback
            servers.append({"urls": "stun:stun.l.google.com:19302"})
            logger.info(f"Using Twilio TURN servers ({len(servers)} configured)")
            return servers
            
        except Exception as e:
            logger.warning(f"Twilio TURN fetch failed, using env vars: {e}")
    
    # Fallback to env vars
    servers: list[dict] = []
    turn_url = os.getenv("TURN_SERVER_URL") or os.getenv("TURN_URL")
    turn_user = os.getenv("TURN_USERNAME") or os.getenv("TURN_USER")
    turn_pass = os.getenv("TURN_PASSWORD") or os.getenv("TURN_PASS")
    
    if turn_url:
        server: dict = {"urls": turn_url}
        if turn_user:
            server["username"] = turn_user
        if turn_pass:
            server["credential"] = turn_pass
        servers.append(server)
        logger.info("Using env var TURN server")
    
    # Always include public STUN
    servers.append({"urls": "stun:stun.l.google.com:19302"})
    return servers


def build_server_ice_servers() -> list[IceServer]:
    """Convert client ICE configs to server IceServer objects.
    
    Returns:
        List of IceServer objects for Pipecat transport
    """
    out: list[IceServer] = []
    for s in build_client_ice_servers():
        urls = s.get("urls")
        username = s.get("username", "")
        credential = s.get("credential", "")
        
        # urls may be a list or string
        if isinstance(urls, list):
            for u in urls:
                out.append(IceServer(urls=u, username=username, credential=credential))
        elif isinstance(urls, str) and urls:
            out.append(IceServer(urls=urls, username=username, credential=credential))
    
    return out


async def run_asr_agent(
    webrtc_connection: SmallWebRTCConnection,
    ws: Optional[WebSocket] = None,
    assistant_override: Optional[str] = None,
    language_override: Optional[str] = None,
    langgraph_url_override: Optional[str] = None,
    agent_config: Optional[dict] = None
):
    """Run ASR + Agent pipeline with text-only output (no TTS).
    
    Args:
        webrtc_connection: WebRTC connection for audio streaming
        ws: Optional WebSocket for control/transcription messages
        assistant_override: Optional assistant name override from client
        language_override: Optional language code override from client
        langgraph_url_override: Optional LangGraph URL override from client
        agent_config: Optional agent-specific configuration dict with 'configurable' and 'metadata' keys
                     Example: {"configurable": {"book_id": "123"}, "metadata": {"user_id": "user@example.com"}}
    """
    stream_id = uuid.uuid4()
    
    logger.info("=" * 80)
    logger.info(f"🚀 Starting ASR + Agent Pipeline (Text-Only) (stream_id: {stream_id})")
    logger.info("=" * 80)
    
    # Log configuration
    if assistant_override:
        logger.info(f"📚 Assistant from client: '{assistant_override}'")
    if language_override:
        logger.info(f"🌐 Language from client: '{language_override}'")
    if langgraph_url_override:
        logger.info(f"🔗 LangGraph URL from client: '{langgraph_url_override}'")
    if agent_config:
        logger.info(f"⚙️  Agent config from client: {agent_config}")
    
    # Transport configuration
    sample_rate = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
    
    # Configure VAD (Voice Activity Detection) parameters
    logger.info("")
    logger.info("🎚️  VAD CONFIGURATION:")
    vad_params = VADParams(
        confidence=0.3,    # Lower = more sensitive to speech (was 0.5)
        start_secs=0.1,    # Wait only 100ms before confirming speech started (was 0.3)
        stop_secs=1.5,     # Wait 1.5s of silence before stopping
        min_volume=0.3     # Lower = picks up quieter speech (was 0.5)
    )
    logger.info(f"   • Confidence: {vad_params.confidence}")
    logger.info(f"   • Start threshold: {vad_params.start_secs}s")
    logger.info(f"   • Stop threshold: {vad_params.stop_secs}s")
    logger.info(f"   • Min volume: {vad_params.min_volume}")
    logger.info("")
    
    transport_params = TransportParams(
        audio_in_enabled=True,
        audio_in_sample_rate=sample_rate,
        audio_out_sample_rate=sample_rate,
        audio_out_enabled=False,  # NO AUDIO OUTPUT (no TTS)
        vad_analyzer=SileroVADAnalyzer(params=vad_params),
    )
    
    transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection,
        params=transport_params,
    )
    
    # LangGraph LLM Service with metadata
    selected_assistant = assistant_override or os.getenv("LANGGRAPH_ASSISTANT", "simple_agent")
    langgraph_base_url = langgraph_url_override or os.getenv("LANGGRAPH_BASE_URL", "http://127.0.0.1:2024")
    
    logger.info("")
    logger.info("🤖 LANGGRAPH CONFIGURATION:")
    logger.info(f"   • Assistant ID: '{selected_assistant}'")
    logger.info(f"   • Base URL: {langgraph_base_url}")
    logger.info(f"   • Override from client: {assistant_override or 'None'}")
    logger.info(f"   • From env (LANGGRAPH_ASSISTANT): {os.getenv('LANGGRAPH_ASSISTANT', 'simple_agent')}")
    
    # Verify assistant exists (optional check)
    try:
        import requests
        resp = requests.get(f"{langgraph_base_url}/assistants", timeout=5)
        if resp.ok:
            assistants_data = resp.json()
            if isinstance(assistants_data, list):
                assistant_ids = [a.get('assistant_id') or a.get('id') or a for a in assistants_data]
            elif isinstance(assistants_data, dict):
                items = assistants_data.get('items', [])
                assistant_ids = [a.get('assistant_id') or a.get('id') or a for a in items]
            else:
                assistant_ids = []
            
            logger.info(f"   • Available assistants: {assistant_ids}")
            
            if selected_assistant not in assistant_ids:
                logger.warning(f"   ⚠️  WARNING: Assistant '{selected_assistant}' not found in available assistants!")
                logger.warning(f"   Available: {assistant_ids}")
    except Exception as e:
        logger.debug(f"   Could not verify assistant (non-fatal): {e}")
    
    llm = LangGraphLLMService(
        base_url=langgraph_base_url,
        assistant=selected_assistant,
        user_email=os.getenv("USER_EMAIL", "test@example.com"),
        stream_mode=os.getenv("LANGGRAPH_STREAM_MODE", "messages"),  # Use 'messages' for token streaming
        debug_stream=os.getenv("LANGGRAPH_DEBUG_STREAM", "false").lower() == "true",
    )
    logger.info(f"   • Stream mode: {os.getenv('LANGGRAPH_STREAM_MODE', 'messages')}")
    logger.info(f"   • User email: {os.getenv('USER_EMAIL', 'test@example.com')}")
    
    # Set runtime config on LLM service if provided
    if agent_config:
        logger.info(f"   Setting agent config on LLM service")
        llm.set_runtime_config(agent_config)
    
    logger.info("")
    
    # NVIDIA Riva STT (Speech-to-Text)
    logger.info("🎤 Creating Riva STT service...")
    
    nvidia_api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("NVIDIA_ASR_API_KEY")
    if not nvidia_api_key:
        raise ValueError("NVIDIA_API_KEY or NVIDIA_ASR_API_KEY required")
    
    asr_function_id = os.getenv("NVIDIA_ASR_FUNCTION_ID", "52b117d2-6c15-4cfa-a905-a67013bee409")
    asr_model_name = os.getenv("RIVA_ASR_MODEL", "parakeet-1.1b-en-US-asr-streaming-silero-vad-asr-bls-ensemble")
    asr_server = os.getenv("RIVA_ASR_URL", "grpc.nvcf.nvidia.com:443")
    
    logger.info(f"   🔑 NGC API Key: {nvidia_api_key[:10]}...{nvidia_api_key[-8:]}")
    logger.info(f"   🆔 Function ID: {asr_function_id}")
    logger.info(f"   🖥️  Server: {asr_server}")
    logger.info(f"   📦 Model: {asr_model_name}")
    
    # Language configuration
    env_language = os.getenv("RIVA_ASR_LANGUAGE", "en-US")
    language_code = language_override or env_language
    
    logger.info("")
    logger.info("🌐 LANGUAGE CONFIGURATION:")
    logger.info(f"   • Environment: {env_language}")
    logger.info(f"   • Override: {language_override or 'None'}")
    logger.info(f"   ➡️  SELECTED: '{language_code}'")
    logger.info("")
    
    stt_language = get_language_from_string(language_code)
    enable_language_detection = stt_language == "multi"
    stt_params_language = Language.EN_US if enable_language_detection else stt_language
    
    # Custom ASR configuration
    custom_config = os.getenv("RIVA_ASR_CUSTOM_CONFIG", 
                              "enable_vad_endpointing:true,neural_vad.onset:0.65,apply_partial_itn:true")
    
    if enable_language_detection:
        if custom_config:
            custom_config += ",enable_automatic_language_detection:true"
        else:
            custom_config = "enable_automatic_language_detection:true"
        logger.info("   🌐 Multi-language auto-detection enabled")
    else:
        logger.info(f"   🎯 Single language mode: {language_code}")
    
    logger.info(f"   ⚙️  ASR config: {custom_config}")
    logger.info("")
    
    stt = RivaSTTService(
        api_key=nvidia_api_key,
        server=asr_server,
        sample_rate=sample_rate,
        model_function_map={
            "function_id": asr_function_id,
            "model_name": asr_model_name
        },
        params=RivaSTTService.InputParams(
            language=stt_params_language
        ),
        custom_configuration=custom_config,
        interim_results=True,
        automatic_punctuation=os.getenv("RIVA_ASR_AUTO_PUNCTUATION", "true").lower() == "true",
        profanity_filter=os.getenv("RIVA_ASR_PROFANITY_FILTER", "false").lower() == "true",
    )
    
    logger.info(f"   ✅ Riva STT Service created")
    logger.info(f"   🎵 Sample rate: {sample_rate}Hz")
    logger.info("")
    
    # Create context (LangGraph manages history via threads)
    context = OpenAILLMContext([])
    
    # Store context, config, and LLM service for session access
    pc_id = webrtc_connection.pc_id
    contexts_map[pc_id] = context
    llm_services_map[pc_id] = llm
    if agent_config:
        configs_map[pc_id] = agent_config
        logger.info(f"   Stored config for session {pc_id}")
    
    # Create context aggregator
    context_aggregator = llm.create_context_aggregator(context)
    
    # Build pipeline
    logger.info("🔗 Building pipeline...")
    logger.info("   Pipeline: WebRTC → RTVI → STT → LLM Agent → Text Output")
    logger.info("   Features: Voice input, Agent intelligence, Text-only output")
    logger.info("   NO TTS: Text responses sent via RTVI (no speech synthesis)")
    
    # Create RTVI processor for handling RTVI protocol messages
    rtvi_processor = RTVIProcessor()
    
    pipeline_processors = [
        transport.input(),              # WebRTC audio input
        rtvi_processor,                # RTVI protocol handler (sends transcriptions + text to client)
        stt,                           # Speech-to-Text (Riva)
        context_aggregator.user(),     # Aggregate user messages
        llm,                           # LLM Agent (LangGraph)
        # NO TTS - text responses go directly to output
        transport.output(),            # WebRTC output (for protocol, no audio)
        context_aggregator.assistant() # Aggregate assistant responses
    ]
    
    pipeline = Pipeline(pipeline_processors)
    logger.info("✅ Pipeline built with RTVI support (text-only mode)")
    
    # Create pipeline task with interruption support
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,  # Support interrupting agent text generation
            enable_metrics=True,
            enable_usage_metrics=True,
            send_initial_empty_metrics=False,
        ),
        observers=[RTVIObserver(rtvi_processor)],
    )
    
    # Set up RTVI event handlers
    @rtvi_processor.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        logger.info("🎯 RTVI client ready")
        await rtvi.set_bot_ready()
    
    logger.info(f"✅ ASR + Agent pipeline ready (pc_id: {pc_id})")
    logger.info("=" * 80)
    
    # Run the pipeline
    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)


@app.post("/api/offer")
async def api_offer(
    request: dict, 
    background_tasks: BackgroundTasks,
    language: Optional[str] = None,
    assistant: Optional[str] = None,
    langgraph_url: Optional[str] = None,
    config_b64: Optional[str] = None
):
    """Handle WebRTC offer for ASR + Agent pipeline.
    
    Args:
        request: Dict with pc_id, sdp, type, and optional 'config' for agent-specific parameters
        background_tasks: FastAPI background tasks
        language: Optional language code from query parameter
        assistant: Optional assistant name from query parameter
        langgraph_url: Optional LangGraph URL from query parameter
        
    Returns:
        WebRTC answer with pc_id
        
    Example request body with config:
        {
            "pc_id": "...",
            "sdp": "...",
            "type": "offer",
            "assistant": "motivator",
            "config": {
                "configurable": {
                    "book_id": "6c3dba595fff66efae64fecbfd1c9ce8",
                    "agent_voice": "author",
                    "motivation_style": "balanced"
                },
                "metadata": {
                    "user_id": "user@example.com"
                }
            }
        }
    """
    logger.info("=" * 80)
    logger.info(f"📞 API /api/offer REQUEST:")
    logger.info(f"   • Body keys: {list(request.keys())}")
    logger.info(f"   • Query - language: {language}")
    logger.info(f"   • Query - assistant: {assistant}")
    logger.info(f"   • Query - langgraph_url: {langgraph_url}")
    logger.info("=" * 80)
    
    pc_id = request.get("pc_id")
    
    # Get parameters from query or request body
    language_from_client = language or request.get("language")
    assistant_from_client = assistant or request.get("assistant")
    langgraph_url_from_client = langgraph_url or request.get("langgraph_url")
    
    # Get config from body or decode from base64 query param
    agent_config_from_client = request.get("config")
    
    # If config not in body, check for base64-encoded query param
    if not agent_config_from_client and config_b64:
        try:
            decoded = base64.b64decode(config_b64).decode('utf-8')
            agent_config_from_client = json.loads(decoded)
            logger.info(f"   📦 Decoded config from base64 query param")
        except Exception as e:
            logger.warning(f"   ⚠️  Failed to decode config_b64: {e}")
    
    logger.info(f"   • pc_id: {pc_id}")
    logger.info(f"   • assistant: {assistant_from_client or 'default'}")
    logger.info(f"   • language: {language_from_client or 'default'}")
    logger.info(f"   • langgraph_url: {langgraph_url_from_client or 'default'}")
    logger.info(f"   • agent_config: {agent_config_from_client or 'None'}")
    
    if pc_id and pc_id in pcs_map:
        # Reuse existing connection
        pipecat_connection = pcs_map[pc_id]
        logger.info(f"Reusing existing connection for pc_id: {pc_id}")
        await pipecat_connection.renegotiate(
            sdp=request["sdp"],
            type=request["type"],
            restart_pc=request.get("restart_pc", False),
        )
    else:
        # Create new WebRTC connection
        ice_servers = build_server_ice_servers()
        pipecat_connection = SmallWebRTCConnection(ice_servers)
        await pipecat_connection.initialize(sdp=request["sdp"], type=request["type"])
        
        # Setup disconnect handler
        @pipecat_connection.event_handler("closed")
        async def handle_disconnected(webrtc_connection: SmallWebRTCConnection):
            logger.info(f"Connection closed for pc_id: {webrtc_connection.pc_id}")
            pcs_map.pop(webrtc_connection.pc_id, None)
            contexts_map.pop(webrtc_connection.pc_id, None)
            configs_map.pop(webrtc_connection.pc_id, None)
            llm_services_map.pop(webrtc_connection.pc_id, None)
        
        # Start pipeline in background
        background_tasks.add_task(
            run_asr_agent,
            pipecat_connection,
            None,
            assistant_from_client,
            language_from_client,
            langgraph_url_from_client,
            agent_config_from_client
        )
    
    # Get answer and store connection
    answer = pipecat_connection.get_answer()
    pcs_map[answer["pc_id"]] = pipecat_connection
    
    return JSONResponse(answer)


@app.patch("/api/offer")
async def api_offer_patch(request: dict):
    """Handle ICE candidate updates via PATCH.
    
    Args:
        request: Dict with pc_id and candidate information
        
    Returns:
        Success response
    """
    pc_id = request.get("pc_id")
    
    if not pc_id or pc_id not in pcs_map:
        logger.warning(f"PATCH request for unknown pc_id: {pc_id}")
        return JSONResponse({"error": "Connection not found"}, status_code=404)
    
    pipecat_connection = pcs_map[pc_id]
    
    # Handle ICE candidate if provided
    if "candidate" in request:
        logger.debug(f"Adding ICE candidate for pc_id: {pc_id}")
        await pipecat_connection.add_ice_candidate(request["candidate"])
    
    # Handle renegotiation if SDP provided
    if "sdp" in request:
        logger.debug(f"Renegotiating connection for pc_id: {pc_id}")
        await pipecat_connection.renegotiate(
            sdp=request["sdp"],
            type=request.get("type", "offer"),
            restart_pc=request.get("restart_pc", False),
        )
        answer = pipecat_connection.get_answer()
        return JSONResponse(answer)
    
    return JSONResponse({"status": "ok"})


@app.get("/assistants")
async def list_assistants(request: Request):
    """List available LangGraph assistants.
    
    Returns:
        List of assistant configurations with display names
    """
    import requests
    
    # Custom display name mappings
    DISPLAY_NAME_OVERRIDES = {
        "simple_agent": "Simple Agent",
        "claims-investigation-agent": "Claims Investigation Agent",
        "wire-transfer-agent": "Banking: Wire Transfer Agent",
        "telco-agent": "Telco Agent",
        "telco_agent": "Telco Agent",
        "rbc-fees-agent": "Banking: Fees Agent",
        "rbc_fees_agent": "Banking: Fees Agent",
        "healthcare-agent": "Healthcare: Telehealth Nurse",
        "healthcare_agent": "Healthcare: Telehealth Nurse",
    }
    
    base_url = os.getenv("LANGGRAPH_BASE_URL", "http://127.0.0.1:2024").rstrip("/")
    
    # Auth handling
    inbound_auth = request.headers.get("authorization")
    token = (
        os.getenv("LANGGRAPH_AUTH_TOKEN")
        or os.getenv("AUTH0_ACCESS_TOKEN")
        or os.getenv("AUTH_BEARER_TOKEN")
    )
    headers = (
        {"Authorization": inbound_auth}
        if inbound_auth
        else {"Authorization": f"Bearer {token}"} if token else None
    )
    
    def normalize_entries(raw_items: list) -> list[dict]:
        """Normalize assistant entries from various API formats."""
        results: list[dict] = []
        for entry in raw_items:
            assistant_id = None
            if isinstance(entry, dict):
                assistant_id = entry.get("assistant_id") or entry.get("id") or entry.get("name")
            elif isinstance(entry, str):
                assistant_id = entry
            
            if assistant_id:
                results.append({
                    "assistant_id": assistant_id,
                    **(entry if isinstance(entry, dict) else {})
                })
        return results
    
    # Try GET /assistants
    items: list[dict] = []
    try:
        resp = requests.get(
            f"{base_url}/assistants",
            params={"limit": 100},
            timeout=8,
            headers=headers
        )
        if resp.ok:
            data = resp.json() or []
            if isinstance(data, dict):
                data = data.get("items") or data.get("results") or data.get("assistants") or []
            items = normalize_entries(data)
            logger.debug(f"Loaded {len(items)} assistants from GET /assistants")
    except Exception as exc:
        logger.warning(f"GET /assistants failed: {exc}")
    
    # Fallback: POST /assistants/search
    if not items:
        try:
            resp = requests.post(
                f"{base_url}/assistants/search",
                json={
                    "metadata": {},
                    "limit": 100,
                    "offset": 0,
                },
                timeout=10,
                headers=headers,
            )
            if resp.ok:
                data = resp.json() or []
                if isinstance(data, dict):
                    data = data.get("items") or data.get("results") or []
                items = normalize_entries(data)
                logger.debug(f"Loaded {len(items)} assistants from POST /assistants/search")
        except Exception as exc:
            logger.warning(f"POST /assistants/search failed: {exc}")
    
    # Enrich with details
    enriched: list[dict] = []
    for item in items:
        detail = dict(item)
        assistant_id = detail.get("assistant_id")
        
        if assistant_id:
            # Try to get more details
            try:
                resp = requests.get(
                    f"{base_url}/assistants/{assistant_id}",
                    timeout=5,
                    headers=headers
                )
                if resp.ok:
                    d = resp.json() or {}
                    detail.update({
                        "graph_id": d.get("graph_id"),
                        "name": d.get("name"),
                        "description": d.get("description"),
                        "metadata": d.get("metadata") or {},
                    })
            except Exception:
                pass
        
        # Determine display name
        metadata = detail.get("metadata") or {}
        graph_id = detail.get("graph_id")
        
        display_name = (
            DISPLAY_NAME_OVERRIDES.get(assistant_id)
            or DISPLAY_NAME_OVERRIDES.get(graph_id)
            or detail.get("name")
            or metadata.get("display_name")
            or metadata.get("friendly_name")
            or graph_id
            or assistant_id
        )
        detail["display_name"] = display_name
        enriched.append(detail)
    
    logger.info(f"Returning {len(enriched)} assistants")
    return enriched


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for ASR + Agent with optional control messages.
    
    Args:
        websocket: WebSocket connection from client
    """
    await websocket.accept()
    
    try:
        # Receive initial connection request
        request = await websocket.receive_json()
        pc_id = request.get("pc_id")
        assistant_from_client = request.get("assistant")
        language_from_client = request.get("language")
        langgraph_url_from_client = request.get("langgraph_url")
        agent_config_from_client = request.get("config")  # Agent-specific config
        
        logger.info("=" * 80)
        logger.info(f"📞 WebSocket /ws connection:")
        logger.info(f"   • pc_id: {pc_id}")
        logger.info(f"   • assistant: {assistant_from_client or 'default'}")
        logger.info(f"   • language: {language_from_client or 'default'}")
        logger.info(f"   • langgraph_url: {langgraph_url_from_client or 'default'}")
        logger.info(f"   • agent_config: {agent_config_from_client or 'None'}")
        logger.info("=" * 80)
        
        if pc_id and pc_id in pcs_map:
            # Reuse existing connection
            pipecat_connection = pcs_map[pc_id]
            logger.info(f"Reusing existing connection for pc_id: {pc_id}")
            await pipecat_connection.renegotiate(sdp=request["sdp"], type=request["type"])
        else:
            # Create new WebRTC connection
            ice_servers = build_server_ice_servers()
            pipecat_connection = SmallWebRTCConnection(ice_servers)
            await pipecat_connection.initialize(sdp=request["sdp"], type=request["type"])
            
            # Setup disconnect handler
            @pipecat_connection.event_handler("closed")
            async def handle_disconnected(webrtc_connection: SmallWebRTCConnection):
                logger.info(f"Connection closed for pc_id: {webrtc_connection.pc_id}")
                pcs_map.pop(webrtc_connection.pc_id, None)
                contexts_map.pop(webrtc_connection.pc_id, None)
                configs_map.pop(webrtc_connection.pc_id, None)
                llm_services_map.pop(webrtc_connection.pc_id, None)
            
            # Start pipeline
            asyncio.create_task(
                run_asr_agent(
                    pipecat_connection,
                    websocket,
                    assistant_from_client,
                    language_from_client,
                    langgraph_url_from_client,
                    agent_config_from_client
                )
            )
        
        # Send answer back to client
        answer = pipecat_connection.get_answer()
        pcs_map[answer["pc_id"]] = pipecat_connection
        await websocket.send_json(answer)
        
        # Keep connection alive and handle messages
        while True:
            try:
                message = await websocket.receive_text()
                
                # Parse JSON messages from UI
                try:
                    data = json.loads(message)
                    msg_type = data.get("type")
                    msg_content = data.get("message", "").strip()
                    
                    if msg_type == "text_input" and msg_content:
                        # Handle text input from UI
                        logger.info(f"Text input from UI: {msg_content}")
                        pc_id = pipecat_connection.pc_id
                        if pc_id in contexts_map:
                            context = contexts_map[pc_id]
                            context.add_message({"role": "user", "content": msg_content})
                
                except json.JSONDecodeError:
                    logger.debug(f"Non-JSON message received: {message}")
                    
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")
                break
    
    except WebSocketDisconnect:
        logger.info("Client disconnected from WebSocket")
    except Exception as e:
        logger.error(f"WebSocket endpoint error: {e}")
        raise


@app.get("/rtc-config")
async def rtc_config():
    """Provide WebRTC ICE configuration to browser clients."""
    try:
        servers = build_client_ice_servers()
        return {"iceServers": servers}
    except Exception as e:
        logger.error(f"rtc-config error: {e}")
        return {"iceServers": [{"urls": "stun:stun.l.google.com:19302"}]}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "mode": "asr_agent_text_only",
        "services": {
            "langgraph": os.getenv("LANGGRAPH_BASE_URL", "http://127.0.0.1:2024"),
            "riva_stt": os.getenv("RIVA_ASR_URL", "grpc.nvcf.nvidia.com:443"),
        }
    }


# Mount Pipecat's standard prebuilt UI at /client
app.mount("/client", SmallWebRTCPrebuiltUI)
logger.info("📺 Pipecat standard UI mounted at /client")

# Mount custom UI at /app (optional)
UI_DIST_DIR = Path(__file__).parent / "ui" / "dist"
if UI_DIST_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(UI_DIST_DIR), html=True), name="custom-ui")
    logger.info(f"📁 Custom UI serving from: {UI_DIST_DIR} at /app")
else:
    logger.warning(f"Custom UI directory not found: {UI_DIST_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ASR + Agent Pipeline (Text-Only Output)")
    parser.add_argument("--host", default="0.0.0.0", help="Host address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=7860, help="Port number (default: 7860)")
    parser.add_argument("--verbose", "-v", action="count", default=0, help="Increase logging verbosity")
    args = parser.parse_args()
    
    # Configure logging
    logger.remove(0)
    if args.verbose >= 2:
        logger.add(sys.stderr, level="TRACE")
    elif args.verbose >= 1:
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.add(sys.stderr, level="INFO")
    
    # Check required environment variables
    nvidia_api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("NVIDIA_ASR_API_KEY")
    if not nvidia_api_key:
        logger.error("❌ Missing NVIDIA_API_KEY or NVIDIA_ASR_API_KEY")
        logger.error("   Set: NVIDIA_API_KEY=nvapi-your-key-here")
        sys.exit(1)
    
    logger.info("=" * 70)
    logger.info("🎤 ASR + Agent Pipeline (Text-Only Output)")
    logger.info("=" * 70)
    logger.info(f"🗣️  Voice Input: ✅ (Riva STT)")
    logger.info(f"🤖 Agent: ✅ (LangGraph)")
    logger.info(f"📝 Text Output: ✅ (No TTS)")
    logger.info(f"🔊 Voice Output: ❌ (Text-only mode)")
    logger.info("")
    logger.info(f"LangGraph: {os.getenv('LANGGRAPH_BASE_URL', 'http://127.0.0.1:2024')}")
    logger.info(f"Assistant: {os.getenv('LANGGRAPH_ASSISTANT', 'simple_agent')}")
    logger.info(f"NVIDIA Key: {nvidia_api_key[:4]}...{nvidia_api_key[-4:]}")
    logger.info(f"Sample Rate: {os.getenv('AUDIO_SAMPLE_RATE', '16000')}Hz")
    logger.info("=" * 70)
    logger.info(f"🌐 Server starting on http://{args.host}:{args.port}")
    logger.info("=" * 70)
    
    uvicorn.run(app, host=args.host, port=args.port)

