import { useEffect, useRef } from 'react';

interface AudioPlayerProps {
  botAudioTrack: MediaStreamTrack | null;
}

/**
 * Simple audio player that plays the bot's audio track
 * Based on official Pipecat React client implementation
 */
export function AudioPlayer({ botAudioTrack }: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    if (!audioRef.current || !botAudioTrack) return;

    // Check if same track is already attached
    if (audioRef.current.srcObject) {
      const oldTrack = (audioRef.current.srcObject as MediaStream).getAudioTracks()[0];
      if (oldTrack && oldTrack.id === botAudioTrack.id) return;
    }

    // Create stream with bot audio track and attach
    const stream = new MediaStream([botAudioTrack]);
    audioRef.current.srcObject = stream;

  }, [botAudioTrack]);

  return (
    <audio 
      ref={audioRef} 
      autoPlay
      playsInline
      style={{ display: 'none' }}
    />
  );
}
