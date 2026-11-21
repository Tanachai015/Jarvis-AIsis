"""
Voice Listener module for Jarvis Desktop Assistant.

Single-Pipeline Push-to-Talk + Wake Trigger + Continuous Loop:
1. STANDBY_WAKE:
   - Uses Local Faster-Whisper (small, int8, beam_size=1) for wake words detection ("jarvis", "จาร์วิส", etc.)
   - On wake word -> Randomly picks a cached ack phrase ("สวัสดีครับ", "พร้อมครับ") -> Plays completely with blocking afplay
   - Flushes mic audio buffer and triggers ACTIVE_PTT immediately.
   - Users can press Cmd + Shift + J at any time to toggle ACTIVE_PTT directly.

2. ACTIVE_PTT (The Single Core Pipeline):
   - Keeps 1D float32 audio arrays throughout the recording pipeline.
   - Auto-stops when speech is followed by 3.0s of silence (post_speech_silence_sec).
   - Transcribes via Groq Cloud STT (whisper-large-v3-turbo) with Local Faster-Whisper fallback.
   - Checks for exit_conversation_phrases ("ขอบคุณครับ", "พอแค่นี้", "พักก่อน") to return to STANDBY_WAKE.
   - Dispatches user text to Event Bus (JarvisBrain).

3. FOLLOWUP_LOOP (Continuous 60s listening window):
   - When JarvisBrain completes and JarvisSpeaker finishes talking (is_speaking == False + 0.3s delay),
     automatically re-enters ACTIVE_PTT without requiring wake word.
   - Followup timeout is 60s: If no speech within 60s, cleanly shuts off recording and returns to STANDBY_WAKE.
"""

import os
import re
import sys
import io
import json
import wave
import time
import queue
import random
import subprocess
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any

import numpy as np
import requests

import config
from core.event_bus import event_bus
from voice.speaker import ensure_cached_ack_phrases

VOICE_SETTINGS_PATH = Path(config.PROJECT_ROOT) / "voice_settings.json"


