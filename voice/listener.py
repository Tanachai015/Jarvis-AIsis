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
from collections import deque
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

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
    BLOCK_SIZE = 512        # 32ms per audio chunk (Optimal for Silero VAD 16kHz & OpenWakeWord)

    # State Machine Constants
    STATE_STANDBY_WAKE = "STANDBY_WAKE"
    STATE_ACTIVE_PTT = "ACTIVE_PTT"
    STATE_FOLLOWUP_LOOP = "FOLLOWUP_LOOP"

    def __init__(self, speaker: Optional[Any] = None):
        super().__init__(daemon=True)
        self.is_running = False
        self._enabled = config.VOICE_INPUT_ENABLED
        self.wake_trigger_enabled = getattr(config, "WAKE_TRIGGER_ENABLED", False)
        self.wake_consecutive_hits = 0
        self.recent_wake_scores: deque = deque(maxlen=4)
        self.last_vad_speech_time = 0.0
        self.stream_wake_event = threading.Event()
        self.speaker = speaker

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
        self.vad_lock = threading.Lock()

        # VAD & Wake Word Models
        self.vad_model = None
        self.oww_model = None
        self.whisper_model = None

        # Cached wake acknowledgment audio files
        self.cached_ack_files: List[str] = []

        # Connect event bus signals
        event_bus.toggle_voice_record_signal.connect(self.toggle_push_to_talk)
        event_bus.cancel_voice_record_signal.connect(self.cancel_listening_direct)
        event_bus.voice_mode_changed.connect(self._on_voice_mode_signal)
        event_bus.state_changed.connect(self._on_assistant_state_changed)

    def _load_voice_settings(self):
        """Loads configuration from voice_settings.json with safe fallbacks."""
        defaults = {
            "wake_words": ["jarvis", "hi jarvis", "hey jarvis", "จาร์วิส", "จาวิส", "ไฮ จาร์วิส"],
            "wake_ack_phrases": ["สวัสดีครับ", "พร้อมครับ", "ว่าไงครับ", "ครับบอส"],
            "exit_conversation_phrases": ["พอแค่นี้", "ขอบคุณครับ", "หยุดฟัง", "พักก่อน", "ไม่มีอะไรแล้ว", "ปิดไมค์"],
            "post_speech_silence_sec": 3.0,
            "followup_timeout_sec": 60.0,
            "wake_rms_threshold": 0.025,
            "wake_model_name": "hey_jarvis",
            "wake_mic_gain": 1.6,
            "wake_score_threshold": 0.48,
            "vad_speech_threshold": 0.5,
            "barge_in_vad_threshold": 0.65,
            "barge_in_enabled": True,
            "barge_in_min_duration_sec": 0.6,
            "barge_in_rms_threshold": 0.025
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
        self.interrupt_stop_phrases = [p.strip().lower() for p in defaults.get("interrupt_stop_phrases", [
            "หยุดก่อน", "โอเคหยุด", "โอเคหยุดก่อน", "หยุดก่อนจาร์วิส", "จาร์วิสหยุดก่อน",
            "โอเคพอ", "พอก่อน", "พอก่อนจาร์วิส", "จาร์วิสพอก่อน",
            "ok stop", "stop stop", "stop please", "please stop"
        ]) if p.strip()]
        self.post_speech_silence = float(defaults["post_speech_silence_sec"])
        self.followup_timeout = float(defaults["followup_timeout_sec"])
        self.wake_rms_threshold = float(defaults["wake_rms_threshold"])
        self.wake_model_name = str(defaults.get("wake_model_name", "hey_jarvis"))
        self.wake_mic_gain = float(defaults.get("wake_mic_gain", 1.6))
        self.wake_score_threshold = float(defaults.get("wake_score_threshold", 0.48))
        self.vad_speech_threshold = float(defaults.get("vad_speech_threshold", 0.5))
        self.barge_in_vad_threshold = float(defaults.get("barge_in_vad_threshold", 0.60))
        self.barge_in_enabled = bool(defaults.get("barge_in_enabled", True))
        self.barge_in_min_duration = float(defaults.get("barge_in_min_duration_sec", 0.6))
        self.barge_in_rms_threshold = float(defaults.get("barge_in_rms_threshold", 0.020))
        self.speech_energy_threshold = config.VOICE_ENERGY_THRESHOLD

        # State tracking for barge-in
        self.barge_in_buffer: List[np.ndarray] = []
        self.barge_in_frames_count = 0
        self.barge_in_silence_grace_frames = 0

        # Audio buffer for OpenWakeWord 1280-sample (80ms) accumulation
        self.oww_audio_buffer: np.ndarray = np.empty(0, dtype=np.int16)

        # Flag to prevent followup loop when conversation has ended with exit phrase
        self.suppress_next_followup: bool = False

    def _load_vad_model(self):
        """Loads Silero VAD neural network for real-time human voice detection."""
        if self.vad_model is not None:
            return
        try:
            with self.vad_lock:
                from silero_vad import load_silero_vad
                self.vad_model = load_silero_vad()
            print("[Listener] ✅ Silero VAD loaded into memory.")
            event_bus.task_log_updated.emit("Voice Listener", "Silero VAD พร้อมตรวจจับเสียงมนุษย์")
        except Exception as e:
            print(f"[Listener] ⚠️ Silero VAD load failed: {e}. Falling back to energy threshold.")
            with self.vad_lock:
                self.vad_model = None

    def _load_openwakeword_model(self):
        """Loads OpenWakeWord ONNX model for low-latency, edge wake word detection."""
        if self.oww_model is not None:
            return
        try:
            print(f"[Listener] ⏳ Initializing OpenWakeWord ONNX model ('{self.wake_model_name}')...")
            import openwakeword
            Model = getattr(openwakeword, "Model", None)
            if Model is None:
                from openwakeword.model import Model  # type: ignore
            self.oww_model = Model(wakeword_models=[self.wake_model_name], inference_framework="onnx")
            print(f"[Listener] ✅ OpenWakeWord ('{self.wake_model_name}') loaded successfully. Ready to detect wake trigger.")
            event_bus.task_log_updated.emit("Voice Listener", f"OpenWakeWord ('{self.wake_model_name}') พร้อมใช้งาน")
        except Exception as e:
            print(f"[Listener] ⚠️ OpenWakeWord load failed: {e}. Wake trigger will be inactive.")
            self.oww_model = None

    def _is_human_speech(self, chunk_1d: np.ndarray, threshold: float = 0.5) -> bool:
        """
        Uses Silero VAD to detect whether a 512-sample (16kHz) float32 chunk contains human speech.
        Protected with vad_lock and torch.no_grad() to guarantee thread safety and prevent C++ segfaults.
        """
        if self.vad_model is not None and len(chunk_1d) == 512:
            try:
                import torch
                with self.vad_lock:
                    with torch.no_grad():
                        tensor_chunk = torch.from_numpy(chunk_1d.copy())
                        prob = self.vad_model(tensor_chunk, self.SAMPLE_RATE).item()
                return prob >= threshold
            except Exception:
                pass
        rms = float(np.sqrt(np.mean(chunk_1d**2))) if len(chunk_1d) > 0 else 0.0
        return rms >= self.speech_energy_threshold

    def _reset_vad_states(self):
        """Resets Silero VAD recurrent hidden states thread-safely."""
        if self.vad_model is not None and hasattr(self.vad_model, "reset_states"):
            try:
                with self.vad_lock:
                    self.vad_model.reset_states()
            except Exception:
                pass

    def _on_voice_mode_signal(self, mode: str):
        """Allows toggling wake trigger via System Tray or Dynamic Island."""
        if mode == "wake_on":
            self.wake_trigger_enabled = True
            if self.oww_model is None:
                self._load_openwakeword_model()
            self.stream_wake_event.set()
            print("[Listener] 🎙️ Wake Trigger Enabled (OpenWakeWord).")
            event_bus.task_log_updated.emit("Voice Listener", "เปิดการดักฟังคำปลุก (OpenWakeWord Active)")
        elif mode == "wake_off":
            self.wake_trigger_enabled = False
            self.wake_consecutive_hits = 0
            self.stream_wake_event.set()
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
            self.barge_in_buffer.clear()
            self.barge_in_frames_count = 0
            self.barge_in_silence_grace_frames = 0
            self.oww_audio_buffer = np.empty(0, dtype=np.int16)
            self._reset_vad_states()
        elif clean_state == "thinking":
            self.is_processing = True
            self.is_speaking = False
            self.barge_in_buffer.clear()
            self.barge_in_frames_count = 0
            self.barge_in_silence_grace_frames = 0
            self.oww_audio_buffer = np.empty(0, dtype=np.int16)
            self._reset_vad_states()
        elif clean_state in ("idle", "running_tool"):
            was_speaking = self.is_speaking
            self.is_speaking = False
            self.is_processing = False
            self.barge_in_buffer.clear()
            self.barge_in_frames_count = 0
            self.barge_in_silence_grace_frames = 0
            self.oww_audio_buffer = np.empty(0, dtype=np.int16)
            self._reset_vad_states()

            # If assistant just finished speaking, initiate Continuous Followup Loop unless suppressed!
            if was_speaking:
                if self.suppress_next_followup:
                    print("[Listener] 🛑 Followup loop suppressed after exit conversation.")
                    self.suppress_next_followup = False
                    self.current_state = self.STATE_STANDBY_WAKE
                else:
                    threading.Thread(target=self._enter_followup_loop_delayed, daemon=True).start()

    def _enter_followup_loop_delayed(self):
        """Waits 0.35s after assistant finishes speaking to prevent acoustic echo, then enters followup loop."""
        time.sleep(0.35)
        with self.state_lock:
            # Check if followup should be suppressed (e.g. exit phrase spoken)
            if self.suppress_next_followup:
                print("[Listener] 🛑 Followup loop suppressed in delayed worker.")
                self.suppress_next_followup = False
                self.current_state = self.STATE_STANDBY_WAKE
                return
            # Check if speaker was interrupted by barge-in; if so, do NOT enter followup loop!
            if self.speaker and getattr(self.speaker, "is_interrupted", False):
                return
            if not self.is_speaking and not self.is_processing and not self.is_recording:
                print(f"[Listener] 🔄 Continuous Followup Loop active (Window: {self.followup_timeout}s)...")
                self.current_state = self.STATE_FOLLOWUP_LOOP
                self._start_recording(is_followup=True)

    def trigger_barge_in_direct(self):
        """Called directly by global hotkey (Esc key) to stop speaking and start listening immediately."""
        self.is_speaking = False
        self.barge_in_buffer.clear()
        self.oww_audio_buffer = np.empty(0, dtype=np.int16)
        self._reset_vad_states()
        with self.state_lock:
            self.current_state = self.STATE_ACTIVE_PTT
            self._start_recording(is_followup=False)

    def cancel_listening_direct(self):
        """Immediately cancels ongoing listening/recording, discards audio without sending, and returns to silent idle."""
        with self.state_lock:
            if self.is_recording:
                print("[Listener] 🛑 Listening cancelled by user (Esc). Audio discarded.")
                self.suppress_next_followup = True
                self._cancel_recording_to_standby("ผู้ใช้กดยกเลิก (Esc)")
                return True
        return False

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

    def _start_recording(self, is_followup: bool = False, initial_chunks: Optional[List[np.ndarray]] = None):
        """Starts capturing microphone frames for a user command."""
        self.is_recording = True
        self.stream_wake_event.set()
        self.record_start_time = time.time()
        self.has_spoken = True if initial_chunks else False
        self.speech_frames = 2 if initial_chunks else 0
        self.last_speech_time = time.time() if initial_chunks else 0.0
        self._reset_vad_states()

        with self.chunks_lock:
            self.recorded_chunks.clear()
            if initial_chunks:
                for c in initial_chunks:
                    self.recorded_chunks.append(np.asarray(c, dtype=np.float32).reshape(-1))

        # Drain leftover chunks from queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

        timeout_sec = self.followup_timeout if is_followup else config.VOICE_RECORD_TIMEOUT
        if initial_chunks:
            state_label = "Barge-in Interrupted (พูดแทรกทันที)"
        else:
            state_label = "Followup Loop (พูดต่อได้เลย)" if is_followup else "Push-to-Talk"

        print(f"[Listener] 🎤 Recording started [{state_label}]. Auto-cutoff: {self.post_speech_silence}s, Timeout: {timeout_sec}s...")
        if not is_followup and not initial_chunks:
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
        self.stream_wake_event.set()
        self.is_processing = True
        self._reset_vad_states()
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
        self.stream_wake_event.set()
        self.is_processing = False
        self.has_spoken = False
        self.current_state = self.STATE_STANDBY_WAKE
        self._reset_vad_states()

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

            # Pre-STT Energy & Silero VAD Gate (active when Silero VAD is loaded in production)
            # Prevents Whisper hallucinations on silence/noise without breaking mocked unit tests.
            audio_rms = float(np.sqrt(np.mean(audio_data ** 2)))
            audio_peak = float(np.max(np.abs(audio_data)))
            if self.vad_model is not None:
                vad_speech_frames = 0
                for i in range(0, len(audio_data) - 511, 512):
                    if self._is_human_speech(audio_data[i:i + 512], threshold=self.vad_speech_threshold):
                        vad_speech_frames += 1
                        if vad_speech_frames >= 2:
                            break

                if (audio_rms < 0.004 and audio_peak < 0.025) or vad_speech_frames == 0:
                    print(f"[Listener] 🔇 Silence/noise rejected pre-STT (RMS={audio_rms:.5f}, Peak={audio_peak:.4f}, VAD={vad_speech_frames}).")
                    event_bus.task_log_updated.emit("Voice Input", "ไม่พบเสียงพูดที่ชัดเจน (ตัดเสียงรบกวน)")
                    self._cancel_recording_to_standby("ไม่พบเสียงพูด")
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

                # Post-STT Hallucination Guard on low-energy audio
                hallucination_norms = {
                    "สวัสดี", "สวัสดีครับ", "สวัสดีค่ะ", "ขอบคุณ", "ขอบคุณครับ", "ขอบคุณค่ะ",
                    "จริงปิดแท็บสวัสดี", "ซับไทยโดย", "โปรดติดตาม", "thankyou", "thanksforwatching",
                    "you", "bye", "mbc"
                }
                if self.vad_model is not None and audio_rms < 0.012 and (norm_text in hallucination_norms or len(norm_text) <= 2):
                    print(f"[Listener] 🛡️ Whisper hallucination rejected (RMS={audio_rms:.5f}): \"{clean_text}\"")
                    self._cancel_recording_to_standby("ตัดข้อความหลอนจากความเงียบ")
                    return

                # Check for conversation exit phrases ("ขอบคุณครับ", "พอแค่นี้", "พักก่อน")
                is_exit_phrase = False
                matched_exit_word = None

                # 1. Exact/Substring check
                for ep in self.exit_phrases:
                    norm_ep = re.sub(r'[\s\.,!_?\'"\-:;()\[\]{}—–~`*#]', '', ep.lower())
                    if norm_ep and norm_ep in norm_text:
                        is_exit_phrase = True
                        matched_exit_word = ep
                        break

                # 2. Fuzzy RapidFuzz check (only if short utterance < 30 chars to protect multi-clause commands)
                if not is_exit_phrase and len(clean_text) < 30:
                    try:
                        from core.thai_nlp import fuzzy_match_phrase
                        fuzzy_match = fuzzy_match_phrase(clean_text, self.exit_phrases, threshold=78.0)
                        if fuzzy_match:
                            is_exit_phrase = True
                            matched_exit_word = f"{fuzzy_match} (fuzzy)"
                    except Exception:
                        pass

                if is_exit_phrase:
                    print(f"[Listener] 🚪 Exit conversation phrase detected ({matched_exit_word}): \"{clean_text}\"")
                    ack_reply = "รับทราบครับ พักก่อนนะครับ"
                    event_bus.task_log_updated.emit("Voice Input", f"สิ้นสุดการสนทนา: \"{clean_text}\"")
                    self.suppress_next_followup = True
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
        """Main background loop maintaining sounddevice input stream On-Demand."""
        # Pre-cache wake ack phrases
        self.cached_ack_files = ensure_cached_ack_phrases(self.wake_ack_phrases)

        # Initialize Silero VAD (Whisper is NOT loaded into RAM on standby)
        self._load_vad_model()
        if self.wake_trigger_enabled:
            self._load_openwakeword_model()

        try:
            import sounddevice as sd

            def _audio_callback(indata, frames, time_info, status):
                speaker_busy = self.is_speaking or (self.speaker is not None and getattr(self.speaker, "is_speaking", False))
                # When assistant is speaking, do NOT capture audio to avoid acoustic echo and conserve API quota
                if speaker_busy:
                    return
                # Put frames if recording or if standby wake listening
                if self.is_recording or (self.wake_trigger_enabled and not self.is_processing):
                    self.audio_queue.put(indata.copy())

            while self.is_running:
                need_stream = self.is_recording or (self.wake_trigger_enabled and not self.is_processing)
                if not need_stream:
                    # In Standard Mode (idle/standby), release microphone stream so macOS does NOT show orange icon!
                    self.stream_wake_event.wait(timeout=0.1)
                    self.stream_wake_event.clear()
                    continue

                # Open microphone stream On-Demand
                try:
                    with sd.InputStream(
                        samplerate=self.SAMPLE_RATE,
                        channels=self.CHANNELS,
                        dtype="float32",
                        blocksize=self.BLOCK_SIZE,
                        callback=_audio_callback
                    ):
                        print(f"[Listener] Single-Pipeline Mic session active @ {self.SAMPLE_RATE}Hz. Block size: {self.BLOCK_SIZE}. Standby wake: {self.wake_trigger_enabled}")
                        event_bus.task_log_updated.emit(
                            "Microphone Session",
                            "Single-Pipeline Microphone พร้อมใช้งาน (Silero VAD + OpenWakeWord)"
                        )

                        while self.is_running and (self.is_recording or (self.wake_trigger_enabled and not self.is_processing)):
                            now = time.time()

                            # 0. Assistant is speaking: Drain audio queue to prevent buildup and sleep briefly (Zero STT / API overhead)
                            speaker_busy = self.is_speaking or (self.speaker is not None and getattr(self.speaker, "is_speaking", False))
                            if speaker_busy:
                                while not self.audio_queue.empty():
                                    try:
                                        self.audio_queue.get_nowait()
                                    except queue.Empty:
                                        break
                                time.sleep(0.04)
                                continue

                            # 1. Active Recording Mode (Push-to-Talk or Continuous Followup)
                            if self.is_recording:
                                elapsed = now - self.record_start_time
                                is_followup = (self.current_state == self.STATE_FOLLOWUP_LOOP)
                                current_timeout = self.followup_timeout if is_followup else config.VOICE_RECORD_TIMEOUT

                                # Fetch available audio frames
                                try:
                                    chunk = self.audio_queue.get(timeout=0.04)
                                    chunk_1d = np.asarray(chunk, dtype=np.float32).reshape(-1)
                                    with self.chunks_lock:
                                        self.recorded_chunks.append(chunk_1d)

                                    # Verify human voice activity via Silero VAD
                                    if self._is_human_speech(chunk_1d, threshold=self.vad_speech_threshold):
                                        self.last_vad_speech_time = now
                                        self.speech_frames += 1
                                        if self.speech_frames >= 2:
                                            if not self.has_spoken:
                                                self.has_spoken = True
                                                print("[Listener] 🗣️ Human voice activity confirmed via Silero VAD.")
                                            self.last_speech_time = now
                                    else:
                                        self.speech_frames = max(0, self.speech_frames - 1)
                                except queue.Empty:
                                    pass

                                # Condition A: User has spoken, and now paused for post_speech_silence (3.0s) -> Auto-stop and process!
                                if self.has_spoken and self.last_speech_time > 0:
                                    silence_duration = now - self.last_speech_time
                                    if silence_duration >= self.post_speech_silence:
                                        print(f"[Listener] ⏱️ Post-speech silence ({silence_duration:.2f}s >= {self.post_speech_silence}s) detected via Silero VAD. Auto-stopping and processing...")
                                        with self.state_lock:
                                            self._stop_and_process()
                                        continue

                                # Condition B: Timeout reached
                                if elapsed >= current_timeout:
                                    if not self.has_spoken:
                                        print(f"[Listener] ⏱️ Timeout ({current_timeout}s) with NO human speech detected.")
                                        with self.state_lock:
                                            self._cancel_recording_to_standby("หมดเวลารอ (ไม่พบเสียงพูด)")
                                    else:
                                        print(f"[Listener] ⏱️ Maximum recording timeout ({current_timeout}s) reached. Stopping...")
                                        with self.state_lock:
                                            self._stop_and_process()
                                    continue

                            # 2. Standby Wake Listening Mode (OpenWakeWord hey_jarvis)
                            else:
                                if self.wake_trigger_enabled and not self.is_speaking and not self.is_processing:
                                    try:
                                        chunk = self.audio_queue.get(timeout=0.06)
                                        chunk_1d = np.asarray(chunk, dtype=np.float32).reshape(-1)
                                        if len(chunk_1d) != 512:
                                            continue

                                        # Track Silero VAD human voice activity in standby
                                        if self._is_human_speech(chunk_1d, threshold=self.vad_speech_threshold):
                                            self.last_vad_speech_time = now

                                        if self.oww_model is not None:
                                            # Convert 1D float32 audio chunk to 16-bit PCM for OpenWakeWord with wake_mic_gain
                                            amplified = chunk_1d * self.wake_mic_gain
                                            chunk_int16 = (np.clip(amplified, -1.0, 1.0) * 32767.0).astype(np.int16)
                                            self.oww_audio_buffer = np.concatenate((self.oww_audio_buffer, chunk_int16)) if len(self.oww_audio_buffer) > 0 else chunk_int16

                                            # OpenWakeWord performs optimal feature extraction on 1280-sample chunks (80ms @ 16kHz)
                                            while len(self.oww_audio_buffer) >= 1280:
                                                oww_chunk = self.oww_audio_buffer[:1280]
                                                self.oww_audio_buffer = self.oww_audio_buffer[1280:]

                                                scores = self.oww_model.predict(oww_chunk)
                                                score = float(scores.get(self.wake_model_name, 0.0))

                                                # Transparent diagnostic logging for scores >= 0.15
                                                if score >= 0.15:
                                                    print(f"[WakeWord Debug] 🎙️ OpenWakeWord '{self.wake_model_name}' Score: {score:.3f} (Threshold: {self.wake_score_threshold})")

                                                self.recent_wake_scores.append(score)
                                                max_recent = max(self.recent_wake_scores) if self.recent_wake_scores else score
                                                avg_recent = (sum(self.recent_wake_scores) / len(self.recent_wake_scores)) if self.recent_wake_scores else score

                                                has_recent_speech = (now - self.last_vad_speech_time) < 1.0

                                                # Deterministic Adaptive Wake Trigger:
                                                # 1. Strong Peak Trigger: Single chunk >= 0.38 (or >= 0.80 * threshold) with recent human speech (Silero VAD)
                                                # 2. Confirmed Multi-Chunk: Chunk >= target_thresh (0.35) and rolling window support with recent human speech
                                                target_thresh = getattr(config, "WAKE_SCORE_THRESHOLD", 0.35)
                                                is_strong_hit = (score >= 0.38) or (score >= (self.wake_score_threshold * 0.80))
                                                is_confirmed_hit = (score >= target_thresh and (self.wake_consecutive_hits >= 1 or avg_recent >= (target_thresh * 0.85)))

                                                if is_strong_hit or is_confirmed_hit:
                                                    self.wake_consecutive_hits += 1
                                                    print(f"[WakeWord Debug] 🎯 Hit #{self.wake_consecutive_hits}: Score {score:.3f} (Strong: {is_strong_hit}, Confirmed: {is_confirmed_hit}, VAD: {has_recent_speech})")

                                                    if has_recent_speech:
                                                        print(f"[Listener] 🎯 Wake Word confirmed! Model: '{self.wake_model_name}', Score: {score:.3f} >= {self.wake_score_threshold}")
                                                        event_bus.task_log_updated.emit(
                                                            "Wake Word Detected",
                                                            f"🎯 ตรวจพบคำปลุก '{self.wake_model_name}' (คะแนน: {score:.2f}) ด้วย OpenWakeWord"
                                                        )
                                                        # Reset wake model internal prediction buffer and accumulation queue
                                                        self.wake_consecutive_hits = 0
                                                        self.recent_wake_scores.clear()
                                                        self.oww_model.reset()
                                                        self.oww_audio_buffer = np.empty(0, dtype=np.int16)

                                                        # Play acknowledgment phrase completely and cleanly before recording command
                                                        self._play_random_wake_ack()

                                                        # Drain leftover queue
                                                        while not self.audio_queue.empty():
                                                            try:
                                                                self.audio_queue.get_nowait()
                                                            except queue.Empty:
                                                                break

                                                        with self.state_lock:
                                                            if not self.is_recording and not self.is_speaking and not self.is_processing:
                                                                self.current_state = self.STATE_ACTIVE_PTT
                                                                self._start_recording(is_followup=False)
                                                        break
                                                    else:
                                                        print(f"[WakeWord Debug] ⚠️ Wake score high but waiting for Silero VAD voice activity within 1.0s.")
                                                else:
                                                    # Only reset hits when score drops back down to background level
                                                    if score < (self.wake_score_threshold * 0.7):
                                                        self.wake_consecutive_hits = 0
                                            continue
                                        else:
                                            time.sleep(0.04)

                                    except queue.Empty:
                                        pass
                                else:
                                    # Discard any queued frames to prevent lag
                                    while not self.audio_queue.empty():
                                        try:
                                            self.audio_queue.get_nowait()
                                        except queue.Empty:
                                            break
                                    time.sleep(0.04)
                    print("[Listener] ⏹️ Mic stream closed (Hardware released).")
                except Exception as inner_e:
                    print(f"[Listener] ⚠️ Stream error: {inner_e}")
                    time.sleep(0.2)

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
        self.stream_wake_event.set()
        self._unload_whisper_model()
        with self.vad_lock:
            self.vad_model = None
        self.oww_model = None
