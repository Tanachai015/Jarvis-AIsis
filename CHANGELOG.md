# Changelog

All notable changes to the **Jarvis Desktop Assistant** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.3.0] - 2026-11-22

### Added
- **Single-Pipeline Push-to-Talk + Wake Trigger Architecture**:
  - Replaced legacy 3-mode system with a clean, unified architecture centering on `push_to_talk`.
  - Added dynamic configuration file `voice_settings.json` for customizable wake words, acknowledgment phrases, and exit triggers.
  - Implemented 3 non-overlapping states: `STANDBY_WAKE`, `ACTIVE_PTT`, and `FOLLOWUP_LOOP`.
- **Pre-cached Wake Acknowledgment Phrases**:
  - Generated and cached TTS audio files in `/tmp/jarvis_acks/` for instant playback upon wake detection.
  - Added blocking playback with echo-flush before opening the microphone.
- **Continuous 60s Follow-up Loop**:
  - Automatically re-opens recording after assistant finishes speaking, enabling natural multi-turn conversations without wake-word repetition.
  - Added support for conversation exit phrases (*"ขอบคุณครับ"*, *"พอแค่นี้"*, *"พักก่อน"*) returning directly to standby.
- **Updated System Tray UI**:
  - Replaced confusing mode switcher with a clean toggle for Wake Word Trigger (Active/Disabled).

---

## [1.2.0] - 2026-11-22

### Added
- **Tiered Context Architecture (L0 - L3)** in `core/brain.py`:
  - **L0 (Soul & Behavioral Core):** Externalized personality, candor, and transparency rules into `memory/soul_core.md`.
  - **L1 (Confirmed Facts):** Dynamically injects verified user facts and preferences from `memory/jarvis_memory.json`.
  - **L2 (Recent Lessons & Context States):** Integrates recent lightweight corrections and user states from `memory/events.jsonl`.
  - **L3 (Active Conversation):** Maintains recent multi-turn conversation from `memory/chat_history.json`.
- **Candor & Confidence Transparency**:
  - Direct, honest feedback with explicit confidence levels (`[ความมั่นใจ: สูง / ปานกลาง / ต่ำ]`) for analytical, architectural, and debugging tasks.
- **Rule of Direct Action**:
  - Differentiates direct action commands (apps, volume, files, git, screen capture) to execute immediately via tools with 0 preliminary hesitation, reserving analytical candor for planning and reviews.
- **Event Journaling & Auto-Rotation (`memory/events.jsonl`)**:
  - Lightweight append-only event logging with safe read fallback and auto-truncation to prevent unbounded growth.

---

## [1.1.0] - 2026-11-22

### Added
- **In-Car Voice Assistant Engine**:
  - Configured 5.0s post-speech silence auto-cutoff and 60s total listening timeout for natural, uninterrupted speech.
  - Added bilingual Thai/English code-switching support via `WHISPER_LANGUAGE=th` and context prompts.
  - Implemented automatic wake word stripping and silence-only filtering to eliminate hallucinations.
  - Fixed audio buffer array dimension mismatch during wake-to-record transitions.
- **PROJECT_SUMMARY.md**:
  - Comprehensive technical architecture documentation.

---

## [1.0.0] - 2026-11-21

### Added
- **Dual-Engine Speech-to-Text (STT) Pipeline**:
  - Integrated **Groq Cloud STT (`whisper-large-v3-turbo`)** as primary transcription engine, achieving ~0.2s - 0.4s response time with 0% local CPU usage.
  - Automatic Local Fallback to **`Faster-Whisper` (`small`, int8)** when offline, unkeyed, or upon network failure without application stalls.
- **3 Adaptive Voice Listening Modes**:
  - `push_to_talk`: Listens and dispatches strictly via global hotkey (`Cmd + Shift + J`), keeping background mic idle at 0% CPU.
  - `hi_jarvis`: Silent background wake-word listening using Local Faster-Whisper exclusively to preserve Groq API quota.
  - `hybrid` (Default): Dual-trigger mode supporting both hotkey and wake words seamlessly.
- **Dynamic System Tray Mode Switcher**:
  - Added interactive radio submenu in macOS Status Bar / System Tray to switch voice modes at runtime without restarting.
- **Strict RAM Lifecycle Management**:
  - Local `Faster-Whisper` model stays resident in RAM during `hi_jarvis` and `hybrid` modes for instant wake-word recognition.
  - Unloads model and invokes Python `gc.collect()` when switching to `push_to_talk` or during graceful shutdown in `main.py`, reclaiming hundreds of megabytes of RAM.
