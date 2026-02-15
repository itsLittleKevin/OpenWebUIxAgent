# VSeeFace Audio Configuration Guide

## Overview
VSeeFace will read audio from the **VB-Audio Virtual Cable (CABLE Input)** to synchronize avatar mouth movements with TTS audio output.

## Architecture

```
┌─────────────────────────────────────────────┐
│ Open WebUI                                  │
│  └─ Auto-TTS: GPT-SoVITS @ localhost:9880   │
└──────────────┬──────────────────────────────┘
               │ (TTS audio MP3/WAV)
               ↓
┌──────────────────────────────────┐
│ Audio Router Service             │
│ (localhost:8765)                  │
│  ├─ Sends to Speakers (Device 9) │
│  └─ Sends to CABLE OUT (Device 10)
└──────────────┬───────────────────┘
               │ (Virtual Cable)
               ↓
┌──────────────────────────────────┐
│ VB-Audio Virtual Cable           │
│ ├─ CABLE Output (write end)      │
│ └─ CABLE Input (read end) ◄──────┤─ VSeeFace reads here
└──────────────────────────────────┘
```

## VSeeFace Setup Steps

### 1. Open VSeeFace Settings
- Launch VSeeFace
- Go to **Menu** → **Settings**

### 2. Audio Input Configuration
- Find the **Audio Input** section
- In the dropdown, select: **Cable Output**
  > ℹ️ Despite the confusing name, "Cable Output" in VSeeFace's input dropdown refers to reading from the CABLE virtual cable. This is the correct choice.
- Ensure the audio levels are being detected (you should see a waveform when audio plays)

### 3. Test with Auto-TTS

#### Start services with full pipeline:
```powershell
cd d:\Projects\Clusters\Agent
.\config\launch.ps1 -WithVoiceTTS -WithAudioRouter
```

#### Test the flow:
1. Open http://localhost:5173 in your browser
2. Navigate to a chat conversation
3. Use voice input to speak (STT via Whisper)
4. Get an LLM response (it should auto-speak via GPT-SoVITS)
5. Watch VSeeFace avatar mouth move in sync

## Troubleshooting

### No audio in VSeeFace
- **Check device in VSeeFace**: Verify "Cable Output" is selected in Audio Input dropdown
- **Check Audio Router**: Ensure `.\config\audio-router-launch.ps1 -Test` plays sound from both speakers and headphones
- **Check GPT-SoVITS**: Test at http://localhost:9880 with sample text request

### Audio latency issues
- VSeeFace may have slight delay (1-2 seconds) before mouth sync starts
- This is normal - it's detecting audio onset
- If delay is too large, check network latency between services

### VSeeFace shows no waveform even though audio plays
- Right-click VSeeFace settings and try different audio input devices
- Ensure "Cable Output" is the one without echoing to speakers (monitoring disabled)

## Device Mapping Reference

**Identified on this system:**
- **CABLE Output (Write)**: Device 10 - Virtual cable for TTS output
- **CABLE Input (Read)**: Same Device 10 - VSeeFace reads from this
- **Speaker**: Device 9 - USB Audio Device (for hearing TTS while avatar speaks)

## Testing Individual Services

### Test GPT-SoVITS TTS:
```powershell
$body = '{"text": "hello world", "text_language": "en"}'
Invoke-WebRequest -Uri "http://localhost:9880/" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body `
  -OutFile "test_audio.wav"

# test_audio.wav now contains synthesized speech
```

### Test Audio Router:
```powershell
cd d:\Projects\Clusters\Agent
.\config\audio-router-launch.ps1 -Test
# Should play 440Hz tone through both Speakers and CABLE
```

### Test end-to-end voice → text → speech → avatar:
1. Start all services: `.\config\launch.ps1 -WithVoiceTTS -WithAudioRouter`  
2. In browser, click the microphone icon and speak
3. Wait for LLM response
4. Watch VSeeFace avatar mouth move

## Service Ports Reference

| Service | Port | Purpose |
|---------|------|---------|
| Ollama | 11434 | LLM inference |
| Open WebUI Backend | 8080 | API & TTS requests |
| Open WebUI Frontend | 5173 | Web interface |
| GPT-SoVITS | 9880 | Voice synthesis |
| Audio Router | 8765 | Dual-output audio routing |

## Open WebUI Audio Configuration

Verify Open WebUI is configured to use GPT-SoVITS:
1. Go to http://localhost:5173 → Admin → Settings → Audio
2. **Text-to-Speech Engine**: Select "GPT-SoVITS (Local)"
3. **API Base URL**: `http://localhost:9880`
4. Click save

## Next Steps

Once everything is working:
- VSeeFace will automatically sync when you use voice input
- The avatar's mouth will move during TTS playback
- You can train a GPT-SoVITS voice model for custom voice cloning
