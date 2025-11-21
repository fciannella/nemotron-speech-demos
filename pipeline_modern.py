#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2024-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: BSD 2-Clause License

"""Modern Voice Agent Pipeline with LangGraph + NVIDIA Riva.

This pipeline uses:
- Plain pipecat Riva services (STT/TTS) with our tested configurations
- LangGraph for LLM/agent logic
- WebRTC for real-time audio streaming
- FastAPI for the web server
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
from typing import AsyncGenerator
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.processors.frameworks.rtvi import RTVIProcessor, RTVIObserver
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.riva.stt import RivaSTTService
from pipecat.services.riva.tts import RivaTTSService
from pipecat.transcriptions.language import Language
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.smallwebrtc.connection import (
    IceServer,
    SmallWebRTCConnection,
)
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import InterimTranscriptionFrame, TranscriptionFrame
from pipecat.utils.time import time_now_iso8601

from langgraph_llm_service import LangGraphLLMService

# Optional: Text-based language detection for validation
try:
    from langdetect import detect_langs, LangDetectException
    LANGDETECT_AVAILABLE = True
    
    # Quick sanity check that langdetect works
    try:
        test_result = detect_langs("Hello, how are you today?")
        if test_result and test_result[0].lang == 'en':
            logger.debug("langdetect sanity check passed ✅")
        else:
            logger.warning(f"⚠️  langdetect sanity check unexpected result: {test_result}")
    except Exception as e:
        logger.warning(f"⚠️  langdetect sanity check failed: {e}")
        
except ImportError:
    LANGDETECT_AVAILABLE = False
    logger.warning("langdetect not installed - text-based language validation disabled")
    logger.warning("Install with: pip install langdetect")

load_dotenv(override=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store connections and contexts by pc_id
pcs_map: dict[str, SmallWebRTCConnection] = {}
contexts_map: dict[str, OpenAILLMContext] = {}


# NOTE: TranscriptionLogger removed due to Pipecat StartFrame handling issues
# The FrameProcessor base class validates StartFrame receipt before allowing
# any frames to be processed, creating a chicken-and-egg problem.
# Future: Implement using Pipecat's event observer pattern instead.

# class TranscriptionLogger(FrameProcessor):
#     """Log ASR transcriptions for debugging."""
#     
#     def __init__(self, enabled: bool = True):
#         super().__init__()
#         self._enabled = enabled
# 
#     async def process_frame(self, frame: Frame, direction: FrameDirection):
#         """Log transcription frames."""
#         ...


class MultilingualRivaSTTService(RivaSTTService):
    """Extended Riva STT Service with language detection logging.
    
    When using language_code="multi", Riva auto-detects the spoken language
    and returns it in the response. This service logs the detected language
    alongside transcriptions for debugging and monitoring.
    
    Optionally validates Riva's acoustic detection against text-based detection
    using langdetect to catch obvious misdetections.
    """
    
    # Map langdetect codes to full language codes
    LANGDETECT_TO_FULL_CODE = {
        "en": "en-US",
        "es": "es-US",
        "fr": "fr-FR",
        "de": "de-DE",
        "zh-cn": "zh-CN",
        "zh-tw": "zh-CN",  # Map Traditional Chinese to Simplified
        "pt": "pt-BR",
        "it": "it-IT",
        "ja": "ja-JP",
        "ko": "ko-KR",
    }
    
    def __init__(self, *args, log_detected_language: bool = True, validate_with_text: bool = True, **kwargs):
        """Initialize with language detection logging option.
        
        Args:
            log_detected_language: Whether to log detected languages (default: True)
            validate_with_text: Whether to validate acoustic detection with text analysis (default: True)
            *args, **kwargs: Passed to RivaSTTService
        """
        super().__init__(*args, **kwargs)
        self._log_detected_language = log_detected_language
        self._validate_with_text = validate_with_text and LANGDETECT_AVAILABLE
        self._last_detected_language = None
    
    def _validate_language_with_text(self, riva_language: str, transcript: str, riva_confidence: float = None) -> str:
        """Validate Riva's acoustic language detection using text analysis.
        
        Args:
            riva_language: Language detected by Riva (e.g., "de-DE")
            transcript: The transcribed text
            riva_confidence: Riva's confidence score (if available)
            
        Returns:
            Validated/corrected language code
        """
        if not self._validate_with_text or not LANGDETECT_AVAILABLE:
            return riva_language
        
        if not transcript or len(transcript.strip()) < 10:
            # Text too short for reliable detection
            logger.debug(f"   Transcript too short for text validation: {len(transcript.strip())} chars")
            return riva_language
        
        try:
            # Clean and prepare text for detection
            clean_text = transcript.strip()
            
            # Debug: Show exactly what we're analyzing
            logger.debug(f"   Analyzing text (length: {len(clean_text)}): '{clean_text}'")
            logger.debug(f"   Text repr: {repr(clean_text)}")
            
            # Detect language from text
            text_detections = detect_langs(clean_text)
            if not text_detections:
                return riva_language
            
            top_text = text_detections[0]
            text_lang_code = self.LANGDETECT_TO_FULL_CODE.get(top_text.lang, riva_language)
            
            # Debug: Show top 3 text detections
            logger.debug(f"   Text detection results:")
            for i, det in enumerate(text_detections[:3], 1):
                logger.debug(f"     {i}. {det.lang}: {det.prob:.3f}")
            
            # Compare base language codes (ignore region)
            riva_base = riva_language.split('-')[0].lower()
            text_base = top_text.lang.lower()
            
            # Check for mismatch
            if riva_base != text_base:
                logger.warning(f"⚠️  LANGUAGE MISMATCH DETECTED!")
                logger.warning(f"   Riva acoustic: {riva_language} (confidence: {riva_confidence or 'N/A'})")
                logger.warning(f"   Text analysis: {text_lang_code} (confidence: {top_text.prob:.2f})")
                logger.warning(f"   Transcript: {transcript[:80]}...")
                
                # Override logic - be more aggressive in trusting text
                # Text is often more reliable than acoustic for written languages
                should_override = False
                reason = ""
                
                # Calculate gap to second place
                second_place_prob = text_detections[1].prob if len(text_detections) > 1 else 0
                confidence_gap = top_text.prob - second_place_prob
                
                # Debug the decision
                logger.debug(f"   Decision logic:")
                logger.debug(f"     text_prob={top_text.prob:.3f}, riva_conf={riva_confidence}, gap={confidence_gap:.3f}")
                
                if top_text.prob > 0.85:
                    # Text is very confident - always override
                    should_override = True
                    reason = "text very confident (>0.85)"
                    logger.debug(f"     → Condition 1 triggered: {top_text.prob:.3f} > 0.85")
                elif top_text.prob > 0.65 and (riva_confidence is None or riva_confidence > 0.95):
                    # Text is reasonably confident AND Riva is suspiciously overconfident
                    # Riva at 0.99 for wrong language is a red flag
                    should_override = True
                    reason = "text confident AND Riva suspiciously overconfident"
                    logger.debug(f"     → Condition 2 triggered: text>{top_text.prob:.3f}>0.65 AND riva={riva_confidence}>0.95")
                elif top_text.prob > 0.60 and confidence_gap > 0.30:
                    # Text has clear winner (big gap to 2nd place)
                    should_override = True
                    reason = f"text has clear winner (gap: {confidence_gap:.2f})"
                    logger.debug(f"     → Condition 3 triggered: {top_text.prob:.3f}>0.60 AND gap={confidence_gap:.3f}>0.30")
                else:
                    logger.debug(f"     → No condition met")
                
                if should_override:
                    logger.warning(f"   🔄 OVERRIDING to {text_lang_code} ({reason})")
                    return text_lang_code
                else:
                    logger.warning(f"   → Keeping {riva_language} (insufficient confidence to override)")
            
            return riva_language
            
        except LangDetectException as e:
            logger.debug(f"Text language detection failed: {e}")
            return riva_language
    
    async def _handle_response(self, response):
        """Override to extract and log detected language from Riva responses.
        
        This method extracts the language_code field from Riva's
        SpeechRecognitionAlternative when using multi-language mode,
        then calls the parent handler.
        """
        # Extract detected language if available
        detected_language = None
        try:
            for result in response.results:
                if result and result.alternatives:
                    alternative = result.alternatives[0]
                    
                    # CRITICAL: Get transcript FIRST before validation
                    transcript = alternative.transcript
                    
                    # Get the detected language code(s)
                    # language_code is a repeated field (list) in the protobuf
                    if hasattr(alternative, 'language_code') and alternative.language_code:
                        # Handle protobuf repeated field (acts like a list)
                        try:
                            # Try to access as a list/sequence
                            if len(alternative.language_code) > 0:
                                detected_language = str(alternative.language_code[0])
                            else:
                                detected_language = None
                                logger.debug("⚠️  Riva returned empty language_code list")
                        except (TypeError, IndexError):
                            # If not subscriptable, try direct string conversion
                            lang_str = str(alternative.language_code)
                            # Clean up if it's a string representation of a list: "['en-US']" -> "en-US"
                            if lang_str.startswith("['") and lang_str.endswith("']"):
                                detected_language = lang_str[2:-2]
                            elif lang_str.startswith("[") and lang_str.endswith("]"):
                                detected_language = lang_str[1:-1].strip("'\"")
                            else:
                                detected_language = lang_str
                        
                        # Get confidence score if available
                        confidence = getattr(alternative, 'confidence', None)
                    
                    # ALWAYS validate with text-based detection if we have transcript
                    # This is important because:
                    # 1. Riva might not return language_code
                    # 2. Riva might return wrong language
                    # 3. Text detection can fill gaps
                    if transcript and self._validate_with_text and LANGDETECT_AVAILABLE:
                        try:
                            # If Riva detected a language, validate it
                            if detected_language:
                                validated_language = self._validate_language_with_text(
                                    detected_language, 
                                    transcript, 
                                    confidence
                                )
                                if validated_language != detected_language:
                                    logger.info(f"✅ Language corrected: {detected_language} → {validated_language}")
                                    detected_language = validated_language
                            else:
                                # Riva didn't detect - use text detection as primary
                                logger.debug("   Riva returned no language, using text detection")
                                text_detections = detect_langs(transcript.strip())
                                if text_detections and text_detections[0].prob > 0.70:
                                    text_lang = text_detections[0].lang
                                    text_conf = text_detections[0].prob
                                    detected_language = self.LANGDETECT_TO_FULL_CODE.get(text_lang, "en-US")
                                    logger.info(f"🌐 Language from text: {detected_language} (confidence: {text_conf:.2f})")
                        except Exception as e:
                            logger.debug(f"Text validation error: {e}")
                    
                    # Store detected/validated language for this session
                    if detected_language:
                        self._detected_language = detected_language
                        
                        # Log language changes (with confidence if available)
                        if self._log_detected_language and detected_language != self._last_detected_language:
                            conf_str = f" (confidence: {confidence:.2f})" if confidence else ""
                            logger.info(f"🌐 Language detected: {detected_language}{conf_str}")
                            # Also log the actual text to help identify misdetections
                            if transcript:
                                logger.debug(f"   Transcript: {transcript[:50]}...")
                            self._last_detected_language = detected_language
                    else:
                        # No language_code in response - log this
                        logger.debug("⚠️  Riva response missing language_code field (not returned for this utterance)")
                    
                    # Log transcription with detected language
                    # (transcript already extracted at top of loop)
                    if transcript and len(transcript) > 0 and self._log_detected_language:
                        # Use detected language, or fall back to last detected, or show None
                        current_lang = detected_language or getattr(self, '_detected_language', None)
                        lang_tag = f" [🌐 {current_lang}]" if current_lang else " [🌐 None]"
                        
                        if result.is_final:
                            if not detected_language and hasattr(self, '_detected_language'):
                                logger.debug(f"   (Using last detected language: {self._detected_language})")
                            logger.info(f"🎤 USER (final){lang_tag}: {transcript}")
                        elif result.stability == 1.0:
                            logger.debug(f"🎤 USER (interim){lang_tag}: {transcript}")
        except Exception as e:
            logger.debug(f"Error extracting language from Riva response: {e}")
        
        # Call parent handler to process the response normally
        await super()._handle_response(response)
    
    def get_detected_language(self) -> str:
        """Get the most recently detected language code.
        
        Uses the last successfully detected language if current response
        doesn't include language_code (common for short utterances or
        interim results).
        
        Returns:
            Language code (e.g., "en-US", "es-ES") or None if no language detected yet
        """
        detected = getattr(self, '_detected_language', None)
        if not detected:
            logger.debug("⚠️  No language detected yet - using default")
        return detected


class LanguageAdaptiveTTSService(RivaTTSService):
    """TTS Service that dynamically switches voices based on detected language.
    
    Works with MultilingualRivaSTTService to automatically use the appropriate
    voice for each detected language, enabling seamless multilingual conversations.
    """
    
    # Voice and language mapping for Magpie TTS Multilingual
    # Riva API requires BOTH voice_id AND language_code to match
    # Format: language_code -> (voice_id, riva_language_code)
    # Magpie supports only 5 languages: en-US, es-US, fr-FR, de-DE, zh-CN
    LANGUAGE_CONFIG_MAP = {
        # English (en-US)
        "en-US": {
            "voice_id": "Magpie-Multilingual.EN-US.Mia.Neutral",
            "language_code": "en-US"
        },
        "en-GB": {
            "voice_id": "Magpie-Multilingual.EN-US.Mia.Neutral",
            "language_code": "en-US"  # Fallback to en-US
        },
        
        # Spanish (es-US)
        "es-US": {
            "voice_id": "Magpie-Multilingual.ES-US.Isabela",
            "language_code": "es-US"
        },
        "es-ES": {
            "voice_id": "Magpie-Multilingual.ES-US.Isabela",
            "language_code": "es-US"  # Fallback to es-US
        },
        
        # French (fr-FR)
        "fr-FR": {
            "voice_id": "Magpie-Multilingual.FR-FR.Pascal",
            "language_code": "fr-FR"
        },
        
        # German (de-DE)
        "de-DE": {
            "voice_id": "Magpie-Multilingual.DE-DE.Aria",
            "language_code": "de-DE"
        },
        
        # Mandarin Chinese (zh-CN)
        "zh-CN": {
            "voice_id": "Magpie-Multilingual.ZH-CN.Mia",
            "language_code": "zh-CN"
        },
    }
    
    def __init__(self, *args, stt_service=None, default_language="en-US", **kwargs):
        """Initialize with reference to STT service for language detection.
        
        Args:
            stt_service: MultilingualRivaSTTService instance to get detected language from
            default_language: Fallback language if no detection available
            *args, **kwargs: Passed to RivaTTSService
        """
        super().__init__(*args, **kwargs)
        self._stt_service = stt_service
        self._default_language = default_language
        self._current_language = default_language
    
    def _get_config_for_language(self, language_code: str) -> dict:
        """Get voice and language configuration for a language code.
        
        Args:
            language_code: Language code (e.g., "es-ES", "fr-FR")
            
        Returns:
            Dict with voice_id and language_code, or None if not supported
        """
        return self.LANGUAGE_CONFIG_MAP.get(language_code)
    
    async def run_tts(self, text: str) -> AsyncGenerator[Frame, None]:
        """Synthesize speech with language-appropriate voice.
        
        Detects language from STT service and switches voice/language accordingly.
        """
        # Get detected language from STT service if available
        detected_lang = None
        if self._stt_service and hasattr(self._stt_service, 'get_detected_language'):
            detected_lang = self._stt_service.get_detected_language()
        
        # Debug logging
        logger.debug(f"TTS: Detected language from STT: {repr(detected_lang)}")
        
        # Use detected language or fallback to default
        target_language = detected_lang or self._default_language
        logger.debug(f"TTS: Target language: {repr(target_language)}")
        
        # Check if target language is supported by Magpie
        lang_config = self._get_config_for_language(target_language)
        if not lang_config:
            logger.warning(f"⚠️  Language {target_language} not supported by Magpie TTS. Falling back to {self._default_language}")
            logger.warning(f"   Magpie supports: en-US, es-US, fr-FR, de-DE, zh-CN")
            target_language = self._default_language
            lang_config = self._get_config_for_language(target_language)
        
        # Log language switch if changed
        if target_language != self._current_language:
            logger.info(f"🔊 TTS switching to language: {target_language}")
            self._current_language = target_language
            
            # Update BOTH voice ID and language code for Magpie Multilingual
            # Riva API requires both to match the supported language groups:
            # "en-US,es-US,fr-FR,de-DE,zh-CN"
            new_voice_id = lang_config["voice_id"]
            new_language_code = lang_config["language_code"]
            
            if new_voice_id != self._voice_id:
                logger.info(f"   Switching voice to: {new_voice_id}")
                self._voice_id = new_voice_id
            
            if new_language_code != self._language_code:
                logger.info(f"   Switching language code to: {new_language_code}")
                self._language_code = new_language_code
            
            logger.debug(f"   Final config - Voice: {self._voice_id}, Language: {self._language_code}")
        
        # Use parent's run_tts with updated language and voice
        async for frame in super().run_tts(text):
            yield frame


class WebsocketTranscriptOutput(FrameProcessor):
    """Send transcriptions to WebSocket for UI display."""

    def __init__(self, websocket: WebSocket):
        super().__init__()
        self._websocket = websocket

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process frames and send transcriptions to WebSocket."""
        
        if isinstance(frame, TranscriptionFrame):
            # User final transcription
            try:
                await self._websocket.send_json({
                    "type": "transcription",
                    "role": "user",
                    "text": frame.text,
                    "final": True
                })
            except Exception as e:
                logger.debug(f"WebSocket send error: {e}")
        
        elif isinstance(frame, InterimTranscriptionFrame):
            # User interim transcription
            try:
                await self._websocket.send_json({
                    "type": "transcription",
                    "role": "user",
                    "text": frame.text,
                    "final": False,
                    "stability": frame.stability if hasattr(frame, 'stability') else None
                })
            except Exception as e:
                logger.debug(f"WebSocket send error: {e}")
        
        elif isinstance(frame, TextFrame):
            # Bot response text (from LLM)
            try:
                await self._websocket.send_json({
                    "type": "transcription",
                    "role": "assistant",
                    "text": frame.text,
                    "final": True
                })
            except Exception as e:
                logger.debug(f"WebSocket send error: {e}")
        
        # Always pass frame downstream
        await self.push_frame(frame, direction)


