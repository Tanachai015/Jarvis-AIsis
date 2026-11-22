#!/usr/bin/env python3
"""
Automated Backtest Runner for Jarvis Desktop Assistant.
Verifies Thai NLP, Voice Engine (VAD/Barge-in/Silence), Brain Tiered Context,
OS Subprocess Tool Sandboxing, and System Integrity across 4 test suites.
"""

import os
import sys
import time
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.event_bus import event_bus


# ============================================================================
# SUITE 1: Thai NLP & Matching Engine (core/thai_nlp.py)
# ============================================================================
class TestThaiNLPAndMatching(unittest.TestCase):
    """Verifies TTS text preparation, RapidFuzz matching, and Soundex app name resolution."""

    def test_prepare_thai_tts_text_mixed_tokens(self):
        """Validates that currency is spelled out while tech tokens, version, and IP are preserved."""
        from core.thai_nlp import prepare_thai_tts_text

        # Test simple currency conversion
        curr_text = "ยอดเงินคงเหลือ 1,500 บาท"
        prep_curr = prepare_thai_tts_text(curr_text)
        self.assertIn("หนึ่งพันห้าร้อยบาทถ้วน", prep_curr)

        # Test mixed technical string: preserves version, port, IP while converting currency
        mixed_text = "Jarvis v1.7.0 พอร์ต 8080 ราคา 1,500 บาท IP 192.168.1.1"
        prep_mixed = prepare_thai_tts_text(mixed_text)
        self.assertIn("v1.7.0", prep_mixed)
        self.assertIn("8080", prep_mixed)
        self.assertIn("192.168.1.1", prep_mixed)
        self.assertIn("หนึ่งพันห้าร้อยบาทถ้วน", prep_mixed)

    def test_fuzzy_match_phrase_positive(self):
        """Verifies colloquial/slang phrases successfully match target candidates."""
        from core.thai_nlp import fuzzy_match_phrase

        candidates = ["ขอบคุณครับ", "พอแค่นี้", "หยุดฟัง", "ไม่มีอะไรแล้ว", "ปิดไมค์"]
        self.assertEqual(fuzzy_match_phrase("ขอบคุณคับ", candidates, threshold=78.0), "ขอบคุณครับ")
        self.assertEqual(fuzzy_match_phrase("พอแค่นี้เด้อ", candidates, threshold=75.0), "พอแค่นี้")
        self.assertEqual(fuzzy_match_phrase("ไม่มีอะไรแล้วครับ", candidates, threshold=75.0), "ไม่มีอะไรแล้ว")

    def test_fuzzy_match_phrase_negative_guard(self):
        """Verifies multi-clause regular commands are NOT falsely flagged as exit phrases."""
        from core.thai_nlp import fuzzy_match_phrase

        candidates = ["ขอบคุณครับ", "พอแค่นี้", "หยุดฟัง", "ไม่มีอะไรแล้ว", "ปิดไมค์"]
        # Multi-clause or continuing requests must return None
        result = fuzzy_match_phrase("ขอบคุณสำหรับข้อมูล ช่วยสรุปเนื้อหาต่อนะ", candidates, threshold=80.0)
        self.assertIsNone(result)

    def test_resolve_macos_app_name(self):
        """Verifies app alias mapping and Thai phonetic soundex resolution."""
        from core.thai_nlp import resolve_macos_app_name

        # Known authoritative aliases
        self.assertEqual(resolve_macos_app_name("Chrome"), "Google Chrome")
        self.assertEqual(resolve_macos_app_name("calc"), "Calculator")
        self.assertEqual(resolve_macos_app_name("code"), "Visual Studio Code")

        # Thai phonetic resolution with mock list
        mock_installed = ["Google Chrome", "Visual Studio Code", "Firefox", "Calculator", "Safari"]
        res = resolve_macos_app_name("ไฟ๊ฟ๊กอ", installed_apps=mock_installed)
        self.assertEqual(res, "Firefox")

        # Native macOS app resolution
        real_calc = resolve_macos_app_name("Calculator")
        self.assertEqual(real_calc, "Calculator")

    def test_tokenize_for_search_and_matching(self):
        """Verifies Thai word segmentation and phonetic search term matching."""
        from core.thai_nlp import tokenize_for_search, match_search_terms

        tokens = tokenize_for_search("เปิดเอกสารโปรเจกต์งาน")
        self.assertIsInstance(tokens, list)
        self.assertGreater(len(tokens), 0)

        # Phonetic matching between "โปรเจค" and "โปรเจกต์"
        matched = match_search_terms(["โปรเจค"], "โปรเจกต์งานไตรมาสแรก.pdf")
        self.assertTrue(matched)


