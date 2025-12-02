# Quick Setup Guide

## 1. Install Dependencies

```bash
npm install
```

## 2. Configure Backend URL (Optional)

If your backend is not running on `localhost:7860`, create a `.env` file:

```bash
echo "VITE_API_BASE_URL=http://your-backend-url:port" > .env
```

## 3. Start Development Server

```bash
npm run dev
```

Visit `http://localhost:5173`

## 4. Test the Connection

1. Make sure your Python backend is running:
   ```bash
   cd ..
   python pipeline_modern.py
   ```

2. In the UI, click **"Start Voice Chat"**
3. Allow microphone access
4. Start speaking!

## Production Build

To build for production (served by the Python backend):

```bash
npm run build
```

The `dist/` folder will be created and can be served by FastAPI from the parent directory.

## Troubleshooting

### Connection Issues

- ✅ Backend running? Check `http://localhost:7860/health`
- ✅ Microphone permission granted?
- ✅ Check browser console for errors

### No Audio

- ✅ Microphone selected in browser settings?
- ✅ Try refreshing the page
- ✅ Check that no other app is using the microphone

### TypeScript Errors

```bash
npm run build
```

All errors should be resolved. If you see errors, check:
- Node modules installed correctly
- TypeScript version compatible





