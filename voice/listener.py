"""
Voice Listener module for Jarvis Desktop Assistant.
1-Tap Toggle Hotkey Mode (Cmd + Shift + J):
- Press 1: Starts recording, plays Tink.aiff, sets Dynamic Island to 'Listening... (Cmd+Shift+J to send)'
- Press 2 (or auto-close timeout 10-25s): Stops recording, plays Pop.aiff, sets Dynamic Island to 'Thinking...',
  transcribes with Faster-Whisper, and dispatches command directly to Event Bus.
- Features automatic cooldown & debounce to prevent accidental re-pressing / overlapping triggers.
"""

import os
import sys
import io
import wave
import time
import queue
import subprocess
import threading
from typing import Optional, List

import numpy as np
import requests

import config
from core.event_bus import event_bus


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
    Operates in 1-Tap Toggle Mode via Cmd+Shift+J with auto-timeout and cooldown guard.
    """

    SAMPLE_RATE = 16000
    CHANNELS = 1
    BLOCK_SIZE = 1024        # ~64ms per audio chunk

    def __init__(self):
        super().__init__(daemon=True)
        self.is_running = False
        self.is_recording = False
        self.is_speaking = False
        self.is_processing = False
        self._enabled = config.VOICE_INPUT_ENABLED
        self.record_start_time = 0.0
        self.last_toggle_time = 0.0

        # Auto-timeout (10 - 25 seconds) and anti-repeat cooldown
        self.timeout_seconds = config.VOICE_RECORD_TIMEOUT
        self.cooldown_seconds = config.VOICE_COOLDOWN_SECONDS

        self.audio_queue = queue.Queue()
        self.recorded_chunks: List[np.ndarray] = []
        self.chunks_lock = threading.Lock()
        self.toggle_lock = threading.Lock()

        self.whisper_model = None

        # Listen to event bus signals
        event_bus.toggle_voice_record_signal.connect(self.toggle_recording)
        event_bus.state_changed.connect(self._on_state_changed)

    def _on_state_changed(self, state: str):
        """Track assistant speaking / thinking state to prevent feedback and overlapping requests."""
        clean_state = state.lower().strip()
        if clean_state == "speaking":
            self.is_speaking = True
            self.is_processing = False
        elif clean_state == "thinking":
            self.is_processing = True
            self.is_speaking = False
        elif clean_state in ("idle", "running_tool"):
            time.sleep(0.2)
            self.is_speaking = False
            self.is_processing = False

    def toggle_recording(self):
        """
        Toggles between starting audio recording and stopping/processing.
        Protected by anti-repeat cooldown and auto-session safeguards.
        """
        if not self._enabled:
            print("[Listener] Voice input is disabled in config.")
            return

        now = time.time()

        with self.toggle_lock:
            if not self.is_recording:
                # 1. Anti-repeat cooldown check before starting a new recording session
                if now - self.last_toggle_time < self.cooldown_seconds:
                    print(f"[Listener] Cooldown active ({now - self.last_toggle_time:.2f}s < {self.cooldown_seconds}s). Ignoring rapid press.")
                    return

                # 2. Prevent starting recording while assistant is speaking or thinking
                if self.is_speaking or self.is_processing:
                    print("[Listener] Assistant is busy (speaking/thinking), ignoring microphone trigger.")
                    event_bus.task_log_updated.emit("Voice Input", "ระบบกำลังประมวลผลหรือพูดตอบกลับ กรุณารอสักครู่...")
                    return

                self.last_toggle_time = now
                self._start_recording()
            else:
                # 3. Minimum recording duration (0.6s) to filter out accidental micro double-taps
                if now - self.record_start_time < 0.6:
                    print("[Listener] Recording just initiated (< 0.6s). Ignoring immediate stop.")
                    return

                self.last_toggle_time = now
                self._stop_and_process()

    def _start_recording(self):
        """Starts recording user command."""
        self.is_recording = True
        self.record_start_time = time.time()

        with self.chunks_lock:
            self.recorded_chunks.clear()

        # Drain leftover chunks from queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

        print(f"[Listener] 🎤 Recording started (Cmd+Shift+J). Auto-timeout: {self.timeout_seconds}s...")
        _play_system_sound("Tink")
        event_bus.state_changed.emit("listening")
        event_bus.task_log_updated.emit(
            "Voice Input",
            f"🎤 กำลังฟังเสียงคำสั่ง... (จะปิดอัตโนมัติใน {self.timeout_seconds} วินาที หรือกด Cmd+Shift+J เพื่อส่ง)"
        )

    def _stop_and_process(self):
        """Stops recording and hands off audio to Whisper."""
        if not self.is_recording:
            return

        self.is_recording = False
        self.is_processing = True
        print("[Listener] ⏹️ Recording stopped. Processing audio...")
        _play_system_sound("Pop")
        event_bus.state_changed.emit("thinking")
        event_bus.task_log_updated.emit("Voice Input", "กำลังประมวลผลเสียงพูดด้วย Faster-Whisper...")

        with self.chunks_lock:
            chunks_to_process = list(self.recorded_chunks)
            self.recorded_chunks.clear()

        # Run transcription in a background thread to keep audio stream responsive
        threading.Thread(
            target=self._transcribe_and_dispatch,
            args=(chunks_to_process,),
            daemon=True
        ).start()

    def _transcribe_and_dispatch(self, chunks: List[np.ndarray]):
        """Transcribes recorded audio frames and dispatches to Brain."""
        if not chunks:
            print("[Listener] No audio captured.")
            event_bus.task_log_updated.emit("Voice Input", "ไม่พบข้อมูลเสียงที่บันทึก")
            self.is_processing = False
            event_bus.state_changed.emit("idle")
            return

        try:
            audio_data = np.concatenate(chunks, axis=0).flatten()
            duration_seconds = len(audio_data) / self.SAMPLE_RATE

            if duration_seconds < 0.3:
                print(f"[Listener] Audio too short ({duration_seconds:.2f}s), discarded.")
                event_bus.task_log_updated.emit("Voice Input", "เสียงสั้นเกินไป กรุณาลองใหม่อีกครั้ง")
                self.is_processing = False
                event_bus.state_changed.emit("idle")
                return

            transcribed_text = None
            used_engine = "local"

            # 1. Attempt Groq Cloud STT (whisper-large-v3-turbo) if enabled & key provided
            if config.STT_MODE == "groq":
                if config.GROQ_API_KEY:
                    print(f"[Listener] 🚀 Transcribing via Groq Cloud ({config.GROQ_WHISPER_MODEL})...")
                    transcribed_text = self._transcribe_groq(audio_data)
                    if transcribed_text is not None:
                        used_engine = f"groq ({config.GROQ_WHISPER_MODEL})"
                    else:
                        print(f"[Listener] ⚠️ Groq Cloud STT failed. Fallback to Local Faster-Whisper ({config.WHISPER_MODEL})...")
                        event_bus.task_log_updated.emit(
                            "Voice Listener",
                            f"Groq STT ขัดข้อง กำลังสลับไปใช้ Local Faster-Whisper ({config.WHISPER_MODEL}) สำรอง..."
                        )
                else:
                    print(f"[Listener] ⚠️ GROQ_API_KEY is empty. Fallback to Local Faster-Whisper ({config.WHISPER_MODEL})...")

            # 2. Local Faster-Whisper Fallback (if Groq skipped, failed, or STT_MODE == 'local')
            if transcribed_text is None:
                transcribed_text = self._transcribe_local(audio_data)
                used_engine = f"local ({config.WHISPER_MODEL})"

            if transcribed_text:
                print(f"[Listener] 🗣️ Transcribed [{used_engine}]: \"{transcribed_text}\"")
                event_bus.task_log_updated.emit("Voice Input", f"ถอดความ [{used_engine}]: \"{transcribed_text}\"")
                event_bus.user_message_received.emit(transcribed_text)
            else:
                print(f"[Listener] No speech recognized [{used_engine}].")
                event_bus.task_log_updated.emit("Voice Input", "ไม่พบเสียงพูดในสิ่งที่บันทึก")
                self.is_processing = False
                event_bus.state_changed.emit("idle")

        except Exception as e:
            print(f"[Listener] Transcription error: {e}")
            event_bus.task_log_updated.emit("Voice Input Error", f"ข้อผิดพลาด: {str(e)}")
            self.is_processing = False
            event_bus.state_changed.emit("idle")

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

        segments, _ = self.whisper_model.transcribe(
            audio_data,
            beam_size=5,
            vad_filter=True,
            vad_parameters={"speech_pad_ms": 400},
            initial_prompt=config.WHISPER_INITIAL_PROMPT if config.WHISPER_INITIAL_PROMPT else None,
        )
        return " ".join([s.text for s in segments]).strip()

    def _load_whisper_model(self):
        """Loads Faster-Whisper model into memory."""
        if self.whisper_model is not None:
            return

        print(f"[Listener] Loading Faster-Whisper ({config.WHISPER_MODEL}) on CPU (int8)...")
        event_bus.task_log_updated.emit(
            "Voice Listener",
            f"กำลังโหลดโมเดล Faster-Whisper ({config.WHISPER_MODEL})..."
        )
        try:
            from faster_whisper import WhisperModel
            self.whisper_model = WhisperModel(
                config.WHISPER_MODEL,
                device="cpu",
                compute_type="int8"
            )
            print(f"[Listener] Faster-Whisper ({config.WHISPER_MODEL}) ready.")
            event_bus.task_log_updated.emit(
                "Voice Listener",
                f"โมเดล Whisper พร้อมใช้งาน กด Cmd+Shift+J เพื่อเริ่ม/หยุดบันทึกเสียง"
            )
        except Exception as e:
            print(f"[Listener] Failed to load Whisper model: {e}")
            event_bus.task_log_updated.emit("Listener Error", f"โหลด Whisper ล้มเหลว: {e}")

    def start_listening(self):
        """Starts background listener if enabled."""
        if not self._enabled:
            print("[Listener] Voice input disabled in config (VOICE_INPUT_ENABLED=false).")
            return

        self.is_running = True
        self.start()

    def run(self):
        """Main background loop maintaining sounddevice input stream."""
        # STT Engine Mode Initialization
        if config.STT_MODE == "groq" and config.GROQ_API_KEY:
            print(f"[Listener] STT Mode: groq ({config.GROQ_WHISPER_MODEL}) - Faster-Whisper ({config.WHISPER_MODEL}) on standby for fallback.")
            event_bus.task_log_updated.emit(
                "Voice Listener",
                f"โหมดรับเสียง: Groq Cloud ({config.GROQ_WHISPER_MODEL}) พร้อมระบบสำรองในเครื่อง"
            )
        elif config.STT_MODE == "groq" and not config.GROQ_API_KEY:
            print(f"[Listener] STT Mode: groq configured but GROQ_API_KEY is empty. Pre-loading Faster-Whisper ({config.WHISPER_MODEL})...")
            self._load_whisper_model()
        else:
            print(f"[Listener] STT Mode: local ({config.WHISPER_MODEL})")
            self._load_whisper_model()

        try:
            import sounddevice as sd

            def _audio_callback(indata, frames, time_info, status):
                # Persistent Mic Session: Return immediately if not recording to use 0% CPU
                if not self.is_recording:
                    return
                if status:
                    pass
                if not self.is_speaking:
                    self.audio_queue.put(indata.copy())

            with sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=self.CHANNELS,
                dtype="float32",
                blocksize=self.BLOCK_SIZE,
                callback=_audio_callback
            ):
                print(f"[Listener] Persistent microphone session active @ {self.SAMPLE_RATE}Hz. (Auto-timeout: {self.timeout_seconds}s)")
                event_bus.task_log_updated.emit(
                    "Microphone Session",
                    f"Persistent microphone session พร้อมใช้งาน (คูลดาวน์/ตัดอัตโนมัติใน {self.timeout_seconds} วินาที)"
                )

                while self.is_running:
                    if self.is_recording:
                        elapsed = time.time() - self.record_start_time

                        # Check auto-timeout (10 - 25 seconds window)
                        if elapsed >= self.timeout_seconds:
                            print(f"[Listener] ⏱️ Auto-close timeout ({self.timeout_seconds}s) reached. Stopping and sending...")
                            with self.toggle_lock:
                                self._stop_and_process()
                            continue

                        try:
                            chunk = self.audio_queue.get(timeout=0.1)
                            with self.chunks_lock:
                                self.recorded_chunks.append(chunk)
                        except queue.Empty:
                            pass
                    else:
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
        """Stops listener thread."""
        self.is_running = False
