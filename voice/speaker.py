"""
Voice Speaker module for Jarvis Desktop Assistant.
Dual-tone synthesis:
- Thai Mode: th-TH-NiwatNeural (pitch -14Hz, rate +14%, volume +40%)
- English Mode: en-GB-RyanNeural (British J.A.R.V.I.S. tone: pitch -8Hz, rate +8%, volume +40%)
Cleans markdown formatting and plays natively on macOS via /usr/bin/afplay.
"""

import os
import re
import sys
import time
import queue
import asyncio
import threading
import subprocess
from typing import Optional, Tuple

import edge_tts

import config
from core.event_bus import event_bus


def clean_markdown_for_speech(text: str) -> str:
    """
    Strips raw markdown syntax (code blocks, asterisks, headers, backticks,
    bullet symbols, and URLs) so speech synthesis sounds fluid and natural.
    """
    if not text:
        return ""

    # Remove code blocks ```...```
    cleaned = re.sub(r'```[\s\S]*?```', '', text)
    # Remove inline code `...`
    cleaned = re.sub(r'`([^`]+)`', r'\1', cleaned)
    # Remove headers (#, ##, etc.)
    cleaned = re.sub(r'#+\s*', '', cleaned)
    # Remove markdown bold/italics (*, **, _, __, ~~)
    cleaned = re.sub(r'[*_~]', '', cleaned)
    # Remove bullet markers (- , * , + )
    cleaned = re.sub(r'^\s*[-*+]\s+', '', cleaned, flags=re.MULTILINE)
    # Convert markdown links [title](url) -> title
    cleaned = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', cleaned)
    # Remove raw URLs
    cleaned = re.sub(r'https?://\S+', '', cleaned)
    # Remove excessive symbols
    cleaned = re.sub(r'[<>{}\[\]|\\]', ' ', cleaned)
    # Normalize whitespaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def has_thai_characters(text: str) -> bool:
    """Detects whether text contains Thai characters (\u0E00-\u0E7F)."""
    return bool(re.search(r'[\u0E00-\u0E7F]', text))


class JarvisSpeaker(threading.Thread):
    """
    Background worker thread that receives text, strips markdown,
    chooses the appropriate J.A.R.V.I.S. voice parameters (Thai / British English),
    and plays audio via native macOS afplay without blocking the UI.
    """

    def __init__(self):
        super().__init__(daemon=True)
        self.queue = queue.Queue()
        self.is_running = True
        self._pygame_initialized = False
        self._init_audio_player()

    def _init_audio_player(self):
        """Initializes fallback audio player for non-macOS systems."""
        if sys.platform == "darwin":
            # On macOS, native /usr/bin/afplay is used directly and cleanly
            self._pygame_initialized = False
            return

        try:
            import pygame
            pygame.mixer.init()
            self._pygame_initialized = True
        except Exception as e:
            print(f"[Speaker] Pygame mixer init note: {e}")
            self._pygame_initialized = False

    def speak(self, text: str):
        """Queues text for speech synthesis."""
        if not config.TTS_ENABLED or not text.strip():
            return
        self.queue.put(text.strip())

    def run(self):
        """Worker loop processing speech queue."""
        while self.is_running:
            try:
                text = self.queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                self._synthesize_and_play(text)
            except Exception as e:
                print(f"[Speaker] Error during speech synthesis: {e}")
                event_bus.state_changed.emit("idle")
            finally:
                self.queue.task_done()

    def _get_voice_params(self, text: str) -> Tuple[str, str, str, str]:
        """
        Determines voice and acoustic parameters based on language:
        - Thai: th-TH-NiwatNeural, -14Hz, +14%, +40%
        - English: en-GB-RyanNeural, -8Hz, +8%, +40%
        """
        if has_thai_characters(text):
            return (
                config.TTS_VOICE_TH,
                config.TTS_PITCH_TH,
                config.TTS_RATE_TH,
                config.TTS_VOLUME_TH,
            )
        else:
            return (
                config.TTS_VOICE_EN,
                config.TTS_PITCH_EN,
                config.TTS_RATE_EN,
                config.TTS_VOLUME_EN,
            )

    def _synthesize_and_play(self, raw_text: str):
        """Prepares text, generates TTS, and plays audio."""
        speech_text = clean_markdown_for_speech(raw_text)
        if not speech_text:
            return

        voice, pitch, rate, volume = self._get_voice_params(speech_text)
        output_file = "/tmp/jarvis_tts.mp3"

        event_bus.state_changed.emit("speaking")

        try:
            # Generate TTS audio file
            asyncio.run(
                self._generate_tts_file(
                    text=speech_text,
                    output_path=output_file,
                    voice=voice,
                    pitch=pitch,
                    rate=rate,
                    volume=volume,
                )
            )

            # Play audio file
            self._play_audio_file(output_file)
        finally:
            # Cleanup temporary file if needed
            if os.path.exists(output_file):
                try:
                    os.remove(output_file)
                except Exception:
                    pass
            # Return to idle state after speech completes
            event_bus.state_changed.emit("idle")

    async def _generate_tts_file(
        self,
        text: str,
        output_path: str,
        voice: str,
        pitch: str,
        rate: str,
        volume: str,
    ):
        """Calls edge-tts Communicate to synthesize speech with custom pitch/rate/volume."""
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            pitch=pitch,
            rate=rate,
            volume=volume,
        )
        await communicate.save(output_path)

    def _play_audio_file(self, file_path: str):
        """Plays the mp3 audio file using native macOS afplay or pygame."""
        if sys.platform == "darwin":
            try:
                subprocess.run(["afplay", file_path], check=True)
                return
            except Exception as e:
                print(f"[Speaker] afplay error: {e}, falling back to pygame")

        if self._pygame_initialized:
            try:
                import pygame
                pygame.mixer.music.load(file_path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.05)
                return
            except Exception as e:
                print(f"[Speaker] pygame playback error: {e}")

    def stop(self):
        """Stops the speaker thread."""
        self.is_running = False
