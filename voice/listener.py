"""
Voice Listener module for Jarvis Desktop Assistant.
1-Tap Toggle Hotkey Mode (Cmd + Shift + J):
- Press 1: Starts recording, plays Tink.aiff, sets Dynamic Island to 'Listening... (Cmd+Shift+J to send)'
- Press 2 (or auto-close timeout 10-25s): Stops recording, plays Pop.aiff, sets Dynamic Island to 'Thinking...',
  transcribes with Groq Cloud STT (whisper-large-v3-turbo) / Local Faster-Whisper fallback, and dispatches command.
- Robust State Isolation: Distinct states for Wake Word Standby, Wake Ack Playback, Command Recording, and STT Processing.
- Automatic RAM Lifecycle: Faster-Whisper is retained in RAM during hi_jarvis/hybrid, and freed with gc.collect() in push_to_talk.
"""

import os
import re
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


def _ensure_wake_ack_sound():
    """Pre-synthesizes wake word acknowledgement sound to /tmp/jarvis_wake_ack.mp3 in background."""
    if not config.WAKE_ACK_ENABLED or not config.WAKE_ACK_TEXT:
        return
    cache_file = "/tmp/jarvis_wake_ack.mp3"
    try:
        import edge_tts
        import asyncio

        async def _synth():
            comm = edge_tts.Communicate(
                text=config.WAKE_ACK_TEXT,
                voice=config.TTS_VOICE_TH,
                pitch=config.TTS_PITCH_TH,
                rate=config.TTS_RATE_TH,
                volume=config.TTS_VOLUME_TH
            )
            await comm.save(cache_file)

        asyncio.run(_synth())
        print(f"[Listener] 🔊 Pre-synthesized wake acknowledgement: '{config.WAKE_ACK_TEXT}'")
    except Exception as e:
        print(f"[Listener] Pre-synthesize wake ack note: {e}")


