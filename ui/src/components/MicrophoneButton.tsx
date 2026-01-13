interface Props {
  status: 'init' | 'connecting' | 'connected' | 'error'
  onStart: () => void
  onStop: () => void
}

export function MicrophoneButton({ status, onStart, onStop }: Props) {
  const isConnected = status === 'connected'
  const isConnecting = status === 'connecting'
  
  const handleClick = () => {
    if (isConnected) {
      onStop()
    } else if (!isConnecting) {
      onStart()
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={isConnecting}
      className={`mic-button ${isConnected ? 'active' : ''} ${isConnecting ? 'connecting' : ''}`}
      aria-label={isConnected ? 'Stop recording' : 'Start recording'}
    >
      <svg 
        className="mic-icon"
        fill="currentColor" 
        viewBox="0 0 24 24"
        xmlns="http://www.w3.org/2000/svg"
      >
        {isConnected ? (
          // Stop icon
          <rect x="6" y="6" width="12" height="12" rx="2" />
        ) : (
          // Microphone icon
          <>
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
            <line x1="12" y1="19" x2="12" y2="23"/>
            <line x1="8" y1="23" x2="16" y2="23"/>
          </>
        )}
      </svg>
      <span className="mic-label">
        {isConnecting && 'Connecting...'}
        {isConnected && 'Recording'}
        {status === 'init' && 'Start'}
        {status === 'error' && 'Retry'}
      </span>
    </button>
  )
}








