import { useState, useCallback, useRef } from 'react'

export interface Transcription {
  text: string
  role: 'user' | 'assistant'
  final: boolean
  stability?: number
  timestamp: Date
}

interface UseWebRTCParams {
  wsUrl: string
  rtcConfig: RTCConfiguration
}

interface UseWebRTCReturn {
  status: 'init' | 'connecting' | 'connected' | 'error'
  transcriptions: Transcription[]
  start: () => void
  stop: () => void
  error?: Error
}

export function useWebRTC({ wsUrl, rtcConfig }: UseWebRTCParams): UseWebRTCReturn {
  const [status, setStatus] = useState<'init' | 'connecting' | 'connected' | 'error'>('init')
  const [transcriptions, setTranscriptions] = useState<Transcription[]>([])
  const [error, setError] = useState<Error>()
  
  const pcRef = useRef<RTCPeerConnection | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const micStreamRef = useRef<MediaStream | null>(null)

  const stop = useCallback(() => {
    // Close WebSocket
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    
    // Stop microphone
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach(track => track.stop())
      micStreamRef.current = null
    }
    
    // Close peer connection
    if (pcRef.current) {
      pcRef.current.close()
      pcRef.current = null
    }
    
    setStatus('init')
  }, [])

  const connect = useCallback(async () => {
    try {
      // Get microphone access
      const micStream = await navigator.mediaDevices.getUserMedia({ audio: true })
      micStreamRef.current = micStream

      // Create peer connection
      const pc = new RTCPeerConnection(rtcConfig)
      pcRef.current = pc

      // Handle connection state changes
      pc.onconnectionstatechange = () => {
        console.log('Connection state:', pc.connectionState)
        if (pc.connectionState === 'connected') {
          setStatus('connected')
        } else if (pc.connectionState === 'disconnected' || pc.connectionState === 'failed') {
          stop()
        }
      }

      // Add microphone track
      const micTrack = micStream.getAudioTracks()[0]
      pc.addTransceiver(micTrack, { direction: 'sendrecv' })
      pc.addTransceiver('video', { direction: 'sendrecv' })

      // Create offer
      const offer = await pc.createOffer()
      await pc.setLocalDescription(offer)

      // Wait for ICE gathering
      await new Promise<void>((resolve) => {
        if (pc.iceGatheringState === 'complete') {
          resolve()
        } else {
          const checkState = () => {
            if (pc.iceGatheringState === 'complete') {
              pc.removeEventListener('icegatheringstatechange', checkState)
              resolve()
            }
          }
          pc.addEventListener('icegatheringstatechange', checkState)
        }
      })

      // Connect WebSocket
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      // Wait for WebSocket open and exchange SDP
      await new Promise<void>((resolve, reject) => {
        ws.onopen = () => {
          ws.send(JSON.stringify({
            sdp: pc.localDescription!.sdp,
            type: pc.localDescription!.type
          }))
        }

        ws.onmessage = async (event) => {
          const answer = JSON.parse(event.data)
          await pc.setRemoteDescription(answer)
          resolve()
        }

        ws.onerror = () => {
          reject(new Error('WebSocket connection failed'))
        }
      })

      // Listen for transcriptions
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          
          if (data.type === 'transcription') {
            const transcription: Transcription = {
              text: data.text,
              role: data.role,
              final: data.final,
              stability: data.stability,
              timestamp: new Date()
            }
            
            setTranscriptions(prev => {
              // For interim results, update the last interim of the same role
              if (!transcription.final) {
                const lastInterimIndex = prev.findIndex(
                  (t, i) => i === prev.length - 1 && !t.final && t.role === transcription.role
                )
                if (lastInterimIndex !== -1) {
                  const updated = [...prev]
                  updated[lastInterimIndex] = transcription
                  return updated
                }
              }
              return [...prev, transcription]
            })
          }
        } catch (e) {
          console.error('Error parsing WebSocket message:', e)
        }
      }

    } catch (e) {
      const err = e instanceof Error ? e : new Error('Connection failed')
      setError(err)
      setStatus('error')
      stop()
    }
  }, [wsUrl, rtcConfig, stop])

  const start = useCallback(() => {
    setStatus('connecting')
    setTranscriptions([]) // Clear old transcriptions
    connect()
  }, [connect])

  return {
    status,
    transcriptions,
    start,
    stop,
    error
  }
}