def get_language_from_string(lang_str: str):
    """Convert language string to Language enum or return raw string for special cases.
    
    Args:
        lang_str: Language code like "en-US", "es-ES", or "multi"
        
    Returns:
        Language enum value, or raw string for "multi" (auto-detection)
    """
    # Special case: "multi" for auto-detection (not in Language enum)
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


async def run_bot(webrtc_connection: SmallWebRTCConnection, ws: Optional[WebSocket] = None, assistant_override: Optional[str] = None, language_override: Optional[str] = None):
    """Run the voice agent pipeline.
    
    Args:
        webrtc_connection: WebRTC connection for audio streaming
        ws: Optional WebSocket for control/transcription messages
        assistant_override: Optional assistant name override from client
        language_override: Optional language code override from client (e.g. 'en-US', 'es-ES', 'multi')
    """
    stream_id = uuid.uuid4()
    
    logger.info("=" * 80)
    logger.info(f"🚀 Starting voice agent bot (stream_id: {stream_id})")
    logger.info("=" * 80)
    
    # Log language selection source
    if language_override:
        logger.info(f"📱 Language from UI: '{language_override}'")
    else:
        logger.info(f"⚙️  No language from UI, using environment variable")
    
    # Transport configuration
    sample_rate = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
    
    # Configure VAD (Voice Activity Detection) parameters
    vad_params = VADParams(
        confidence=0.5,    # Lower = more sensitive (default: 0.7)
        start_secs=0.3,    # Wait 300ms before confirming speech started (default: 0.2)
        stop_secs=1.5,     # Wait 1.5s of silence before stopping (default: 0.8) ← KEY CHANGE!
        min_volume=0.5     # Lower = picks up quieter speech (default: 0.6)
    )
    
    transport_params = TransportParams(
        audio_in_enabled=True,
        audio_in_sample_rate=sample_rate,
        audio_out_sample_rate=sample_rate,
        audio_out_enabled=True,
        vad_analyzer=SileroVADAnalyzer(params=vad_params),
        audio_out_10ms_chunks=5,
    )
    
    transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection,
        params=transport_params,
    )
    
    # LLM Configuration - choose between OpenAI or LangGraph
    use_simple_llm = os.getenv("USE_SIMPLE_LLM", "false").lower() == "true"
    
    if use_simple_llm:
        # Simple OpenAI LLM for testing
        logger.info("🤖 Using OpenAI LLM (simple mode)")
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY required when USE_SIMPLE_LLM=true")
        
        llm = OpenAILLMService(
            api_key=openai_api_key,
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        )
        logger.info(f"   Model: {os.getenv('OPENAI_MODEL', 'gpt-4o-mini')}")
    else:
        # LangGraph LLM Service
        selected_assistant = assistant_override or os.getenv("LANGGRAPH_ASSISTANT", "simple_agent")
        langgraph_base_url = os.getenv("LANGGRAPH_BASE_URL", "http://127.0.0.1:2024")
        
        logger.info(f"📚 Using LangGraph assistant: {selected_assistant}")
        logger.info(f"   URL: {langgraph_base_url}")
        
        llm = LangGraphLLMService(
            base_url=langgraph_base_url,
            assistant=selected_assistant,
            user_email=os.getenv("USER_EMAIL", "test@example.com"),
            stream_mode=os.getenv("LANGGRAPH_STREAM_MODE", "messages"),
            debug_stream=os.getenv("LANGGRAPH_DEBUG_STREAM", "false").lower() == "true",
        )
        logger.info(f"   Stream mode: {os.getenv('LANGGRAPH_STREAM_MODE', 'messages')}")


    
    # NVIDIA Riva STT (Speech-to-Text)
    logger.info("🎤 Creating Riva STT service...")
    
    # Support separate ASR key or fall back to general NVIDIA key
    nvidia_asr_api_key = (
        os.getenv("NVIDIA_ASR_API_KEY") 
        or os.getenv("NVIDIA_API_KEY")
    )
    if not nvidia_asr_api_key:
        raise ValueError("NVIDIA_ASR_API_KEY or NVIDIA_API_KEY environment variable required")
    
    # Log ASR configuration for debugging
    asr_function_id = os.getenv("NVIDIA_ASR_FUNCTION_ID", "52b117d2-6c15-4cfa-a905-a67013bee409")
    asr_model_name = os.getenv("RIVA_ASR_MODEL", "parakeet-1.1b-en-US-asr-streaming-silero-vad-asr-bls-ensemble")
    asr_server = os.getenv("RIVA_ASR_URL", "grpc.nvcf.nvidia.com:443")
    
    logger.info(f"   🔑 NGC API Key: {nvidia_asr_api_key[:10]}...{nvidia_asr_api_key[-8:]}")
    logger.info(f"   🆔 Function ID: {asr_function_id}")
    logger.info(f"   🖥️  Server: {asr_server}")
    logger.info(f"   📦 Model: {asr_model_name}")
    
    # Use language override from client if provided, otherwise fall back to env variable
    env_language = os.getenv("RIVA_ASR_LANGUAGE", "en-US")
    language_code = language_override or env_language
    
    logger.info("")
    logger.info("🌐 LANGUAGE CONFIGURATION:")
    logger.info(f"   • Environment variable (RIVA_ASR_LANGUAGE): {env_language}")
    logger.info(f"   • UI override: {language_override or 'None'}")
    logger.info(f"   ➡️  SELECTED LANGUAGE: '{language_code}'")
    logger.info("")
    
    stt_language = get_language_from_string(language_code)
    enable_language_detection = stt_language == "multi"
    
    # For "multi" language, use Language.EN_US as placeholder (Riva will auto-detect)
    # The actual language code "multi" will be set via custom_configuration
    stt_params_language = Language.EN_US if enable_language_detection else stt_language
    
    # Build custom configuration for multi-language detection
    custom_config = os.getenv("RIVA_ASR_CUSTOM_CONFIG", 
                              "enable_vad_endpointing:true,neural_vad.onset:0.65,apply_partial_itn:true")
    if enable_language_detection:
        # Add language detection configuration
        if custom_config:
            custom_config += ",enable_automatic_language_detection:true"
        else:
            custom_config = "enable_automatic_language_detection:true"
        logger.info("   🌐 MODE: Multi-language auto-detection enabled")
        logger.info(f"   ⚙️  Custom config: {custom_config}")
    else:
        logger.info(f"   🎯 MODE: Single language (language-specific)")
        logger.info(f"   ⚙️  Custom config: {custom_config}")
    
    # Text-based validation option (requires langdetect)
    validate_with_text = os.getenv("VALIDATE_LANGUAGE_WITH_TEXT", "true").lower() == "true"
    if validate_with_text and not LANGDETECT_AVAILABLE:
        logger.warning("⚠️  VALIDATE_LANGUAGE_WITH_TEXT=true but langdetect not installed")
        logger.warning("   Install with: pip install langdetect")
        validate_with_text = False
    elif validate_with_text:
        logger.info("   ✅ Text-based language validation enabled")
    
    stt = MultilingualRivaSTTService(
        api_key=nvidia_asr_api_key,
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
        log_detected_language=enable_language_detection or os.getenv("LOG_DETECTED_LANGUAGE", "true").lower() == "true",
        validate_with_text=validate_with_text,
    )
    logger.info(f"   ✅ Riva STT Service created")
    if enable_language_detection:
        logger.info(f"   📝 Language: MULTI (auto-detect any language)")
    else:
        logger.info(f"   📝 Language: {stt._language_code} (language-specific mode)")
    logger.info(f"   🎵 Sample rate: {stt._sample_rate}Hz")
    logger.info(f"   🔧 Interim results: {stt._interim_results}")
    logger.info(f"   🔧 Auto punctuation: {os.getenv('RIVA_ASR_AUTO_PUNCTUATION', 'true')}")
    logger.info("")
    
    # NVIDIA Riva TTS (Text-to-Speech)
    logger.info("🔊 Creating Riva TTS service...")
    
    # Support separate TTS key or fall back to general NVIDIA key
    nvidia_tts_api_key = (
        os.getenv("NVIDIA_TTS_API_KEY")
        or os.getenv("NVIDIA_API_KEY")
    )
    if not nvidia_tts_api_key:
        raise ValueError("NVIDIA_TTS_API_KEY or NVIDIA_API_KEY environment variable required")
    
    # Log TTS configuration for debugging
    tts_function_id = os.getenv("NVIDIA_TTS_FUNCTION_ID", "c811837c-3343-42d9-83ef-a0a9e8f2be8c")
    tts_model_name = os.getenv("RIVA_TTS_MODEL", "magpie-tts-multilingual")
    tts_server = os.getenv("RIVA_TTS_URL", "grpc.nvcf.nvidia.com:443")
    
    # Select default voice based on the selected language (if in language-specific mode)
    # Otherwise use env variable or default to English
    default_voice_map = {
        "en-US": "Magpie-Multilingual.EN-US.Mia.Neutral",
        "es-US": "Magpie-Multilingual.ES-US.Isabela",
        "de-DE": "Magpie-Multilingual.DE-DE.Erik",
        "fr-FR": "Magpie-Multilingual.FR-FR.Pascal",
        "zh-CN": "Magpie-Multilingual.ZH-CN.Qingqing",
    }
    
    # Use language from UI selection if not in multi mode
    selected_lang_for_voice = language_code if not enable_language_detection else "en-US"
    default_voice_for_lang = default_voice_map.get(selected_lang_for_voice, "Magpie-Multilingual.EN-US.Mia.Neutral")
    tts_voice_id = os.getenv("RIVA_TTS_VOICE_ID", default_voice_for_lang)
    
    logger.info(f"   🔑 NGC API Key: {nvidia_tts_api_key[:10]}...{nvidia_tts_api_key[-8:]}")
    logger.info(f"   🆔 Function ID: {tts_function_id}")
    logger.info(f"   🖥️  Server: {tts_server}")
    logger.info(f"   📦 Model: {tts_model_name}")
    logger.info(f"   🎙️  Voice: {tts_voice_id}")
    if not enable_language_detection:
        logger.info(f"   🎤 Voice auto-selected for language: {selected_lang_for_voice}")
    
    # TTS doesn't support "multi" - always needs a valid language enum
    # When using language-adaptive TTS, this is just the initial/default language
    # Use the same language as STT (from UI or env variable)
    if enable_language_detection:
        # Multi-language mode: start with default, will adapt
        tts_language_str = "en-US"
        logger.info("   💡 Note: Multi-language mode - TTS starting with en-US, will adapt dynamically")
    else:
        # Language-specific mode: use the selected language
        tts_language_str = language_code  # Use the same language as STT
        logger.info(f"   🎯 Language-specific mode: TTS using {tts_language_str}")
    
    tts_language = get_language_from_string(tts_language_str)
    
    # Load IPA dictionary if configured
    ipa_dict = {}
    ipa_file_path = os.getenv("IPA_DICT_FILE")
    if ipa_file_path:
        ipa_file = Path(ipa_file_path)
        if ipa_file.exists():
            try:
                with open(ipa_file, encoding="utf-8") as f:
                    ipa_dict = json.load(f)
                logger.info(f"   Loaded IPA dictionary: {len(ipa_dict)} entries")
            except Exception as e:
                logger.warning(f"Failed to load IPA dictionary: {e}")
    
    # Zero-shot audio prompt (optional)
    zero_shot_prompt = None
    zero_shot_path = os.getenv("ZERO_SHOT_AUDIO_PROMPT")
    if zero_shot_path and Path(zero_shot_path).exists():
        zero_shot_prompt = Path(zero_shot_path)
        logger.info(f"   Using zero-shot audio prompt: {zero_shot_prompt}")
    
    # Use language-adaptive TTS when multi-language detection is enabled
    if enable_language_detection:
        logger.info("   🌐 Language-adaptive TTS enabled (will switch based on detected language)")
        tts = LanguageAdaptiveTTSService(
            api_key=nvidia_tts_api_key,
            server=tts_server,
            voice_id=tts_voice_id,
            sample_rate=sample_rate,
            model_function_map={
                "function_id": tts_function_id,
                "model_name": tts_model_name
            },
            params=RivaTTSService.InputParams(
                language=tts_language,  # Valid Language enum (never "multi")
                quality=int(os.getenv("RIVA_TTS_QUALITY", "20"))
            ),
            custom_dictionary=ipa_dict if ipa_dict else None,
            zero_shot_audio_prompt_file=zero_shot_prompt,
            stt_service=stt,  # Pass STT reference for language detection
            default_language=tts_language_str,  # Use the validated string, not "multi"
        )
    else:
        # Standard TTS without language adaptation
        tts = RivaTTSService(
            api_key=nvidia_tts_api_key,
            server=tts_server,
            voice_id=tts_voice_id,
            sample_rate=sample_rate,
            model_function_map={
                "function_id": tts_function_id,
                "model_name": tts_model_name
            },
            params=RivaTTSService.InputParams(
                language=tts_language,
                quality=int(os.getenv("RIVA_TTS_QUALITY", "20"))
            ),
            custom_dictionary=ipa_dict if ipa_dict else None,
            zero_shot_audio_prompt_file=zero_shot_prompt,
        )
    
    logger.info(f"   ✅ Service created")
    logger.info(f"   📝 Language: {tts._language_code}")
    logger.info(f"   🎵 Sample rate: {tts._sample_rate}Hz")
    
    # Create context with initial system prompt
    if use_simple_llm:
        # Add system prompt for OpenAI
        system_prompt = os.getenv(
            "SYSTEM_PROMPT",
            "You are a helpful AI voice assistant. Keep your responses concise and natural "
            "for voice conversation. Be friendly and engaging."
        )
        context = OpenAILLMContext([
            {"role": "system", "content": system_prompt}
        ])
        logger.info("   Added system prompt for OpenAI")
    else:
        # LangGraph manages history via threads, so empty context
        context = OpenAILLMContext([])
    
    # Store context for WebSocket access
    pc_id = webrtc_connection.pc_id
    contexts_map[pc_id] = context
    
    # Create context aggregator (standard pipecat)
    context_aggregator = llm.create_context_aggregator(context)
    
    # Create transcription logger for debugging (optional)
    # Note: Disabled for now due to Pipecat StartFrame handling
    # Will add back with proper event observer pattern in future
    enable_transcription_logging = os.getenv("TRANSCRIPTION_LOGGING", "false").lower() == "true"
    if enable_transcription_logging:
        logger.warning("⚠️  Transcription logging is currently disabled (Pipecat compatibility issue)")
    
    # Build pipeline
    logger.info("🔗 Building pipeline...")
    
    # Create RTVI processor for handling RTVI protocol messages (transcriptions, etc.)
    rtvi_processor = RTVIProcessor()
    
    pipeline_processors = [
        transport.input(),              # WebRTC audio input
        rtvi_processor,                # RTVI protocol handler (sends transcriptions to client)
        stt,                           # Speech-to-Text (Riva)
        # transcription_logger removed - causes StartFrame issues
        context_aggregator.user(),     # Aggregate user messages
        llm,                           # LLM (LangGraph)
        tts,                           # Text-to-Speech (Riva)
    ]
    
    # Add transcript output if WebSocket is provided (optional, for debugging)
    if ws:
        transcript_output = WebsocketTranscriptOutput(ws)
        pipeline_processors.append(transcript_output)
    
    pipeline_processors.extend([
        transport.output(),            # WebRTC audio output
        context_aggregator.assistant() # Aggregate assistant responses
    ])
    
    pipeline = Pipeline(pipeline_processors)
    logger.info("✅ Pipeline built with RTVI support")
    
    # Create pipeline task with RTVI observer for sending transcriptions
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
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
    
    logger.info(f"✅ Voice agent ready with RTVI observers (pc_id: {pc_id})")
    
    # Run the pipeline
    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)


