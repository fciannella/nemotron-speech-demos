import type { ConnectionState, Language } from '../types';
import { LanguageSelector } from './LanguageSelector';

interface VoiceControlsFooterProps {
  connectionState: ConnectionState;
  isMuted: boolean;
  selectedLanguage: Language;
  onLanguageChange: (language: Language) => void;
  onConnect: () => void;
  onDisconnect: () => void;
  onToggleMute: () => void;
  showLanguageSelector: boolean;
}

export function VoiceControlsFooter({
  connectionState,
  isMuted,
  selectedLanguage,
  onLanguageChange,
  onConnect,
  onDisconnect,
  onToggleMute,
  showLanguageSelector,
}: VoiceControlsFooterProps) {
  const { isConnected, isConnecting } = connectionState;

  const handleConnect = () => {
    console.log('🎬 VoiceControlsFooter: Connect button clicked');
    console.log(`   • Show language selector: ${showLanguageSelector}`);
    console.log(`   • Selected language: ${selectedLanguage.code} (${selectedLanguage.name})`);
    onConnect();
  };

  return (
    <footer className="bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700 px-6 py-4">
      {/* Voice Controls */}
      <div className="flex items-center justify-center gap-4">
        {!isConnected ? (
          <>
            {/* Language Selector - only show for language-specific conversation */}
            {showLanguageSelector && (
              <LanguageSelector
                selectedLanguage={selectedLanguage}
                onLanguageChange={onLanguageChange}
                disabled={isConnecting}
              />
            )}
            
            {/* Start Voice Chat Button */}
            <button
              onClick={handleConnect}
              disabled={isConnecting}
              className="px-6 py-2 bg-[#76B900] hover:bg-[#6AA000] disabled:bg-gray-400 disabled:cursor-not-allowed text-white font-medium rounded-full transition-colors flex items-center gap-2"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>
              {isConnecting ? 'Connecting...' : 'Start Voice Chat'}
            </button>
          </>
        ) : (
          <>
            <button
              onClick={onToggleMute}
              className={`px-4 py-2 ${
                isMuted
                  ? 'bg-yellow-500 hover:bg-yellow-600'
                  : 'bg-[#76B900] hover:bg-[#6AA000]'
              } text-white font-medium rounded-full transition-colors flex items-center gap-2`}
            >
              {isMuted ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                </svg>
              )}
              {isMuted ? 'Unmute' : 'Mute'}
            </button>

            <button
              onClick={onDisconnect}
              className="px-4 py-2 bg-red-500 hover:bg-red-600 text-white font-medium rounded-full transition-colors flex items-center gap-2"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
              End Chat
            </button>
          </>
        )}
      </div>
    </footer>
  );
}

