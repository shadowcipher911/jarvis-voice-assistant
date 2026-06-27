"""
voice/listener.py — Continuous speech-to-text via faster-whisper.

Architecture:
  1. WakeWordDetector fires trigger_listen() when "Hey JARVIS" is heard.
  2. trigger_listen() records audio until 2 s of silence.
  3. Whisper transcribes the audio.
  4. The transcribed text is passed to the provided on_text callback.
  5. Falls back to plain keyboard input when no microphone is available.
"""

import logging
import os
import queue
import tempfile
import threading
import time
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("jarvis.listener")

SAMPLE_RATE = 16_000      # Hz — Whisper expects 16 kHz
SILENCE_SECONDS = 2.0     # stop recording after this many silent seconds
SILENCE_THRESHOLD = 500   # RMS below this = silence
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")


class Listener:
    """
    Always-on microphone manager.

    After waking up, records audio frames until silence, then transcribes
    with Whisper and calls on_text with the result.
    """

    def __init__(self, on_text: Callable[[str], None]):
        self.on_text = on_text
        self._whisper = None          # lazy-loaded
        self._recording = False
        self._running = False
        self._audio_queue: queue.Queue = queue.Queue()
        self._mic_available = True

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    def start(self):
        """Start the listener (blocking loop — run in a daemon thread)."""
        self._running = True
        self._load_whisper()

        # Test microphone availability
        try:
            sd.query_devices(kind="input")
        except Exception:
            logger.warning("No microphone detected — keyboard input mode only.")
            self._mic_available = False
            self._keyboard_fallback()
            return

        logger.info("Listener started. Waiting for wake trigger...")
        while self._running:
            time.sleep(0.1)

    def stop(self):
        self._running = False

    # -----------------------------------------------------------------------
    # Wake trigger — called by WakeWordDetector
    # -----------------------------------------------------------------------

    def trigger_listen(self):
        """Start a single recording → transcribe → callback cycle."""
        if self._recording:
            return   # already recording
        if not self._mic_available:
            return

        threading.Thread(target=self._record_and_transcribe, daemon=True).start()

    # -----------------------------------------------------------------------
    # Recording
    # -----------------------------------------------------------------------

    def _record_and_transcribe(self):
        self._recording = True
        logger.info("Listening...")
        frames = []
        silence_start = None

        def _callback(indata, frame_count, time_info, status):
            frames.append(indata.copy())
            rms = np.sqrt(np.mean(indata.astype(np.float32) ** 2))
            nonlocal silence_start
            if rms < SILENCE_THRESHOLD:
                if silence_start is None:
                    silence_start = time.time()
            else:
                silence_start = None

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            callback=_callback,
            blocksize=int(SAMPLE_RATE * 0.1),  # 100 ms blocks
        ):
            while self._recording:
                time.sleep(0.05)
                if silence_start and (time.time() - silence_start) >= SILENCE_SECONDS:
                    break

        self._recording = False

        if not frames:
            logger.warning("No audio captured.")
            return

        audio = np.concatenate(frames, axis=0).flatten().astype(np.float32) / 32768.0
        text = self._transcribe(audio)
        if text:
            logger.info("Transcribed: %s", text)
            self.on_text(text)

    # -----------------------------------------------------------------------
    # Whisper transcription
    # -----------------------------------------------------------------------

    def _load_whisper(self):
        if self._whisper is not None:
            return
        try:
            from faster_whisper import WhisperModel
            cfg_model = os.getenv("JARVIS_WHISPER_MODEL", WHISPER_MODEL)
            self._whisper = WhisperModel(cfg_model, device="cpu", compute_type="int8")
            logger.info("Whisper model '%s' loaded.", cfg_model)
        except ImportError:
            logger.warning("faster-whisper not installed — transcription unavailable.")
        except Exception as e:
            logger.error("Whisper load error: %s", e)

    def _transcribe(self, audio: np.ndarray) -> str:
        if self._whisper is None:
            return ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_path = f.name

            import soundfile as sf
            sf.write(tmp_path, audio, SAMPLE_RATE)

            segments, _ = self._whisper.transcribe(tmp_path, language="en")
            text = " ".join(s.text for s in segments).strip()

            os.unlink(tmp_path)
            return text
        except Exception as e:
            logger.error("Transcription error: %s", e)
            return ""

    # -----------------------------------------------------------------------
    # Keyboard fallback
    # -----------------------------------------------------------------------

    def _keyboard_fallback(self):
        """Read input from the terminal when no microphone is available."""
        print("[JARVIS] Microphone unavailable — type your commands below.")
        while self._running:
            try:
                text = input("You: ").strip()
                if text:
                    self.on_text(text)
            except (EOFError, KeyboardInterrupt):
                break


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_listener: Optional[Listener] = None


def get_listener(on_text: Callable) -> Listener:
    global _listener
    if _listener is None:
        _listener = Listener(on_text=on_text)
    return _listener
