"""
voice/wake_word.py — Wake word detector.

Primary: Picovoice Porcupine ("Hey JARVIS") — ultra-low CPU, fully offline.
Fallback: Keyboard trigger (press Enter) when PICOVOICE_ACCESS_KEY is absent.
"""

import logging
import os
import threading
from typing import Callable, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("jarvis.wake_word")

PICOVOICE_KEY = os.getenv("PICOVOICE_ACCESS_KEY", "")


class WakeWordDetector:
    """Listens for the wake word and fires a callback when detected."""

    def __init__(self, callback: Callable, keyword: str = "jarvis"):
        self.callback = callback
        self.keyword = keyword.lower()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._use_porcupine = bool(PICOVOICE_KEY)

    # -----------------------------------------------------------------------
    # Start / stop
    # -----------------------------------------------------------------------

    def start(self):
        """Start detection in a background daemon thread."""
        self._running = True
        if self._use_porcupine:
            self._thread = threading.Thread(
                target=self._porcupine_loop, name="wake-word", daemon=True
            )
        else:
            logger.warning(
                "PICOVOICE_ACCESS_KEY not set — using keyboard fallback (press Enter to activate JARVIS)."
            )
            self._thread = threading.Thread(
                target=self._keyboard_loop, name="wake-word-kb", daemon=True
            )
        self._thread.start()
        return self._thread

    def stop(self):
        self._running = False

    # -----------------------------------------------------------------------
    # Porcupine (hardware wake word)
    # -----------------------------------------------------------------------

    def _porcupine_loop(self):
        try:
            import pvporcupine
            import sounddevice as sd
            import numpy as np

            porcupine = pvporcupine.create(
                access_key=PICOVOICE_KEY,
                keywords=[self.keyword] if self.keyword in pvporcupine.KEYWORDS else ["jarvis"],
            )
            logger.info("Porcupine wake-word detector active (keyword='%s').", self.keyword)

            frame_len = porcupine.frame_length
            sample_rate = porcupine.sample_rate

            with sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="int16",
                blocksize=frame_len,
            ) as stream:
                while self._running:
                    data, _ = stream.read(frame_len)
                    pcm = np.frombuffer(data, dtype=np.int16).flatten()
                    index = porcupine.process(pcm)
                    if index >= 0:
                        logger.info("Wake word detected!")
                        self.callback()

            porcupine.delete()

        except ImportError as e:
            logger.error("pvporcupine not installed: %s — falling back to keyboard.", e)
            self._keyboard_loop()
        except Exception as e:
            logger.error("Porcupine error: %s — falling back to keyboard.", e)
            self._keyboard_loop()

    # -----------------------------------------------------------------------
    # Keyboard fallback
    # -----------------------------------------------------------------------

    def _keyboard_loop(self):
        """Press Enter in the terminal to trigger a JARVIS listen cycle."""
        print("\n[JARVIS] No wake word hardware key. Press ENTER at any time to speak to JARVIS.")
        while self._running:
            try:
                input()          # blocks until the user presses Enter
                self.callback()
            except EOFError:
                break
            except KeyboardInterrupt:
                break


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

_detector: Optional[WakeWordDetector] = None


def start_detection(callback: Callable) -> WakeWordDetector:
    """Create and start the wake-word detector; returns the instance."""
    global _detector
    _detector = WakeWordDetector(callback=callback)
    _detector.start()
    return _detector


def stop_detection():
    global _detector
    if _detector:
        _detector.stop()