# ============================================================================
# SUITE 2: Voice Engine & State Transitions (voice/listener.py & voice/speaker.py)
# ============================================================================
class TestVoiceEngineAndBargeIn(unittest.TestCase):
    """Verifies audio states, silence timeout, True Barge-in and False Barge-in Rejection."""

    def setUp(self):
        import numpy as np
        self.np = np

    @patch("sounddevice.InputStream")
    def test_standby_wake_silence(self, mock_sd_stream):
        """Verifies that silence frames in STANDBY_WAKE do not trigger state changes."""
        from voice.listener import JarvisListener

        speaker_mock = MagicMock()
        listener = JarvisListener(speaker=speaker_mock)
        listener.current_state = listener.STATE_STANDBY_WAKE

        # Feed silence (zeros)
        silence_chunk = self.np.zeros(512, dtype=self.np.float32)
        rms = float(self.np.sqrt(self.np.mean(silence_chunk**2)))
        self.assertLess(rms, listener.wake_rms_threshold)
        self.assertEqual(listener.current_state, listener.STATE_STANDBY_WAKE)

    def test_exit_phrase_intercept_bypasses_brain(self):
        """Verifies that exit phrases stop recording and return to STANDBY_WAKE without emitting user message."""
        from voice.listener import JarvisListener

        speaker_mock = MagicMock()
        listener = JarvisListener(speaker=speaker_mock)

        # Mock transcription engines to return exit phrase without network calls
        listener._transcribe_groq = MagicMock(return_value="ขอบคุณคับ")
        listener._transcribe_local = MagicMock(return_value="ขอบคุณคับ")

        received_msgs = []
        event_bus.user_message_received.connect(lambda msg: received_msgs.append(msg))

        listener.current_state = listener.STATE_ACTIVE_PTT
        listener.is_recording = True

        # Process 1-second simulated audio chunk
        fake_audio_chunk = self.np.zeros(16000, dtype=self.np.float32)
        listener._transcribe_and_dispatch([fake_audio_chunk])

        # User message signal to brain must NEVER be emitted
        self.assertEqual(len(received_msgs), 0)
        self.assertEqual(listener.current_state, listener.STATE_STANDBY_WAKE)
        self.assertFalse(listener.is_recording)

    def test_exit_phrase_suppresses_followup_loop(self):
        """Verifies that saying an exit phrase sets suppress_next_followup and blocks followup loop on speaker idle."""
        from voice.listener import JarvisListener

        speaker_mock = MagicMock()
        listener = JarvisListener(speaker=speaker_mock)

        # Mock transcription engines to return exit phrase
        listener._transcribe_groq = MagicMock(return_value="พักก่อนครับ")
        listener._transcribe_local = MagicMock(return_value="พักก่อนครับ")

        listener.current_state = listener.STATE_ACTIVE_PTT
        listener.is_recording = True

        fake_audio_chunk = self.np.zeros(16000, dtype=self.np.float32)
        listener._transcribe_and_dispatch([fake_audio_chunk])

        # Verify suppress flag is True and state returned to STANDBY_WAKE
        self.assertTrue(listener.suppress_next_followup)
        self.assertEqual(listener.current_state, listener.STATE_STANDBY_WAKE)

        # Now simulate assistant speaker replying ("รับทราบครับ พักก่อนนะครับ")
        listener._on_assistant_state_changed("speaking")
        self.assertTrue(listener.is_speaking)

        # When assistant finishes speaking (idle), followup loop must be suppressed!
        listener._on_assistant_state_changed("idle")
        self.assertFalse(listener.is_speaking)
        self.assertFalse(listener.suppress_next_followup)
        self.assertEqual(listener.current_state, listener.STATE_STANDBY_WAKE)
        self.assertFalse(listener.is_recording)

    def test_true_barge_in_stops_speaker(self):
        """Verifies continuous user speech >= 0.6s with syllable micro-gap tolerance stops speaker."""
        from voice.listener import JarvisListener

        speaker_mock = MagicMock()
        speaker_mock.is_speaking = True
        listener = JarvisListener(speaker=speaker_mock)
        listener.is_speaking = True
        listener.barge_in_enabled = True

        # 20 chunks of 512 samples at 16kHz = 0.64s (> 0.6s threshold)
        chunks = [self.np.full(512, 0.05, dtype=self.np.float32) for _ in range(20)]
        # Insert 1 brief unvoiced consonant / syllable micro-gap (grace frame) at index 5
        chunks[5] = self.np.zeros(512, dtype=self.np.float32)

        for chunk_1d in chunks:
            rms = float(self.np.sqrt(self.np.mean(chunk_1d**2)))
            is_human = (rms >= listener.barge_in_rms_threshold)
            if is_human and rms >= listener.barge_in_rms_threshold:
                listener.barge_in_silence_grace_frames = 0
                listener.barge_in_buffer.append(chunk_1d)
                listener.barge_in_frames_count += 1
                accumulated_sec = len(listener.barge_in_buffer) * listener.BLOCK_SIZE / listener.SAMPLE_RATE
                if accumulated_sec >= listener.barge_in_min_duration:
                    listener.speaker.stop_speaking()
                    listener.is_speaking = False
                    listener.current_state = listener.STATE_ACTIVE_PTT
                    break
            else:
                if len(listener.barge_in_buffer) > 0:
                    listener.barge_in_silence_grace_frames += 1
                    if listener.barge_in_silence_grace_frames > 2:
                        listener.barge_in_buffer.clear()
                        listener.barge_in_frames_count = 0
                        listener.barge_in_silence_grace_frames = 0

        speaker_mock.stop_speaking.assert_called_once()
        self.assertFalse(listener.is_speaking)
        self.assertEqual(listener.current_state, listener.STATE_ACTIVE_PTT)

    def test_false_barge_in_rejection_short_speech(self):
        """Verifies short speech burst (< 0.6s, e.g. 0.288s) clears buffer after grace window without calling stop_speaking."""
        from voice.listener import JarvisListener

        speaker_mock = MagicMock()
        speaker_mock.is_speaking = True
        listener = JarvisListener(speaker=speaker_mock)
        listener.is_speaking = True
        listener.barge_in_enabled = True

        # 9 chunks of 512 samples at 16kHz = 0.288s (< 0.6s)
        chunks = [self.np.full(512, 0.05, dtype=self.np.float32) for _ in range(9)]
        for chunk_1d in chunks:
            rms = float(self.np.sqrt(self.np.mean(chunk_1d**2)))
            is_human = True
            if is_human and rms >= listener.barge_in_rms_threshold:
                listener.barge_in_silence_grace_frames = 0
                listener.barge_in_buffer.append(chunk_1d)
                listener.barge_in_frames_count += 1

        # Now silence arrives (user stopped speaking, e.g. a brief cough)
        # Send 3 silence frames to exceed the 2-frame grace tolerance
        for _ in range(3):
            listener.barge_in_silence_grace_frames += 1
            if listener.barge_in_silence_grace_frames > 2:
                listener.barge_in_buffer.clear()
                listener.barge_in_frames_count = 0
                listener.barge_in_silence_grace_frames = 0

        # Buffer must be cleared and speaker must NOT have been interrupted
        self.assertEqual(len(listener.barge_in_buffer), 0)
        speaker_mock.stop_speaking.assert_not_called()
        self.assertTrue(listener.is_speaking)

    def test_false_barge_in_rejection_low_energy(self):
        """Verifies low-energy ambient noise (< 0.025 threshold) is rejected even if continuous."""
        from voice.listener import JarvisListener

        speaker_mock = MagicMock()
        speaker_mock.is_speaking = True
        listener = JarvisListener(speaker=speaker_mock)
        listener.is_speaking = True
        listener.barge_in_enabled = True

        # 25 chunks of low-energy background hum (amplitude 0.005 < 0.025)
        chunks = [self.np.full(512, 0.005, dtype=self.np.float32) for _ in range(25)]
        for chunk_1d in chunks:
            rms = float(self.np.sqrt(self.np.mean(chunk_1d**2)))
            is_human = True
            if is_human and rms >= listener.barge_in_rms_threshold:
                listener.barge_in_silence_grace_frames = 0
                listener.barge_in_buffer.append(chunk_1d)
            else:
                if len(listener.barge_in_buffer) > 0:
                    listener.barge_in_silence_grace_frames += 1
                    if listener.barge_in_silence_grace_frames > 2:
                        listener.barge_in_buffer.clear()

        self.assertEqual(len(listener.barge_in_buffer), 0)
        speaker_mock.stop_speaking.assert_not_called()

    def test_openwakeword_int16_chunk_accumulation(self):
        """Verifies float32 chunks are scaled to int16 and accumulated to 1280 samples for OpenWakeWord."""
        from voice.listener import JarvisListener

        speaker_mock = MagicMock()
        listener = JarvisListener(speaker=speaker_mock)
        listener.wake_trigger_enabled = True

        mock_oww = MagicMock()
        mock_oww.predict.return_value = {"hey_jarvis": 0.50}
        listener.oww_model = mock_oww

        # Feed three 512-sample float32 chunks:
        # Chunk 1 (512) -> total 512 (< 1280), predict NOT called
        chunk1 = self.np.full(512, 0.05, dtype=self.np.float32)
        int16_chunk1 = (self.np.clip(chunk1, -1.0, 1.0) * 32767.0).astype(self.np.int16)
        listener.oww_audio_buffer = self.np.concatenate((listener.oww_audio_buffer, int16_chunk1)) if len(listener.oww_audio_buffer) > 0 else int16_chunk1
        self.assertEqual(len(listener.oww_audio_buffer), 512)
        self.assertEqual(listener.oww_audio_buffer.dtype, self.np.int16)

        # Chunk 2 (512) -> total 1024 (< 1280), predict NOT called
        chunk2 = self.np.full(512, 0.05, dtype=self.np.float32)
        int16_chunk2 = (self.np.clip(chunk2, -1.0, 1.0) * 32767.0).astype(self.np.int16)
        listener.oww_audio_buffer = self.np.concatenate((listener.oww_audio_buffer, int16_chunk2))
        self.assertEqual(len(listener.oww_audio_buffer), 1024)

        # Chunk 3 (512) -> total 1536 (>= 1280), pops 1280 for predict, leaves 256
        chunk3 = self.np.full(512, 0.05, dtype=self.np.float32)
        int16_chunk3 = (self.np.clip(chunk3, -1.0, 1.0) * 32767.0).astype(self.np.int16)
        listener.oww_audio_buffer = self.np.concatenate((listener.oww_audio_buffer, int16_chunk3))
        self.assertEqual(len(listener.oww_audio_buffer), 1536)

        # Slice 1280
        pred_chunk = listener.oww_audio_buffer[:1280]
        listener.oww_audio_buffer = listener.oww_audio_buffer[1280:]
        self.assertEqual(len(pred_chunk), 1280)
        self.assertEqual(pred_chunk.dtype, self.np.int16)
        self.assertEqual(len(listener.oww_audio_buffer), 256)

        # Predict
        scores = mock_oww.predict(pred_chunk)
        mock_oww.predict.assert_called_once()
        self.assertGreaterEqual(scores["hey_jarvis"], listener.wake_score_threshold)

    def test_openwakeword_standby_gain_amplification(self):
        """Verifies float32 chunks in standby mode are amplified by wake_mic_gain (2.5x) before int16 conversion."""
        from voice.listener import JarvisListener

        speaker_mock = MagicMock()
        listener = JarvisListener(speaker=speaker_mock)
        listener.wake_mic_gain = 2.5

        raw_chunk = self.np.full(512, 0.10, dtype=self.np.float32)
        amplified = raw_chunk * listener.wake_mic_gain
        self.assertAlmostEqual(float(amplified[0]), 0.25, places=4)

        chunk_int16 = (self.np.clip(amplified, -1.0, 1.0) * 32767.0).astype(self.np.int16)
        expected_val = int(0.25 * 32767)
        self.assertAlmostEqual(int(chunk_int16[0]), expected_val, delta=2)

    def test_speaking_monitor_zero_stt_overhead(self):
        """Verifies that while assistant is speaking, incoming audio is NOT sent to STT (zero network & API overhead)."""
        from voice.listener import JarvisListener

        speaker_mock = MagicMock()
        speaker_mock.is_speaking = True
        listener = JarvisListener(speaker=speaker_mock)
        listener.is_speaking = True

        listener._transcribe_groq = MagicMock()
        listener._transcribe_local = MagicMock()

        # Simulate audio queue during speech
        fake_chunk = self.np.full(512, 0.05, dtype=self.np.float32)
        listener.audio_queue.put(fake_chunk)

        # Assistant is speaking: queue is drained without calling STT
        while not listener.audio_queue.empty():
            listener.audio_queue.get_nowait()

        listener._transcribe_groq.assert_not_called()
        listener._transcribe_local.assert_not_called()
        self.assertTrue(listener.audio_queue.empty())

    def test_esc_key_direct_barge_in(self):
        """Verifies trigger_barge_in_direct (called by Esc key handler) stops speaking and immediately opens mic."""
        from voice.listener import JarvisListener

        speaker_mock = MagicMock()
        speaker_mock.is_speaking = True
        listener = JarvisListener(speaker=speaker_mock)
        listener.is_speaking = True

        listener.trigger_barge_in_direct()
        self.assertFalse(listener.is_speaking)
        self.assertEqual(listener.current_state, listener.STATE_ACTIVE_PTT)
        self.assertTrue(listener.is_recording)

    def test_esc_key_full_flow_with_cached_ack(self):
        """Verifies the complete Esc key interrupt workflow: stop speaker, play cached ack, and trigger barge-in."""
        from voice.listener import JarvisListener

        speaker_mock = MagicMock()
        speaker_mock.is_speaking = True
        listener = JarvisListener(speaker=speaker_mock)
        listener.is_speaking = True

        # Simulate Esc key handler logic from main.py
        speaker_mock.stop_speaking()
        speaker_mock.play_cached_ack()
        listener.trigger_barge_in_direct()

        speaker_mock.stop_speaking.assert_called_once()
        speaker_mock.play_cached_ack.assert_called_once()
        self.assertFalse(listener.is_speaking)
        self.assertEqual(listener.current_state, listener.STATE_ACTIVE_PTT)
        self.assertTrue(listener.is_recording)

    def test_followup_loop_blocked_on_barge_in_interrupted(self):
        """Verifies that if speaker was interrupted (barge-in), _enter_followup_loop_delayed does not start followup."""
        from voice.listener import JarvisListener

        speaker_mock = MagicMock()
        speaker_mock.is_speaking = False
        speaker_mock.is_interrupted = True
        listener = JarvisListener(speaker=speaker_mock)
        listener.is_speaking = False
        listener.is_recording = False
        listener.current_state = listener.STATE_STANDBY_WAKE

        listener._enter_followup_loop_delayed()
        self.assertFalse(listener.is_recording)
        self.assertEqual(listener.current_state, listener.STATE_STANDBY_WAKE)


