#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2024-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: BSD 2-Clause License

"""ASR-Only Pipeline - Speech to Text without TTS.

This pipeline demonstrates a transcription-only service:
- WebRTC for real-time audio input
- NVIDIA Riva STT for speech recognition
- Streams transcribed text back to client via RTVI protocol
- NO LLM or TTS - just pure transcription

Perfect for:
- Live captioning/subtitles
- Meeting transcription
- Voice notes/dictation
- Transcription services

Architecture Notes:
- Uses RTVIProcessor to automatically stream transcriptions to client
- Avoids custom FrameProcessor to prevent StartFrame initialization issues
- Follows the same pattern as pipeline_modern.py for reliability
- Transcriptions appear in browser console and can be captured via RTVI events
"""

import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from pipecat_ai_small_webrtc_prebuilt.frontend import SmallWebRTCPrebuiltUI

from pipecat.frames.frames import (
    Frame,
    TranscriptionFrame,
    InterimTranscriptionFrame,
    EndFrame
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
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

load_dotenv(override=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active connections
pcs_map: dict[str, SmallWebRTCConnection] = {}


# NOTE: Custom FrameProcessor for transcriptions removed due to Pipecat StartFrame issue
# The FrameProcessor base class validates StartFrame receipt before allowing
# any frames to be processed, creating a chicken-and-egg problem.
# 
# Instead, we rely on RTVIProcessor which automatically sends transcriptions
# to the client via the RTVI protocol. This is the same approach used in
# pipeline_modern.py to avoid the StartFrame handling issue.
#
# Transcriptions will appear in the browser console and can be captured
# via the RTVI client's transcription events.


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
    """Build ICE servers for client using env vars."""
    servers: list[dict] = []
    
    # Check for TURN server in env
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
    """Convert client ICE configs to server IceServer objects."""
    out: list[IceServer] = []
    for s in build_client_ice_servers():
        urls = s.get("urls")
        username = s.get("username", "")
        credential = s.get("credential", "")
        
        if isinstance(urls, list):
            for u in urls:
                out.append(IceServer(urls=u, username=username, credential=credential))
        elif isinstance(urls, str) and urls:
            out.append(IceServer(urls=urls, username=username, credential=credential))
    
    return out


async def run_asr_only(
    webrtc_connection: SmallWebRTCConnection, 
    ws: Optional[WebSocket] = None,
    language_override: Optional[str] = None
):
    """Run ASR-only pipeline (no LLM, no TTS).
    
    Args:
        webrtc_connection: WebRTC connection for audio
        ws: Optional WebSocket for transcription streaming
        language_override: Optional language code override
    """
    stream_id = uuid.uuid4()
    
    logger.info("=" * 80)
    logger.info(f"🎤 Starting ASR-Only Pipeline (stream_id: {stream_id})")
    logger.info("=" * 80)
    
    # Get language configuration
    env_language = os.getenv("RIVA_ASR_LANGUAGE", "en-US")
    language_code = language_override or env_language
    
    logger.info(f"🌐 Language: {language_code}")
    
    # Transport configuration
    sample_rate = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
    
    # VAD configuration for voice activity detection
    vad_params = VADParams(
        confidence=0.5,
        start_secs=0.3,
        stop_secs=1.0,
        min_volume=0.5
    )
    
    transport_params = TransportParams(
        audio_in_enabled=True,
        audio_in_sample_rate=sample_rate,
        audio_out_enabled=False,  # No audio output needed (no TTS)
        vad_analyzer=SileroVADAnalyzer(params=vad_params),
    )
    
    transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection,
        params=transport_params,
    )
    
    # NVIDIA Riva STT Service
    logger.info("🎤 Creating Riva STT service...")
    
    nvidia_api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("NVIDIA_ASR_API_KEY")
    if not nvidia_api_key:
        raise ValueError("NVIDIA_API_KEY or NVIDIA_ASR_API_KEY required")
    
    asr_function_id = os.getenv("NVIDIA_ASR_FUNCTION_ID", "52b117d2-6c15-4cfa-a905-a67013bee409")
    asr_model_name = os.getenv("RIVA_ASR_MODEL", "parakeet-1.1b-en-US-asr-streaming-silero-vad-asr-bls-ensemble")
    asr_server = os.getenv("RIVA_ASR_URL", "grpc.nvcf.nvidia.com:443")
    
    logger.info(f"   🔑 API Key: {nvidia_api_key[:10]}...{nvidia_api_key[-8:]}")
    logger.info(f"   🆔 Function ID: {asr_function_id}")
    logger.info(f"   🖥️  Server: {asr_server}")
    logger.info(f"   📦 Model: {asr_model_name}")
    logger.info(f"   🎵 Sample rate: {sample_rate}Hz")
    
    stt_language = get_language_from_string(language_code)
    enable_language_detection = stt_language == "multi"
    
    # For multi-language, use EN_US as placeholder (Riva auto-detects)
    stt_params_language = Language.EN_US if enable_language_detection else stt_language
    
    # Custom configuration
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
    
    # Build pipeline - JUST STT, no custom processors
    # Following pipeline_modern.py pattern to avoid StartFrame issues
    logger.info("🔗 Building ASR-only pipeline...")
    
    # Create RTVI processor - this handles transcription streaming automatically
    rtvi_processor = RTVIProcessor()
    
    pipeline_processors = [
        transport.input(),           # Audio input via WebRTC
        rtvi_processor,             # RTVI protocol (sends transcriptions to client automatically)
        stt,                        # Speech-to-Text (Riva)
        transport.output(),         # Output (required for protocol)
    ]
    
    pipeline = Pipeline(pipeline_processors)
    logger.info("   ✅ Pipeline: WebRTC → RTVI → STT → Output")
    logger.info("   📝 No LLM, No TTS - Pure transcription!")
    logger.info("   📡 Transcriptions sent via RTVI protocol")
    
    # Create task
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=False,  # Not needed without TTS
            enable_metrics=True,
            enable_usage_metrics=True,
            send_initial_empty_metrics=False,
        ),
        observers=[RTVIObserver(rtvi_processor)],
    )
    
    # Set up RTVI handlers
    @rtvi_processor.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        logger.info("🎯 Client ready - starting transcription")
        await rtvi.set_bot_ready()
    
    pc_id = webrtc_connection.pc_id
    logger.info(f"✅ ASR pipeline ready (pc_id: {pc_id})")
    
    # Run the pipeline
    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)
    
    # Pipeline complete
    logger.info("=" * 80)
    logger.info("📊 ASR Pipeline Session Complete")
    logger.info("=" * 80)


