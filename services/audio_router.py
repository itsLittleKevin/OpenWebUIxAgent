"""
Audio Router for VMC Lip Sync
Routes TTS audio to speakers and analyzes it for VSeeFace VMC/OSC lip sync.

Usage:
  python audio_router.py --help
  python audio_router.py --test                    # Test with a tone
  python audio_router.py --serve                   # Start HTTP API server (port 8765)

The HTTP API lets Open WebUI backend request audio playback with VMC lip sync:
  POST http://localhost:8765/play-bytes
  [raw audio bytes]
"""

import asyncio
import argparse
import json
import logging
import io
import sys
from pathlib import Path
from typing import Optional

import numpy as np

# Try importing audio libraries
try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False
    logging.warning("sounddevice not installed. Install: pip install sounddevice")

try:
    from pydub import AudioSegment
    from pydub.playback import play as pydub_play
    HAS_PYDUB = True
except ImportError:
    HAS_PYDUB = False
    logging.warning("pydub not installed. Install: pip install pydub")

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

try:
    from pythonosc.udp_client import SimpleUDPClient
    from pythonosc.osc_bundle_builder import OscBundleBuilder, IMMEDIATELY
    from pythonosc.osc_message_builder import OscMessageBuilder
    HAS_OSC = True
except ImportError:
    HAS_OSC = False
    logging.warning("python-osc not installed. Install: pip install python-osc")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | audio_router: %(message)s'
)
log = logging.getLogger(__name__)


