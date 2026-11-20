"""
Configuration module for Jarvis Desktop Assistant.
Loads environment variables and provides global configuration constants.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Project Root
PROJECT_ROOT = Path(__file__).resolve().parent

# Load environment variables from .env file
load_dotenv(PROJECT_ROOT / ".env")

# Gemini Model Settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
THINKING_LEVEL = os.getenv("THINKING_LEVEL", "low")

# Desktop Interaction Hotkey
HOTKEY = os.getenv("HOTKEY", "alt+space")

# Voice & Speech Synthesis Settings (J.A.R.V.I.S. Dual Tone)
TTS_ENABLED = os.getenv("TTS_ENABLED", "true").lower() in ("true", "1", "yes")

# Thai Tone: th-TH-NiwatNeural
TTS_VOICE_TH = os.getenv("TTS_VOICE_TH", "th-TH-NiwatNeural")
TTS_PITCH_TH = os.getenv("TTS_PITCH_TH", "-14Hz")
TTS_RATE_TH = os.getenv("TTS_RATE_TH", "+6%")
TTS_VOLUME_TH = os.getenv("TTS_VOLUME_TH", "+40%")

# British English Tone: en-GB-RyanNeural
TTS_VOICE_EN = os.getenv("TTS_VOICE_EN", "en-GB-RyanNeural")
TTS_PITCH_EN = os.getenv("TTS_PITCH_EN", "-8Hz")
TTS_RATE_EN = os.getenv("TTS_RATE_EN", "+8%")
TTS_VOLUME_EN = os.getenv("TTS_VOLUME_EN", "+40%")

# Backward compatibility fallback
TTS_VOICE = TTS_VOICE_TH
# Voice Listener Settings
VOICE_INPUT_ENABLED = os.getenv("VOICE_INPUT_ENABLED", "true").lower() in ("true", "1", "yes")
VOICE_TOGGLE_HOTKEY = os.getenv("VOICE_TOGGLE_HOTKEY", "<cmd>+<shift>+j")
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")
_wake_words_raw = os.getenv("WAKE_WORDS", "jarvis,จาร์วิส,จาวิส")
WAKE_WORDS = [w.strip().lower() for w in _wake_words_raw.split(",") if w.strip()]

# Voice Listening Auto-Close & Anti-Repeat Cooldown (10 - 25 seconds auto-timeout)
_timeout_raw = int(os.getenv("VOICE_RECORD_TIMEOUT", "15"))
VOICE_RECORD_TIMEOUT = max(10, min(25, _timeout_raw))  # Clamped to 10 - 25 seconds
VOICE_COOLDOWN_SECONDS = float(os.getenv("VOICE_COOLDOWN_SECONDS", "1.5"))

# Antigravity Bridge Settings
ANTIGRAVITY_WINDOW_TITLE = os.getenv("ANTIGRAVITY_WINDOW_TITLE", "Antigravity")
TASK_FILE_NAME = os.getenv("TASK_FILE_NAME", ".jarvis_task.md")
TASK_FILE_PATH = PROJECT_ROOT / TASK_FILE_NAME
RESULT_FILE_NAME = os.getenv("RESULT_FILE_NAME", ".jarvis_result.md")
RESULT_FILE_PATH = PROJECT_ROOT / RESULT_FILE_NAME

# History Limit
MAX_HISTORY_TURNS = 6
