import { useState } from 'react';

interface ArchitecturePageProps {
  onClose: () => void;
}

type ComponentId = 'ui' | 'pipecat' | 'stt' | 'tts' | 'langgraph' | 'agents' | 'webrtc' | null;

interface ComponentInfo {
  title: string;
  description: string;
  tech: string[];
  color: string;
  icon: string;
  docsUrl?: string;
  docsLabel?: string;
}

// Generate QR code URL using free API
const getQRCodeUrl = (url: string, size: number = 150) => {
  return `https://api.qrserver.com/v1/create-qr-code/?size=${size}x${size}&data=${encodeURIComponent(url)}&bgcolor=1a1a2e&color=ffffff`;
};

const componentDetails: Record<string, ComponentInfo> = {
  ui: {
    title: 'React UI',
    icon: '⚛️',
    description: 'Modern web interface built with React 19 and TypeScript. Provides real-time transcription display, voice controls, language selection, and conversation management. Connects to the backend via WebRTC for ultra-low latency audio streaming.',
    tech: ['React 19', 'TypeScript', 'Tailwind CSS', 'Vite', '@pipecat-ai/client-js'],
    color: '#61DAFB',
    docsUrl: 'https://react.dev/',
    docsLabel: 'React Documentation'
  },
  webrtc: {
    title: 'WebRTC Transport',
    icon: '📡',
    description: 'Real-time audio/video communication protocol enabling peer-to-peer streaming between browser and server. Provides <100ms latency for voice interactions with built-in echo cancellation and noise suppression.',
    tech: ['SmallWebRTC', 'ICE/STUN/TURN', 'Opus Codec', 'MediaStream API'],
    color: '#FF6B6B',
    docsUrl: 'https://webrtc.org/',
    docsLabel: 'WebRTC Documentation'
  },
  pipecat: {
    title: 'Pipecat Pipeline',
    icon: '🎙️',
    description: 'Open-source framework for building voice AI applications. Orchestrates the flow of audio frames through STT, LLM, and TTS processors. Handles interruption, VAD (Voice Activity Detection), and conversation context management.',
    tech: ['Pipecat AI', 'FastAPI', 'Uvicorn', 'Python asyncio', 'Silero VAD'],
    color: '#76B900',
    docsUrl: 'https://github.com/pipecat-ai/pipecat',
    docsLabel: 'Pipecat GitHub'
  },
  stt: {
    title: 'NVIDIA Riva STT',
    icon: '🎤',
    description: 'State-of-the-art Speech-to-Text powered by NVIDIA Riva. Supports real-time streaming ASR with multilingual capabilities (English, Spanish, French, German, Mandarin). Features automatic language detection and punctuation.',
    tech: ['Riva ASR', 'Parakeet 1.1B', 'gRPC Streaming', 'Multilingual'],
    color: '#FFD93D',
    docsUrl: 'https://catalog.ngc.nvidia.com/orgs/nim/teams/nvidia/containers/parakeet-ctc-1.1b-asr?version=1.0.0',
    docsLabel: 'NVIDIA NGC Catalog'
  },
  tts: {
    title: 'NVIDIA Riva TTS',
    icon: '🔊',
    description: 'High-quality Text-to-Speech synthesis using NVIDIA Magpie multilingual model. Produces natural, expressive speech with support for multiple voices and languages. Streams audio in real-time for instant responses.',
    tech: ['Riva TTS', 'Magpie Multilingual', 'Neural TTS', '16kHz Audio'],
    color: '#6BCB77',
    docsUrl: 'https://catalog.ngc.nvidia.com/orgs/nim/teams/nvidia/containers/magpie-tts-multilingual?version=latest',
    docsLabel: 'NVIDIA NGC Catalog'
  },
  langgraph: {
    title: 'LangGraph Service',
    icon: '🧠',
    description: 'Custom Pipecat LLM service that bridges to LangGraph agents. Manages conversation threads, handles message streaming, and routes to appropriate specialized agents based on conversation type.',
    tech: ['LangGraph SDK', 'LangChain', 'Thread Management', 'Streaming API'],
    color: '#9B59B6',
    docsUrl: 'https://www.langchain.com/langgraph',
    docsLabel: 'LangGraph Documentation'
  },
  agents: {
    title: 'Specialized AI Agents',
    icon: '🤖',
    description: 'Domain-specific conversational agents built with LangGraph. Each agent has specialized knowledge, tools, and conversation flows for their domain: Healthcare (symptom triage), Wire Transfer (banking), Telco (mobile plans), Banking Fees, and Claims Investigation.',
    tech: ['GPT-4o-mini', 'ReAct Pattern', 'Tool Calling', 'Mock Data'],
    color: '#E74C3C',
    docsUrl: 'https://www.langchain.com/langgraph',
    docsLabel: 'LangGraph Documentation'
  }
};

