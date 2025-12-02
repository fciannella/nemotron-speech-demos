import { useEffect, useRef, useState, useCallback } from 'react';
import { PipecatClient } from '@pipecat-ai/client-js';
import { SmallWebRTCTransport } from '@pipecat-ai/small-webrtc-transport';
import type { TranscriptionMessage, ConnectionState } from '../types';

// Smart API URL detection:
// 1. If accessing via localhost, use localhost for API (SSH tunnel scenario)
// 2. Otherwise, use the same hostname/IP as the page to ensure connectivity
// 3. Falls back to configured VITE_API_BASE_URL if needed
function getApiBaseUrl(): string {
  const pageHostname = window.location.hostname;
  const pageProtocol = window.location.protocol;
  
  // If we're accessing the page via localhost, assume SSH tunnel and use localhost for API too
  if (pageHostname === 'localhost' || pageHostname === '127.0.0.1') {
    console.log('🔍 Detected localhost access - using localhost for API (SSH tunnel mode)');
    return 'http://localhost:7860';
  }
  
  // Use the same hostname/IP as the page is accessed from
  // This ensures DNS resolution consistency and works for both IPs and hostnames
  const autoUrl = `${pageProtocol}//${pageHostname}:7860`;
  console.log('🔍 Auto-detected API URL from page hostname:', autoUrl);
  return autoUrl;
}

const API_BASE_URL = getApiBaseUrl();

// Type definitions from Pipecat
type TranscriptData = {
  text: string;
  final: boolean;
  timestamp: string;
  user_id: string;
};

type BotLLMTextData = {
  text: string;
};