@app.post("/api/offer")
async def api_offer(
    request: dict, 
    background_tasks: BackgroundTasks,
    language: Optional[str] = None,  # Accept as query parameter
    assistant: Optional[str] = None  # Accept as query parameter
):
    """Handle WebRTC offer from standard Pipecat UI.
    
    This endpoint is used by the SmallWebRTCPrebuiltUI at /client/
    
    Args:
        request: Dict with pc_id, sdp, type
        background_tasks: FastAPI background tasks
        language: Optional language code from query parameter
        assistant: Optional assistant name from query parameter
        
    Returns:
        WebRTC answer with pc_id
    """
    logger.info("=" * 80)
    logger.info(f"📞 API /api/offer REQUEST:")
    logger.info(f"   • Body keys: {list(request.keys())}")
    logger.info(f"   • Query param - language: {language}")
    logger.info(f"   • Query param - assistant: {assistant}")
    logger.info("=" * 80)
    
    pc_id = request.get("pc_id")
    
    # Use query parameters if provided, otherwise check request body (for backwards compatibility)
    language_from_client = language or request.get("language")
    assistant_from_client = assistant or request.get("assistant")
    
    logger.info("=" * 80)
    logger.info(f"📞 API /api/offer FINAL PARAMS:")
    logger.info(f"   • pc_id: {pc_id}")
    logger.info(f"   • assistant: {assistant_from_client or 'None (using default)'}")
    logger.info(f"   • language: {language_from_client or 'None (will use env variable)'}")
    logger.info("=" * 80)
    
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
        
        # Start bot pipeline in background (no WebSocket for standard UI)
        background_tasks.add_task(run_bot, pipecat_connection, None, assistant_from_client, language_from_client)
    
    # Get answer and store connection
    answer = pipecat_connection.get_answer()
    pcs_map[answer["pc_id"]] = pipecat_connection
    
    return JSONResponse(answer)


