# KEMSININ-DUBBER-AI-VIDEO

AI Video Voice Over Studio with real-time WebSocket support, Whisper speech-to-text, neural translation, Edge-TTS/GPT-SoVITS voice synthesis, interactive timeline editor, Electron desktop support, and Android APK deployment.

## Features
- **Speech-to-Text**: Automatic transcription with OpenAI Whisper.
- **Multilingual Dubbing**: Neural machine translation with timing preservation.
- **Voice Synthesis**: Natural Edge-TTS and GPT-SoVITS voice cloning.
- **Interactive Timeline Editor**: Real-time subtitle editing and segment adjustments.
- **Multi-Platform**: Web Studio, Electron Desktop application, and Android APK build via Capacitor.

## Getting Started

### 1. Backend Setup
```bash
python -m venv .venv
# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

### 2. Run Web UI
Access the application directly at `http://localhost:8000` or open `index.html`.

### 3. Android APK
```bash
npm install
npm run sync
npm run build:apk
```
The compiled APK will be located at `android/app/build/outputs/apk/debug/app-debug.apk`.
