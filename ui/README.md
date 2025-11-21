# Pipecat Nemotron Demos - UI

A modern React TypeScript UI for the Pipecat Nemotron project with real-time WebRTC voice interaction and transcription display.

## Tech Stack

- **React 18** - Modern React with hooks
- **TypeScript** - Type-safe development
- **Vite 7** - Lightning-fast build tool and dev server
- **Tailwind CSS 3** - Utility-first CSS framework
- **Pipecat Client** - WebRTC voice integration
- **PostCSS** - CSS transformations

## Features

✅ Real-time WebRTC voice communication  
✅ Live transcription display (user & bot)  
✅ Voice controls (connect, disconnect, mute/unmute)  
✅ Interim and final transcription support  
✅ Session statistics  
✅ Beautiful, responsive UI with dark mode support  
✅ Automatic scroll to latest transcriptions  

## Getting Started

### Prerequisites

- Node.js 20.18.1 or later
- Running Pipecat backend on `localhost:7860` (or configured URL)

### Install Dependencies

```bash
npm install
```

### Configuration

Create a `.env` file (or use the default):

```bash
VITE_API_BASE_URL=http://localhost:7860
```

The default configuration connects to `localhost:7860`. Modify this if your backend is running on a different host/port.

### Development Server

Start the development server with hot module replacement:

```bash
npm run dev
```

The app will be available at `http://localhost:5173`

### Build for Production

Create an optimized production build:

```bash
npm run build
```

The build output will be in the `dist` directory, which can be served by the Python backend at `/`.

### Preview Production Build

Preview the production build locally:

```bash
npm run preview
```

## Project Structure

```
ui/
├── src/
│   ├── components/
│   │   ├── TranscriptionDisplay.tsx  # Real-time transcription viewer
│   │   └── VoiceControls.tsx         # Voice connection controls
│   ├── hooks/
│   │   └── usePipecatClient.ts       # Pipecat WebRTC client hook
│   ├── types/
│   │   └── index.ts                  # TypeScript type definitions
│   ├── App.tsx                       # Main application component
│   ├── main.tsx                      # Application entry point
│   └── index.css                     # Tailwind CSS directives
├── public/                            # Static assets
├── .env                               # Environment configuration
├── index.html                         # HTML template
├── vite.config.ts                     # Vite configuration
├── postcss.config.js                  # PostCSS configuration
├── tailwind.config.ts                 # Tailwind CSS configuration
├── tsconfig.json                      # TypeScript configuration
└── package.json                       # Dependencies and scripts
```

## Usage

### Starting a Voice Session

1. **Open the UI** in your browser (`http://localhost:5173` in dev mode)
2. **Click "Start Voice Chat"** button
3. **Allow microphone access** when prompted by your browser
4. **Start speaking** - your speech will be transcribed and sent to the bot
5. **See transcriptions** appear in real-time for both you and the bot

### During a Session

- **Mute/Unmute**: Click the microphone button to toggle your microphone
- **View Stats**: See message counts in the stats panel
- **Clear Transcriptions**: Click "Clear" to remove all transcriptions
- **End Session**: Click "End Voice Chat" to disconnect

### Troubleshooting

**Connection fails:**
- Ensure the backend is running on `localhost:7860` (or your configured URL)
- Check browser console for WebRTC errors
- Verify microphone permissions are granted

**No transcriptions appearing:**
- Check backend logs for NVIDIA Riva connection issues
- Ensure your NVIDIA API keys are configured in the backend
- Verify VAD (Voice Activity Detection) is working

**Audio issues:**
- Check browser microphone permissions
- Try a different microphone in browser settings
- Ensure no other application is using the microphone

## API Integration

The UI connects to these backend endpoints:

- `GET /rtc-config` - Fetch ICE server configuration
- `POST /api/offer` - WebRTC signaling endpoint
- `WebSocket /ws` - Control messages and transcriptions (optional)

## Development

### Adding New Components

Create components in `src/components/`:

```typescript
// src/components/MyComponent.tsx
export function MyComponent() {
  return <div>My Component</div>;
}
```

### Custom Hooks

Add hooks in `src/hooks/`:

```typescript
// src/hooks/useMyHook.ts
export function useMyHook() {
  // Hook logic
}
```

### TypeScript Types

Define types in `src/types/index.ts`:

```typescript
export interface MyType {
  // Type definition
}
```

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production (includes TypeScript compilation)
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint

## WebRTC Architecture

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Browser   │────────▶│   Pipecat    │────────▶│ NVIDIA Riva │
│     UI      │  WebRTC │   Backend    │   API   │   STT/TTS   │
│             │◀────────│   (Python)   │◀────────│             │
└─────────────┘  Audio  └──────────────┘  Text   └─────────────┘
      │                        │
      │                        │
  Pipecat.js              SmallWebRTCTransport
  Client Library          (aiortc)
```

## Learn More

- [React Documentation](https://react.dev)
- [TypeScript Documentation](https://www.typescriptlang.org)
- [Vite Documentation](https://vite.dev)
- [Tailwind CSS Documentation](https://tailwindcss.com)
- [Pipecat Documentation](https://docs.pipecat.ai)
- [Pipecat JS Client](https://docs.pipecat.ai/client/js)

## Notes

- The project uses Tailwind CSS 3 (stable) instead of v4 (beta) for compatibility
- WebRTC requires HTTPS in production (localhost is exempt)
- Microphone access requires user permission
- ICE servers configuration is fetched from the backend
