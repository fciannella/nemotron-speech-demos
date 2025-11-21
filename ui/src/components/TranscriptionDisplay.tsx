import { useEffect, useRef } from 'react';
import type { TranscriptionMessage } from '../types';

interface TranscriptionDisplayProps {
  transcriptions: TranscriptionMessage[];
  onClear?: () => void;
  conversationTitle?: string;
}

export function TranscriptionDisplay({ transcriptions, onClear, conversationTitle = 'Conversation' }: TranscriptionDisplayProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new transcriptions arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [transcriptions]);

  // Determine subtitle
  const getSubtitle = () => {
    if (transcriptions.length === 0) return 'Start a conversation';
    return 'AI voice assistant';
  };

  return (
    <div className="h-full flex flex-col bg-white dark:bg-gray-900">
      <div className="flex items-center justify-between px-6 py-3 flex-shrink-0 bg-gray-50 dark:bg-gray-800">
        <div className="flex-1">
          <h2 className="text-lg font-medium text-gray-900 dark:text-white">
            {conversationTitle}
          </h2>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {getSubtitle()}
          </p>
        </div>
        {transcriptions.length > 0 && onClear && (
          <button
            onClick={onClear}
            className="px-3 py-1.5 text-xs bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 rounded-md transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-6 py-4 space-y-3"
      >
        {transcriptions.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <p className="text-gray-400 dark:text-gray-500 text-center text-lg">
              Click "Start Voice Chat" and begin speaking
            </p>
          </div>
        ) : (
          transcriptions.map((transcription) => (
            <div
              key={transcription.id}
              className={`flex ${transcription.isUser ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[75%] px-3 py-2 rounded-lg ${
                  transcription.isUser
                    ? 'text-white rounded-br-sm'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white rounded-bl-sm'
                } ${!transcription.isFinal ? 'opacity-70' : ''}`}
                style={transcription.isUser ? { backgroundColor: '#76B900' } : {}}
              >
                <p className="text-sm whitespace-pre-wrap break-words leading-relaxed">
                  {transcription.text}
                </p>
                {!transcription.isFinal && (
                  <span className="text-xs opacity-60 italic mt-1 block">
                    typing...
                  </span>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