def _play_system_sound(sound_name: str):
    """Plays macOS system sound asynchronously via afplay."""
    if sys.platform != "darwin":
        return
    sound_path = f"/System/Library/Sounds/{sound_name}.aiff"
    if os.path.exists(sound_path):
        try:
            subprocess.Popen(
                ["/usr/bin/afplay", sound_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass


class JarvisListener(threading.Thread):
    """
    Dedicated worker thread for microphone capture and speech-to-text.
    Operates as a Single-Pipeline Push-to-Talk engine with wake trigger and continuous loop.
    """

    SAMPLE_RATE = 16000
    CHANNELS = 1
    BLOCK_SIZE = 1024        # ~64ms per audio chunk

    # State Machine Constants
    STATE_STANDBY_WAKE = "STANDBY_WAKE"
    STATE_ACTIVE_PTT = "ACTIVE_PTT"
    STATE_FOLLOWUP_LOOP = "FOLLOWUP_LOOP"

    def __init__(self):
        super().__init__(daemon=True)
        self.is_running = False
        self._enabled = config.VOICE_INPUT_ENABLED
        self.wake_trigger_enabled = getattr(config, "WAKE_TRIGGER_ENABLED", True)

        # Load dynamic voice settings
        self._load_voice_settings()

        # State tracking
        self.current_state = self.STATE_STANDBY_WAKE
        self.is_recording = False
        self.is_speaking = False
        self.is_processing = False

        self.record_start_time = 0.0
        self.last_toggle_time = 0.0
        self.last_speech_time = 0.0
        self.has_spoken = False
        self.speech_frames = 0
        self.cooldown_seconds = config.VOICE_COOLDOWN_SECONDS

        # Buffers & Locks
        self.audio_queue = queue.Queue()
        self.recorded_chunks: List[np.ndarray] = []
        self.chunks_lock = threading.Lock()
        self.state_lock = threading.Lock()

        # Wake Word buffer
        self.wake_buffer: List[np.ndarray] = []
        self.wake_buffer_lock = threading.Lock()
        self.wake_silence_count = 0

        # Faster-Whisper Model for Wake Words & Local Fallback
        self.whisper_model = None

        # Cached wake acknowledgment audio files
        self.cached_ack_files: List[str] = []

        # Connect event bus signals
        event_bus.toggle_voice_record_signal.connect(self.toggle_push_to_talk)
        event_bus.voice_mode_changed.connect(self._on_voice_mode_signal)
        event_bus.state_changed.connect(self._on_assistant_state_changed)

    def _load_voice_settings(self):
        """Loads configuration from voice_settings.json with safe fallbacks."""
        defaults = {
            "wake_words": ["jarvis", "hi jarvis", "จาร์วิส", "จาวิส", "ไฮ จาร์วิส"],
            "wake_ack_phrases": ["สวัสดีครับ", "พร้อมครับ", "ว่าไงครับ", "ครับบอส"],
            "exit_conversation_phrases": ["พอแค่นี้", "ขอบคุณครับ", "หยุดฟัง", "พักก่อน", "ไม่มีอะไรแล้ว", "ปิดไมค์"],
            "post_speech_silence_sec": 3.0,
            "followup_timeout_sec": 60.0,
            "wake_rms_threshold": 0.025
        }
        if VOICE_SETTINGS_PATH.exists():
            try:
                with open(VOICE_SETTINGS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    defaults.update(data)
            except Exception as e:
                print(f"[Listener] Error loading voice_settings.json: {e}")

        self.wake_words = [w.strip().lower() for w in defaults["wake_words"] if w.strip()]
        self.wake_ack_phrases = defaults["wake_ack_phrases"]
        self.exit_phrases = [p.strip().lower() for p in defaults["exit_conversation_phrases"] if p.strip()]
        self.post_speech_silence = float(defaults["post_speech_silence_sec"])
        self.followup_timeout = float(defaults["followup_timeout_sec"])
        self.wake_rms_threshold = float(defaults["wake_rms_threshold"])
        self.speech_energy_threshold = config.VOICE_ENERGY_THRESHOLD

    def _on_voice_mode_signal(self, mode: str):
        """Allows toggling wake trigger via System Tray."""
        if mode == "wake_on":
            self.wake_trigger_enabled = True
            print("[Listener] 🎙️ Wake Trigger Enabled.")
            event_bus.task_log_updated.emit("Voice Listener", "เปิดการดักฟังคำปลุก (Wake Trigger Active)")
        elif mode == "wake_off":
            self.wake_trigger_enabled = False
            print("[Listener] 🎙️ Wake Trigger Disabled. Push-to-Talk only.")
            event_bus.task_log_updated.emit("Voice Listener", "ปิดการดักฟังคำปลุก (Push-to-Talk Only)")

    def _on_assistant_state_changed(self, state: str):
        """
        Monitors assistant speech. When speech ends, triggers FOLLOWUP_LOOP.
        """
        clean_state = state.lower().strip()

        if clean_state == "speaking":
            self.is_speaking = True
            self.is_processing = False
        elif clean_state == "thinking":
            self.is_processing = True
            self.is_speaking = False
        elif clean_state in ("idle", "running_tool"):
            was_speaking = self.is_speaking
            self.is_speaking = False
            self.is_processing = False

            # If assistant just finished speaking, initiate Continuous Followup Loop!
            if was_speaking:
                threading.Thread(target=self._enter_followup_loop_delayed, daemon=True).start()

    def _enter_followup_loop_delayed(self):
        """Waits 0.35s after assistant finishes speaking to prevent acoustic echo, then enters followup loop."""
        time.sleep(0.35)
        with self.state_lock:
            if not self.is_speaking and not self.is_processing and not self.is_recording:
                print(f"[Listener] 🔄 Continuous Followup Loop active (Window: {self.followup_timeout}s)...")
                self.current_state = self.STATE_FOLLOWUP_LOOP
                self._start_recording(is_followup=True)

    def toggle_push_to_talk(self):
        """
        Triggered by global hotkey (Cmd + Shift + J) or tray menu.
        Toggles between starting active recording and processing audio.
        """
        if not self._enabled:
            print("[Listener] Voice input is disabled in config.")
            return

        now = time.time()
        with self.state_lock:
            if not self.is_recording:
                # Anti-repeat cooldown check
                if now - self.last_toggle_time < self.cooldown_seconds:
                    print(f"[Listener] Cooldown active ({now - self.last_toggle_time:.2f}s < {self.cooldown_seconds}s). Ignoring rapid press.")
                    return

                if self.is_speaking or self.is_processing:
                    print("[Listener] Assistant is busy (speaking/thinking), ignoring microphone trigger.")
                    event_bus.task_log_updated.emit("Voice Input", "ระบบกำลังประมวลผลหรือพูดตอบกลับ กรุณารอสักครู่...")
                    return

                self.last_toggle_time = now
                self.current_state = self.STATE_ACTIVE_PTT
                self._start_recording(is_followup=False)
            else:
                # Minimum duration check (0.5s) to prevent double-tap cancellation
                if now - self.record_start_time < 0.5:
                    print("[Listener] Recording just initiated (< 0.5s). Ignoring immediate stop.")
                    return

                self.last_toggle_time = now
                self._stop_and_process()

    def _start_recording(self, is_followup: bool = False):
        """Starts capturing microphone frames for a user command."""
        self.is_recording = True
        self.record_start_time = time.time()
        self.has_spoken = False
        self.speech_frames = 0
        self.last_speech_time = 0.0

        with self.chunks_lock:
            self.recorded_chunks.clear()

        # Drain leftover chunks from queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

        timeout_sec = self.followup_timeout if is_followup else config.VOICE_RECORD_TIMEOUT
        state_label = "Followup Loop (พูดต่อได้เลย)" if is_followup else "Push-to-Talk"

        print(f"[Listener] 🎤 Recording started [{state_label}]. Auto-cutoff: {self.post_speech_silence}s, Timeout: {timeout_sec}s...")
        if not is_followup:
            _play_system_sound("Tink")

        event_bus.state_changed.emit("listening")
        event_bus.task_log_updated.emit(
            "Voice Input",
            f"🎤 กำลังฟังคำสั่ง... [{state_label}] (ตัดอัตโนมัติเมื่อหยุดพูด {self.post_speech_silence}s)"
        )

    def _stop_and_process(self):
        """Stops recording and hands audio off to transcription pipeline."""
        if not self.is_recording:
            return

        self.is_recording = False
        self.is_processing = True
        print("[Listener] ⏹️ Recording stopped. Processing audio...")
        _play_system_sound("Pop")
        event_bus.state_changed.emit("thinking")
        event_bus.task_log_updated.emit("Voice Input", "กำลังประมวลผลเสียงพูดด้วย Whisper...")

        with self.chunks_lock:
            chunks_to_process = list(self.recorded_chunks)
            self.recorded_chunks.clear()

        threading.Thread(
            target=self._transcribe_and_dispatch,
            args=(chunks_to_process,),
            daemon=True
        ).start()

    def _cancel_recording_to_standby(self, reason: str = "หมดเวลา"):
        """Cancels recording cleanly and transitions back to STANDBY_WAKE."""
        self.is_recording = False
        self.is_processing = False
        self.has_spoken = False
        self.current_state = self.STATE_STANDBY_WAKE

        with self.chunks_lock:
            self.recorded_chunks.clear()

        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

        print(f"[Listener] ⏹️ Recording cancelled ({reason}). Returned to STANDBY_WAKE.")
        event_bus.task_log_updated.emit("Voice Input", f"ปิดการรับเสียง ({reason}) กลับสู่โหมดรอคำปลุก")
        event_bus.state_changed.emit("idle")

    def _transcribe_and_dispatch(self, chunks: List[np.ndarray]):
        """Transcribes recorded audio frames and dispatches to Brain."""
        if not chunks:
            print("[Listener] No audio captured.")
            event_bus.task_log_updated.emit("Voice Input", "ไม่พบข้อมูลเสียงที่บันทึก")
            self._cancel_recording_to_standby("ไม่มีข้อมูลเสียง")
            return

        try:
            # Flatten all chunks to guaranteed 1D float32 arrays
            flattened_chunks = [np.asarray(c, dtype=np.float32).reshape(-1) for c in chunks if len(c) > 0]
            if not flattened_chunks:
                print("[Listener] Empty flattened chunks.")
                self._cancel_recording_to_standby("ข้อมูลเสียงว่างเปล่า")
                return

            audio_data = np.concatenate(flattened_chunks, axis=0)
            duration_seconds = len(audio_data) / self.SAMPLE_RATE

            if duration_seconds < 0.35:
                print(f"[Listener] Audio too short ({duration_seconds:.2f}s), discarded.")
                event_bus.task_log_updated.emit("Voice Input", "เสียงสั้นเกินไป")
                self._cancel_recording_to_standby("เสียงสั้นเกินไป")
                return

            transcribed_text = None
            used_engine = "local"

            # 1. Attempt Groq Cloud STT (whisper-large-v3-turbo) if enabled & key provided
            if config.STT_MODE == "groq" and config.GROQ_API_KEY:
                print(f"[Listener] 🚀 Transcribing via Groq Cloud ({config.GROQ_WHISPER_MODEL})...")
                transcribed_text = self._transcribe_groq(audio_data)
                if transcribed_text is not None:
                    used_engine = f"groq ({config.GROQ_WHISPER_MODEL})"
                else:
                    print(f"[Listener] ⚠️ Groq Cloud STT failed. Fallback to Local Faster-Whisper...")
                    event_bus.task_log_updated.emit("Voice Listener", "Groq STT ขัดข้อง กำลังใช้ Local Whisper สำรอง...")

            # 2. Local Faster-Whisper Fallback
            if transcribed_text is None:
                transcribed_text = self._transcribe_local(audio_data)
                used_engine = f"local ({config.WHISPER_MODEL})"

            if transcribed_text:
                clean_text = transcribed_text.strip()
                norm_text = re.sub(r'[\s\.,!_?\'"\-:;()\[\]{}—–~`*#]', '', clean_text.lower())

                # Check for conversation exit phrases ("ขอบคุณครับ", "พอแค่นี้", "พักก่อน")
                is_exit_phrase = False
                for ep in self.exit_phrases:
                    norm_ep = re.sub(r'[\s\.,!_?\'"\-:;()\[\]{}—–~`*#]', '', ep.lower())
                    if norm_ep and norm_ep in norm_text:
                        is_exit_phrase = True
                        break

                if is_exit_phrase:
                    print(f"[Listener] 🚪 Exit conversation phrase detected: \"{clean_text}\"")
                    ack_reply = "รับทราบครับ พักก่อนนะครับ"
                    event_bus.task_log_updated.emit("Voice Input", f"สิ้นสุดการสนทนา: \"{clean_text}\"")
                    event_bus.assistant_reply_ready.emit(ack_reply)
                    event_bus.assistant_speak_ready.emit(ack_reply)
                    self._cancel_recording_to_standby("ผู้ใช้แจ้งสิ้นสุดการสนทนา")
                    return

                # Check if transcribed text is ONLY a wake word
                wake_variants = [re.sub(r'[\s\.,!_?\'"\-:;()\[\]{}—–~`*#]', '', w.lower()) for w in self.wake_words]
                wake_variants.extend(["heygaby", "gaby", "heyjarvis", "hijarvis", "jarvis"])
                is_wake_only = norm_text in wake_variants

                # Strip leading wake words if followed by actual command
                if not is_wake_only:
                    for w in sorted(self.wake_words, key=len, reverse=True):
                        pattern = rf'^(?:{re.escape(w)})[\s,:\.!?]*'
                        clean_text = re.sub(pattern, '', clean_text, flags=re.IGNORECASE).strip()

                if is_wake_only or not clean_text:
                    print(f"[Listener] ℹ️ Only wake word was recognized: \"{transcribed_text}\". Awaiting command...")
                    event_bus.task_log_updated.emit("Voice Input", f"ตรวจพบคำเรียก \"{transcribed_text}\" พร้อมรับคำสั่ง...")
                    self._cancel_recording_to_standby("พบเฉพาะคำปลุก")
                    return

                print(f"[Listener] 🗣️ Transcribed [{used_engine}]: \"{clean_text}\"")
                event_bus.task_log_updated.emit("Voice Input", f"ถอดความ [{used_engine}]: \"{clean_text}\"")
                event_bus.user_message_received.emit(clean_text)
            else:
                print(f"[Listener] No speech recognized [{used_engine}].")
                event_bus.task_log_updated.emit("Voice Input", "ไม่พบเสียงพูดในสิ่งที่บันทึก")
                self._cancel_recording_to_standby("ไม่พบเสียงพูด")

        except Exception as e:
            print(f"[Listener] Transcription error: {e}")
            event_bus.task_log_updated.emit("Voice Input Error", f"ข้อผิดพลาด: {str(e)}")
            self._cancel_recording_to_standby("เกิดข้อผิดพลาดในการถอดความ")

    def _play_random_wake_ack(self):
        """
        Picks a random cached wake ack audio file, plays it completely using blocking afplay,
        and flushes the mic buffer to prevent acoustic echo leakage.
        """
        if not self.cached_ack_files:
            self.cached_ack_files = ensure_cached_ack_phrases(self.wake_ack_phrases)

        if self.cached_ack_files and sys.platform == "darwin":
            ack_path = random.choice(self.cached_ack_files)
            try:
                # Play completely (BLOCKING)
                subprocess.run(["/usr/bin/afplay", ack_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # Small pause to clear residual acoustic room echo
                time.sleep(0.15)
            except Exception as e:
                print(f"[Listener] Error playing ack audio: {e}")

        # Flush any mic frames accumulated while the ack was playing
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

    def _check_wake_snippet(self, audio_data: np.ndarray):
        """
        Checks a short speech burst for wake words using Local Faster-Whisper (beam_size=1).
        """
        if self.is_recording or self.is_speaking or self.is_processing:
            return

        try:
            if self.whisper_model is None:
                self._load_whisper_model()

            if self.whisper_model is None:
                return

            segments, info = self.whisper_model.transcribe(
                audio_data,
                beam_size=1,
                vad_filter=True,
                vad_parameters={"speech_pad_ms": 200},
                initial_prompt="hi jarvis, jarvis, จาร์วิส, จาวิส, ไฮ จาร์วิส",
            )

            # Filter out non-speech noise bursts
            if info and getattr(info, "all_language_probs", None) is None and getattr(info, "no_speech_prob", 0.0) > 0.65:
                return

            transcribed = " ".join([s.text for s in segments]).strip()
            if not transcribed:
                return

            # Check matching against wake words
            norm_text = re.sub(r'[\s\.,!_?\'"\-:;()\[\]{}—–~`*#]', '', transcribed.lower())
            matched_wake_word = None
            for w in self.wake_words:
                norm_w = re.sub(r'[\s\.,!_?\'"\-:;()\[\]{}—–~`*#]', '', w.lower())
                if norm_w and norm_w in norm_text:
                    matched_wake_word = w
                    break

            if matched_wake_word:
                print(f"[Listener] 🔔 Wake word detected: \"{matched_wake_word}\" (Text: \"{transcribed}\")")
                event_bus.task_log_updated.emit("Wake Word", f"ตรวจพบคำปลุก: '{matched_wake_word}'")

                # Play acknowledgment phrase completely and cleanly before recording command
                self._play_random_wake_ack()

                with self.state_lock:
                    if not self.is_recording and not self.is_speaking and not self.is_processing:
                        self.current_state = self.STATE_ACTIVE_PTT
                        self._start_recording(is_followup=False)

        except Exception as e:
            print(f"[Listener] Wake check error: {e}")

    def _audio_to_wav_bytes(self, audio_data: np.ndarray, sample_rate: int = 16000) -> io.BytesIO:
        """Converts float32 audio numpy array to 16-bit PCM WAV in memory."""
        if audio_data.dtype in (np.float32, np.float64):
            audio_int16 = np.clip(audio_data, -1.0, 1.0)
            audio_int16 = (audio_int16 * 32767).astype(np.int16)
        else:
            audio_int16 = audio_data.astype(np.int16)

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(audio_int16.tobytes())
        buffer.seek(0)
        return buffer

    def _transcribe_groq(self, audio_data: np.ndarray) -> Optional[str]:
        """Transcribes audio using Groq Cloud API (whisper-large-v3-turbo)."""
        api_key = config.GROQ_API_KEY
        if not api_key:
            return None

        try:
            wav_buffer = self._audio_to_wav_bytes(audio_data, self.SAMPLE_RATE)
            url = "https://api.groq.com/openai/v1/audio/transcriptions"
            headers = {"Authorization": f"Bearer {api_key}"}
            files = {"file": ("speech.wav", wav_buffer.read(), "audio/wav")}
            data = {
                "model": config.GROQ_WHISPER_MODEL,
                "response_format": "json"
            }
            if getattr(config, "WHISPER_LANGUAGE", None):
                data["language"] = config.WHISPER_LANGUAGE
            if config.WHISPER_INITIAL_PROMPT:
                data["prompt"] = config.WHISPER_INITIAL_PROMPT

            response = requests.post(url, headers=headers, files=files, data=data, timeout=12)
            if response.status_code == 200:
                result = response.json()
                return result.get("text", "").strip()
            else:
                print(f"[Listener] Groq STT HTTP {response.status_code}: {response.text}")
                return None
        except Exception as e:
            print(f"[Listener] Groq STT request failed: {e}")
            return None

    def _transcribe_local(self, audio_data: np.ndarray) -> str:
        """Transcribes audio using local Faster-Whisper model."""
        if self.whisper_model is None:
            self._load_whisper_model()

        transcribe_kwargs = {
            "beam_size": 5,
            "vad_filter": True,
            "vad_parameters": {"speech_pad_ms": 400},
            "initial_prompt": config.WHISPER_INITIAL_PROMPT if config.WHISPER_INITIAL_PROMPT else None,
        }
        if getattr(config, "WHISPER_LANGUAGE", None):
            transcribe_kwargs["language"] = config.WHISPER_LANGUAGE

        segments, _ = self.whisper_model.transcribe(
            audio_data,
            **transcribe_kwargs
        )
        return " ".join([s.text for s in segments]).strip()

    def _load_whisper_model(self):
        """Loads Faster-Whisper model into memory if not already loaded."""
        if self.whisper_model is not None:
            return

        print(f"[Listener] 🧠 Loading Faster-Whisper ({config.WHISPER_MODEL}) into RAM on CPU (int8)...")
        event_bus.task_log_updated.emit(
            "Voice Listener",
            f"กำลังโหลดโมเดล Faster-Whisper ({config.WHISPER_MODEL}) เข้า RAM..."
        )
        try:
            from faster_whisper import WhisperModel
            self.whisper_model = WhisperModel(
                config.WHISPER_MODEL,
                device="cpu",
                compute_type="int8"
            )
            print(f"[Listener] ✅ Faster-Whisper ({config.WHISPER_MODEL}) loaded in RAM.")
            event_bus.task_log_updated.emit(
                "Voice Listener",
                f"โมเดล Faster-Whisper ({config.WHISPER_MODEL}) พร้อมใช้งานใน RAM"
            )
        except Exception as e:
            print(f"[Listener] ❌ Failed to load Whisper model: {e}")
            event_bus.task_log_updated.emit("Listener Error", f"โหลด Whisper ล้มเหลว: {e}")

    def _unload_whisper_model(self):
        """Unloads Faster-Whisper model from memory and triggers garbage collection to free RAM."""
        if self.whisper_model is not None:
            print(f"[Listener] 🧹 Unloading Faster-Whisper from RAM...")
            try:
                del self.whisper_model
            except Exception:
                pass
            self.whisper_model = None
            import gc
            gc.collect()
            print("[Listener] 🍃 RAM successfully freed.")

    def start_listening(self):
        """Starts background listener if enabled."""
        if not self._enabled:
            print("[Listener] Voice input disabled in config (VOICE_INPUT_ENABLED=false).")
            return

        self.is_running = True
        self.start()

    def run(self):
        """Main background loop maintaining sounddevice input stream."""
        # Pre-cache wake ack phrases
        self.cached_ack_files = ensure_cached_ack_phrases(self.wake_ack_phrases)

        # Pre-load Local Faster-Whisper for Wake Word detection if enabled
        if self.wake_trigger_enabled:
            self._load_whisper_model()

        try:
            import sounddevice as sd

            def _audio_callback(indata, frames, time_info, status):
                if self.is_speaking:
                    return
                # Put frames if recording or if standby wake listening
                if self.is_recording or (self.wake_trigger_enabled and not self.is_processing):
                    self.audio_queue.put(indata.copy())

            with sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=self.CHANNELS,
                dtype="float32",
                blocksize=self.BLOCK_SIZE,
                callback=_audio_callback
            ):
                print(f"[Listener] Single-Pipeline Mic session active @ {self.SAMPLE_RATE}Hz. Standby wake: {self.wake_trigger_enabled}")
                event_bus.task_log_updated.emit(
                    "Microphone Session",
                    "Single-Pipeline Microphone พร้อมใช้งาน (Push-to-Talk + Wake Trigger)"
                )

                while self.is_running:
                    now = time.time()

                    # 1. Active Recording Mode (Push-to-Talk or Continuous Followup)
                    if self.is_recording:
                        elapsed = now - self.record_start_time
                        is_followup = (self.current_state == self.STATE_FOLLOWUP_LOOP)
                        current_timeout = self.followup_timeout if is_followup else config.VOICE_RECORD_TIMEOUT

                        # Fetch available audio frames
                        try:
                            chunk = self.audio_queue.get(timeout=0.06)
                            chunk_1d = np.asarray(chunk, dtype=np.float32).reshape(-1)
                            with self.chunks_lock:
                                self.recorded_chunks.append(chunk_1d)

                            # Calculate RMS energy of current audio block
                            rms = float(np.sqrt(np.mean(chunk_1d**2))) if len(chunk_1d) > 0 else 0.0
                            if rms >= self.speech_energy_threshold:
                                self.speech_frames += 1
                                if self.speech_frames >= 2:
                                    if not self.has_spoken:
                                        self.has_spoken = True
                                        print(f"[Listener] 🗣️ Voice activity confirmed (RMS: {rms:.4f} >= {self.speech_energy_threshold}).")
                                    self.last_speech_time = now
                            else:
                                self.speech_frames = max(0, self.speech_frames - 1)
                        except queue.Empty:
                            pass

                        # Condition A: User has spoken, and now paused for post_speech_silence (3.0s) -> Auto-stop and process!
                        if self.has_spoken and self.last_speech_time > 0:
                            silence_duration = now - self.last_speech_time
                            if silence_duration >= self.post_speech_silence:
                                print(f"[Listener] ⏱️ Post-speech silence ({silence_duration:.2f}s >= {self.post_speech_silence}s) detected. Auto-stopping and processing...")
                                with self.state_lock:
                                    self._stop_and_process()
                                continue

                        # Condition B: Timeout reached
                        if elapsed >= current_timeout:
                            if not self.has_spoken:
                                print(f"[Listener] ⏱️ Timeout ({current_timeout}s) with NO speech detected.")
                                with self.state_lock:
                                    self._cancel_recording_to_standby("หมดเวลารอ (ไม่พบเสียงพูด)")
                            else:
                                print(f"[Listener] ⏱️ Maximum recording timeout ({current_timeout}s) reached. Stopping...")
                                with self.state_lock:
                                    self._stop_and_process()
                            continue

                    # 2. Standby Wake Listening Mode (Local Whisper beam_size=1)
                    else:
                        if self.wake_trigger_enabled and not self.is_speaking and not self.is_processing:
                            try:
                                chunk = self.audio_queue.get(timeout=0.08)
                                chunk_1d = np.asarray(chunk, dtype=np.float32).reshape(-1)
                                rms = float(np.sqrt(np.mean(chunk_1d**2))) if len(chunk_1d) > 0 else 0.0

                                if rms >= self.wake_rms_threshold:
                                    with self.wake_buffer_lock:
                                        self.wake_buffer.append(chunk_1d)
                                        self.wake_silence_count = 0
                                else:
                                    with self.wake_buffer_lock:
                                        if len(self.wake_buffer) > 0:
                                            self.wake_silence_count += 1
                                            self.wake_buffer.append(chunk_1d)

                                            # Pause of ~0.35s (approx 5-6 blocks) after speech burst
                                            if self.wake_silence_count >= 5:
                                                snippet = np.concatenate(self.wake_buffer, axis=0).flatten()
                                                self.wake_buffer.clear()
                                                self.wake_silence_count = 0
                                                duration = len(snippet) / self.SAMPLE_RATE
                                                if 0.35 <= duration <= 3.5:
                                                    threading.Thread(
                                                        target=self._check_wake_snippet,
                                                        args=(snippet,),
                                                        daemon=True
                                                    ).start()

                                with self.wake_buffer_lock:
                                    # Cap max buffer to 3.5s to prevent runaway memory
                                    if len(self.wake_buffer) > int(3.5 * self.SAMPLE_RATE / self.BLOCK_SIZE):
                                        snippet = np.concatenate(self.wake_buffer, axis=0).flatten()
                                        self.wake_buffer.clear()
                                        self.wake_silence_count = 0
                                        threading.Thread(
                                            target=self._check_wake_snippet,
                                            args=(snippet,),
                                            daemon=True
                                        ).start()

                            except queue.Empty:
                                pass
                        else:
                            # Discard any queued frames to prevent lag
                            while not self.audio_queue.empty():
                                try:
                                    self.audio_queue.get_nowait()
                                except queue.Empty:
                                    break
                            time.sleep(0.05)

        except Exception as e:
            perm_msg = (
                "ไม่สามารถเข้าถึงไมโครโฟนได้ กรุณาตรวจสอบสิทธิ์ Microphone "
                "ใน System Settings > Privacy & Security > Microphone (กำลังเปิดหน้าตั้งค่าให้อัตโนมัติ...)"
            )
            print(f"[Listener] ⚠️ Microphone access error: {e}")
            event_bus.task_log_updated.emit("Microphone Permission Required", perm_msg)
            if sys.platform == "darwin":
                try:
                    subprocess.Popen(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone"])
                except Exception:
                    pass
            self.is_running = False

    def stop(self):
        """Stops listener thread and cleans up RAM."""
        self.is_running = False
        self._unload_whisper_model()