class VMCLipSync:
    """Sends lip sync blend shapes to VSeeFace via VMC protocol (OSC/UDP).

    Uses an envelope-follower approach: the mouth opens quickly on audio
    energy but *closes slowly*, preventing the rapid open-close flutter
    that raw RMS tracking causes.  Vowel shapes rotate smoothly over
    time while the mouth is open, giving natural-looking articulation.
    """

    VOWELS = ['A', 'I', 'U', 'E', 'O']
    FPS = 30  # Send rate

    def __init__(self, host: str = '127.0.0.1', port: int = 39540,
                 gain: float = 6.0, max_open: float = 0.65,
                 attack: float = 0.55, release: float = 0.75,
                 vowel_speed: float = 3.5):
        """
        Args:
            host/port: VMC/OSC target (VSeeFace).
            gain: Amplitude multiplier. Default 6.0.
            max_open: Hard cap on mouth-open value (0-1). Default 0.65.
            attack: Envelope attack factor (0-1). Higher = mouth opens faster.
                    Default 0.55 — mouth opens responsively within a few frames.
            release: Envelope release factor (0-1). Higher = mouth closes slower.
                     Default 0.75 — mouth holds open, fading gradually.
            vowel_speed: How quickly to cycle through vowel shapes (Hz).
                         Default 3.5 — a few vowel changes per second.
        """
        self.host = host
        self.port = port
        self.gain = gain
        self.max_open = max_open
        self.attack = attack
        self.release = release
        self.vowel_speed = vowel_speed
        self.client: Optional[SimpleUDPClient] = None

        # Internal state
        self._envelope = 0.0        # current envelope level (slow-release)
        self._vowel_phase = 0.0     # phase for cycling vowel shapes
        self._frame_count = 0       # count frames for time-based effects
        # Previous blend shape values for interpolation
        self._prev_shapes: dict[str, float] = {v: 0.0 for v in self.VOWELS}

        if HAS_OSC:
            self.client = SimpleUDPClient(host, port)
            log.info(f"VMC lip sync sender -> {host}:{port} "
                     f"(gain={gain}, max={max_open}, "
                     f"attack={attack}, release={release}, "
                     f"vowel_speed={vowel_speed})")
        else:
            log.warning("python-osc not available, VMC lip sync disabled")

    def _send_blend_shapes(self, values: dict[str, float]):
        """Send blend shape values via VMC protocol."""
        if not self.client:
            return
        for name, val in values.items():
            self.client.send_message("/VMC/Ext/Blend/Val", [name, float(val)])
        self.client.send_message("/VMC/Ext/Blend/Apply", [])

    def rms_to_blend_shapes(self, rms: float, _prev_open: float = 0.0) -> float:
        """Convert RMS amplitude to smooth VMC blend shapes.

        Uses an envelope follower with fast attack / slow release so the
        mouth opens quickly but never snaps shut between syllables.
        Vowel shapes rotate smoothly over time while the envelope is above
        the speaking threshold.

        Returns the current envelope value (pass back as prev_open for compat).
        """
        import math

        target = min(self.max_open, rms * self.gain)

        # Asymmetric envelope: fast attack, slow release
        if target > self._envelope:
            # Opening — blend toward new target quickly
            self._envelope += (target - self._envelope) * self.attack
        else:
            # Closing — decay slowly so mouth doesn't snap shut
            self._envelope += (target - self._envelope) * (1.0 - self.release)

        # Clamp
        envelope = max(0.0, min(self.max_open, self._envelope))

        # Speaking threshold — below this, mouth is closed
        if envelope < 0.02:
            envelope = 0.0
            self._vowel_phase = 0.0
            target_shapes = {v: 0.0 for v in self.VOWELS}
        else:
            # Advance vowel phase (time-based, not amplitude-based)
            self._vowel_phase += self.vowel_speed / self.FPS

            # Use sine waves at different phases to create smooth vowel blending
            phase = self._vowel_phase
            # Each vowel gets a sine wave offset by a different amount
            raw_a = max(0.0, math.sin(phase * 2.0 * math.pi))
            raw_e = max(0.0, math.sin(phase * 2.0 * math.pi + 1.2))
            raw_i = max(0.0, math.sin(phase * 2.0 * math.pi + 2.5))
            raw_o = max(0.0, math.sin(phase * 2.0 * math.pi + 3.8))
            raw_u = max(0.0, math.sin(phase * 2.0 * math.pi + 5.0))

            # Normalize so the dominant vowel gets most of the envelope
            total = raw_a + raw_e + raw_i + raw_o + raw_u
            if total < 0.01:
                total = 1.0

            target_shapes = {
                'A': (raw_a / total) * envelope,
                'E': (raw_e / total) * envelope * 0.85,
                'I': (raw_i / total) * envelope * 0.7,
                'O': (raw_o / total) * envelope * 0.9,
                'U': (raw_u / total) * envelope * 0.75,
            }

        # Smooth interpolation of individual blend shapes (prevents jumps)
        shape_lerp = 0.35
        smoothed = {}
        for v in self.VOWELS:
            smoothed[v] = self._prev_shapes[v] + (target_shapes[v] - self._prev_shapes[v]) * shape_lerp
            # Snap to zero if very small
            if smoothed[v] < 0.005:
                smoothed[v] = 0.0

        self._prev_shapes = smoothed
        self._send_blend_shapes(smoothed)
        self._frame_count += 1
        return envelope

    def send_lip_sync(self, samples: np.ndarray, sample_rate: int):
        """Pre-analyze entire buffer and send lip sync frame by frame."""
        import time

        if samples.ndim == 2:
            mono = samples.mean(axis=1)
        else:
            mono = samples

        frame_dur = 1.0 / self.FPS
        chunk_size = int(sample_rate * frame_dur)
        total_frames = len(mono) // chunk_size

        log.info(f"VMC lip sync: {total_frames} frames at {self.FPS} fps")
        start_time = time.perf_counter()

        for i in range(total_frames):
            target_time = start_time + i * frame_dur
            chunk = mono[i * chunk_size : (i + 1) * chunk_size]
            rms = float(np.sqrt(np.mean(chunk ** 2)))
            self.rms_to_blend_shapes(rms)

            now = time.perf_counter()
            sleep_time = target_time + frame_dur - now
            if sleep_time > 0:
                time.sleep(sleep_time)

        self._fade_close()

    def _fade_close(self, _prev_open: float = 0.0):
        """Gradually close the mouth over several frames."""
        import time
        frame_dur = 1.0 / self.FPS
        for step in range(8):
            fade = 1.0 - (step + 1) / 8.0
            shapes = {v: self._prev_shapes.get(v, 0.0) * fade for v in self.VOWELS}
            self._prev_shapes = shapes
            self._send_blend_shapes(shapes)
            time.sleep(frame_dur)
        self._send_blend_shapes({v: 0.0 for v in self.VOWELS})
        self._prev_shapes = {v: 0.0 for v in self.VOWELS}
        self._envelope = 0.0

    def close_mouth(self):
        """Reset all mouth blend shapes to 0."""
        self._send_blend_shapes({v: 0.0 for v in self.VOWELS})
        self._prev_shapes = {v: 0.0 for v in self.VOWELS}
        self._envelope = 0.0


