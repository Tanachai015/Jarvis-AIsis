# Jarvis Desktop Assistant (Jarvis-AIsis) 🚀

[![Platform](https://img.shields.io/badge/Platform-macOS%2014%2B%20(Tahoe%20%2F%20Sonoma%20%2F%20Sequoia)-blue?logo=apple)](https://www.apple.com/macos/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![GUI](https://img.shields.io/badge/UI-PySide6%20(Qt6)-41CD52?logo=qt)](https://www.qt.io/)
[![AI Engine](https://img.shields.io/badge/AI-Google%20GenAI%20SDK-4285F4?logo=google)](https://aistudio.google.com/)
[![Protocol](https://img.shields.io/badge/Standard-Model%20Context%20Protocol%20(MCP)-8B5CF6)](https://modelcontextprotocol.io/)
[![Speech](https://img.shields.io/badge/STT-Groq%20Cloud%20%2B%20Faster--Whisper-F55036)](https://groq.com/)
[![Wake Engine](https://img.shields.io/badge/Wake%20Word-OpenWakeWord%20ONNX-orange)](https://github.com/dscripka/openWakeWord)
[![VAD](https://img.shields.io/badge/VAD-Silero%20VAD%20v5-purple)](https://github.com/snakers4/silero-vad)
[![Testing](https://img.shields.io/badge/Automated%20Tests-25%2F25%20PASS%20(100%25)-success)](file:///Volumes/WorkDrive/Javis%20Project/automated_backtest_full_report.md)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

An agentic, event-driven, multimodal desktop AI companion built natively for macOS. Designed with a **decoupled PySide6 architecture**, a **Single-Pipeline Unified Microphone Architecture combining Silero VAD neural filtering and OpenWakeWord ONNX edge detection**, a **True Full-Duplex Barge-in engine with pre-roll buffer stitching**, **specialized Thai NLP & RapidFuzz Phonetic Matching**, **computer vision desktop automation**, and **100% stealth background execution**.

---

## 🌟 Key Features & Engineering Highlights

### 1. 🎙️ Single-Pipeline Microphone Architecture & Edge Wake Trigger
- **Unified Audio Pipeline:** Single low-latency `sounddevice.InputStream` (`16kHz`, mono `float32`, `512 samples` / 32ms blocks) servicing both Push-to-Talk and hands-free wake word detection without opening/closing audio streams.
- **Edge Wake Engine (`OpenWakeWord`):** Sub-100ms on-device wake word detection (`hey_jarvis`) running locally via ONNX Runtime with an internal 1280-sample (`80ms`) PCM `int16` accumulation buffer. Consumes **< 1% CPU** on Apple Silicon and unloads heavy Whisper models from standby RAM.
- **Neural Voice Filtering (`Silero VAD`):** High-precision neural voice activity detection (512-sample float32 tensors) thread-safe via `vad_lock` and `torch.no_grad()`, 100% immune to keyboard typing, air conditioning hum, and ambient environmental noise.
- **Pre-Cached Instant Acknowledgments:** Pre-synthesizes and caches wake acknowledgment audio files (`"ครับบอส"`, `"สวัสดีครับ"`, `"พร้อมครับ"`, `"ว่าไงครับ"`) for zero-latency vocal responses before opening the listening window.

### 2. ⚡ True Full-Duplex Voice & Instant Barge-in (> 0.6s)
- **Simultaneous Playback & Microphone Capture:** Microphone stream remains live and active even while Jarvis is actively speaking through `/usr/bin/afplay`.
- **Dual-Guard Barge-in Detection:** Combines calibrated Silero VAD (`threshold: 0.65`) and acoustic RMS (`threshold: 0.025`) with a 2-frame grace tolerance (~64ms) to accommodate natural unvoiced consonants and syllable gaps.
- **Instant Playback Interruption:** Speaking continuously for **>= 0.6 seconds** immediately halts audio playback via `speaker.stop_speaking()`.
- **Pre-roll Buffer Stitching:** Seamlessly retains the initial 0.6s speech burst and prepends it to the active recording session. The user can speak continuously without needing to repeat their sentence or wait for modes to switch!
- **Continuous Follow-up Loop:** Stays in listening mode for 60 seconds after Jarvis replies, allowing fluid multi-turn back-and-forth dialogue without pressing keys or repeating wake words.

### 3. 🇹🇭 Thai NLP & RapidFuzz Phonetic Matching Engine (`core/thai_nlp.py`)
- **100% Lazy Loading:** Zero impact on cold-start boot time (< 0.005s initial load).
- **TTS Pacing & Currency Normalization:** Automatically converts Thai Baht amounts (e.g. `1,500 บาท` -> `หนึ่งพันห้าร้อยบาทถ้วน`) while strictly preserving technical tokens (e.g. `v1.8.1`, `พอร์ต 8080`, `IP 192.168.1.1`).
- **Intelligent macOS App Name Resolution:** Scans `/Applications` and utilizes `Thai Soundex (lk82)` + `RapidFuzz WRatio` to resolve app aliases (e.g., `"Chrome"` -> `"Google Chrome"`, `"calc"` -> `"Calculator"`, and Thai phonetic queries `"ไฟ๊ฟ๊กอ"` -> `"Firefox"`), blacklisting uninstallers from accidental activation.
- **Fast Pre-Brain Exit Filtering:** Colloquial dismissal phrases (e.g., *"ขอบคุณคับ"*, *"พอแค่นี้เด้อ"*, *"พักก่อน"*) are intercepted by RapidFuzz and acknowledged locally, returning to standby immediately and saving 100% of Gemini API tokens.
- **Phonetic Archive Search:** Semantic word segmentation (`newmm`) and Soundex matching across historical records (e.g., matching *"โปรเจค"* with *"โปรเจกต์"*).

### 4. 🧠 Multi-Tier Cognitive Architecture & Dual-Output Protocol
- **4-Tier Context Engine (`core/brain.py`):**
  - **L0 (Soul Core):** Philosophical anchor, candor, transparent confidence scoring, and strict behavioral guidelines (`memory/soul_core.md`).
  - **L1 (User Facts):** Permanent user preferences and confirmed facts (`memory/jarvis_memory.json`).
  - **L2 (Lessons & Context):** Dynamic rolling history of recent session events and lessons (`memory/events.jsonl`).
  - **L3 (Active Conversation):** Rolling multi-turn chat history (`memory/chat_history.json`).
- **Dual-Output Protocol:** Separates rich Markdown formatting, tables, and code blocks for visual HUD display from concise 1-2 sentence spoken summaries enclosed in `[SPEAK]...[/SPEAK]` tags for Edge-TTS speech synthesis.
- **Explicit Fallback Chain:** Automatically falls back across `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gemini-3.6-flash`, and `gemini-3.8-flash` on rate limits or API outages.

### 5. 👁️ macOS Vision GUI Automation (Retina-Aware Mouse & Keyboard)
- **`click_on_screen`**: Captures screen, prompts Gemini Vision for coordinates, and calculates exact **Retina Display scale factors** (`img_w / screen_w`) for pixel-perfect mouse clicking.
- **Inactive Window Focus Handling**: Automatically performs a two-stage click sequence (focus click + 0.15s window manager delay + action click) guaranteeing background windows (e.g. Firefox, Chrome) activate and play videos/links immediately.
- **`type_text_on_screen`**: Injects text via macOS Clipboard (`pbcopy` + `Cmd+V`) supporting **Thai, English, Unicode, and Emoji** without dropping keystrokes, with asynchronous clipboard restoration.
- **`click_and_type`**: Single-step GUI locator, window focus activator, and keyboard input tool.

### 6. 🛠️ Static Tool Registry & Official MCP Ecosystem (40 Tools)
- **Pre-Compiled Tool Registry:** Native tools and MCP tools are pre-compiled into `GenerateContentConfig` once at startup, eliminating per-request schema construction overhead.
- **Instant Boot (0.005s):** Persistent tool schema cache (`memory/mcp_tools_cache.json`) with SHA-256 configuration checksum validation.
- **Official MCP Servers:** Runs standard Stdio sub-processes:
  - `@modelcontextprotocol/server-filesystem` (16 tools)
  - `mcp-server-fetch` (1 tool)
  - `mcp-server-git` (14 tools)
  - Native macOS Tools: Vision, System Control, Antigravity Bridge, Memory, Reveal, Raw History, Mouse & Keyboard (9 tools)

### 7. 🧪 Automated Backtest Suite (`tests/run_backtest.py`)
- **100% Offline-Safe & Zero-Token-Burn:** Complete mocking of external hardware (`sounddevice`, `/usr/bin/afplay`), operating system subprocesses (`open -a`, `screencapture`), and AI APIs.
- **Strict Memory Sandboxing:** Tests run in temporary directories (`tempfile.TemporaryDirectory`) guaranteeing zero mutations to production memory files.
- **18 Test Cases Passing 100% in ~2.9s:** Covers Thai NLP, Voice Engine states, Barge-in thresholds, Grace tolerances, OpenWakeWord int16 accumulation, and MCP schema validation.

---

## 🏛️ System Architecture & Data Flow

```text
[User Trigger: Cmd+Shift+J (PTT)  OR  "Hey Jarvis" (Edge Wake Trigger)]
                               │
                               ▼
        [JarvisListener Single-Pipeline (voice/listener.py)]
                               │
       ┌───────────────────────┴────────────────────────┐
       ▼                                                ▼
[Standby Wake Mode]                            [Active Recording (PTT)]
- Silero VAD (512 float32, 16kHz)             - Captures user command audio
- OpenWakeWord (1280 int16 accumulation)       - Silero VAD speech detection
- Plays cached acknowledgment audio            - 3.0s post-speech silence cutoff
                               │                        │
                               └───────────┬────────────┘
                                           ▼
                       [Speech-to-Text Pipeline (voice/listener.py)]
                                           │
                               ┌───────────┴───────────┐
                               ▼                       ▼
                      [Primary Cloud STT]     [Local Fallback STT]
                       Groq whisper-large        Faster-Whisper
                         (~0.2s latency)         (Offline / int8)
                               │                       │
                               └───────────┬───────────┘
                                           │
                                           ▼
                      [Pre-Brain Exit Guard (RapidFuzz WRatio)]
                       Intersects exit phrases ("ขอบคุณครับ", "พอแค่นี้")
                                           │ (normal commands)
                                           ▼ (emit user_message_received)
                               [JarvisBrain (core/brain.py)]
                                           │
                               ┌───────────┴───────────┐
                               ▼                       ▼
                     [4-Tier Context]         [Static Tool Registry (40 Tools)]
                     - L0: Soul Core          - Native macOS System & Vision Tools
                     - L1: User Facts         - Official MCP (Filesystem, Fetch, Git)
                     - L2: Events & State     - Antigravity IDE Stealth Bridge
                     - L3: Chat History
                                           │
                                           ▼
                               [Dual-Output Protocol]
                                           │
                               ┌───────────┴───────────┐
                               ▼                       ▼
                      [Visual Screen HUD]     [Neural Voice Synthesis]
                       OverlayChat Window      Microsoft Edge-TTS
                       (Markdown, Tables,      (Pacing Normalized, Dual TH/EN)
                        Code Blocks)                   │
                                                       ▼
                                            [macOS /usr/bin/afplay]
                                                       │
                           ┌───────────────────────────┴───────────────────────────┐
                           ▼                                                       ▼
               [Continuous Follow-up Loop (60s)]                     [Full-Duplex Barge-in (> 0.6s)]
                Listens for follow-up questions                       User interrupts speaker playback:
                without repeating wake words                          - Instantly halts afplay
                                                                      - Stitches 0.6s pre-roll buffer
                                                                      - Immediately resumes recording
```

---

## 📂 Project Directory Structure

```text
Javis Project/
├── .env                              # Local environment secrets (Git-ignored)
├── .env.example                      # Safe environment configuration template
├── .gitignore                        # Strict security & cache ignore rules
├── requirements.txt                  # Python dependencies
├── config.py                         # Central configuration & runtime constants
├── main.py                           # Entry point & application lifecycle manager
├── voice_settings.json               # Configurable voice thresholds & wake settings
├── mcp_servers.json                  # Official MCP server configurations
├── automated_backtest_full_report.md # Full report of 18 automated backtest suites
├── PROJECT_ARCHITECTURE.md           # In-depth architectural blueprint
├── CHANGELOG.md                      # Release version history
├── README.md                         # Project documentation & overview
│
├── tests/                            # Automated Testing Suite
│   └── run_backtest.py               # 18-case offline automated backtest runner
│
├── core/                             # Core system logic
│   ├── event_bus.py                  # Thread-safe PySide6 signal bus
│   ├── brain.py                      # Gemini cognitive processor & 4-tier context
│   ├── tools.py                      # Native macOS tools (Vision, Mouse, Keyboard)
│   ├── thai_nlp.py                   # PyThaiNLP & RapidFuzz Phonetic Matching Engine
│   ├── task_manager.py               # Stealth task registry & on-demand reveal
│   ├── raw_archive.py                # 365-day monthly partitioned JSONL raw storage
│   └── mcp_manager.py                # MCP client & persistent schema disk cache
│
├── integrations/                     # External developer integrations
│   └── antigravity_bridge.py         # Silent file-based task bridge + Watchdog
│
├── voice/                            # Voice I/O pipeline
│   ├── listener.py                   # Single-Pipeline STT, VAD, OpenWakeWord, Barge-in
│   └── speaker.py                    # Bilingual dual-tone Edge-TTS + macOS afplay
│
├── ui/                               # PySide6 desktop interface
│   ├── dynamic_island.py             # Floating macOS pill status indicator
│   ├── overlay_chat.py               # Spotlight/Raycast style chat HUD
│   └── tray.py                       # Menu bar status icon & wake trigger toggle
│
└── memory/                           # Local data storage (Git-ignored)
    ├── soul_core.md                  # L0: Personality & candor anchor
    ├── jarvis_memory.json            # L1: Permanent confirmed facts
    ├── events.jsonl                  # L2: Lessons & dynamic state events
    ├── chat_history.json             # L3: Rolling active conversation turns
    └── raw_archive/                  # Monthly partitioned raw data (YYYY-MM.jsonl)
```

---

## 🛠️ Prerequisites & macOS Permissions

To enable seamless low-level system interaction on macOS:

1. **Accessibility (`AXIsProcessTrustedWithOptions`)**:
   - Required for Quartz System EventTap (`Cmd+Shift+J`, `Alt+Space`) and synthetic mouse/keyboard automation.
   - Go to: **System Settings > Privacy & Security > Accessibility**
   - Enable: **Terminal / iTerm / IDE / Python**
2. **Microphone**:
   - Required for `voice/listener.py` Single-Pipeline input.
   - Go to: **System Settings > Privacy & Security > Microphone**
   - Enable your terminal or IDE.
3. **Screen Recording**:
   - Required for `screencapture -x` vision analysis and GUI coordinate detection.
   - Go to: **System Settings > Privacy & Security > Screen Recording**
   - Enable your terminal or IDE.

---

## ⚡ Quickstart & Installation

### 1. Clone & Setup Environment
```bash
git clone https://github.com/Tanachai015/Jarvis-AIsis.git
cd "Jarvis-AIsis"

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment (`.env`)
```bash
cp .env.example .env
```
Edit `.env` with your API keys:
```ini
# Google Gemini API Key (Required for Brain & Vision)
GEMINI_API_KEY=AIzaSy...

# Groq Cloud API Key (Recommended for ultra-fast ~0.2s STT)
GROQ_API_KEY=gsk_...
STT_MODE=groq
GROQ_WHISPER_MODEL=whisper-large-v3-turbo

# Wake Word Detection Enabled on startup
WAKE_TRIGGER_ENABLED=true
```

### 3. Run Automated Backtest Suite (Recommended before launch)
```bash
python3 tests/run_backtest.py
```

### 4. Launch Jarvis
```bash
python3 main.py
```

---

## ⌨️ Control & Shortcuts

| Action | Shortcut / Trigger | Description |
| :--- | :--- | :--- |
| **Toggle Chat HUD** | `Alt + Space` | Show/hide Spotlight-style overlay chat window |
| **Toggle Voice Mic** | `Cmd + Shift + J` | Press to record (Tink sound), press again to send (Pop sound) |
| **Wake Word Trigger** | *"Hey Jarvis"* | Hands-free edge wake word via OpenWakeWord ONNX (`< 1% CPU`) |
| **Full-Duplex Barge-in** | *Speak > 0.6s during reply* | Instantly interrupts speaker and captures new command with pre-roll |
| **Follow-up Dialogue** | *Speak within 60s* | Continuous conversation loop without repeating wake words |
| **Silence Auto-Cutoff** | *3.0s pause* | Automatically dispatches voice query after speaking ends |
| **Exit Conversation** | *"ขอบคุณครับ" / "พอแค่นี้"* | Instantly returns to standby without invoking Gemini API |
| **Toggle Wake Word** | Status Bar Menu | Toggle `🎙️ Wake Word Trigger (Active/Disabled)` in real time |
| **Inspect Work** | *"เปิดดูผลงานล่าสุด"* | Reveals completed background files/URLs on screen on demand |

---

## 📋 Technology Stack

- **Core Runtime:** Python 3.11+, PySide6 (Qt for Python 6.6+)
- **Large Language Models:** Google GenAI SDK (`gemini-3.5-flash-lite`, `gemini-3.6-flash`, `gemini-3.8-flash`)
- **Speech-to-Text:** Groq Cloud API (`whisper-large-v3-turbo`), Faster-Whisper (CTranslate2, int8)
- **Wake Word & VAD:** OpenWakeWord ONNX (`hey_jarvis`), Silero VAD v5 (PyTorch JIT)
- **NLP & Phonetics:** PyThaiNLP (2024.1+), RapidFuzz (3.9+ C++ WRatio), Thai Soundex (`lk82`)
- **Speech Synthesis:** Microsoft Edge-TTS (`th-TH-NiwatNeural`, `en-GB-RyanNeural`), macOS `/usr/bin/afplay`
- **Protocols & Standards:** Model Context Protocol (MCP) Stdio Client
- **macOS Low-Level APIs:** Quartz Event Tap (`CGEventTapCreate`), ApplicationServices Accessibility, `screencapture`, `pbcopy`/`pbpaste`
- **GUI Automation:** PyAutoGUI, Pillow (PIL), NumPy, SoundDevice

---

## 📄 License

This project is open-sourced under the [MIT License](LICENSE).