export function ArchitecturePage({ onClose }: ArchitecturePageProps) {
  // Default to STT (Riva ASR) panel open
  const [selectedComponent, setSelectedComponent] = useState<ComponentId>('stt');
  const [hoveredComponent, setHoveredComponent] = useState<ComponentId>(null);

  const activeComponent = selectedComponent || hoveredComponent;

  const handleComponentClick = (componentId: ComponentId) => {
    setSelectedComponent(selectedComponent === componentId ? null : componentId);
  };

  const closeDetailPanel = () => {
    setSelectedComponent(null);
  };

  return (
    <div className="fixed inset-0 bg-[#0a0a0f] z-50 flex flex-col overflow-hidden">
      {/* Background Grid Pattern */}
      <div className="absolute inset-0 opacity-10 pointer-events-none">
        <div 
          className="w-full h-full"
          style={{
            backgroundImage: `
              linear-gradient(rgba(118, 185, 0, 0.1) 1px, transparent 1px),
              linear-gradient(90deg, rgba(118, 185, 0, 0.1) 1px, transparent 1px)
            `,
            backgroundSize: '50px 50px'
          }}
        />
      </div>

      {/* Header */}
      <header className="relative bg-black px-6 py-3 flex items-center justify-between sticky top-0 z-10 shadow-lg">
        <div className="flex items-center gap-4">
          <img src="/images.png" alt="NVIDIA" className="h-12 w-auto object-contain" />
          <h1 className="text-xl font-bold" style={{ color: '#76B900' }}>
            System Architecture
          </h1>
        </div>
        <button
          onClick={onClose}
          className="flex items-center gap-2 px-4 py-2 bg-[#76B900] hover:bg-[#8fd000] text-black font-semibold rounded-lg transition-all"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to Chat
        </button>
      </header>

      <div className="relative flex-1 flex p-4 gap-4">
        {/* Architecture Diagram */}
        <div className="flex-1 relative bg-gradient-to-br from-[#12121a] to-[#1a1a2e] rounded-2xl p-4 border border-gray-800 overflow-auto min-h-0">
            {/* Animated Background Particles */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
              {[...Array(20)].map((_, i) => (
                <div
                  key={i}
                  className="absolute w-1 h-1 bg-[#76B900]/30 rounded-full animate-pulse"
                  style={{
                    left: `${Math.random() * 100}%`,
                    top: `${Math.random() * 100}%`,
                    animationDelay: `${Math.random() * 2}s`,
                    animationDuration: `${2 + Math.random() * 2}s`
                  }}
                />
              ))}
            </div>

            {/* SVG Diagram */}
            <svg viewBox="0 0 1000 700" className="w-full relative z-10" style={{ minHeight: '600px', height: 'auto' }} preserveAspectRatio="xMidYMid meet">
              {/* Define gradients and filters */}
              <defs>
                <linearGradient id="flowGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#76B900" stopOpacity="0.2" />
                  <stop offset="50%" stopColor="#76B900" stopOpacity="1" />
                  <stop offset="100%" stopColor="#76B900" stopOpacity="0.2" />
                </linearGradient>
                <filter id="glow">
                  <feGaussianBlur stdDeviation="3" result="coloredBlur" />
                  <feMerge>
                    <feMergeNode in="coloredBlur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
                <filter id="dropShadow">
                  <feDropShadow dx="0" dy="4" stdDeviation="4" floodOpacity="0.3" />
                </filter>
                <filter id="selectedGlow">
                  <feGaussianBlur stdDeviation="6" result="coloredBlur" />
                  <feMerge>
                    <feMergeNode in="coloredBlur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>

              {/* Connection Lines - Animated Flow */}
              {/* UI to WebRTC */}
              <path
                d="M 150 150 Q 250 150 250 200"
                fill="none"
                stroke={activeComponent === 'ui' || activeComponent === 'webrtc' ? '#76B900' : '#333'}
                strokeWidth="3"
                strokeDasharray="8,4"
                className="transition-all duration-300"
              >
                <animate attributeName="stroke-dashoffset" from="24" to="0" dur="1s" repeatCount="indefinite" />
              </path>

              {/* WebRTC to Pipecat */}
              <path
                d="M 350 200 L 400 200"
                fill="none"
                stroke={activeComponent === 'webrtc' || activeComponent === 'pipecat' ? '#76B900' : '#333'}
                strokeWidth="3"
                strokeDasharray="8,4"
                className="transition-all duration-300"
              >
                <animate attributeName="stroke-dashoffset" from="24" to="0" dur="1s" repeatCount="indefinite" />
              </path>

              {/* Pipecat to STT */}
              <path
                d="M 500 150 L 500 80"
                fill="none"
                stroke={activeComponent === 'pipecat' || activeComponent === 'stt' ? '#FFD93D' : '#333'}
                strokeWidth="3"
                strokeDasharray="8,4"
                className="transition-all duration-300"
              >
                <animate attributeName="stroke-dashoffset" from="24" to="0" dur="0.8s" repeatCount="indefinite" />
              </path>

              {/* Pipecat to TTS */}
              <path
                d="M 500 250 L 500 320"
                fill="none"
                stroke={activeComponent === 'pipecat' || activeComponent === 'tts' ? '#6BCB77' : '#333'}
                strokeWidth="3"
                strokeDasharray="8,4"
                className="transition-all duration-300"
              >
                <animate attributeName="stroke-dashoffset" from="0" to="24" dur="0.8s" repeatCount="indefinite" />
              </path>

              {/* Pipecat to LangGraph */}
              <path
                d="M 600 200 L 700 200"
                fill="none"
                stroke={activeComponent === 'pipecat' || activeComponent === 'langgraph' ? '#9B59B6' : '#333'}
                strokeWidth="3"
                strokeDasharray="8,4"
                className="transition-all duration-300"
              >
                <animate attributeName="stroke-dashoffset" from="24" to="0" dur="1s" repeatCount="indefinite" />
              </path>

              {/* LangGraph to Agents */}
              <path
                d="M 800 250 L 800 380"
                fill="none"
                stroke={activeComponent === 'langgraph' || activeComponent === 'agents' ? '#E74C3C' : '#333'}
                strokeWidth="3"
                strokeDasharray="8,4"
                className="transition-all duration-300"
              >
                <animate attributeName="stroke-dashoffset" from="24" to="0" dur="0.8s" repeatCount="indefinite" />
              </path>

              {/* User Icon */}
              <g transform="translate(100, 100)">
                <circle cx="0" cy="0" r="30" fill="#1a1a2e" stroke="#61DAFB" strokeWidth="2" />
                <circle cx="0" cy="-8" r="10" fill="#61DAFB" />
                <path d="M -15 15 Q 0 5 15 15" fill="none" stroke="#61DAFB" strokeWidth="3" />
                <text x="0" y="55" textAnchor="middle" fill="#888" fontSize="12">User</text>
              </g>

              {/* UI Component */}
              <g
                transform="translate(50, 130)"
                onClick={() => handleComponentClick('ui')}
                onMouseEnter={() => setHoveredComponent('ui')}
                onMouseLeave={() => setHoveredComponent(null)}
                style={{ cursor: 'pointer' }}
                filter={selectedComponent === 'ui' ? 'url(#selectedGlow)' : 'url(#dropShadow)'}
              >
                <rect
                  x="0" y="0" width="100" height="60" rx="8"
                  fill={activeComponent === 'ui' ? '#1e3a5f' : '#1a1a2e'}
                  stroke="#61DAFB"
                  strokeWidth={selectedComponent === 'ui' ? '4' : activeComponent === 'ui' ? '3' : '2'}
                  style={{ transition: 'all 0.3s' }}
                />
                <text x="50" y="25" textAnchor="middle" fill="#61DAFB" fontSize="12" fontWeight="bold" style={{ pointerEvents: 'none' }}>React</text>
                <text x="50" y="42" textAnchor="middle" fill="#61DAFB" fontSize="11" style={{ pointerEvents: 'none' }}>UI</text>
              </g>

              {/* WebRTC Component */}
              <g
                transform="translate(200, 170)"
                onClick={() => handleComponentClick('webrtc')}
                onMouseEnter={() => setHoveredComponent('webrtc')}
                onMouseLeave={() => setHoveredComponent(null)}
                style={{ cursor: 'pointer' }}
                filter={selectedComponent === 'webrtc' ? 'url(#selectedGlow)' : 'url(#dropShadow)'}
              >
                <rect
                  x="0" y="0" width="150" height="60" rx="8"
                  fill={activeComponent === 'webrtc' ? '#3d1f1f' : '#1a1a2e'}
                  stroke="#FF6B6B"
                  strokeWidth={selectedComponent === 'webrtc' ? '4' : activeComponent === 'webrtc' ? '3' : '2'}
                  style={{ transition: 'all 0.3s' }}
                />
                <text x="75" y="25" textAnchor="middle" fill="#FF6B6B" fontSize="12" fontWeight="bold" style={{ pointerEvents: 'none' }}>WebRTC</text>
                <text x="75" y="42" textAnchor="middle" fill="#FF6B6B" fontSize="11" style={{ pointerEvents: 'none' }}>Transport</text>
              </g>

              {/* Pipecat Component */}
              <g
                transform="translate(400, 150)"
                onClick={() => handleComponentClick('pipecat')}
                onMouseEnter={() => setHoveredComponent('pipecat')}
                onMouseLeave={() => setHoveredComponent(null)}
                style={{ cursor: 'pointer' }}
                filter={selectedComponent === 'pipecat' ? 'url(#selectedGlow)' : 'url(#dropShadow)'}
              >
                <rect
                  x="0" y="0" width="200" height="100" rx="12"
                  fill={activeComponent === 'pipecat' ? '#1e3d1e' : '#1a1a2e'}
                  stroke="#76B900"
                  strokeWidth={selectedComponent === 'pipecat' ? '5' : activeComponent === 'pipecat' ? '4' : '2'}
                  style={{ transition: 'all 0.3s' }}
                />
                <text x="100" y="35" textAnchor="middle" fill="#76B900" fontSize="14" fontWeight="bold" style={{ pointerEvents: 'none' }}>🎙️ Pipecat</text>
                <text x="100" y="55" textAnchor="middle" fill="#76B900" fontSize="12" style={{ pointerEvents: 'none' }}>Voice Pipeline</text>
                <text x="100" y="75" textAnchor="middle" fill="#666" fontSize="10" style={{ pointerEvents: 'none' }}>STT → LLM → TTS</text>
              </g>

              {/* NVIDIA Riva STT */}
              <g
                transform="translate(420, 20)"
                onClick={() => handleComponentClick('stt')}
                onMouseEnter={() => setHoveredComponent('stt')}
                onMouseLeave={() => setHoveredComponent(null)}
                style={{ cursor: 'pointer' }}
                filter={selectedComponent === 'stt' ? 'url(#selectedGlow)' : 'url(#dropShadow)'}
              >
                <rect
                  x="0" y="0" width="160" height="55" rx="8"
                  fill={activeComponent === 'stt' ? '#3d3d1a' : '#1a1a2e'}
                  stroke="#FFD93D"
                  strokeWidth={selectedComponent === 'stt' ? '4' : activeComponent === 'stt' ? '3' : '2'}
                  style={{ transition: 'all 0.3s' }}
                />
                <text x="80" y="22" textAnchor="middle" fill="#FFD93D" fontSize="11" fontWeight="bold" style={{ pointerEvents: 'none' }}>🎤 NVIDIA Riva</text>
                <text x="80" y="40" textAnchor="middle" fill="#FFD93D" fontSize="10" style={{ pointerEvents: 'none' }}>Speech-to-Text</text>
              </g>

              {/* NVIDIA Riva TTS */}
              <g
                transform="translate(420, 325)"
                onClick={() => handleComponentClick('tts')}
                onMouseEnter={() => setHoveredComponent('tts')}
                onMouseLeave={() => setHoveredComponent(null)}
                style={{ cursor: 'pointer' }}
                filter={selectedComponent === 'tts' ? 'url(#selectedGlow)' : 'url(#dropShadow)'}
              >
                <rect
                  x="0" y="0" width="160" height="55" rx="8"
                  fill={activeComponent === 'tts' ? '#1a3d2a' : '#1a1a2e'}
                  stroke="#6BCB77"
                  strokeWidth={selectedComponent === 'tts' ? '4' : activeComponent === 'tts' ? '3' : '2'}
                  style={{ transition: 'all 0.3s' }}
                />
                <text x="80" y="22" textAnchor="middle" fill="#6BCB77" fontSize="11" fontWeight="bold" style={{ pointerEvents: 'none' }}>🔊 NVIDIA Riva</text>
                <text x="80" y="40" textAnchor="middle" fill="#6BCB77" fontSize="10" style={{ pointerEvents: 'none' }}>Text-to-Speech</text>
              </g>

              {/* LangGraph Service */}
              <g
                transform="translate(700, 150)"
                onClick={() => handleComponentClick('langgraph')}
                onMouseEnter={() => setHoveredComponent('langgraph')}
                onMouseLeave={() => setHoveredComponent(null)}
                style={{ cursor: 'pointer' }}
                filter={selectedComponent === 'langgraph' ? 'url(#selectedGlow)' : 'url(#dropShadow)'}
              >
                <rect
                  x="0" y="0" width="200" height="100" rx="12"
                  fill={activeComponent === 'langgraph' ? '#2d1a3d' : '#1a1a2e'}
                  stroke="#9B59B6"
                  strokeWidth={selectedComponent === 'langgraph' ? '5' : activeComponent === 'langgraph' ? '4' : '2'}
                  style={{ transition: 'all 0.3s' }}
                />
                <text x="100" y="35" textAnchor="middle" fill="#9B59B6" fontSize="14" fontWeight="bold" style={{ pointerEvents: 'none' }}>🧠 LangGraph</text>
                <text x="100" y="55" textAnchor="middle" fill="#9B59B6" fontSize="12" style={{ pointerEvents: 'none' }}>LLM Service</text>
                <text x="100" y="75" textAnchor="middle" fill="#666" fontSize="10" style={{ pointerEvents: 'none' }}>Thread Management</text>
              </g>

              {/* Agents */}
              <g transform="translate(650, 400)">
                <g
                  onClick={() => handleComponentClick('agents')}
                  onMouseEnter={() => setHoveredComponent('agents')}
                  onMouseLeave={() => setHoveredComponent(null)}
                  style={{ cursor: 'pointer' }}
                  filter={selectedComponent === 'agents' ? 'url(#selectedGlow)' : 'url(#dropShadow)'}
                >
                  <rect
                    x="0" y="0" width="300" height="160" rx="12"
                    fill={activeComponent === 'agents' ? '#3d1a1a' : '#1a1a2e'}
                    stroke="#E74C3C"
                    strokeWidth={selectedComponent === 'agents' ? '5' : activeComponent === 'agents' ? '4' : '2'}
                    style={{ transition: 'all 0.3s' }}
                  />
                  <text x="150" y="25" textAnchor="middle" fill="#E74C3C" fontSize="13" fontWeight="bold" style={{ pointerEvents: 'none' }}>🤖 Specialized Agents</text>
                  
                  {/* Agent Icons */}
                  <g transform="translate(25, 45)" style={{ pointerEvents: 'none' }}>
                    <rect x="0" y="0" width="75" height="45" rx="6" fill="#2a2a3a" stroke="#666" />
                    <text x="37.5" y="20" textAnchor="middle" fill="#fff" fontSize="16">🏥</text>
                    <text x="37.5" y="38" textAnchor="middle" fill="#888" fontSize="8">Healthcare</text>
                  </g>
                  <g transform="translate(112.5, 45)" style={{ pointerEvents: 'none' }}>
                    <rect x="0" y="0" width="75" height="45" rx="6" fill="#2a2a3a" stroke="#666" />
                    <text x="37.5" y="20" textAnchor="middle" fill="#fff" fontSize="16">💳</text>
                    <text x="37.5" y="38" textAnchor="middle" fill="#888" fontSize="8">Wire Transfer</text>
                  </g>
                  <g transform="translate(200, 45)" style={{ pointerEvents: 'none' }}>
                    <rect x="0" y="0" width="75" height="45" rx="6" fill="#2a2a3a" stroke="#666" />
                    <text x="37.5" y="20" textAnchor="middle" fill="#fff" fontSize="16">📱</text>
                    <text x="37.5" y="38" textAnchor="middle" fill="#888" fontSize="8">Telco</text>
                  </g>
                  <g transform="translate(25, 100)" style={{ pointerEvents: 'none' }}>
                    <rect x="0" y="0" width="75" height="45" rx="6" fill="#2a2a3a" stroke="#666" />
                    <text x="37.5" y="20" textAnchor="middle" fill="#fff" fontSize="16">💰</text>
                    <text x="37.5" y="38" textAnchor="middle" fill="#888" fontSize="8">Banking Fees</text>
                  </g>
                  <g transform="translate(112.5, 100)" style={{ pointerEvents: 'none' }}>
                    <rect x="0" y="0" width="75" height="45" rx="6" fill="#2a2a3a" stroke="#666" />
                    <text x="37.5" y="20" textAnchor="middle" fill="#fff" fontSize="16">🔍</text>
                    <text x="37.5" y="38" textAnchor="middle" fill="#888" fontSize="8">Claims</text>
                  </g>
                  <g transform="translate(200, 100)" style={{ pointerEvents: 'none' }}>
                    <rect x="0" y="0" width="75" height="45" rx="6" fill="#2a2a3a" stroke="#666" />
                    <text x="37.5" y="20" textAnchor="middle" fill="#fff" fontSize="16">💬</text>
                    <text x="37.5" y="38" textAnchor="middle" fill="#888" fontSize="8">Simple Chat</text>
                  </g>
                </g>
              </g>


              {/* Legend */}
              <g transform="translate(30, 620)">
                <text fill="#888" fontSize="11" fontWeight="bold">Data Flow:</text>
                <line x1="0" y1="20" x2="30" y2="20" stroke="#76B900" strokeWidth="2" strokeDasharray="8,4" />
                <text x="40" y="24" fill="#666" fontSize="10">Real-time streaming</text>
              </g>
            </svg>
          </div>

        {/* Detail Panel - Slide in from right */}
        <div 
          className={`
            ${selectedComponent ? 'w-96 opacity-100' : 'w-0 opacity-0'} 
            transition-all duration-300 ease-in-out overflow-hidden
          `}
        >
          {selectedComponent && componentDetails[selectedComponent] && (
            <div 
              className="h-full bg-gradient-to-br from-[#12121a] to-[#1a1a2e] rounded-2xl border border-gray-800 p-6 flex flex-col"
              style={{ borderColor: `${componentDetails[selectedComponent].color}40` }}
            >
              {/* Close Button */}
              <button
                onClick={closeDetailPanel}
                className="absolute top-2 right-2 p-2 text-gray-500 hover:text-white transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>

              {/* Header */}
              <div className="mb-6">
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-3xl">{componentDetails[selectedComponent].icon}</span>
                  <h2 
                    className="text-2xl font-bold"
                    style={{ color: componentDetails[selectedComponent].color }}
                  >
                    {componentDetails[selectedComponent].title}
                  </h2>
                </div>
                <div 
                  className="h-1 rounded-full w-20"
                  style={{ backgroundColor: componentDetails[selectedComponent].color }}
                />
              </div>

              {/* Description */}
              <div className="flex-1 overflow-y-auto">
                <h3 className="text-sm font-semibold text-gray-400 mb-2 uppercase tracking-wider">Overview</h3>
                <p className="text-gray-300 leading-relaxed mb-6 text-sm">
                  {componentDetails[selectedComponent].description}
                </p>

                {/* Technologies */}
                <h3 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wider">Technologies</h3>
                <div className="flex flex-wrap gap-2 mb-6">
                  {componentDetails[selectedComponent].tech.map((tech) => (
                    <span
                      key={tech}
                      className="px-3 py-1.5 rounded-lg text-sm font-medium"
                      style={{
                        backgroundColor: `${componentDetails[selectedComponent].color}15`,
                        color: componentDetails[selectedComponent].color,
                        border: `1px solid ${componentDetails[selectedComponent].color}30`
                      }}
                    >
                      {tech}
                    </span>
                  ))}
                </div>

                {/* QR Code for Documentation */}
                {componentDetails[selectedComponent].docsUrl && (
                  <div className="mt-4">
                    <h3 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wider">Documentation</h3>
                    <div 
                      className="bg-black/40 rounded-xl p-4 border border-gray-700 flex flex-col items-center"
                      style={{ borderColor: `${componentDetails[selectedComponent].color}30` }}
                    >
                      {/* QR Code */}
                      <div className="bg-white p-2 rounded-lg mb-3">
                        <img 
                          src={getQRCodeUrl(componentDetails[selectedComponent].docsUrl!, 120)}
                          alt={`QR Code for ${componentDetails[selectedComponent].title} documentation`}
                          className="w-[120px] h-[120px]"
                        />
                      </div>
                      
                      {/* Label */}
                      <p className="text-xs text-gray-400 mb-2 text-center">
                        Scan to view documentation
                      </p>
                      
                      {/* Link */}
                      <a
                        href={componentDetails[selectedComponent].docsUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all hover:scale-105"
                        style={{
                          backgroundColor: `${componentDetails[selectedComponent].color}20`,
                          color: componentDetails[selectedComponent].color,
                          border: `1px solid ${componentDetails[selectedComponent].color}40`
                        }}
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                        </svg>
                        {componentDetails[selectedComponent].docsLabel}
                      </a>
                    </div>
                  </div>
                )}
              </div>

              {/* Footer hint */}
              <div className="mt-4 pt-4 border-t border-gray-800">
                <p className="text-xs text-gray-500 text-center">
                  Click another component or click again to close
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
