# 🎉 Setup Complete! Voice → TTS → Avatar Lip Sync Pipeline

## System Status

Your local AI agent, voice TTS, and avatar lip sync system is now fully configured and deployed.

---

## ✅ What's Been Implemented

### **Phase 1: Auto-TTS Feature** ✓
- ✅ Voice input detection (Whisper STT)
- ✅ Metadata tracking (voice input flag on messages)
- ✅ Auto-trigger TTS when LLM response completes
- ✅ Works with any OpenWebUI-supported TTS engine

### **Phase 2: GPT-SoVITS TTS Deployment** ✓
- ✅ Symlinked GPT-SoVITS from `D:\Projects\Vocal10n\vendor\gpt-sovits`
- ✅ Pre-configured Python environment (venv_tts with 392 packages)
- ✅ Launch script with auto-initialization (`gpt-sovits-launch.ps1`)
- ✅ Endpoint: `http://localhost:9880/`
- ✅ Supports voice cloning (trained models can be added)

### **Phase 3: Audio Router for Virtual Cable** ✓
- ✅ Dual-output audio routing (speakers + CABLE)
- ✅ Device auto-detection (CABLE: Device 10, Speaker: Device 9)
- ✅ HTTP API for programmatic audio playback
- ✅ Test tone generation
- ✅ Graceful retry handling with exponential backoff
- ✅ Endpoint: `http://localhost:8765/`

### **Phase 4: Open WebUI Integration** ✓
- ✅ Added "GPT-SoVITS (Local)" TTS dropdown option
- ✅ Custom API Base URL configuration field
- ✅ Backend handler for GPT-SoVITS requests
- ✅ Configuration persistence
- ✅ Voice/model selection (defaults for local operation)

---

## 🚀 How to Launch

### **Option 1: Full System (Recommended)**
```powershell
cd d:\Projects\Clusters\Agent
.\config\launch.ps1 -WithVoiceTTS -WithAudioRouter
```
Starts:
- ✓ Ollama (LLM inference)
- ✓ Open WebUI Backend (API on port 8080)
- ✓ Open WebUI Frontend (Web UI on port 5173)
- ✓ GPT-SoVITS (Voice synthesis on port 9880)
- ✓ Audio Router (Dual-output on port 8765)

### **Option 2: Without Optional Services**
```powershell
.\config\launch.ps1
```
Only starts Ollama + Open WebUI (no voice TTS or audio routing)

### **Option 3: Only Backend & LLM**
```powershell
.\config\launch.ps1 -BackendOnly
```

### **Option 4: Only Frontend**
```powershell
.\config\launch.ps1 -FrontendOnly
```
(Assumes backend is already running on port 8080)

### **Stop All Services**
```powershell
.\config\launch.ps1 -Stop
```

---

## 📋 Configuration Steps

### **1️⃣ Open WebUI TTS Configuration** (5 minutes)

1. Open http://localhost:5173 in your browser
2. Go to **Admin** → **Settings** → **Audio**
3. Scroll to **Text-to-Speech** section
4. Set:
   - **Text-to-Speech Engine**: Select "**GPT-SoVITS (Local)**"
   - **API Base URL**: `http://localhost:9880`
5. Click **Save**

✅ Open WebUI is now configured to use GPT-SoVITS

### **2️⃣ VSeeFace Audio Input Configuration** (3 minutes)

1. Launch VSeeFace
2. Go to **Settings** (Menu → Settings)
3. Find **Audio Input** section
4. In the dropdown, select: **"Cable Output"**
   - ✓ This reads from the VB-Audio Virtual Cable (CABLE Input)
   - ✓ Our audio router writes to CABLE Output (Device 10)
   - ✓ Same cable, different ends (works correctly)
5. Verify waveform appears when audio plays
6. Close settings

✅ VSeeFace is now listening to the virtual cable

---

## 🧪 Testing the Full Pipeline

### **Test 1: GPT-SoVITS TTS Directly**
```powershell
$body = '{"text": "hello world", "text_language": "en"}'
Invoke-WebRequest -Uri "http://localhost:9880/" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body `
  -OutFile "test_tts.wav"

