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

# Cache directory for wake acknowledgment audios
CACHE_ACK_DIR = "/tmp/jarvis_acks"


def ensure_cached_ack_phrases(phrases: list[str]) -> list[str]:
    """
    Synthesizes and caches acknowledgment phrases (e.g. 'สวัสดีครับ', 'พร้อมครับ')
    into /tmp/jarvis_acks/*.mp3 asynchronously or on startup using th-TH-NiwatNeural.
    Returns list of cached valid audio file paths.
    """
    os.makedirs(CACHE_ACK_DIR, exist_ok=True)
    cached_paths = []

    async def _synth(phrase: str, out_path: str):
        try:
            comm = edge_tts.Communicate(
                text=phrase,
                voice=config.TTS_VOICE_TH,
                pitch=config.TTS_PITCH_TH,
                rate=config.TTS_RATE_TH,
                volume=config.TTS_VOLUME_TH
            )
            await comm.save(out_path)
        except Exception as e:
            print(f"[Speaker] Failed to cache ack phrase '{phrase}': {e}")

    for idx, phrase in enumerate(phrases):
        filename = f"ack_{idx}.mp3"
        filepath = os.path.join(CACHE_ACK_DIR, filename)
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            try:
                asyncio.run(_synth(phrase, filepath))
            except Exception as ex:
                print(f"[Speaker] Error generating ack audio '{phrase}': {ex}")

        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            cached_paths.append(filepath)

    return cached_paths


def clean_markdown_for_speech(text: str) -> str:
    """
    Cleans and optimizes text specifically for Edge-TTS speech synthesis:
    - Strips [SPEAK]...[/SPEAK] tags if present
    - Strips code blocks, inline code, headers, markdown bullets, bold/italic symbols
    - Removes raw URLs, email addresses, and bracketed links
    - Removes emojis and unicode pictographs to prevent synthetic voice distortion
    - Adjusts pacing: adds natural spacing between Thai script and English/numbers
    - Normalizes punctuation to create smooth acoustic pauses
    """
    if not text:
        return ""

    # 1. Extract [SPEAK] content if tags are wrapped around text
    speak_match = re.search(r'\[SPEAK\](.*?)\[/SPEAK\]', text, flags=re.DOTALL | re.IGNORECASE)
    if speak_match:
        text = speak_match.group(1)
    else:
        text = re.sub(r'\[/?SPEAK\]', '', text, flags=re.IGNORECASE)

    # 2. Remove code blocks ```...``` completely
    cleaned = re.sub(r'```[\s\S]*?```', '', text)
    # Remove inline code `...`
    cleaned = re.sub(r'`([^`]+)`', r'\1', cleaned)
    # Remove markdown headers (#, ##, etc.)
    cleaned = re.sub(r'#+\s*', '', cleaned)
    # Remove bold, italics, strikethrough (*, **, _, __, ~~)
    cleaned = re.sub(r'[*_~]', '', cleaned)
    # Remove bullet markers (- , * , + ) and numbered list prefixes (1. , 2. )
    cleaned = re.sub(r'^\s*[-*+]\s+', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'^\s*\d+\.\s+', '', cleaned, flags=re.MULTILINE)
    # Convert markdown links [title](url) -> title
    cleaned = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', cleaned)
    # Remove raw URLs
    cleaned = re.sub(r'https?://\S+', '', cleaned)

    # 3. Remove emojis and special graphical symbols
    emoji_pattern = re.compile(
        r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]',
        flags=re.UNICODE
    )
    cleaned = emoji_pattern.sub('', cleaned)

    # 4. Remove brackets, braces, angle brackets, and pipe symbols
    cleaned = re.sub(r'[<>{}\[\]|\\/]', ' ', cleaned)

    # 5. Pacing optimization for Thai + English mixed text:
    # Insert space between Thai characters and English/Numbers for clear phoneme transitions
    cleaned = re.sub(r'([\u0E00-\u0E7F])([A-Za-z0-9])', r'\1 \2', cleaned)
    cleaned = re.sub(r'([A-Za-z0-9])([\u0E00-\u0E7F])', r'\1 \2', cleaned)

    # 6. Normalize punctuation for natural vocal pauses
    # Colons and semicolons become a comma pause
    cleaned = re.sub(r'[:;]', ', ', cleaned)
    # Multiple dots or dashes become a single period or comma
    cleaned = re.sub(r'\.{2,}', '. ', cleaned)
    cleaned = re.sub(r'-{2,}', ', ', cleaned)
    # Clean up redundant commas and spaces
    cleaned = re.sub(r',\s*,+', ', ', cleaned)
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
        self.current_process: Optional[subprocess.Popen] = None
        self.is_interrupted = False
        self._playback_lock = threading.Lock()
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
        self.is_interrupted = False
        speech_text = clean_markdown_for_speech(raw_text)
        if not speech_text:
            return

        # Enhance Thai speech pacing, currency, and numbers via PyThaiNLP
        if has_thai_characters(speech_text):
            try:
                from core.thai_nlp import prepare_thai_tts_text
                speech_text = prepare_thai_tts_text(speech_text)
            except Exception as e:
                print(f"[Speaker] Thai NLP prep note: {e}")

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

            # Check if interrupted during synthesis
            if self.is_interrupted:
                return

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

    def stop_speaking(self):
        """Instantly interrupts any ongoing speech playback and drains the pending queue."""
        self.is_interrupted = True
        # Drain queue
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except (queue.Empty, ValueError):
                break

        # Terminate active audio player process
        with self._playback_lock:
            if self.current_process is not None:
                try:
                    self.current_process.terminate()
                    self.current_process.kill()
                except Exception:
                    pass
                self.current_process = None

        if self._pygame_initialized:
            try:
                import pygame
                pygame.mixer.music.stop()
            except Exception:
                pass

        print("[Speaker] 🛑 Speech interrupted immediately (Barge-in).")
        event_bus.state_changed.emit("idle")

    def _play_audio_file(self, file_path: str):
        """Plays the mp3 audio file using native macOS afplay or pygame with interrupt support."""
        if self.is_interrupted:
            return

        if sys.platform == "darwin":
            try:
                with self._playback_lock:
                    if self.is_interrupted:
                        return
                    self.current_process = subprocess.Popen(
                        ["/usr/bin/afplay", file_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )

                # Wait for playback to complete or terminate
                while self.current_process and self.current_process.poll() is None:
                    time.sleep(0.04)

                with self._playback_lock:
                    self.current_process = None
                return
            except Exception as e:
                print(f"[Speaker] afplay error: {e}, falling back to pygame")
                with self._playback_lock:
                    self.current_process = None

        if self._pygame_initialized and not self.is_interrupted:
            try:
                import pygame
                pygame.mixer.music.load(file_path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy() and not self.is_interrupted:
                    time.sleep(0.04)
                return
            except Exception as e:
                print(f"[Speaker] pygame playback error: {e}")

    def stop(self):
        """Stops the speaker thread."""
        self.is_running = False