@app.post("/api/offer")
async def api_offer(
    request: dict,
    background_tasks: BackgroundTasks,
    language: Optional[str] = None
):
    """Handle WebRTC offer from client.
    
    Args:
        request: WebRTC offer with pc_id, sdp, type
        background_tasks: FastAPI background tasks
        language: Optional language code
        
    Returns:
        WebRTC answer
    """
    logger.info(f"📞 /api/offer - language: {language}")
    
    pc_id = request.get("pc_id")
    language_from_client = language or request.get("language")
    
    if pc_id and pc_id in pcs_map:
        # Reuse existing connection
        pipecat_connection = pcs_map[pc_id]
        logger.info(f"Reusing connection: {pc_id}")
        await pipecat_connection.renegotiate(
            sdp=request["sdp"],
            type=request["type"],
            restart_pc=request.get("restart_pc", False),
        )
    else:
        # Create new connection
        ice_servers = build_server_ice_servers()
        pipecat_connection = SmallWebRTCConnection(ice_servers)
        await pipecat_connection.initialize(sdp=request["sdp"], type=request["type"])
        
        # Disconnect handler
        @pipecat_connection.event_handler("closed")
        async def handle_disconnected(webrtc_connection: SmallWebRTCConnection):
            logger.info(f"Connection closed: {webrtc_connection.pc_id}")
            pcs_map.pop(webrtc_connection.pc_id, None)
        
        # Start ASR pipeline in background
        background_tasks.add_task(run_asr_only, pipecat_connection, None, language_from_client)
    
    # Return answer
    answer = pipecat_connection.get_answer()
    pcs_map[answer["pc_id"]] = pipecat_connection
    
    return JSONResponse(answer)