- **2-Stage Voice Activity & Silence Cutoff**:
  - Implemented RMS energy speech threshold detection combined with `VOICE_POST_SPEECH_SILENCE` (3.5s auto-cutoff after speaking).
  - Maintains `VOICE_RECORD_TIMEOUT` (15s) fallback when no speech is initiated.
- **Phonetic Mistranscription & Ambiguous Speech Guard**:
  - Added cognitive guardrails in `JarvisBrain` System Instruction to catch phonetic mishearings (e.g. "เลิก 3,000" for "Love 3000") and request clarification before executing web searches or browser launches.

---

## [0.3.0] - 2026-11-20

### Added
- **macOS Vision GUI Automation**:
  - `click_on_screen`: Captures screen via `screencapture -x`, prompts Gemini Vision for coordinates, and calculates Retina Display scale factors (`img_w / screen_w`) for 100% accurate pixel-to-point mouse clicking.
  - **Inactive Window Focus Handling**: Implemented two-stage click sequence (focus activation + 0.15s window manager delay + action click) guaranteeing background windows (e.g. Firefox) trigger video playback or link navigation reliably.
  - `type_text_on_screen`: Reliable Thai, English, Unicode, and Emoji text input using Clipboard Injection (`pbcopy` + `Cmd+V`) with automatic background clipboard restoration.
  - `click_and_type`: Single-step GUI locator, focus activator, and keyboard input tool.
- **100% Stealth Background Execution Principle**:
  - Modified file modifications, code execution, and Antigravity IDE delegation to run completely in background without stealing screen focus.
  - Added `core/task_manager.py` with persistent task history (`memory/background_tasks.json`).
  - Added `reveal_task_result` tool to open files or focus windows only when explicitly commanded by the user ("เปิดดู", "reveal").
- **365-Day Long-Term Raw Archive**:
  - Created `core/raw_archive.py` with monthly partitioned JSONL storage (`memory/raw_archive/YYYY-MM.jsonl`).
  - Added `search_raw_history` tool allowing semantic search across past months/years of execution logs.
- **Continuous Multi-Line Speech & Dual-Response Protocol**:
  - Updated `split_display_and_spoken_text` and Edge-TTS synthesis to speak full conversational answers across multiple lines without truncating after the first sentence.
  - Clear separation between screen Markdown in `OverlayChat` and natural conversational speech via `[SPEAK]` tags.

---

## [0.2.0] - 2026-11-19

### Added
- **Official Model Context Protocol (MCP) Integration**:
  - Implemented `core/mcp_manager.py` with Stdio Client connecting to official MCP servers:
    - `@modelcontextprotocol/server-filesystem` (16 tools)
    - `mcp-server-fetch` (1 tool)
    - `mcp-server-git` (14 tools)
- **Static Tool Registry (40 Total Tools)**:
  - Combined 9 Native macOS tools with 31 Dynamic MCP tools into Gemini's `GenerateContentConfig` once at startup, eliminating per-turn schema generation overhead.
- **Persistent Schema Disk Cache**:
  - Added `memory/mcp_tools_cache.json` with SHA-256 config checksum validation, reducing application boot time to **0.005 seconds**.
- **Explicit Fallback Chain**:
  - Multi-tier model resilience chain: `gemini-3.5-flash-lite` ➔ `gemini-3.1-flash-lite` ➔ `gemini-3.6-flash` ➔ `gemini-3.8-flash` to handle 429 quota exhaustion and service outages gracefully.

---

## [0.1.0] - 2026-11-18

### Added
- **Decoupled Architecture**:
  - Thread-safe cross-component communication using PySide6 `EventBus` signals.
- **Desktop Graphical Interface**:
  - **Dynamic Island**: Floating top capsule widget with animated status dots (`idle`, `listening`, `thinking`, `speaking`).
  - **Overlay Chat**: Spotlight / Raycast style floating HUD window with Markdown rendering and multi-turn chat history.
  - **System Tray Icon**: Procedural cyan status ring icon on macOS Menu Bar.
- **Dual-Tone Speech Synthesis**:
  - Natural bilingual TTS via Microsoft Edge-TTS (`th-TH-NiwatNeural` for Thai, `en-GB-RyanNeural` British Butler for English) played natively via macOS `/usr/bin/afplay`.
- **System-Level Global Hotkeys**:
  - Quartz `CGEventTapCreate` capturing `Cmd + Shift + J` (Voice Toggle) and `Alt + Space` (Chat Overlay) from any active window with event swallowing.
- **Native Antigravity Bridge**:
  - Watchdog-based file synchronization (`.jarvis_task.md` and `.jarvis_result.md`) for silent IDE delegation.
