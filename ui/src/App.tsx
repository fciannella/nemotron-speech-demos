import { useState } from 'react';
import { usePipecatClient } from './hooks/usePipecatClient';
import { TranscriptionDisplay } from './components/TranscriptionDisplay';
import { ConversationsList } from './components/ConversationsList';
import { VoiceControlsFooter } from './components/VoiceControlsFooter';
import { AudioPlayer } from './components/AudioPlayer';
import { AgentInfoPanel } from './components/AgentInfoPanel';
import { ArchitecturePage } from './components/ArchitecturePage';
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
  const [languageMode, setLanguageMode] = useState<'multi' | 'specific'>('multi');

  // Conversations list
  const [selectedConversationId, setSelectedConversationId] = useState('multilingual-auto');
  
  // Agent info panel state
  const [isAgentInfoOpen, setIsAgentInfoOpen] = useState(false);
  
  // Architecture page state
  const [showArchitecture, setShowArchitecture] = useState(false);
  const conversations = [
    {
      id: 'multilingual-auto',
      name: 'Multilingual (Auto-detect)',
      description: 'General conversation with auto language detection',
      lastMessage: transcriptions[transcriptions.length - 1]?.text.substring(0, 50),
      unread: 0,
    },
    {
      id: 'language-specific',
      name: `Language-Specific (${selectedLanguage.flag} ${selectedLanguage.name})`,
      description: 'Chat in a specific language',
      lastMessage: transcriptions[transcriptions.length - 1]?.text.substring(0, 50),
      unread: 0,
    },
    {
      id: 'wire-transfer',
      name: '💳 Wire Transfer Agent',
      description: 'Banking assistant for domestic & international wire transfers',
      lastMessage: transcriptions[transcriptions.length - 1]?.text.substring(0, 50),
      unread: 0,
    },
    {
      id: 'claims-investigation',
      name: '🔍 Claims Investigation',
      description: 'AI agent for investigating insurance claims via phone calls',
      lastMessage: transcriptions[transcriptions.length - 1]?.text.substring(0, 50),
      unread: 0,
    },
    {
      id: 'telco-agent',
      name: '📱 Telco Agent',
      description: 'Telecommunications assistant for mobile plans, roaming, and billing',
      lastMessage: transcriptions[transcriptions.length - 1]?.text.substring(0, 50),
      unread: 0,
    },
    {
      id: 'rbc-fees-agent',
      name: '💰 Banking Fees Agent',
      description: 'Banking assistant to review account fees and suggest package upgrades',
      lastMessage: transcriptions[transcriptions.length - 1]?.text.substring(0, 50),
      unread: 0,
    },
    {
      id: 'healthcare-agent',
      name: '🏥 Healthcare Nurse',
      description: '24/7 AI telehealth nurse for symptom triage, appointments, and medical advice',
      lastMessage: transcriptions[transcriptions.length - 1]?.text.substring(0, 50),
      unread: 0,
    },
  ];

  const selectedConversation = conversations.find(c => c.id === selectedConversationId);

  // Handle conversation selection - clear transcriptions when switching
  const handleConversationSelect = (id: string) => {
    if (id !== selectedConversationId && !connectionState.isConnected) {
      clearTranscriptions();
    }
    setSelectedConversationId(id);
    
    // Close agent info panel when switching away from specialized agents
    if (id !== 'wire-transfer' && id !== 'claims-investigation' && id !== 'telco-agent' && id !== 'rbc-fees-agent' && id !== 'healthcare-agent') {
      setIsAgentInfoOpen(false);
    }
  };

  // Handle connection with language and assistant parameters
  const handleConnect = () => {
    let languageToUse: string | undefined;
    let assistantToUse: string | undefined;
    
    // Determine assistant and language based on conversation type
    if (selectedConversationId === 'wire-transfer') {
      // Wire Transfer Agent
      assistantToUse = 'wire_transfer_agent';
      // Use language mode selector for wire transfer
      if (languageMode === 'specific') {
        languageToUse = selectedLanguage.code;
      } else {
        languageToUse = 'multi';
      }
    } else if (selectedConversationId === 'claims-investigation') {
      // Claims Investigation Agent
      assistantToUse = 'claims_investigation_agent';
      // Use language mode selector for claims investigation
      if (languageMode === 'specific') {
        languageToUse = selectedLanguage.code;
      } else {
        languageToUse = 'multi';
      }
    } else if (selectedConversationId === 'telco-agent') {
      // Telco Agent
      assistantToUse = 'telco_agent';
      // Use language mode selector for telco agent
      if (languageMode === 'specific') {
        languageToUse = selectedLanguage.code;
      } else {
        languageToUse = 'multi';
      }
    } else if (selectedConversationId === 'rbc-fees-agent') {
      // Banking Fees Agent
      assistantToUse = 'rbc_fees_agent';
      // Use language mode selector for fees agent
      if (languageMode === 'specific') {
        languageToUse = selectedLanguage.code;
      } else {
        languageToUse = 'multi';
      }
    } else if (selectedConversationId === 'healthcare-agent') {
      // Healthcare Telehealth Nurse Agent
      assistantToUse = 'healthcare_agent';
      // Use language mode selector for healthcare agent
      if (languageMode === 'specific') {
        languageToUse = selectedLanguage.code;
      } else {
        languageToUse = 'multi';
      }
    } else if (selectedConversationId === 'language-specific') {
      // Language-specific conversation - always use selected language
      languageToUse = selectedLanguage.code;
    } else {
      // Multilingual conversation - always auto-detect
      languageToUse = 'multi';
    }
    
    console.log('='.repeat(80));
    console.log('🚀 App.handleConnect() called');
    console.log(`   • Selected conversation: ${selectedConversationId}`);
    console.log(`   • Language mode: ${languageMode}`);
    console.log(`   • Selected language: ${selectedLanguage.code} (${selectedLanguage.name})`);
    console.log(`   • Language to send: ${languageToUse}`);
    console.log(`   • Assistant to use: ${assistantToUse || 'default (simple_agent)'}`);
    console.log('='.repeat(80));
    
    connect(languageToUse, assistantToUse);
  };

  // Determine if language mode toggle should be shown (wire-transfer, claims-investigation, telco-agent, rbc-fees-agent, and healthcare-agent)
  const showLanguageModeToggle = !connectionState.isConnected && 
    (selectedConversationId === 'wire-transfer' || selectedConversationId === 'claims-investigation' || selectedConversationId === 'telco-agent' || selectedConversationId === 'rbc-fees-agent' || selectedConversationId === 'healthcare-agent');
  
  // Determine if language selector should be shown
  // For wire-transfer: show if in specific mode
  // For claims-investigation: show if in specific mode
  // For telco-agent: show if in specific mode
  // For rbc-fees-agent: show if in specific mode
  // For healthcare-agent: show if in specific mode
  // For language-specific: always show
  const showLanguageSelector = !connectionState.isConnected && (
    (selectedConversationId === 'wire-transfer' && languageMode === 'specific') ||
    (selectedConversationId === 'claims-investigation' && languageMode === 'specific') ||
    (selectedConversationId === 'telco-agent' && languageMode === 'specific') ||
    (selectedConversationId === 'rbc-fees-agent' && languageMode === 'specific') ||
    (selectedConversationId === 'healthcare-agent' && languageMode === 'specific') ||
    selectedConversationId === 'language-specific'
  );

  return (
    <div className="h-screen flex flex-col bg-white dark:bg-gray-900">
      {/* Audio player */}
      {botAudioTrack && <AudioPlayer botAudioTrack={botAudioTrack} />}
      
      {/* Main Container - Full Height */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* NVIDIA Header Bar - Absolute positioned over content */}
        <header className="absolute top-0 left-0 right-0 bg-black px-6 py-3 flex items-center gap-4 shadow-lg z-30">
          {/* NVIDIA Logo */}
          <img 
            src="/images.png" 
            alt="NVIDIA" 
            className="h-12 w-auto object-contain"
          />
          <h1 className="text-xl font-bold" style={{ color: '#76B900' }}>
            Multilingual Voice Agents
          </h1>
          
          {/* Connection Status with Language Indicator */}
          <div className="ml-auto flex items-center gap-4 text-white">
            {/* Architecture Button */}
            <button
              onClick={() => setShowArchitecture(true)}
              className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded-lg border border-gray-700 hover:border-[#76B900]/50 transition-all group"
            >
              <svg className="w-4 h-4 text-gray-400 group-hover:text-[#76B900] transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
              </svg>
              <span className="text-xs font-medium text-gray-400 group-hover:text-white transition-colors">Architecture</span>
            </button>
            
            {/* Language Indicator - only when connected and not in multi mode */}
            {connectionState.isConnected && languageMode === 'specific' && (
              <div className="flex items-center gap-2 px-3 py-1 bg-gray-800 rounded-full border border-gray-700">
                <span className="text-lg">{selectedLanguage.flag}</span>
                <span className="text-xs font-medium">{selectedLanguage.name}</span>
              </div>
            )}
            
            {/* Connection Status */}
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${connectionState.isConnected ? 'bg-[#76B900] animate-pulse' : 'bg-gray-500'}`}></div>
              <span className="text-sm">{connectionState.isConnected ? 'Connected' : 'Disconnected'}</span>
            </div>
          </div>
        </header>

        {/* Left Sidebar - Conversations List - Full Height */}
        <aside className="w-80 flex-shrink-0 border-r border-gray-200 dark:border-gray-700 pt-[72px]">
          <ConversationsList
            conversations={conversations}
            selectedId={selectedConversationId}
            onSelect={handleConversationSelect}
          />
        </aside>

        {/* Main Chat Area - with Agent Info Panel and Footer - Full Height */}
        <main className="flex-1 flex overflow-hidden relative pt-[72px]">
          {/* Chat Display with Footer */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Transcription Display */}
            <div className="flex-1 overflow-hidden">
              <TranscriptionDisplay
                transcriptions={transcriptions}
                onClear={clearTranscriptions}
                conversationTitle={selectedConversation?.name || 'Conversation'}
              />
            </div>
            
            {/* Footer - Voice Controls (only in chat area) */}
            <VoiceControlsFooter
              connectionState={connectionState}
              isMuted={isMuted}
              selectedLanguage={selectedLanguage}
              languageMode={languageMode}
              onLanguageModeChange={setLanguageMode}
              onLanguageChange={setSelectedLanguage}
              onConnect={handleConnect}
              onDisconnect={disconnect}
              onToggleMute={toggleMute}
              showLanguageModeToggle={showLanguageModeToggle}
              showLanguageSelector={showLanguageSelector}
            />
          </div>

          {/* Agent Info Panel - For specialized agents - Full Height */}
          {(selectedConversationId === 'wire-transfer' || selectedConversationId === 'claims-investigation' || selectedConversationId === 'telco-agent' || selectedConversationId === 'rbc-fees-agent' || selectedConversationId === 'healthcare-agent') && (
            <AgentInfoPanel
              isOpen={isAgentInfoOpen}
              onToggle={() => setIsAgentInfoOpen(!isAgentInfoOpen)}
              agentId={
                selectedConversationId === 'wire-transfer' ? 'wire_transfer_agent' :
                selectedConversationId === 'claims-investigation' ? 'claims_investigation_agent' :
                selectedConversationId === 'telco-agent' ? 'telco_agent' :
                selectedConversationId === 'rbc-fees-agent' ? 'rbc_fees_agent' :
                'healthcare_agent'
              }
            />
          )}
        </main>
      </div>
      
      {/* Architecture Page Overlay */}
      {showArchitecture && (
        <ArchitecturePage onClose={() => setShowArchitecture(false)} />
      )}
    </div>
  );
}

export default App;
