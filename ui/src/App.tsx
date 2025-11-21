import { useState } from 'react';
import { usePipecatClient } from './hooks/usePipecatClient';
import { TranscriptionDisplay } from './components/TranscriptionDisplay';
import { ConversationsList } from './components/ConversationsList';
import { VoiceControlsFooter } from './components/VoiceControlsFooter';
import { AudioPlayer } from './components/AudioPlayer';
import { SUPPORTED_LANGUAGES } from './components/LanguageSelector';
import type { Language } from './types';

function App() {
  const {
    connectionState,
    transcriptions,
    isMuted,
    botAudioTrack,
    connect,
    disconnect,
    toggleMute,
    clearTranscriptions,
  } = usePipecatClient();

  // Language selection state
  const [selectedLanguage, setSelectedLanguage] = useState<Language>(SUPPORTED_LANGUAGES[0]); // Default to en-US

  // Conversations list
  const [selectedConversationId, setSelectedConversationId] = useState('multilingual-auto');
  const conversations = [
    {
      id: 'multilingual-auto',
      name: 'Multilingual (Auto-detect)',
      lastMessage: transcriptions[transcriptions.length - 1]?.text.substring(0, 50),
      unread: 0,
    },
    {
      id: 'language-specific',
      name: `Language-Specific (${selectedLanguage.flag} ${selectedLanguage.name})`,
      lastMessage: transcriptions[transcriptions.length - 1]?.text.substring(0, 50),
      unread: 0,
    },
  ];

  const selectedConversation = conversations.find(c => c.id === selectedConversationId);

  // Handle connection with language parameter
  const handleConnect = () => {
    const languageToUse = selectedConversationId === 'language-specific' ? selectedLanguage.code : 'multi';
    
    console.log('='.repeat(80));
    console.log('🚀 App.handleConnect() called');
    console.log(`   • Selected conversation: ${selectedConversationId}`);
    console.log(`   • Selected language: ${selectedLanguage.code} (${selectedLanguage.name})`);
    console.log(`   • Language to send: ${languageToUse}`);
    console.log('='.repeat(80));
    
    connect(languageToUse);
  };

  // Determine if language selector should be shown
  const showLanguageSelector = !connectionState.isConnected && selectedConversationId === 'language-specific';

  return (
    <div className="h-screen flex flex-col bg-white dark:bg-gray-900">
      {/* Audio player */}
      {botAudioTrack && <AudioPlayer botAudioTrack={botAudioTrack} />}
      
      {/* NVIDIA Header Bar */}
      <header className="bg-black px-6 py-3 flex items-center gap-4 shadow-lg flex-shrink-0">
        {/* NVIDIA Logo */}
        <img 
          src="/images.png" 
          alt="NVIDIA" 
          className="h-12 w-auto object-contain"
        />
        <h1 className="text-xl font-bold" style={{ color: '#76B900' }}>
          Multilingual Voice Agents
        </h1>
        
        {/* Connection Status */}
        <div className="ml-auto flex items-center gap-2 text-white">
          <div className={`w-2 h-2 rounded-full ${connectionState.isConnected ? 'bg-[#76B900] animate-pulse' : 'bg-gray-500'}`}></div>
          <span className="text-sm">{connectionState.isConnected ? 'Connected' : 'Disconnected'}</span>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar - Conversations List - border extends to bottom */}
        <aside className="w-80 flex-shrink-0 border-r border-gray-200 dark:border-gray-700">
          <ConversationsList
            conversations={conversations}
            selectedId={selectedConversationId}
            onSelect={setSelectedConversationId}
          />
        </aside>

        {/* Main Chat Area */}
        <main className="flex-1 flex flex-col overflow-hidden">
          <TranscriptionDisplay
            transcriptions={transcriptions}
            onClear={clearTranscriptions}
            conversationTitle={selectedConversation?.name || 'Conversation'}
          />
        </main>
      </div>

      {/* Footer - Voice Controls */}
      <VoiceControlsFooter
        connectionState={connectionState}
        isMuted={isMuted}
        selectedLanguage={selectedLanguage}
        onLanguageChange={setSelectedLanguage}
        onConnect={handleConnect}
        onDisconnect={disconnect}
        onToggleMute={toggleMute}
        showLanguageSelector={showLanguageSelector}
      />
    </div>
  );
}

export default App;
