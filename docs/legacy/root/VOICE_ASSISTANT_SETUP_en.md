# Voice Text Assistant - Installation and Usage Guide

## Architecture Description

The voice text assistant uses a **backend processing** architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                        Backend Server (Mac/Linux)            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Whisper    │  │  Piper TTS   │  │   PyAudio    │     │
│  │   ASR Model  │  │  Speech Synth│  │Audio Capture │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                 │                 │              │
│         └─────────────────┴─────────────────┘              │
│                           │                                │
│                    ┌──────┴──────┐                         │
│                    │ Tornado WS  │ ← Port 8878            │
│                    │  WebSocket  │                         │
│                    └──────┴──────┘                         │
└───────────────────────────┼─────────────────────────────────┘
                            │
                      WebSocket
                            │
┌───────────────────────────┼─────────────────────────────────┐
│                    Frontend (Phone/Tablet)                  │
│  ┌────────────────────────┴──────────────────────────┐      │
│  │              mobile_voice_text.html              │      │
│  │  - Text display only                             │      │
│  │  - Text command sending only                     │      │
│  │  - No audio processing                          │      │
│  └──────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## Installation Steps

### 1. Install Python Dependencies

```bash
cd /Users/cheenle/UHRR/MRRC

# Install Whisper and other dependencies
pip3 install openai-whisper sounddevice soundfile tornado numpy

# Optional: Install Piper TTS (higher quality speech synthesis)
pip3 install piper-tts
```

### 2. Start Voice Assistant Service

```bash
# Use startup script
./start_voice_assistant.sh

# Or start manually
python3 voice_assistant_service.py --port 8878 --whisper-model base --language zh
```

Parameter description:
- `--port`: Service port, default 8878
- `--whisper-model`: Model size (tiny/base/small/medium/large), default base
- `--language`: Recognition language, default zh (Chinese)

### 3. Access Voice Text Assistant

1. Start MRRC main service
2. Open mobile interface `mobile_modern.html`
3. Click menu → 🎙️ **Voice Text Assistant**
4. Or access directly: `http://<server IP>:<MRRC port>/mobile_voice_text.html`

## Usage Instructions

### Speech Recognition (Radio → Text)

1. Click **"Start"** button to begin recognition
2. Backend automatically captures audio from sound card
3. Recognition results displayed in real-time in "Radio Reception Recognition" area
4. Recognized content automatically added to conversation history

### Speech Synthesis (Text → Radio)

1. Enter text in "Send Reply" box
2. Can select speech speed (slow/normal/fast)
3. Click **"Hold to Transmit"** button to send
4. Backend synthesizes speech and transmits via radio

### Quick Functions

- **⚡ Quick**: Preset common amateur radio phrases
- **🕐 History**: View and quickly select transmission history
- **▶️ Preview**: Use browser TTS for preview (no transmission)
- **⏹️ Stop**: Stop current synthesis and transmission

## Model Selection

| Model | Size | Speed | Accuracy | Use Case |
|-------|------|-------|----------|----------|
| tiny | 39 MB | Fastest | Average | Testing/low-spec devices |
| base | 74 MB | Fast | Good | Daily use recommended |
| small | 244 MB | Medium | Good | High accuracy requirement |
| medium | 769 MB | Slow | Very Good | Professional use |
| large | 1550 MB | Very Slow | Best | Highest accuracy |

**Recommendation**: base model has good balance between accuracy and speed.

## Troubleshooting

### Service Fails to Start

```bash
# Check if port is occupied
lsof -i :8878

# Check if dependencies are installed
pip3 list | grep -E "whisper|sounddevice|tornado"
```

### Cannot Recognize Speech

1. Check if sound card input device is correct
2. Check if system volume is on
3. Check backend logs for errors

### WebSocket Connection Failed

1. Confirm service is started: `curl http://localhost:8878/api/status`
2. Check firewall settings
3. Confirm port is accessible

### Speech Synthesis Failed

1. If Piper TTS is not installed, pyttsx3 (system TTS) will be used
2. Check if system audio output is normal
3. Check backend logs

## Configuration

Can set environment variables:

```bash
export VOICE_PORT=8878          # Service port
export WHISPER_MODEL=base       # Model size
export LANGUAGE=zh              # Recognition language
```

## Integration with MRRC

The voice assistant service runs independently, but can be integrated with MRRC in the following ways:

1. **Frequency Sync**: Automatically display current radio frequency
2. **PTT Control**: Holding transmit button also controls MRRC's PTT
3. **Status Sharing**: Communicate with main page via postMessage

## Tech Stack

- **Backend**: Python 3.8+, Tornado, OpenAI Whisper
- **Frontend**: HTML5, CSS3, Vanilla JS
- **Communication**: WebSocket
- **Audio**: PyAudio, SoundDevice

## Version Information

- **Document Version**: V4.9.0
- **Update Date**: 2026-03-14
- **Corresponding MRRC Version**: V4.9.0

---

## Future Optimizations

- [ ] VAD (Voice Activity Detection) automatic segmentation
- [ ] Noise suppression preprocessing
- [ ] Callsign automatic recognition and logging
- [ ] Multi-language mixed recognition
- [ ] Local LLM intelligent reply suggestions