class ListenerState:
    """Discrete states for clear isolation of voice processing lifecycle."""
    IDLE = "idle"                        # Standby in push_to_talk, or idle
    WAKE_LISTENING = "wake_listening"    # Standby in hi_jarvis / hybrid, actively listening for wake word
    RECORDING = "recording"              # Actively recording user command
    PROCESSING = "processing"            # STT transcribing & dispatching to Brain


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
        self._enabled = config.VOICE_INPUT_ENABLED

        # State machine and generational epoch
        self.listen_mode = config.VOICE_LISTEN_MODE
        self.state = ListenerState.WAKE_LISTENING if self.listen_mode in ("hi_jarvis", "hybrid") else ListenerState.IDLE
        self.session_epoch = 0

        # Public boolean flags for UI / compatibility
        self.is_recording = False
        self.is_speaking = False
        self.is_processing = False

        self.record_start_time = 0.0
        self.last_toggle_time = 0.0

        # Thresholds and timers
        self.timeout_seconds = config.VOICE_RECORD_TIMEOUT
        self.cooldown_seconds = config.VOICE_COOLDOWN_SECONDS
        self.post_speech_silence = config.VOICE_POST_SPEECH_SILENCE
        self.speech_energy_threshold = config.VOICE_ENERGY_THRESHOLD
        self.wake_energy_threshold = config.WAKE_ENERGY_THRESHOLD
        self.has_spoken = False
        self.last_speech_time = 0.0

        # Wake word detection
        self.wake_words = [w.strip().lower() for w in config.WAKE_WORDS]
        self.wake_buffer: List[np.ndarray] = []
        self.wake_buffer_lock = threading.Lock()
        self.wake_silence_count = 0
        self._wake_buffering_logged = False
        self._wake_check_lock = threading.Lock()

        # Dedicated queues for complete isolation:
        # 1. record_queue: used exclusively during active command recording
        # 2. wake_queue: used exclusively during wake word standby
        self.record_queue = queue.Queue()
        self.wake_queue = queue.Queue()
        self.audio_queue = self.record_queue  # Backward-compatibility alias

        self.recorded_chunks: List[np.ndarray] = []
        self.chunks_lock = threading.Lock()
        self.toggle_lock = threading.Lock()

        self.whisper_model = None

        # Listen to event bus signals
        event_bus.toggle_voice_record_signal.connect(self.toggle_recording)
        event_bus.voice_mode_changed.connect(self.set_listen_mode)
        event_bus.state_changed.connect(self._on_state_changed)

    def set_listen_mode(self, mode: str):
        """Switches voice listening mode at runtime without restarting."""
        clean_mode = mode.lower().strip()
        if clean_mode not in ("push_to_talk", "hi_jarvis", "hybrid"):
            return

        old_mode = self.listen_mode
        self.listen_mode = clean_mode

        mode_names = {
            "hybrid": "Hybrid (Hotkey + Hi Jarvis)",
            "push_to_talk": "Push-to-Talk (Cmd+Shift+J Only)",
            "hi_jarvis": "Wake Word Only (Hi Jarvis)",
        }
        desc = mode_names.get(self.listen_mode, self.listen_mode)
        print(f"[Listener] 🎙️ Voice Listen Mode switched to: {self.listen_mode} [{desc}]")
        event_bus.task_log_updated.emit("Voice Listener", f"เปลี่ยนโหมดรับเสียงเป็น: {desc}")

        # Invalidate any in-flight wake checks or transitions
        self.session_epoch += 1

        # Clean up buffers, queues, and transient flags to guarantee a clean state across mode switches
        with self.wake_buffer_lock:
            self.wake_buffer.clear()
            self.wake_silence_count = 0
            self._wake_buffering_logged = False

        while not self.wake_queue.empty():
            try:
                self.wake_queue.get_nowait()
            except queue.Empty:
                break

        while not self.record_queue.empty():
            try:
                self.record_queue.get_nowait()
            except queue.Empty:
                break

        # Reset transient flags
        self.is_recording = False
        self.is_speaking = False
        self.is_processing = False
        with self.chunks_lock:
            self.recorded_chunks.clear()

        # State transition and RAM Management Policy according to mode:
        if self.listen_mode == "push_to_talk":
            self.state = ListenerState.IDLE
            # Unload Local Faster-Whisper to immediately return RAM to system
            self._unload_whisper_model()
        else:
            self.state = ListenerState.WAKE_LISTENING
            # Keep Local Faster-Whisper in RAM for wake word detection
            if self.whisper_model is None:
                self._load_whisper_model()
            threading.Thread(target=_ensure_wake_ack_sound, daemon=True).start()

        event_bus.state_changed.emit("idle")

    def _on_state_changed(self, state: str):
        """Track assistant speaking / thinking state to prevent feedback and overlapping requests."""
        clean_state = state.lower().strip()
        if clean_state == "speaking":
            self.is_speaking = True
            self.is_processing = False
        elif clean_state == "thinking":
            self.is_processing = True
            self.is_speaking = False
        elif clean_state in ("idle", "running_tool", "listening"):
            self.is_speaking = False
            self.is_processing = False
            if clean_state == "idle" and not self.is_recording:
                if self.listen_mode in ("hi_jarvis", "hybrid"):
                    self.state = ListenerState.WAKE_LISTENING
                else:
                    self.state = ListenerState.IDLE

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
                # 0. Check if mode is hi_jarvis (wake word only)
                if self.listen_mode == "hi_jarvis":
                    print("[Listener] Mode is 'hi_jarvis' (Wake Word Only). Say 'Hi Jarvis' to activate, or switch mode via Menu Bar.")
                    event_bus.task_log_updated.emit(
                        "Voice Listener",
                        "โหมดปัจจุบันคือ Wake Word Only กรุณาพูด 'Hi Jarvis' หรือเปลี่ยนโหมดในเมนูบาร์"
                    )
                    return

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

    def _start_recording(self, initial_audio: Optional[np.ndarray] = None):
        """Starts recording user command."""
        self.session_epoch += 1
        self.state = ListenerState.RECORDING
        self.is_recording = True
        self.is_speaking = False
        self.is_processing = False
        self.record_start_time = time.time()
        self.has_spoken = True if initial_audio is not None else False
        self.last_speech_time = time.time() if initial_audio is not None else 0.0

        with self.chunks_lock:
            self.recorded_chunks.clear()
            if initial_audio is not None:
                arr = np.asarray(initial_audio, dtype=np.float32).reshape(-1)
                if arr.size > 0:
                    self.recorded_chunks.append(arr)

        # Clear wake buffer and drain both queues
        with self.wake_buffer_lock:
            self.wake_buffer.clear()
            self.wake_silence_count = 0
            self._wake_buffering_logged = False

        while not self.wake_queue.empty():
            try:
                self.wake_queue.get_nowait()
            except queue.Empty:
                break

        while not self.record_queue.empty():
            try:
                self.record_queue.get_nowait()
            except queue.Empty:
                break

        print(f"[Listener] 🎤 Recording started (Mode: {self.listen_mode}). Auto-timeout: {self.timeout_seconds}s...")
        _play_system_sound("Tink")
        event_bus.state_changed.emit("listening")
        event_bus.task_log_updated.emit(
            "Voice Input",
            f"🎤 กำลังฟังเสียงคำสั่ง... (โหมด: {self.listen_mode}, ตัดอัตโนมัติหลังเงียบ {self.post_speech_silence}s)"
        )

    def _stop_and_process(self):
        """Stops recording and hands off audio to Whisper."""
        if not self.is_recording:
            return

        self.session_epoch += 1
        self.state = ListenerState.PROCESSING
        self.is_recording = False
        self.is_processing = True
        print("[Listener] ⏹️ Recording stopped. Processing audio...")
        _play_system_sound("Pop")
        event_bus.state_changed.emit("thinking")
        event_bus.task_log_updated.emit("Voice Input", "กำลังประมวลผลเสียงพูด...")

        with self.chunks_lock:
            chunks_to_process = list(self.recorded_chunks)
            self.recorded_chunks.clear()

        # Run transcription in a background thread to keep audio stream responsive
        threading.Thread(
            target=self._transcribe_and_dispatch,
            args=(chunks_to_process, self.session_epoch),
            daemon=True
        ).start()

    def _transcribe_and_dispatch(self, chunks: List[np.ndarray], epoch: int):
        """Transcribes recorded audio frames and dispatches to Brain."""
        if not chunks:
            print("[Listener] No audio captured.")
            event_bus.task_log_updated.emit("Voice Input", "ไม่พบข้อมูลเสียงที่บันทึก")
            self.is_processing = False
            self.state = ListenerState.WAKE_LISTENING if self.listen_mode in ("hi_jarvis", "hybrid") else ListenerState.IDLE
            event_bus.state_changed.emit("idle")
            return

        try:
            # Enforce 1D float32 representation on all chunks before concatenation
            flattened_chunks = [
                np.asarray(c, dtype=np.float32).reshape(-1)
                for c in chunks
                if c is not None and len(c) > 0
            ]
            if not flattened_chunks:
                print("[Listener] No valid audio captured.")
                event_bus.task_log_updated.emit("Voice Input", "ไม่พบข้อมูลเสียงที่บันทึก")
                self.is_processing = False
                self.state = ListenerState.WAKE_LISTENING if self.listen_mode in ("hi_jarvis", "hybrid") else ListenerState.IDLE
                event_bus.state_changed.emit("idle")
                return

            audio_data = np.concatenate(flattened_chunks, axis=0).reshape(-1)
            duration_seconds = len(audio_data) / self.SAMPLE_RATE

            if duration_seconds < 0.45:
                print(f"[Listener] Audio too short ({duration_seconds:.2f}s < 0.45s), discarded.")
                event_bus.task_log_updated.emit("Voice Input", "เสียงสั้นเกินไป กรุณาลองใหม่อีกครั้ง")
                self.is_processing = False
                self.state = ListenerState.WAKE_LISTENING if self.listen_mode in ("hi_jarvis", "hybrid") else ListenerState.IDLE
                event_bus.state_changed.emit("idle")
                return

            # Reject empty/quiet background noise before transcribing command
            overall_rms = float(np.sqrt(np.mean(audio_data**2)))
            if overall_rms < self.speech_energy_threshold * 0.5:
                print(f"[Listener] Audio energy too low (RMS: {overall_rms:.4f} < {self.speech_energy_threshold * 0.5:.4f}), discarded.")
                event_bus.task_log_updated.emit("Voice Input", "ระดับเสียงเบาเกินไป ไม่พบคำสั่ง")
                self.is_processing = False
                self.state = ListenerState.WAKE_LISTENING if self.listen_mode in ("hi_jarvis", "hybrid") else ListenerState.IDLE
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

        except Exception as e:
            print(f"[Listener] Transcription error: {e}")
            event_bus.task_log_updated.emit("Voice Input Error", f"ข้อผิดพลาด: {str(e)}")
        finally:
            self.is_processing = False
            if self.listen_mode in ("hi_jarvis", "hybrid"):
                self.state = ListenerState.WAKE_LISTENING
            else:
                self.state = ListenerState.IDLE
            event_bus.state_changed.emit("idle")

    def _play_wake_ack_non_blocking(self):
        """
        Plays wake acknowledgement sound (MP3 or Tink) non-blocking in background subprocess
        without blocking the command recording loop and without muting the microphone (never sets is_speaking=True).
        """
        ack_file = "/tmp/jarvis_wake_ack.mp3"
        played = False
        if config.WAKE_ACK_ENABLED and config.WAKE_ACK_TEXT:
            # If cache file does not exist yet, trigger background synthesis for future use
            if not os.path.exists(ack_file) or os.path.getsize(ack_file) < 500:
                threading.Thread(target=_ensure_wake_ack_sound, daemon=True).start()

            if sys.platform == "darwin" and os.path.exists(ack_file) and os.path.getsize(ack_file) >= 500:
                try:
                    subprocess.Popen(
                        ["/usr/bin/afplay", ack_file],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    played = True
                except Exception as e:
                    print(f"[Listener] afplay wake ack note: {e}")

        if not played:
            _play_system_sound("Tink")

    def _handle_wake_ack_and_record(self, epoch: int):
        """
        Acknowledges wake word non-blocking (independent playback) and immediately
        starts recording the user's actual command without muting microphone or freezing round 2.
        """
        with self.toggle_lock:
            # Verify generational epoch and state
            if epoch != self.session_epoch or self.state != ListenerState.WAKE_LISTENING or self.listen_mode not in ("hi_jarvis", "hybrid"):
                return

            if self.is_recording or self.is_processing:
                return

            event_bus.task_log_updated.emit("Wake Word", f"จาร์วิส: '{config.WAKE_ACK_TEXT}'")

            # Guarantee microphone remains unmuted
            self.is_speaking = False

            # Invalidate any concurrent wake checks
            self.session_epoch += 1
            self.state = ListenerState.RECORDING

            # Clear and drain wake state completely
            with self.wake_buffer_lock:
                self.wake_buffer.clear()
                self.wake_silence_count = 0
                self._wake_buffering_logged = False

            while not self.wake_queue.empty():
                try:
                    self.wake_queue.get_nowait()
                except queue.Empty:
                    break

            # Play wake ack non-blocking
            self._play_wake_ack_non_blocking()

            # Start recording user command immediately
            self._start_recording()

    def _check_wake_snippet(self, audio_data: np.ndarray, epoch: int):
        """
        Transcribes a short speech burst to detect wake words.
        MANDATORY: Uses Local Faster-Whisper ONLY (beam_size=1) to preserve Groq Cloud API quota.
        Includes anti-hallucination filters (duration, RMS energy, no_speech_prob, compression_ratio).
        """
        if epoch != self.session_epoch or self.state != ListenerState.WAKE_LISTENING or self.listen_mode not in ("hi_jarvis", "hybrid"):
            return

        if self.is_recording or self.is_speaking or self.is_processing:
            return

        # Prevent concurrent Faster-Whisper transcribe calls on CPU
        if not self._wake_check_lock.acquire(blocking=False):
            return

        try:
            if epoch != self.session_epoch or self.state != ListenerState.WAKE_LISTENING or self.listen_mode not in ("hi_jarvis", "hybrid"):
                return

            # Force 1D float32 representation
            audio_data = np.asarray(audio_data, dtype=np.float32).reshape(-1)
            if len(audio_data) == 0:
                return

            duration = len(audio_data) / self.SAMPLE_RATE
            # Filter 1: Duration check (wake word phrase like 'Hi Jarvis' or 'จาร์วิส' is typically 0.45s - 3.5s)
            if duration < 0.45 or duration > 3.5:
                return

            # Filter 2: Snippet RMS energy check (prevent low background noise from waking Jarvis)
            snippet_rms = float(np.sqrt(np.mean(audio_data**2)))
            min_energy = self.wake_energy_threshold * 0.70
            if snippet_rms < min_energy:
                return

            print(f"[Listener] ⚡ Checking wake word with Faster-Whisper ({duration:.2f}s, RMS: {snippet_rms:.4f} >= {min_energy:.4f})...")

            # Wake word checking uses Local Faster-Whisper exclusively, NEVER Groq Cloud
            if self.whisper_model is None:
                if self.listen_mode in ("hi_jarvis", "hybrid"):
                    self._load_whisper_model()
                else:
                    return

            if self.whisper_model is None:
                return

            # Fast 1-beam transcribe without VAD (already an energy-detected speech segment)
            segments, _ = self.whisper_model.transcribe(
                audio_data,
                beam_size=1,  # Fast 1-beam search (~50ms)
                vad_filter=False,
                initial_prompt="hi jarvis, jarvis, จาร์วิส, จาวิส, ไฮ จาร์วิส",
            )

            # Filter 3: Whisper Hallucination Filter (no_speech_prob, compression_ratio, avg_logprob)
            valid_words = []
            for s in segments:
                if s.no_speech_prob > 0.60:
                    print(f"[Listener] ⚠️ Wake snippet discarded (no_speech_prob={s.no_speech_prob:.2f} > 0.60): '{s.text}'")
                    continue
                if s.compression_ratio > 2.4:
                    print(f"[Listener] ⚠️ Wake snippet discarded (compression_ratio={s.compression_ratio:.2f} > 2.4): '{s.text}'")
                    continue
                if s.avg_logprob < -1.2:
                    print(f"[Listener] ⚠️ Wake snippet discarded (avg_logprob={s.avg_logprob:.2f} < -1.2): '{s.text}'")
                    continue
                t = s.text.strip()
                if t:
                    valid_words.append(t)

            transcribed = " ".join(valid_words).strip()
            if not transcribed:
                return

            # Check again if epoch is still valid before processing matched word
            if epoch != self.session_epoch or self.state != ListenerState.WAKE_LISTENING:
                return

            print(f"[Listener] 🔍 Whisper heard: \"{transcribed}\" (Target words: {self.wake_words})")

            # Normalize text (lowercase, strip whitespace, punctuation, and symbols)
            norm_text = re.sub(r'[\s\.,!_?\'"\-:;()\[\]{}—–~`*#]', '', transcribed.lower())
            matched_wake_word = None
            for w in self.wake_words:
                norm_w = re.sub(r'[\s\.,!_?\'"\-:;()\[\]{}—–~`*#]', '', w.lower())
                if norm_w and norm_w in norm_text:
                    matched_wake_word = w
                    break

            if matched_wake_word:
                print(f"[Listener] 🔔 Wake word detected via Local Whisper: \"{matched_wake_word}\" (Text: \"{transcribed}\")")
                event_bus.task_log_updated.emit("Wake Word", f"ตรวจพบคำปลุก: '{matched_wake_word}' (Local Whisper)")
                threading.Thread(
                    target=self._handle_wake_ack_and_record,
                    args=(epoch,),
                    daemon=True
                ).start()

        except Exception as e:
            print(f"[Listener] Wake check error: {e}")
        finally:
            self._wake_check_lock.release()

    def _audio_to_wav_bytes(self, audio_data: np.ndarray, sample_rate: int = 16000) -> io.BytesIO:
        """Converts float32 audio numpy array to 16-bit PCM WAV in memory."""
        audio_data = np.asarray(audio_data, dtype=np.float32).reshape(-1)
        audio_int16 = np.clip(audio_data, -1.0, 1.0)
        audio_int16 = (audio_int16 * 32767).astype(np.int16)

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
            audio_data = np.asarray(audio_data, dtype=np.float32).reshape(-1)
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
        """Transcribes audio using local Faster-Whisper model with anti-hallucination filtering."""
        if self.whisper_model is None:
            self._load_whisper_model()

        audio_data = np.asarray(audio_data, dtype=np.float32).reshape(-1)
        segments, _ = self.whisper_model.transcribe(
            audio_data,
            beam_size=5,
            vad_filter=True,
            vad_parameters={"speech_pad_ms": 400},
            initial_prompt=config.WHISPER_INITIAL_PROMPT if config.WHISPER_INITIAL_PROMPT else None,
        )
        valid_segments = []
        for s in segments:
            # Hallucination safeguards:
            if s.no_speech_prob > 0.65:
                print(f"[Listener] Local Whisper dropped segment (no_speech_prob={s.no_speech_prob:.2f}): '{s.text}'")
                continue
            if s.compression_ratio > 2.4:
                print(f"[Listener] Local Whisper dropped segment (compression_ratio={s.compression_ratio:.2f}): '{s.text}'")
                continue
            if s.avg_logprob < -1.2:
                print(f"[Listener] Local Whisper dropped segment (avg_logprob={s.avg_logprob:.2f}): '{s.text}'")
                continue
            t = s.text.strip()
            if t:
                valid_segments.append(t)

        return " ".join(valid_segments).strip()

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
            print(f"[Listener] 🧹 Unloading Faster-Whisper ({config.WHISPER_MODEL}) from RAM to free memory...")
            try:
                del self.whisper_model
            except Exception:
                pass
            self.whisper_model = None
            import gc
            gc.collect()
            print("[Listener] 🍃 RAM successfully freed.")
            event_bus.task_log_updated.emit("Voice Listener", "คืน RAM จากโมเดล Whisper เรียบร้อยแล้ว")

    def start_listening(self):
        """Starts background listener if enabled."""
        if not self._enabled:
            print("[Listener] Voice input disabled in config (VOICE_INPUT_ENABLED=false).")
            return

        self.is_running = True
        self.start()

    def run(self):
        """Main background loop maintaining sounddevice input stream."""
        # STT Engine & RAM Pre-loading based on initial Voice Listen Mode
        if self.listen_mode in ("hi_jarvis", "hybrid"):
            print(f"[Listener] Mode '{self.listen_mode}' active at startup. Pre-loading Local Faster-Whisper into RAM for Wake Word detection...")
            self._load_whisper_model()
            threading.Thread(target=_ensure_wake_ack_sound, daemon=True).start()
        else:
            print(f"[Listener] Mode 'push_to_talk' active at startup. Local Faster-Whisper NOT loaded into RAM (saving memory).")

        try:
            import sounddevice as sd

            def _audio_callback(indata, frames, time_info, status):
                if self.is_speaking:
                    return
                # Always flatten chunk to 1D float32 at audio intake
                chunk_1d = np.asarray(indata, dtype=np.float32).reshape(-1)

                current_state = self.state
                # Only feed record_queue when actively recording
                if current_state == ListenerState.RECORDING:
                    self.record_queue.put(chunk_1d)
                # Only feed wake_queue when actively in wake listening standby
                elif current_state == ListenerState.WAKE_LISTENING:
                    if self.listen_mode in ("hi_jarvis", "hybrid") and not self.is_processing:
                        self.wake_queue.put(chunk_1d)

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
                    current_state = self.state

                    # STATE 1: Active Command Recording
                    if current_state == ListenerState.RECORDING:
                        now = time.time()
                        elapsed = now - self.record_start_time

                        # Fetch available audio chunks from dedicated record_queue
                        try:
                            chunk = self.record_queue.get(timeout=0.06)
                            chunk_1d = np.asarray(chunk, dtype=np.float32).reshape(-1)
                            with self.chunks_lock:
                                self.recorded_chunks.append(chunk_1d)

                            # Calculate RMS energy of current audio block
                            rms = float(np.sqrt(np.mean(chunk_1d**2))) if len(chunk_1d) > 0 else 0.0
                            if rms >= self.speech_energy_threshold:
                                if not self.has_spoken:
                                    self.has_spoken = True
                                    print(f"[Listener] 🗣️ Voice activity detected (RMS: {rms:.4f} >= {self.speech_energy_threshold}).")
                                self.last_speech_time = now
                        except queue.Empty:
                            pass

                        # Post-speech silence auto-cutoff (e.g. 3.5s)
                        if self.has_spoken and self.last_speech_time > 0:
                            silence_duration = now - self.last_speech_time
                            if silence_duration >= self.post_speech_silence:
                                print(f"[Listener] ⏱️ Post-speech silence ({silence_duration:.2f}s >= {self.post_speech_silence}s) detected. Auto-stopping and processing...")
                                with self.toggle_lock:
                                    self._stop_and_process()
                                continue

                        # Maximum recording timeout cutoff (e.g. 15s)
                        if elapsed >= self.timeout_seconds:
                            print(f"[Listener] ⏱️ Maximum recording timeout ({self.timeout_seconds}s) reached without silence trigger. Stopping...")
                            with self.toggle_lock:
                                self._stop_and_process()
                            continue

                    # STATE 2: Wake Word Standby (hi_jarvis or hybrid)
                    elif current_state == ListenerState.WAKE_LISTENING and self.listen_mode in ("hi_jarvis", "hybrid") and not self.is_speaking and not self.is_processing:
                        try:
                            chunk = self.wake_queue.get(timeout=0.08)
                            chunk_1d = np.asarray(chunk, dtype=np.float32).reshape(-1)
                            rms = float(np.sqrt(np.mean(chunk_1d**2))) if len(chunk_1d) > 0 else 0.0

                            # Configurable threshold to prevent low background noise from triggering wake detection
                            wake_threshold = self.wake_energy_threshold

                            if rms >= wake_threshold:
                                with self.wake_buffer_lock:
                                    if len(self.wake_buffer) == 0 and not self._wake_buffering_logged:
                                        print(f"[Listener] 🎙️ Mic input active (RMS: {rms:.4f} >= {wake_threshold:.4f}) -> Buffering wake audio...")
                                        self._wake_buffering_logged = True
                                    self.wake_buffer.append(chunk_1d)
                                    self.wake_silence_count = 0
                            else:
                                with self.wake_buffer_lock:
                                    if len(self.wake_buffer) > 0:
                                        self.wake_silence_count += 1
                                        self.wake_buffer.append(chunk_1d)

                                        # Pause of ~0.45s (approx 7 blocks) after speech to capture compound wake words ("hi jarvis")
                                        if self.wake_silence_count >= 7:
                                            valid_wake = [
                                                np.asarray(c, dtype=np.float32).reshape(-1)
                                                for c in self.wake_buffer
                                                if c is not None and len(c) > 0
                                            ]
                                            snippet = np.concatenate(valid_wake, axis=0).reshape(-1) if valid_wake else np.zeros(0, dtype=np.float32)
                                            self.wake_buffer.clear()
                                            self.wake_silence_count = 0
                                            self._wake_buffering_logged = False
                                            duration = len(snippet) / self.SAMPLE_RATE
                                            if 0.45 <= duration <= 3.5:
                                                threading.Thread(
                                                    target=self._check_wake_snippet,
                                                    args=(snippet, self.session_epoch),
                                                    daemon=True
                                                ).start()

                            with self.wake_buffer_lock:
                                # Cap max buffer to 3.5s to prevent runaway memory
                                if len(self.wake_buffer) > int(3.5 * self.SAMPLE_RATE / self.BLOCK_SIZE):
                                    valid_wake = [
                                        np.asarray(c, dtype=np.float32).reshape(-1)
                                        for c in self.wake_buffer
                                        if c is not None and len(c) > 0
                                    ]
                                    snippet = np.concatenate(valid_wake, axis=0).reshape(-1) if valid_wake else np.zeros(0, dtype=np.float32)
                                    self.wake_buffer.clear()
                                    self.wake_silence_count = 0
                                    self._wake_buffering_logged = False
                                    duration = len(snippet) / self.SAMPLE_RATE
                                    if 0.45 <= duration <= 3.5:
                                        threading.Thread(
                                            target=self._check_wake_snippet,
                                            args=(snippet, self.session_epoch),
                                            daemon=True
                                        ).start()

                        except queue.Empty:
                            pass

                    # STATE 3: Idle / Push-to-Talk / Processing Standby
                    else:
                        # In push_to_talk, processing, or idle mode, discard any queue frames to use 0% CPU
                        while not self.wake_queue.empty():
                            try:
                                self.wake_queue.get_nowait()
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
        self.state = ListenerState.IDLE
        self.session_epoch += 1
        with self.wake_buffer_lock:
            self.wake_buffer.clear()
        while not self.wake_queue.empty():
            try:
                self.wake_queue.get_nowait()
            except queue.Empty:
                break
        while not self.record_queue.empty():
            try:
                self.record_queue.get_nowait()
            except queue.Empty:
                break
        self._unload_whisper_model()