class AudioRouter:
    """Routes audio to multiple outputs simultaneously."""
    
    def __init__(self, speaker_device_name: Optional[str] = None,
                 sample_rate: int = 24000,
                 vmc_port: int = 39540,
                 lip_gain: float = 6.0,
                 lip_max: float = 0.65):
        """
        Initialize audio router.
        
        Args:
            speaker_device_name: Name of speaker device (auto-detect if None)
            sample_rate: Audio sample rate in Hz
            vmc_port: VMC/OSC port for VSeeFace lip sync (default 39540)
            lip_gain: Amplitude gain for lip sync (default 6.0)
            lip_max: Maximum mouth openness 0-1 (default 0.65)
        """
        self.sample_rate = sample_rate
        self.speaker_device_id = None
        self.vmc = VMCLipSync(port=vmc_port, gain=lip_gain,
                              max_open=lip_max)
        
        if HAS_SOUNDDEVICE:
            self._detect_devices(speaker_device_name)
    
    def _detect_devices(self, speaker_name: Optional[str]):
        """Detect speaker output device."""
        devices = sd.query_devices()
        
        speaker_candidates = []
        
        for idx, device in enumerate(devices):
            if device['max_output_channels'] > 0:  # Output devices only
                device_name = device['name'].lower()
                
                # Look for speakers (physical audio output)
                if 'speaker' in device_name and 'steam' not in device_name and 'oculus' not in device_name:
                    speaker_candidates.append((idx, device))
        
        # Prefer SPEAKER with highest channel count
        if speaker_candidates:
            # Sort by channel count descending, then by index ascending
            speaker_candidates.sort(key=lambda x: (-x[1]['max_output_channels'], x[0]))
            self.speaker_device_id = speaker_candidates[0][0]
            log.info(f"Found speaker device: {speaker_candidates[0][1]['name']} (index {self.speaker_device_id})")
            
            # Log other candidates
            for idx, dev in speaker_candidates[1:3]:
                log.debug(f"  (also available: [{idx}] {dev['name']})")
        
        if self.speaker_device_id is None:
            log.warning("Speaker device not found. Available output devices:")
            for idx, device in enumerate(devices):
                if device['max_output_channels'] > 0:
                    log.warning(f"  [{idx}] {device['name']}")
    
    def play_audio_bytes(self, audio_data: bytes, format: str = 'wav') -> bool:
        """
        Play audio data to both outputs.
        
        Args:
            audio_data: Raw audio bytes
            format: Audio format ('wav', 'mp3', 'wav', etc.)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if not HAS_PYDUB:
                log.error("pydub required for audio playback")
                return False
            
            # Load audio from bytes
            audio = AudioSegment.from_file(io.BytesIO(audio_data), format=format.lower())
            
            # Convert to numpy array
            samples = np.array(audio.get_array_of_samples()).astype(np.float32)
            
            # If stereo, reshape; if mono, keep as is
            if audio.channels == 2:
                samples = samples.reshape((-1, 2))
            elif audio.channels != 1:
                log.warning(f"Unexpected channel count: {audio.channels}")
            
            # Normalize to [-1, 1]
            samples = samples / (2 ** 15)
            
            log.info(f"Playing audio: {len(samples)} samples, {audio.channels} channels, "
                    f"{audio.frame_rate} Hz")
            
            return self.play_audio_samples(samples, audio.frame_rate)
        
        except Exception as e:
            log.error(f"Failed to play audio: {e}")
            return False
    
    def play_audio_samples(self, audio: np.ndarray, sample_rate: int) -> bool:
        """
        Play audio samples to speakers.
        
        Args:
            audio: Numpy array of audio samples ([-1, 1] range)
            sample_rate: Sample rate of audio
        
        Returns:
            True if successful, False otherwise
        """
        if not HAS_SOUNDDEVICE:
            log.error("sounddevice required for playback")
            return False
        
        try:
            if self.speaker_device_id is not None:
                log.info(f"Playing to speakers (device {self.speaker_device_id})...")
                sd.play(audio, samplerate=sample_rate, device=self.speaker_device_id, 
                       blocksize=4096)
                sd.wait()
            else:
                log.warning("Speaker device not found, using default output")
                sd.play(audio, samplerate=sample_rate, blocksize=4096)
                sd.wait()
            
            log.info("Playback complete")
            return True
        
        except Exception as e:
            log.error(f"Playback failed: {e}")
            return False
    
    def play_test_tone(self, duration: float = 2.0, frequency: float = 440.0):
        """Play a test tone to both outputs."""
        log.info(f"Playing {frequency}Hz test tone for {duration}s...")
        
        t = np.linspace(0, duration, int(self.sample_rate * duration))
        audio = 0.3 * np.sin(2 * np.pi * frequency * t).astype(np.float32)
        
        self.play_audio_samples(audio, self.sample_rate)
        log.info("Test tone complete")

    def play_audio_with_vmc(self, audio_data: bytes, format: str = 'wav') -> bool:
        """Play audio to speakers with real-time VMC lip sync.

        Uses sounddevice callback mode: the audio driver tells us exactly
        which chunk is playing right now, we compute its amplitude, and a
        VMC thread sends blend shapes at ~30 fps driven by the real output.
        This guarantees mouth movement is perfectly synced to audio.
        """
        try:
            if not HAS_PYDUB or not HAS_SOUNDDEVICE:
                log.error("pydub and sounddevice required")
                return False

            audio_seg = AudioSegment.from_file(io.BytesIO(audio_data), format=format.lower())
            samples = np.array(audio_seg.get_array_of_samples()).astype(np.float32)
            if audio_seg.channels == 2:
                samples = samples.reshape((-1, 2))
            samples = samples / (2 ** 15)

            sr = audio_seg.frame_rate
            channels = audio_seg.channels
            total_samples = len(samples)
            duration = total_samples / sr

            log.info(f"Playing with real-time VMC lip sync: "
                     f"{total_samples} frames, {channels}ch, {sr} Hz, "
                     f"duration={duration:.2f}s")

            import threading

            # Shared state between audio callback and VMC thread
            current_rms = [0.0]       # amplitude of the chunk being played NOW
            write_pos = [0]           # how far into the sample buffer we are
            playback_done = threading.Event()

            def audio_callback(outdata, frames, time_info, status):
                """Called by sounddevice for each output chunk — fills speaker buffer."""
                start = write_pos[0]
                end = start + frames

                if start >= total_samples:
                    outdata[:] = 0
                    current_rms[0] = 0.0
                    playback_done.set()
                    raise sd.CallbackStop()

                if end > total_samples:
                    end = total_samples

                actual = end - start
                if samples.ndim == 2:
                    outdata[:actual] = samples[start:end]
                    outdata[actual:] = 0
                    mono_chunk = samples[start:end, 0]
                else:
                    outdata[:actual, 0] = samples[start:end]
                    outdata[actual:] = 0
                    mono_chunk = samples[start:end]

                # Compute RMS of what's actually going to the speaker
                current_rms[0] = float(np.sqrt(np.mean(mono_chunk ** 2)))
                write_pos[0] = end

                if end >= total_samples:
                    playback_done.set()
                    raise sd.CallbackStop()

            def vmc_worker():
                """Poll current_rms at ~30 fps and send VMC blend shapes."""
                interval = 1.0 / self.vmc.FPS
                while not playback_done.is_set():
                    rms = current_rms[0]
                    self.vmc.rms_to_blend_shapes(rms)
                    playback_done.wait(timeout=interval)
                # Fade mouth closed
                self.vmc._fade_close()
                log.info("VMC lip sync complete")

            # Start VMC thread
            vmc_thread = threading.Thread(target=vmc_worker, daemon=True)
            vmc_thread.start()

            # Start callback-driven audio output
            device = self.speaker_device_id
            stream = sd.OutputStream(
                samplerate=sr,
                channels=channels,
                callback=audio_callback,
                device=device,
                blocksize=1024,
            )
            with stream:
                playback_done.wait()

            vmc_thread.join(timeout=5)
            log.info("Audio playback + VMC lip sync complete")
            return True
        except Exception as e:
            log.error(f"Audio playback failed: {e}")
            self.vmc.close_mouth()
            return False


# ── API Server (optional HTTP interface) ────────────────────────────────

async def start_api_server(router: AudioRouter, port: int = 8765):
    """Start HTTP API server for audio routing."""
    if not HAS_AIOHTTP:
        log.error("aiohttp required for API server. Install: pip install aiohttp")
        return
    
    from aiohttp import web
    
    async def handle_play(request):
        """Handle POST /play request."""
        try:
            data = await request.json()
            audio_url = data.get('audio_url')
            text = data.get('text', '(no text)')
            
            log.info(f"Received request to play: {text}")
            
            # Fetch audio from URL
            async with aiohttp.ClientSession() as session:
                async with session.get(audio_url, timeout=30) as resp:
                    if resp.status == 200:
                        audio_data = await resp.read()
                        success = router.play_audio_bytes(audio_data, format='wav')
                        return web.json_response({'success': success, 'text': text})
                    else:
                        return web.json_response(
                            {'success': False, 'error': f'HTTP {resp.status}'},
                            status=resp.status
                        )
        
        except Exception as e:
            log.error(f"API error: {e}")
            return web.json_response({'success': False, 'error': str(e)}, status=400)
    
    async def handle_test(request):
        """Handle GET /test endpoint."""
        log.info("Test tone requested")
        asyncio.create_task(asyncio.to_thread(router.play_test_tone, 1.0, 440.0))
        return web.json_response({'success': True, 'message': 'Test tone started'})
    
    async def handle_status(request):
        """Handle GET /status endpoint."""
        return web.json_response({
            'status': 'running',
            'speaker_device': router.speaker_device_id,
            'sample_rate': router.sample_rate,
            'vmc_port': router.vmc.port,
            'vmc_enabled': router.vmc.client is not None,
        })
    
    # ── Playback queue: serialise audio so concurrent requests don't clash ──
    playback_queue: asyncio.Queue = asyncio.Queue()

    async def playback_worker():
        """Single consumer – plays queued audio one item at a time."""
        while True:
            audio_data = await playback_queue.get()
            try:
                await asyncio.to_thread(router.play_audio_with_vmc, audio_data)
            except Exception as e:
                log.error(f"Playback worker error: {e}")
            finally:
                playback_queue.task_done()

    asyncio.ensure_future(playback_worker())

    async def handle_play_bytes(request):
        """Handle POST /play-bytes - queue raw audio for sequential playback with VMC lip sync."""
        try:
            audio_data = await request.read()
            if not audio_data:
                return web.json_response({'success': False, 'error': 'No audio data'}, status=400)
            qsize = playback_queue.qsize()
            log.info(f"Received {len(audio_data)} bytes, queued for playback (queue depth: {qsize})")
            await playback_queue.put(audio_data)
            return web.json_response({'success': True, 'queued': True, 'position': qsize + 1})
        except Exception as e:
            log.error(f"play-bytes error: {e}")
            return web.json_response({'success': False, 'error': str(e)}, status=500)

    async def handle_clear(request):
        """Handle POST /clear - empty the playback queue."""
        cleared = 0
        while not playback_queue.empty():
            try:
                playback_queue.get_nowait()
                playback_queue.task_done()
                cleared += 1
            except asyncio.QueueEmpty:
                break
        log.info(f"Cleared {cleared} items from playback queue")
        return web.json_response({'success': True, 'cleared': cleared})

    app = web.Application()
    app.router.add_post('/play', handle_play)
    app.router.add_post('/play-bytes', handle_play_bytes)
    app.router.add_post('/clear', handle_clear)
    app.router.add_get('/test', handle_test)
    app.router.add_get('/status', handle_status)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port, reuse_address=True)
    
    # Retry binding with exponential backoff if port is in TIME_WAIT
    max_retries = 5
    retry_delay = 1
    for attempt in range(max_retries):
        try:
            await site.start()
            break
        except OSError as e:
            if attempt < max_retries - 1:
                log.warning(f"Failed to bind port {port} (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                raise
    
    log.info(f"API server listening on http://0.0.0.0:{port}")
    log.info("Endpoints:")
    log.info(f"  POST /play-bytes - Play audio bytes to speakers with VMC lip sync")
    log.info(f"  GET  /status     - Get router status")
    
    # Keep running
    try:
        await asyncio.sleep(3600 * 24)  # Run for 24 hours
    except KeyboardInterrupt:
        await runner.cleanup()


# ── CLI ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Audio Router: Playback with VMC lip sync',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('--test', action='store_true',
                       help='Play test tone to both outputs')
    parser.add_argument('--file', type=str,
                       help='Audio file to play to both outputs')
    parser.add_argument('--serve', action='store_true',
                       help='Start HTTP API server (port 8765)')
    parser.add_argument('--port', type=int, default=8765,
                       help='API server port (default: 8765)')
    parser.add_argument('--speaker-device-id', type=int, default=None,
                       help='Manually specify speaker device ID')
    parser.add_argument('--list-devices', action='store_true',
                       help='List all audio devices and exit')
    parser.add_argument('--frequency', type=float, default=440.0,
                       help='Test tone frequency in Hz (default: 440)')
    parser.add_argument('--duration', type=float, default=2.0,
                       help='Test tone duration in seconds (default: 2)')
    parser.add_argument('--vmc-port', type=int, default=39540,
                       help='VMC/OSC port for VSeeFace lip sync (default: 39540)')
    parser.add_argument('--lip-gain', type=float, default=6.0,
                       help='Lip sync amplitude gain (default: 6.0, lower=subtler)')
    parser.add_argument('--lip-max', type=float, default=0.65,
                       help='Max mouth openness 0-1 (default: 0.65)')
    
    args = parser.parse_args()
    
    # List devices and exit
    if args.list_devices:
        if HAS_SOUNDDEVICE:
            print("\nAvailable audio devices:")
            devices = sd.query_devices()
            for idx, device in enumerate(devices):
                out_ch = device['max_output_channels']
                if out_ch > 0:
                    marker = " ← SPEAKER" if 'speaker' in device['name'].lower() else ""
                    print(f"  [{idx}] {device['name']} ({out_ch} ch){marker}")
        else:
            print("sounddevice not available")
        return
    
    # Create router
    router = AudioRouter(
        speaker_device_name=None,
        vmc_port=args.vmc_port,
        lip_gain=args.lip_gain,
        lip_max=args.lip_max,
    )
    
    # Manual override for speaker device
    if args.speaker_device_id is not None:
        router.speaker_device_id = args.speaker_device_id
    
    log.info(f"Audio router initialized:")
    log.info(f"  Speaker device: {router.speaker_device_id}")
    log.info(f"  Sample rate:    {router.sample_rate} Hz")
    
    # Execute command
    if args.test:
        router.play_test_tone(args.duration, args.frequency)
    
    elif args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            log.error(f"File not found: {args.file}")
            sys.exit(1)
        
        with open(file_path, 'rb') as f:
            audio_data = f.read()
        
        ext = file_path.suffix.lstrip('.').lower()
        router.play_audio_bytes(audio_data, format=ext)
    
    elif args.serve:
        log.info("Starting audio router API server...")
        try:
            asyncio.run(start_api_server(router, args.port))
        except KeyboardInterrupt:
            log.info("Shutting down...")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