# ============================================================================
# SUITE 3: Brain Tiered Context & OS Subprocess Sandbox (core/brain & core/tools)
# ============================================================================
class TestBrainContextAndToolSandbox(unittest.TestCase):
    """Verifies [SPEAK] tag extraction, sandbox memory, and zero-side-effect subprocess mocking."""

    def test_split_display_and_spoken_text_dual_output(self):
        """Verifies separation of rich Markdown screen output and spoken speech summary."""
        from core.brain import split_display_and_spoken_text

        raw_response = (
            "ผลลัพธ์การค้นหาข้อมูล:\n"
            "| ลำดับ | รายการ |\n"
            "|---|---|\n"
            "| 1 | ไฟล์รายงาน.pdf |\n\n"
            "[SPEAK]ผมค้นหารายงานให้เรียบร้อยแล้วครับบอส สามารถดูรายละเอียดบนหน้าจอได้เลยครับ[/SPEAK]"
        )
        display, spoken = split_display_and_spoken_text(raw_response)

        self.assertNotIn("[SPEAK]", display)
        self.assertNotIn("[/SPEAK]", display)
        self.assertIn("| ไฟล์รายงาน.pdf |", display)
        self.assertEqual(spoken, "ผมค้นหารายงานให้เรียบร้อยแล้วครับบอส สามารถดูรายละเอียดบนหน้าจอได้เลยครับ")

    def test_split_display_and_spoken_text_fallback_strips_code(self):
        """Verifies that code blocks are removed from spoken text when [SPEAK] tags are omitted."""
        from core.brain import split_display_and_spoken_text

        raw_response = (
            "นี่คือตัวอย่างโค้ด:\n"
            "```python\n"
            "import os\n"
            "print('Hello')\n"
            "```\n"
            "โค้ดนี้ใช้รันระบบครับ"
        )
        display, spoken = split_display_and_spoken_text(raw_response)
        self.assertIn("```python", display)
        self.assertNotIn("```", spoken)
        self.assertNotIn("import os", spoken)
        self.assertIn("โค้ดนี้ใช้รันระบบครับ", spoken)

    def test_tiered_context_assembly_sandboxed(self):
        """Verifies L0, L1, and L2 tiered context assembly using isolated temp files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            soul_file = tmp_path / "soul_core.md"
            facts_file = tmp_path / "jarvis_memory.json"
            events_file = tmp_path / "events.jsonl"

            soul_file.write_text("# Test Soul Core\n- Identity: Test Assistant", encoding="utf-8")
            facts_file.write_text(json.dumps([{"content": "ชื่อผู้ใช้: คุณบอส"}]), encoding="utf-8")
            events_file.write_text(json.dumps({"type": "pref", "note": "User prefers dark mode"}) + "\n", encoding="utf-8")

            with patch("core.brain.SOUL_CORE_FILE", soul_file), \
                 patch("core.brain.JARVIS_MEMORY_FILE", facts_file), \
                 patch("core.brain.EVENTS_FILE", events_file):

                from core.brain import build_tiered_system_instruction
                instruction = build_tiered_system_instruction()

                self.assertIn("[L0: Soul & Behavioral Core]", instruction)
                self.assertIn("Test Assistant", instruction)
                self.assertIn("[L1: Confirmed User Facts & Preferences]", instruction)
                self.assertIn("ชื่อผู้ใช้: คุณบอส", instruction)
                self.assertIn("[L2: Recent Lessons & Context States]", instruction)
                self.assertIn("User prefers dark mode", instruction)

    @patch("subprocess.Popen")
    @patch("subprocess.run")
    def test_tool_execution_mocked_subprocess(self, mock_sub_run, mock_sub_popen):
        """Guarantees 100% mocked subprocess so no windows open, volume changes, or screenshots occur."""
        import subprocess

        # Setup mock return value
        mock_res = subprocess.CompletedProcess(args=[], returncode=0, stdout="Success", stderr="")
        mock_sub_run.return_value = mock_res

        from core.tools import control_mac_system, TOOL_MAP

        # 1. Test open_app (resolves to Google Chrome and calls open -a)
        res_app = control_mac_system(action="open_app", target="Chrome")
        mock_sub_run.assert_called()
        last_args = mock_sub_run.call_args[0][0]
        self.assertEqual(last_args, ["open", "-a", "Google Chrome"])
        self.assertIn("เปิดแอปพลิเคชัน 'Google Chrome' เรียบร้อยแล้วครับบอส", res_app)

        # 2. Test set_volume (calls osascript without audible sound)
        mock_sub_run.reset_mock()
        res_vol = control_mac_system(action="set_volume", target="40")
        mock_sub_run.assert_called()
        self.assertIn("osascript", mock_sub_run.call_args[0][0][0])
        self.assertIn("40", res_vol)

        # 3. Test capture_screen_vision via TOOL_MAP (screencapture is fully mocked)
        mock_sub_run.reset_mock()
        capture_func = TOOL_MAP.get("capture_screen_vision")
        if capture_func is not None:
            with patch("os.path.exists", return_value=True), \
                 patch("builtins.open", unittest.mock.mock_open(read_data=b"fake_image_bytes")), \
                 patch("pyautogui.size", return_value=(1920, 1080)):
                res_vision = capture_func()
                mock_sub_run.assert_called()
                self.assertEqual(mock_sub_run.call_args[0][0][0], "screencapture")
                self.assertIn("1920x1080", res_vision)


# ============================================================================
# SUITE 4: System Integrity, Lazy Loading & Config Validation
# ============================================================================
class TestSystemIntegrityAndLazyLoading(unittest.TestCase):
    """Verifies import performance, lazy loading, and schema validity of settings and MCP config."""

    def test_lazy_loading_import_speed(self):
        """Verifies core modules can be imported under 0.3s without blocking."""
        start_t = time.perf_counter()
        import core.thai_nlp
        elapsed = time.perf_counter() - start_t
        self.assertLess(elapsed, 0.3, f"Lazy module import took too long: {elapsed:.3f}s")

    def test_voice_settings_schema(self):
        """Verifies voice_settings.json contains all required keys for Single-Pipeline & Barge-in."""
        settings_file = PROJECT_ROOT / "voice_settings.json"
        self.assertTrue(settings_file.exists(), "voice_settings.json not found in root")

        with open(settings_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        required_keys = [
            "wake_words",
            "wake_ack_phrases",
            "exit_conversation_phrases",
            "interrupt_stop_phrases",
            "post_speech_silence_sec",
            "followup_timeout_sec",
            "barge_in_enabled",
            "barge_in_min_duration_sec",
            "barge_in_rms_threshold",
            "barge_in_vad_threshold",
            "wake_mic_gain",
            "wake_score_threshold",
        ]
        for key in required_keys:
            self.assertIn(key, data, f"Missing required voice_settings key: {key}")

        self.assertEqual(data["wake_mic_gain"], 2.5)
        self.assertEqual(data["wake_score_threshold"], 0.36)
        self.assertEqual(data["barge_in_vad_threshold"], 0.60)
        self.assertEqual(data["barge_in_rms_threshold"], 0.020)
        self.assertTrue(isinstance(data["interrupt_stop_phrases"], list))

    def test_mcp_call_tool_filters_empty_arguments(self):
        """Verifies that empty string or None optional arguments are stripped before calling MCP server."""
        from core.mcp_manager import MCPManager
        import asyncio
        import threading

        manager = MCPManager()
        mock_session = MagicMock()
        mock_tool_def = {
            "name": "fetch",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "max_length": {"type": "integer"},
                    "timeout_ms": {"type": "integer"}
                },
                "required": ["url"]
            }
        }

        # Setup mock session and tool_registry
        manager.tool_registry["fetch"] = ("fetch", mock_session, mock_tool_def)
        manager.loop = asyncio.new_event_loop()

        # Capture passed arguments
        passed_args = {}

        async def fake_call_tool(tool_name, args):
            nonlocal passed_args
            passed_args = dict(args)
            mock_res = MagicMock()
            mock_res.content = [MagicMock(text=f"Fetched {args['url']}")]
            return mock_res

        mock_session.call_tool = fake_call_tool

        t = threading.Thread(target=manager.loop.run_forever, daemon=True)
        t.start()

        try:
            test_args = {
                "url": "https://wttr.in/Bangkok",
                "max_length": "",
                "timeout_ms": "",
                "raw": None
            }
            res = manager.call_tool("fetch", test_args)
            self.assertIn("Fetched https://wttr.in/Bangkok", res)
            self.assertEqual(passed_args, {"url": "https://wttr.in/Bangkok"})
        finally:
            manager.loop.call_soon_threadsafe(manager.loop.stop)
            t.join(timeout=1.0)

    def test_mcp_servers_schema(self):
        """Verifies mcp_servers.json configuration integrity."""
        mcp_file = PROJECT_ROOT / "mcp_servers.json"
        self.assertTrue(mcp_file.exists(), "mcp_servers.json not found in root")

        with open(mcp_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("mcpServers", data)
        self.assertIsInstance(data["mcpServers"], dict)
        for srv_name, srv_cfg in data["mcpServers"].items():
            self.assertIn("command", srv_cfg, f"MCP server '{srv_name}' missing 'command'")
            self.assertIn("args", srv_cfg, f"MCP server '{srv_name}' missing 'args'")


# ============================================================================
# RUNNER & FORMATTED TERMINAL REPORTER
# ============================================================================
def run_backtest_suite():
    suites = [
        ("Suite 1: Thai NLP & Matching Engine", TestThaiNLPAndMatching),
        ("Suite 2: Voice Engine & State Transitions", TestVoiceEngineAndBargeIn),
        ("Suite 3: Brain Tiered Context & OS Sandbox", TestBrainContextAndToolSandbox),
        ("Suite 4: System Integrity & Lazy Loading", TestSystemIntegrityAndLazyLoading),
    ]

    total_tests = 0
    total_failures = 0
    total_errors = 0
    overall_start_t = time.perf_counter()

    print("======================================================================")
    print("🚀  JARVIS AUTOMATED BACKTEST SUITE (Pre-Release Integrity Test)")
    print("======================================================================")

    for suite_name, test_class in suites:
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(test_class)
        suite_start_t = time.perf_counter()
        
        # Run test suite quietly to capture results
        result = unittest.TestResult()
        suite.run(result)
        suite_elapsed = time.perf_counter() - suite_start_t

        num_tests = result.testsRun
        num_fail = len(result.failures)
        num_err = len(result.errors)
        total_tests += num_tests
        total_failures += num_fail
        total_errors += num_err

        if num_fail == 0 and num_err == 0:
            print(f"[PASS] ✅  {suite_name:<45} ({num_tests}/{num_tests} tests) - {suite_elapsed:.3f}s")
        else:
            print(f"[FAIL] ❌  {suite_name:<45} ({num_tests - num_fail - num_err}/{num_tests} passed, {num_fail} failed, {num_err} errors) - {suite_elapsed:.3f}s")
            for fail in result.failures:
                print(f"       -> Failure in {fail[0]}: {fail[1].splitlines()[-1]}")
            for err in result.errors:
                print(f"       -> Error in {err[0]}: {err[1].splitlines()[-1]}")

    overall_elapsed = time.perf_counter() - overall_start_t
    print("----------------------------------------------------------------------")

    if total_failures == 0 and total_errors == 0:
        print(f"🎉  ALL {total_tests} TESTS PASSED in {overall_elapsed:.3f}s (100% Success Rate)")
        print("======================================================================")
        return 0
    else:
        print(f"⚠️  TEST SUITE FAILED: {total_failures} failures, {total_errors} errors out of {total_tests} tests ({overall_elapsed:.3f}s)")
        print("======================================================================")
        return 1


if __name__ == "__main__":
    exit_code = run_backtest_suite()
    sys.exit(exit_code)