@app.patch("/api/offer")
async def api_offer_patch(request: dict):
    """Handle ICE candidate updates via PATCH.
    
    This allows the client to send additional ICE candidates after the initial connection.
    
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
        "ace-base-agent": "ACE Base Agent",
        "rbc-fees-agent": "Banking: Fee Agent",
        "wire-transfer-agent": "Banking: Wire Transfer Agent",
        "telco-agent": "Telco: Mobile Billing Agent",
        "healthcare-agent": "Healthcare: Patient Intake",
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
    
    # Try GET /assistants (newer LangGraph servers)
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
    
    # Fallback: POST /assistants/search (older servers)
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
    
    # Filter out specific assistants if needed
    exclude_list = os.getenv("EXCLUDE_ASSISTANTS", "").split(",")
    if exclude_list:
        enriched = [
            agent for agent in enriched
            if agent.get("assistant_id") not in exclude_list
            and agent.get("graph_id") not in exclude_list
        ]
    
    logger.info(f"Returning {len(enriched)} assistants")
    return enriched


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for voice agent connections.
    
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
        
        logger.info("=" * 80)
        logger.info(f"📞 WebSocket /ws connection request received:")
        logger.info(f"   • pc_id: {pc_id}")
        logger.info(f"   • assistant: {assistant_from_client or 'None (using default)'}")
        logger.info(f"   • language: {language_from_client or 'None (will use env variable)'}")
        logger.info("=" * 80)
        
        if pc_id and pc_id in pcs_map:
            # Reuse existing connection (renegotiate)
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
            
            # Start bot pipeline
            asyncio.create_task(run_bot(pipecat_connection, websocket, assistant_from_client, language_from_client))
        
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
                    
                    if msg_type == "context_reset" and msg_content:
                        logger.info(f"Context reset request: {msg_content}")
                        
                        # Add message to context for next turn
                        pc_id = pipecat_connection.pc_id
                        if pc_id in contexts_map:
                            context = contexts_map[pc_id]
                            context.add_message({"role": "user", "content": msg_content})
                        else:
                            logger.warning(f"No context found for pc_id: {pc_id}")
                    
                    elif msg_type == "text_input" and msg_content:
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


@app.get("/get_prompt")
async def get_prompt():
    """Return prompt information (managed by LangGraph)."""
    return {
        "prompt": "",
        "name": "LangGraph-managed",
        "description": "Prompt and persona are managed by the LangGraph agent.",
    }


@app.get("/rtc-config")
async def rtc_config():
    """Provide WebRTC ICE configuration to browser clients.
    
    Returns dynamic Twilio TURN credentials when configured, otherwise
    uses environment variables. Always includes public STUN fallback.
    """
    try:
        servers = build_client_ice_servers()
        return {"iceServers": servers}
    except Exception as e:
        logger.error(f"rtc-config error: {e}")
        # Safe fallback
        return {"iceServers": [{"urls": "stun:stun.l.google.com:19302"}]}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "services": {
            "langgraph": os.getenv("LANGGRAPH_BASE_URL", "http://127.0.0.1:2024"),
            "riva_stt": os.getenv("RIVA_ASR_URL", "grpc.nvcf.nvidia.com:443"),
            "riva_tts": os.getenv("RIVA_TTS_URL", "grpc.nvcf.nvidia.com:443"),
        }
    }


# Mount Pipecat's standard prebuilt UI at /client
app.mount("/client", SmallWebRTCPrebuiltUI)
logger.info("📺 Pipecat standard UI mounted at /client")

# Mount custom UI at /app (not at / to avoid intercepting /client)
UI_DIST_DIR = Path(__file__).parent / "ui" / "dist"
if UI_DIST_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(UI_DIST_DIR), html=True), name="custom-ui")
    logger.info(f"📁 Custom UI serving from: {UI_DIST_DIR} at /app")
    logger.info(f"📱 Access custom UI at: http://localhost:7860/app")
else:
    logger.warning(f"Custom UI directory not found: {UI_DIST_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Modern Voice Agent with LangGraph + Riva")
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
    # Need either a shared NVIDIA_API_KEY or separate ASR/TTS keys
    has_shared_key = os.getenv("NVIDIA_API_KEY")
    has_asr_key = os.getenv("NVIDIA_ASR_API_KEY") or has_shared_key
    has_tts_key = os.getenv("NVIDIA_TTS_API_KEY") or has_shared_key
    
    if not has_asr_key or not has_tts_key:
        logger.error("❌ Missing required NVIDIA API keys")
        logger.error("   Option 1: Set a shared key for both services:")
        logger.error("     NVIDIA_API_KEY=nvapi-your-key-here")
        logger.error("   Option 2: Set separate keys for ASR and TTS:")
        logger.error("     NVIDIA_ASR_API_KEY=nvapi-your-asr-key-here")
        logger.error("     NVIDIA_TTS_API_KEY=nvapi-your-tts-key-here")
        sys.exit(1)
    
    logger.info("=" * 70)
    logger.info("🎙️  Modern Voice Agent")
    logger.info("=" * 70)
    
    # Show LLM mode
    use_simple = os.getenv("USE_SIMPLE_LLM", "false").lower() == "true"
    if use_simple:
        logger.info(f"LLM: OpenAI {os.getenv('OPENAI_MODEL', 'gpt-4o-mini')} (simple mode)")
    else:
        logger.info(f"LLM: LangGraph @ {os.getenv('LANGGRAPH_BASE_URL', 'http://127.0.0.1:2024')}")
    
    # Show API key info (separate keys or shared)
    asr_key = os.getenv('NVIDIA_ASR_API_KEY') or os.getenv('NVIDIA_API_KEY', '')
    tts_key = os.getenv('NVIDIA_TTS_API_KEY') or os.getenv('NVIDIA_API_KEY', '')
    
    if asr_key:
        logger.info(f"NVIDIA ASR Key: {asr_key[:4]}...{asr_key[-4:]}")
    if tts_key and tts_key != asr_key:
        logger.info(f"NVIDIA TTS Key: {tts_key[:4]}...{tts_key[-4:]}")
    elif tts_key == asr_key:
        logger.info(f"NVIDIA TTS Key: (same as ASR)")
    
    logger.info(f"Sample Rate: {os.getenv('AUDIO_SAMPLE_RATE', '16000')}Hz")
    logger.info("=" * 70)
    logger.info(f"🌐 Server starting on http://{args.host}:{args.port}")
    logger.info("=" * 70)
    
    uvicorn.run(app, host=args.host, port=args.port)