@app.patch("/api/offer")
async def api_offer_patch(request: dict):
    """Handle ICE candidate updates."""
    pc_id = request.get("pc_id")
    
    if not pc_id or pc_id not in pcs_map:
        return JSONResponse({"error": "Connection not found"}, status_code=404)
    
    pipecat_connection = pcs_map[pc_id]
    
    if "candidate" in request:
        await pipecat_connection.add_ice_candidate(request["candidate"])
    
    if "sdp" in request:
        await pipecat_connection.renegotiate(
            sdp=request["sdp"],
            type=request.get("type", "offer"),
            restart_pc=request.get("restart_pc", False),
        )
        answer = pipecat_connection.get_answer()
        return JSONResponse(answer)
    
    return JSONResponse({"status": "ok"})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for ASR with live transcription updates.
    
    Args:
        websocket: WebSocket connection
    """
    await websocket.accept()
    
    try:
        # Receive connection request
        request = await websocket.receive_json()
        pc_id = request.get("pc_id")
        language_from_client = request.get("language")
        
        logger.info(f"📞 WebSocket connection - language: {language_from_client}")
        
        if pc_id and pc_id in pcs_map:
            # Reuse connection
            pipecat_connection = pcs_map[pc_id]
            await pipecat_connection.renegotiate(sdp=request["sdp"], type=request["type"])
        else:
            # New connection
            ice_servers = build_server_ice_servers()
            pipecat_connection = SmallWebRTCConnection(ice_servers)
            await pipecat_connection.initialize(sdp=request["sdp"], type=request["type"])
            
            # Disconnect handler
            @pipecat_connection.event_handler("closed")
            async def handle_disconnected(webrtc_connection: SmallWebRTCConnection):
                logger.info(f"Connection closed: {webrtc_connection.pc_id}")
                pcs_map.pop(webrtc_connection.pc_id, None)
            
            # Start ASR pipeline with WebSocket
            asyncio.create_task(run_asr_only(pipecat_connection, websocket, language_from_client))
        
        # Send answer
        answer = pipecat_connection.get_answer()
        pcs_map[answer["pc_id"]] = pipecat_connection
        await websocket.send_json(answer)
        
        # Keep connection alive
        while True:
            try:
                message = await websocket.receive_text()
                logger.debug(f"WebSocket message: {message}")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break
    
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        raise


@app.get("/rtc-config")
async def rtc_config():
    """Provide WebRTC ICE configuration."""
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
        "mode": "asr_only",
        "services": {
            "riva_stt": os.getenv("RIVA_ASR_URL", "grpc.nvcf.nvidia.com:443"),
        }
    }


# Mount Pipecat's prebuilt UI
app.mount("/", SmallWebRTCPrebuiltUI)
logger.info("📺 Pipecat UI mounted at /")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ASR-Only Pipeline (No TTS)")
    parser.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=7860, help="Port (default: 7860)")
    parser.add_argument("--verbose", "-v", action="count", default=0, help="Verbosity")
    args = parser.parse_args()
    
    # Configure logging
    logger.remove(0)
    if args.verbose >= 2:
        logger.add(sys.stderr, level="TRACE")
    elif args.verbose >= 1:
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.add(sys.stderr, level="INFO")
    
    # Check API key
    nvidia_api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("NVIDIA_ASR_API_KEY")
    if not nvidia_api_key:
        logger.error("❌ Missing NVIDIA_API_KEY or NVIDIA_ASR_API_KEY")
        sys.exit(1)
    
    logger.info("=" * 70)
    logger.info("🎤 ASR-Only Pipeline (No TTS)")
    logger.info("=" * 70)
    logger.info(f"API Key: {nvidia_api_key[:4]}...{nvidia_api_key[-4:]}")
    logger.info(f"Sample Rate: {os.getenv('AUDIO_SAMPLE_RATE', '16000')}Hz")
    logger.info(f"Language: {os.getenv('RIVA_ASR_LANGUAGE', 'en-US')}")
    logger.info("=" * 70)
    logger.info(f"🌐 Server: http://{args.host}:{args.port}")
    logger.info("=" * 70)
    logger.info("")
    logger.info("📝 This pipeline does:")
    logger.info("   ✅ Speech-to-Text (ASR)")
    logger.info("   ✅ Transcription streaming")
    logger.info("   ❌ NO LLM (no AI responses)")
    logger.info("   ❌ NO TTS (no voice output)")
    logger.info("")
    logger.info("Perfect for: transcription, captioning, dictation")
    logger.info("=" * 70)
    
    uvicorn.run(app, host=args.host, port=args.port)