export function usePipecatClient() {
  const [connectionState, setConnectionState] = useState<ConnectionState>({
    isConnected: false,
    isConnecting: false,
    error: null,
  });
  const [transcriptions, setTranscriptions] = useState<TranscriptionMessage[]>([]);
  const [isMuted, setIsMuted] = useState(false);
  const [botAudioTrack, setBotAudioTrack] = useState<MediaStreamTrack | null>(null);
  const clientRef = useRef<PipecatClient | null>(null);
  const botMessageBufferRef = useRef<string>('');

  const addTranscription = useCallback((text: string, isFinal: boolean, isUser: boolean) => {
    // Filter out invalid messages (empty, "0", single digits, etc.)
    if (!text || text.trim().length === 0) {
      console.log('⚠️ Ignoring empty transcription');
      return;
    }
    // Filter out ASR garbage - "0 ." "0。" "0" patterns from silence/noise
    // This is common with Mandarin ASR interpreting silence as "0"
    if (/^[0-9]\s*[\.。，,]?\s*$/.test(text.trim())) {
      console.log(`⚠️ Ignoring ASR noise: "${text}"`);
      return;
    }
    
    setTranscriptions((prev) => {
      // Get the LAST message (most recent)
      const lastMessage = prev[prev.length - 1];
      
      // Should we append? Only if LAST message is from SAME speaker
      const shouldAppendToLast = lastMessage && lastMessage.isUser === isUser;
      
      if (!shouldAppendToLast) {
        // Speaker changed or first message - create NEW bubble
        // Mark all previous messages as final (they're complete - speaker changed)
        const finalized = prev.map(t => t.isFinal ? t : { ...t, isFinal: true });
        return [
          ...finalized,
          {
            id: `${Date.now()}-${Math.random()}`,
            text,
            isFinal,
            isUser,
            timestamp: Date.now(),
          },
        ];
      }

      // Append to last message (same speaker continuing)
      const updated = [...prev];
      const lastIndex = prev.length - 1;
      const baseText = lastMessage.baseText || (lastMessage.isFinal ? lastMessage.text : '');
      
      if (isFinal) {
        // Final message - append to base
        updated[lastIndex] = {
          ...lastMessage,
          text: lastMessage.isFinal
            ? (lastMessage.baseText || lastMessage.text) + ' ' + text
            : (baseText ? baseText + ' ' + text : text),
          baseText: lastMessage.isFinal
            ? (lastMessage.baseText || lastMessage.text) + ' ' + text
            : (baseText ? baseText + ' ' + text : text),
          isFinal: true,
          timestamp: Date.now(),
        };
      } else {
        // Interim - append to base
        updated[lastIndex] = {
          ...lastMessage,
          text: lastMessage.isFinal
            ? lastMessage.text + ' ' + text
            : (baseText ? baseText + ' ' + text : text),
          baseText: lastMessage.isFinal ? lastMessage.text : baseText,
          isFinal: false,
          timestamp: Date.now(),
        };
      }
      
      return updated;
    });
  }, []);

  const connect = useCallback(async (languageCode?: string, assistantId?: string) => {
    console.log('='.repeat(80));
    console.log('🎯 usePipecatClient.connect() called');
    console.log(`   • languageCode parameter: ${languageCode || 'undefined'}`);
    console.log(`   • assistantId parameter: ${assistantId || 'undefined'}`);
    console.log(`   • API_BASE_URL: ${API_BASE_URL}`);
    console.log(`   • Current page URL: ${window.location.href}`);
    console.log(`   • Protocol: ${window.location.protocol}`);
    console.log('='.repeat(80));
    
    if (clientRef.current) {
      console.warn('Client already exists');
      return;
    }

    // Check for secure context and media devices API
    console.log('🔍 Checking browser capabilities...');
    console.log(`   • Is secure context: ${window.isSecureContext}`);
    console.log(`   • navigator.mediaDevices exists: ${!!navigator.mediaDevices}`);
    console.log(`   • getUserMedia available: ${!!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia)}`);
    
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      const errorMsg = window.location.protocol === 'http:' && window.location.hostname !== 'localhost'
        ? 'Microphone access requires HTTPS. Please access this page via HTTPS or use localhost.'
        : 'Your browser does not support media devices. Please use a modern browser.';
      console.error('❌ ' + errorMsg);
      setConnectionState({
        isConnected: false,
        isConnecting: false,
        error: errorMsg,
      });
      return;
    }

    setConnectionState({ isConnected: false, isConnecting: true, error: null });

    try {
      // Fetch ICE servers from backend
      let iceServers: RTCIceServer[] = [{ urls: 'stun:stun.l.google.com:19302' }];
      try {
        console.log(`📡 Fetching ICE servers from: ${API_BASE_URL}/rtc-config`);
        const iceResponse = await fetch(`${API_BASE_URL}/rtc-config`);
        const iceConfig = await iceResponse.json();
        if (iceConfig.iceServers) {
          iceServers = iceConfig.iceServers;
          console.log('✅ ICE servers fetched successfully');
        }
      } catch (error) {
        console.warn('Could not fetch ICE servers, using defaults:', error);
      }

      // Create transport
      console.log('🔧 Creating WebRTC transport...');
      console.log('   • ICE servers:', JSON.stringify(iceServers, null, 2));
      
      // If accessing via localhost (SSH tunnel), log a note
      if (window.location.hostname === 'localhost') {
        console.log('   ℹ️  Using SSH tunnel - WebRTC may require TURN servers');
      }
      
      const transport = new SmallWebRTCTransport({
        iceServers,
      });

      // Create Pipecat client
      const client = new PipecatClient({
        transport,
        enableMic: true,
        enableCam: false,
        callbacks: {
          onConnected: () => {
            console.log('✅ Connected to Pipecat');
            setConnectionState({ isConnected: true, isConnecting: false, error: null });
          },
          onDisconnected: () => {
            console.log('❌ Disconnected from Pipecat');
            setConnectionState({ isConnected: false, isConnecting: false, error: null });
            clientRef.current = null;
          },
          onTransportStateChanged: (state: string) => {
            console.log('🔄 Transport state:', state);
            if (state === 'connected') {
              console.log('✅ WebRTC transport connected successfully!');
            } else if (state === 'failed') {
              console.error('❌ WebRTC transport failed!');
              setConnectionState({
                isConnected: false,
                isConnecting: false,
                error: 'WebRTC connection failed. This may be due to network/firewall issues.',
              });
            } else if (state === 'disconnected') {
              console.warn('⚠️  WebRTC transport disconnected');
            }
          },
          onBotReady: () => {
            console.log('🤖 Bot ready');
          },
          onUserTranscript: (data: TranscriptData) => {
            const { text, final: isFinal } = data;
            console.log(`👤 onUserTranscript: "${text}" (final=${isFinal}, ${text?.length || 0} chars)`);
            if (text) {
              addTranscription(text, isFinal, true);
            }
          },
          onBotLlmStarted: () => {
            // Clear buffer when bot starts new response
            console.log('🤖 onBotLlmStarted: clearing buffer');
            botMessageBufferRef.current = '';
          },
          onBotLlmText: (data: BotLLMTextData) => {
            // Accumulate streaming LLM text
            const { text } = data;
            console.log(`🤖 onBotLlmText: received "${text}" (${text?.length || 0} chars)`);
            if (text && text.trim()) {
              botMessageBufferRef.current += text;
              console.log(`🤖 Buffer now: "${botMessageBufferRef.current.substring(0, 50)}..." (${botMessageBufferRef.current.length} chars)`);
              // Show as interim (streaming)
              addTranscription(botMessageBufferRef.current, false, false);
            }
          },
          onBotLlmStopped: () => {
            // LLM finished - show final message
            console.log(`🤖 onBotLlmStopped: buffer="${botMessageBufferRef.current.substring(0, 50)}..." (${botMessageBufferRef.current.length} chars)`);
            if (botMessageBufferRef.current.trim()) {
              addTranscription(botMessageBufferRef.current.trim(), true, false);
              botMessageBufferRef.current = '';
            }
          },
          onBotTtsStarted: () => {
            // TTS audio started
          },
          onBotTtsStopped: () => {
            // TTS audio stopped
          },
          onTrackStarted: (track: MediaStreamTrack, participant: any) => {
            // Capture bot audio track for playback
            if (track.kind === 'audio' && !participant?.local) {
              setBotAudioTrack(track);
            }
          },
          onTrackStopped: (track: MediaStreamTrack, participant: any) => {
            if (track.kind === 'audio' && !participant?.local) {
              setBotAudioTrack(null);
            }
          },
          onMessageError: (message: unknown) => {
            console.error('❌ Message error:', message);
          },
        },
      });

      clientRef.current = client;

      // Initialize devices
      await client.initDevices();

      // Connect to the bot
      // Note: Pipecat client doesn't merge body params, so we use URL parameters
      let endpoint = `${API_BASE_URL}/api/offer`;
      const params = new URLSearchParams();
      
      if (languageCode) {
        params.append('language', languageCode);
      }
      if (assistantId) {
        params.append('assistant', assistantId);
      }
      
      const queryString = params.toString();
      if (queryString) {
        endpoint += `?${queryString}`;
      }
      
      console.log('📡 Connecting to bot with parameters:');
      console.log(`   • endpoint: ${endpoint}`);
      console.log(`   • language: ${languageCode || 'none'}`);
      console.log(`   • assistant: ${assistantId || 'default'}`);
      
      await client.connect({
        webrtcRequestParams: {
          endpoint: endpoint,
        },
      });
      
      console.log('✅ Connection initiated successfully');
    } catch (error: any) {
      console.error('Connection error:', error);
      setConnectionState({
        isConnected: false,
        isConnecting: false,
        error: error.message || 'Failed to connect',
      });
      clientRef.current = null;
    }
  }, [addTranscription]);

  const disconnect = useCallback(async () => {
    if (clientRef.current) {
      try {
        await clientRef.current.disconnect();
        clientRef.current = null;
        setConnectionState({ isConnected: false, isConnecting: false, error: null });
        setTranscriptions([]);
        setBotAudioTrack(null);
      } catch (error: any) {
        console.error('Disconnect error:', error);
      }
    }
  }, []);

  const toggleMute = useCallback(async () => {
    if (clientRef.current) {
      try {
        const newMutedState = !isMuted;
        clientRef.current.enableMic(!newMutedState);
        setIsMuted(newMutedState);
      } catch (error: any) {
        console.error('Toggle mute error:', error);
      }
    }
  }, [isMuted]);

  const clearTranscriptions = useCallback(() => {
    setTranscriptions([]);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (clientRef.current) {
        clientRef.current.disconnect().catch(console.error);
      }
    };
  }, []);

  return {
    connectionState,
    transcriptions,
    isMuted,
    botAudioTrack,  // Export bot audio track
    connect,
    disconnect,
    toggleMute,
    clearTranscriptions,
    clientRef,
  };
}
