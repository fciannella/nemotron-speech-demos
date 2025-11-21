import type { ConnectionState } from '../types';

interface VoiceControlsProps {
  connectionState: ConnectionState;
  isMuted: boolean;
  onConnect: () => void;
  onDisconnect: () => void;
  onToggleMute: () => void;
}

export function VoiceControls({
  connectionState,
  isMuted,
  onConnect,
  onDisconnect,
  onToggleMute,
}: VoiceControlsProps) {
  const { isConnected, isConnecting, error } = connectionState;

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6">
      <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
        Voice Controls
      </h2>

      {/* Connection Status */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <div
            className={`w-3 h-3 rounded-full ${
              isConnected
                ? 'bg-green-500 animate-pulse'
                : isConnecting
                ? 'bg-yellow-500 animate-pulse'
                : 'bg-gray-400'
            }`}
          />
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            {isConnected
              ? 'Connected'
              : isConnecting
              ? 'Connecting...'
              : 'Disconnected'}
          </span>
        </div>
        {error && (
          <div className="mt-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          </div>
        )}
      </div>

      {/* Control Buttons */}
      <div className="space-y-3">
        {!isConnected ? (
          <button
            onClick={onConnect}
            disabled={isConnecting}
            className="w-full px-6 py-4 bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white font-semibold rounded-lg shadow-md hover:shadow-lg transition-all duration-200 transform hover:scale-105 disabled:hover:scale-100 flex items-center justify-center gap-2"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
            </svg>
            {isConnecting ? 'Connecting...' : 'Start Voice Chat'}
          </button>
        ) : (
          <>
            <button
              onClick={onToggleMute}
              className={`w-full px-6 py-4 ${
                isMuted
                  ? 'bg-yellow-500 hover:bg-yellow-600'
                  : 'bg-green-500 hover:bg-green-600'
              } text-white font-semibold rounded-lg shadow-md hover:shadow-lg transition-all duration-200 transform hover:scale-105 flex items-center justify-center gap-2`}
            >
              {isMuted ? (
                <>
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
                  </svg>
                  Unmute Microphone
                </>
              ) : (
                <>
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                  </svg>
                  Microphone Active
                </>
              )}
            </button>

            <button
              onClick={onDisconnect}
              className="w-full px-6 py-4 bg-red-500 hover:bg-red-600 text-white font-semibold rounded-lg shadow-md hover:shadow-lg transition-all duration-200 transform hover:scale-105 flex items-center justify-center gap-2"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
              End Voice Chat
            </button>
          </>
        )}
      </div>

      {/* Instructions */}
      {!isConnected && (
        <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
          <h3 className="text-sm font-semibold text-blue-900 dark:text-blue-300 mb-2">
            How to use:
          </h3>
          <ul className="text-sm text-blue-800 dark:text-blue-400 space-y-1 list-disc list-inside">
            <li>Click "Start Voice Chat" to connect</li>
            <li>Allow microphone access when prompted</li>
            <li>Start speaking naturally</li>
            <li>See transcriptions appear in real-time</li>
          </ul>
        </div>
      )}
    </div>
  );
}


