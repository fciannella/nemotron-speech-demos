import { useState, useRef, useEffect } from 'react';
import type { Language } from '../types';

interface LanguageSelectorProps {
  selectedLanguage: Language;
  onLanguageChange: (language: Language) => void;
  disabled?: boolean;
}

export const SUPPORTED_LANGUAGES: Language[] = [
  { code: 'en-US', name: 'English (US)', flag: '🇺🇸' },
  { code: 'es-US', name: 'Spanish (US)', flag: '🇲🇽' },
  { code: 'de-DE', name: 'German', flag: '🇩🇪' },
  { code: 'fr-FR', name: 'French', flag: '🇫🇷' },
  { code: 'zh-CN', name: 'Chinese (Mandarin)', flag: '🇨🇳' },
  // Note: Chinese uses a separate Mandarin-specific ASR endpoint (NVIDIA_ASR_MANDARIN_FUNCTION_ID)
];

export function LanguageSelector({ 
  selectedLanguage, 
  onLanguageChange, 
  disabled = false 
}: LanguageSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const handleLanguageChange = (lang: Language) => {
    console.log(`🌍 Language selected: ${lang.code} (${lang.name}) ${lang.flag}`);
    onLanguageChange(lang);
    setIsOpen(false);
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Dropdown Button */}
      <button
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        className={`px-4 py-2 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-900 dark:text-white font-medium rounded-full transition-colors flex items-center gap-2 border border-gray-300 dark:border-gray-600 ${
          disabled ? 'opacity-50 cursor-not-allowed' : ''
        }`}
      >
        <span className="text-xl">{selectedLanguage.flag}</span>
        <span className="text-sm">{selectedLanguage.name}</span>
        <svg 
          className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} 
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Dropdown Menu (Drop-up) */}
      {isOpen && (
        <div className="absolute bottom-full left-0 mb-2 w-64 bg-white dark:bg-gray-800 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 overflow-hidden z-50">
          {SUPPORTED_LANGUAGES.map((lang) => (
            <button
              key={lang.code}
              onClick={() => handleLanguageChange(lang)}
              className={`w-full px-4 py-3 flex items-center gap-3 transition-colors ${
                selectedLanguage.code === lang.code
                  ? 'bg-[#76B900] text-white'
                  : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-900 dark:text-white'
              }`}
            >
              <span className="text-2xl">{lang.flag}</span>
              <div className="flex-1 text-left">
                <div className="font-medium">{lang.name}</div>
                <div className={`text-xs ${
                  selectedLanguage.code === lang.code ? 'text-white/80' : 'text-gray-500 dark:text-gray-400'
                }`}>
                  {lang.code}
                </div>
              </div>
              {selectedLanguage.code === lang.code && (
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

