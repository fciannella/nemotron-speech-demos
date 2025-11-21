import { useEffect, useRef, useState, useCallback } from 'react';
import { PipecatClient } from '@pipecat-ai/client-js';
import { SmallWebRTCTransport } from '@pipecat-ai/small-webrtc-transport';
import type { TranscriptionMessage, ConnectionState } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:7860';

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
    setTranscriptions((prev) => {
      // Get the LAST message (most recent)
      const lastMessage = prev[prev.length - 1];
      
      // Should we append? Only if LAST message is from SAME speaker
      const shouldAppendToLast = lastMessage && lastMessage.isUser === isUser;
      
      if (!shouldAppendToLast) {
        // Speaker changed or first message - create NEW bubble
        return [
          ...prev.filter(t => t.isFinal),
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

  const connect = useCallback(async (languageCode?: string) => {
    console.log('='.repeat(80));
    console.log('🎯 usePipecatClient.connect() called');
    console.log(`   • languageCode parameter: ${languageCode || 'undefined'}`);
    console.log('='.repeat(80));
    
    if (clientRef.current) {
      console.warn('Client already exists');
      return;
    }

    setConnectionState({ isConnected: false, isConnecting: true, error: null });

    try {
      // Fetch ICE servers from backend
      let iceServers: RTCIceServer[] = [{ urls: 'stun:stun.l.google.com:19302' }];
      try {
        const iceResponse = await fetch(`${API_BASE_URL}/rtc-config`);
        const iceConfig = await iceResponse.json();
        if (iceConfig.iceServers) {
          iceServers = iceConfig.iceServers;
        }
      } catch (error) {
        console.warn('Could not fetch ICE servers, using defaults:', error);
      }

      // Create transport
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
          },
          onBotReady: () => {
            console.log('🤖 Bot ready');
          },
          onUserTranscript: (data: TranscriptData) => {
            const { text, final: isFinal } = data;
            if (text) {
              addTranscription(text, isFinal, true);
            }
          },
          onBotLlmStarted: () => {
            // Clear buffer when bot starts new response
            botMessageBufferRef.current = '';
          },
          onBotLlmText: (data: BotLLMTextData) => {
            // Accumulate streaming LLM text
            const { text } = data;
            if (text) {
              botMessageBufferRef.current += text;
              // Show as interim (streaming)
              addTranscription(botMessageBufferRef.current, false, false);
            }
          },
          onBotLlmStopped: () => {
            // LLM finished - show final message
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
      if (languageCode) {
        endpoint += `?language=${encodeURIComponent(languageCode)}`;
      }
      
      console.log('📡 Connecting to bot with parameters:');
      console.log(`   • endpoint: ${endpoint}`);
      console.log(`   • language: ${languageCode || 'none'}`);
      
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