# Play the generated audio
& "test_tts.wav"
```
✓ Should hear synthesized speech

### **Test 2: Audio Router Dual Output**
```powershell
cd d:\Projects\Clusters\Agent
.\config\audio-router-launch.ps1 -Test
```
✓ Should hear 440Hz tone through both speakers AND virtual cable

### **Test 3: Voice → Text → Speech → Avatar**
1. Go to http://localhost:5173
2. Start a new chat
3. Click the **🎤 Microphone icon** and speak your message
4. Wait for response
5. **Listen**: You should hear the response spoken
6. **Watch VSeeFace**: Avatar's mouth should sync with audio

✓ If all 3 work, the full pipeline is operational

---

## 📊 System Ports & Services

| Service | Port | Command | Status |
|---------|------|---------|--------|
| **Ollama** | 11434 | (auto) | Local LLM |
| **Open WebUI Backend** | 8080 | (auto) | REST API |
| **Open WebUI Frontend** | 5173 | (auto) | Web browser UI |
| **GPT-SoVITS** | 9880 | `-WithVoiceTTS` | Voice synthesis |
| **Audio Router** | 8765 | `-WithAudioRouter` | Audio routing |

---

## 📁 Key File Locations

```
d:\Projects\Clusters\Agent\
├── config/
│   ├── launch.ps1                    # Main launcher (with flags)
│   ├── gpt-sovits-launch.ps1         # GPT-SoVITS service launcher
│   ├── audio-router-launch.ps1       # Audio router service launcher
│   └── .env                          # Environment configuration
├── services/
│   └── audio_router.py               # Dual-output audio router service
├── open-webui/                       # Open WebUI (backend + frontend)
│   ├── backend/                      # FastAPI backend
│   └── src/                          # Svelte frontend
├── vendor/
│   └── gpt-sovits/                   # Symlink to voice synthesis model
└── docs/
    └── VSEEFACE_SETUP.md             # VSeeFace configuration guide
```

---

## 🔧 Troubleshooting

### **Issue: "Port already in use" error**
```powershell
# Kill any lingering processes
Stop-Process -Name python -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Then restart
.\config\launch.ps1 -WithVoiceTTS -WithAudioRouter
```

### **Issue: GPT-SoVITS not appearing in TTS dropdown**
- Restart Open WebUI Backend (it reloads config on startup)
- Check http://localhost:9880 is responding:
  ```powershell
  Invoke-RestMethod -Uri "http://localhost:9880/" -Method GET
  ```

### **Issue: No audio from avatar mouth**
- Verify VSeeFace has "Cable Output" selected (not "Cable Input")
- Run audio router test: `.\config\audio-router-launch.ps1 -Test`
- Check speakers are unmuted

### **Issue: Voice input not triggering TTS**
- Verify STT engine is working (input green bar shows)
- Check Open WebUI uses GPT-SoVITS in Admin > Settings > Audio
- Restart backend to reload TTS config

### **Issue: Avatar mouth not syncing**
- VSeeFace needs 1-2 seconds before detecting audio
- Check VSeeFace is getting audio (waveform visible in settings)
- Ensure audio is playing through speakers (not muted)
- Try lowering audio threshold in VSeeFace

---

## 🎯 What's Next

### **Immediate** (Ready now)
- ✅ Use voice input for hands-free chat
- ✅ Auto-play TTS responses as you chat
- ✅ Watch avatar mouth move with speech

### **Soon** (Requires GPT-SoVITS training)
- [ ] Train custom voice model (voice cloning)
- [ ] Use avatar's own voice for responses
- [ ] Control avatar expressions with emotion detection

### **Future** (Nice to have)
- [ ] Fine-tune GPT-SoVITS model for better quality
- [ ] Add background music (via audio router)
- [ ] Stream TTS output (no waiting for full response)
- [ ] Multi-language responses

---

## 📞 Support References

**GPT-SoVITS:**
- Repo: https://github.com/RVC-Boss/GPT-SoVITS
- Docs: Model setup in `D:\Projects\Vocal10n\vendor\gpt-sovits\README.md`

**VB-Audio Virtual Cable:**
- Download: https://vb-audio.com/Cable/
- 20-minute trial timer resets on every reboot

**Open WebUI:**
- Docs: http://localhost:5173/help
- Settings: http://localhost:8080/docs

**VSeeFace:**
- Docs: https://www.vseeface.icu/
- Supported face formats: VRM, MMD, Live2D

---

## ✨ You're All Set!

Your personal AI agent with voice input, automatic TTS, and avatar lip sync is ready to use.

**Next step:** Open http://localhost:5173 and start chatting! 🎤 → 🤖 → 🗣️ → 👄

---

*Last updated: February 14, 2026*
*Setup completed with auto-TTS, GPT-SoVITS TTS, and dual-output audio routing*
