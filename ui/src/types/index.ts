export interface TranscriptionMessage {
  id: string;
  text: string;
  isFinal: boolean;
  isUser: boolean;
  timestamp: number;
  baseText?: string; // Original final text before any interim additions
  detectedLanguage?: string; // Detected language code (e.g., 'en-US', 'fr-FR')
}

export interface ConnectionState {
  isConnected: boolean;
  isConnecting: boolean;
  error: string | null;
}

export interface Assistant {
  name: string;
  description?: string;
}

export interface Language {
  code: string;
  name: string;
  flag: string;
}
