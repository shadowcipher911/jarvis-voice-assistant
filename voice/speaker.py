"""
voice/speaker.py — Text-to-speech output.

Primary:  ElevenLabs API — realistic AI voice (requires ELEVENLABS_API_KEY).
Fallback: pyttsx3 — fully offline, no API key needed.

Speaking is non-blocking: audio plays in a daemon thread so JARVIS can
continue listening while speaking.
"""

import logging
import os
import threading
import tempfile
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("jarvis.speaker")

ELEVENLABS_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")

# Trim spoken output to 3 sentences max to keep responses concise
MAX_SPOKEN_SENTENCES = 3


class Speaker:
    """Handles TTS output with ElevenLabs primary and pyttsx3 fallback."""

    def __init__(self):
        self._muted = False
        self._engine = None           # pyttsx3 engine (lazy-loaded)
        self._lock = threading.Lock() # prevents overlapping speech

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def speak(self, text: str) -> None:
        """Speak the given text asynchronously (non-blocking)."""
        if self._muted:
            return
        trimmed = self._trim_to_sentences(text, MAX_SPOKEN_SENTENCES)
        threading.Thread(
            target=self._speak_sync,
            args=(trimmed,),
            daemon=True,
            name="jarvis-tts",
        ).start()

    def speak_sync(self, text: str) -> None:
        """Speak and block until finished (used for critical messages)."""
        if self._muted:
            return
        trimmed = self._trim_to_sentences(text, MAX_SPOKEN_SENTENCES)
        self._speak_sync(trimmed)

    def mute(self) -> None:
        self._muted = True
        logger.info("Speaker muted.")

    def unmute(self) -> None:
        self._muted = False
        logger.info("Speaker unmuted.")

    @property
    def is_muted(self) -> bool:
        return self._muted

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _speak_sync(self, text: str) -> None:
        with self._lock:
            if ELEVENLABS_KEY:
                success = self._elevenlabs(text)
                if success:
                    return
            self._pyttsx3(text)

    def _elevenlabs(self, text: str) -> bool:
        """Speak using ElevenLabs API. Returns True on success."""
        try:
            from elevenlabs.client import ElevenLabs
            import pygame

            client = ElevenLabs(api_key=ELEVENLABS_KEY)
            audio_generator = client.generate(
                text=text,
                voice=ELEVENLABS_VOICE_ID,
                model="eleven_monolingual_v1",
            )

            # Collect bytes from generator
            audio_bytes = b"".join(audio_generator)

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_bytes)
                tmp_path = f.name

            # Play with pygame
            try:
                pygame.mixer.init()
                pygame.mixer.music.load(tmp_path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    import time; time.sleep(0.05)
            finally:
                pygame.mixer.music.stop()
                pygame.mixer.quit()
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

            return True

        except ImportError:
            logger.debug("ElevenLabs or pygame not installed — using pyttsx3.")
            return False
        except Exception as e:
            logger.warning("ElevenLabs TTS error: %s — falling back to pyttsx3.", e)
            return False

    def _pyttsx3(self, text: str) -> None:
        """Speak using the offline pyttsx3 engine."""
        try:
            import pyttsx3
            if self._engine is None:
                self._engine = pyttsx3.init()
                self._engine.setProperty("rate", 170)   # slightly faster than default
                self._engine.setProperty("volume", 0.9)

            self._engine.say(text)
            self._engine.runAndWait()
        except Exception as e:
            logger.error("pyttsx3 TTS error: %s", e)

    @staticmethod
    def _trim_to_sentences(text: str, max_sentences: int) -> str:
        """
        Return at most max_sentences sentences from text.
        Splits on '.', '!', '?' followed by whitespace or end-of-string.
        """
        import re
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        return " ".join(sentences[:max_sentences])


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_speaker: Optional[Speaker] = None


def get_speaker() -> Speaker:
    global _speaker
    if _speaker is None:
        _speaker = Speaker()
    return _speaker


def speak(text: str) -> None:
    """Convenience function — speak text via the shared speaker instance."""
    get_speaker().speak(text)
