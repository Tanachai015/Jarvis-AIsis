# Jarvis Desktop Assistant 🚀

[![Platform](https://img.shields.io/badge/Platform-macOS%2014%2B%20(Tahoe%20%2F%20Sonoma%20%2F%20Sequoia)-blue?logo=apple)](https://www.apple.com/macos/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![GUI](https://img.shields.io/badge/UI-PySide6%20(Qt6)-41CD52?logo=qt)](https://www.qt.io/)
[![AI Engine](https://img.shields.io/badge/AI-Google%20GenAI%20SDK-4285F4?logo=google)](https://aistudio.google.com/)
[![Protocol](https://img.shields.io/badge/Standard-Model%20Context%20Protocol%20(MCP)-8B5CF6)](https://modelcontextprotocol.io/)
[![Speech](https://img.shields.io/badge/STT-Groq%20Cloud%20%2B%20Faster--Whisper-F55036)](https://groq.com/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

An agentic, event-driven, multimodal desktop AI companion built natively for macOS. Designed with a **decoupled PySide6 architecture**, a **Static Tool Registry combining Native macOS tools with Official Model Context Protocol (MCP) servers**, a **dual-engine hybrid Speech-to-Text pipeline**, **computer vision desktop automation**, and **100% stealth background execution**.

---

## 🌟 Key Features & Engineering Highlights

### 1. 🎙️ Dual-Engine Hybrid STT Pipeline (~0.2s Latency)
- **Primary Cloud Engine:** Integrates **Groq Cloud STT (`whisper-large-v3-turbo`)** via in-memory 16kHz WAV streaming (`io.BytesIO`), achieving sub-second response times (~0.2s - 0.4s) at **0% local CPU usage**.
- **Automatic Local Fallback:** Seamlessly fails over to an on-device **`Faster-Whisper` (`small`, int8)** model if offline, rate-limited, or network-disconnected without interrupting the user.
- **Smart Pacing & Silence Auto-Cutoff:** Real-time RMS audio energy detection automatically cuts off and submits queries after **3.5 seconds of silence** (`VOICE_POST_SPEECH_SILENCE`), with a 15-second maximum safety timeout.

### 2. 🎛️ 3 Adaptive Voice Listening Modes (Real-Time Switcher)
- **`push_to_talk`**: Triggers recording solely via macOS system hotkey (**`Cmd + Shift + J`**), consuming 0% mic CPU when idle.
- **`hi_jarvis`**: Silent background wake-word detection powered strictly by **Local `Faster-Whisper`** (preserving Groq API quota). Supports *"Hi Jarvis"*, *"Jarvis"*, *"จาร์วิส"*, *"จาวิส"*, and *"ไฮ จาร์วิส"*.
- **`hybrid` (Default)**: Dual trigger — seamlessly activate via hotkey or speak the wake word anytime.
- **Runtime Mode Switcher:** Switch modes instantly without application restart via the macOS Menu Bar Status Item.
- **RAM Lifecycle Management:** Pre-loads model in RAM for `hi_jarvis`/`hybrid`, and immediately unloads with `gc.collect()` when switching to `push_to_talk` or quitting.

### 3. 👁️ macOS Vision GUI Automation (Retina-Aware Mouse & Keyboard)
- **`click_on_screen`**: Captures screen, prompts Gemini Vision for coordinates, and calculates exact **Retina Display scale factors** (`img_w / screen_w`) for 100% accurate pixel-to-point mouse clicking.
- **Inactive Window Focus Handling**: Automatically performs a two-stage click sequence (focus click + 0.15s window manager delay + action click) guaranteeing background windows (e.g. Firefox, Chrome) activate and play videos/links immediately.
- **`type_text_on_screen`**: Injects text via macOS Clipboard (`pbcopy` + `Cmd+V`) supporting **Thai, English, Unicode, and Emoji** without dropping keystrokes, with asynchronous clipboard restoration.
- **`click_and_type`**: Single-step GUI locator, window focus activator, and keyboard input tool.

### 4. 🛠️ Static Tool Registry & Official MCP Ecosystem (40 Tools)
- **Pre-Compiled Tool Registry:** Native tools and MCP tools are pre-compiled into `GenerateContentConfig` once at startup, eliminating per-request schema construction overhead.
- **Instant Boot (0.005s):** Persistent tool schema cache (`memory/mcp_tools_cache.json`) with SHA-256 configuration checksum validation.
- **Official MCP Servers:** Runs standard Stdio sub-processes:
  - `@modelcontextprotocol/server-filesystem` (16 tools)
  - `mcp-server-fetch` (1 tool)
  - `mcp-server-git` (14 tools)
  - Native macOS Tools: Vision, System Control, Antigravity Bridge, Memory, Reveal, Raw History, Mouse & Keyboard (9 tools)

### 5. 🥷 100% Stealth Background Execution & On-Demand Reveal
- Never steals desktop focus during background file edits, code refactoring, or IDE task delegations.
- **On-Demand Reveal (`reveal_task_result`):** Results, modified files, and browser outputs open on-screen **only when explicitly commanded by the user** (e.g. *"เปิดดูผลงานล่าสุด"*, *"reveal"*).

### 6. 🗣️ Dual-Output Protocol & Continuous Bilingual Speech
- **Visual Display (Overlay Chat):** Full comprehensive Markdown, tables, and fenced code blocks.
- **Natural Spoken Speech (Edge-TTS):** Clean spoken summary inside `[SPEAK]` tags across multi-line paragraphs without premature sentence cutoffs.
- **Bilingual Tone:** Automatic script detection toggling between Thai (`th-TH-NiwatNeural`, -14Hz) and British Butler English (`en-GB-RyanNeural`, -8Hz).

---

## 🏛️ System Architecture

```text
[User Trigger: Cmd+Shift+J / "Hi Jarvis"]
                 │
                 ▼
     [Quartz CGEventTap / sounddevice Mic]
                 │
                 ├── Mode: push_to_talk ──> Hotkey only
                 ├── Mode: hi_jarvis   ──> Local Faster-Whisper (Wake Word)
                 └── Mode: hybrid      ──> Both triggers active
                                 │
                                 ▼
                     [Speech-to-Text Pipeline]
                                 │
                     ┌───────────┴───────────┐
                     ▼                       ▼
            [Primary Cloud STT]     [Local Fallback STT]
             Groq whisper-large        Faster-Whisper
               (~0.2s latency)         (Offline / int8)
                     │                       │
                     └───────────┬───────────┘
                                 │ (emit user_message_received)
                                 ▼
                     [JarvisBrain (core/brain.py)]
                                 │
                     ┌───────────┴───────────┐
                     ▼                       ▼
           [Explicit Fallback Chain]  [Static Tool Registry (40 Tools)]
           gemini-3.5-flash-lite      • Native macOS Tools (9)
           gemini-3.1-flash-lite        - Vision Screen Analysis
           gemini-3.6-flash             - Retina Click / Clipboard Type
           gemini-3.8-flash             - System Control & Memory
                                        - Stealth Reveal & Raw Archive
                                      • Official MCP Servers (31)
                                        - filesystem, fetch, git
                                 │
                                 ▼
                     [Dual-Output Protocol]
                                 │
                     ┌───────────┴───────────┐
                     ▼                       ▼
            [Visual Screen HUD]     [Neural Voice Synthesis]
             OverlayChat Window      Microsoft Edge-TTS
             (Markdown, Code)        (Dual-Tone TH/EN afplay)
```

---

## 📂 Project Directory Structure

```text
Javis Project/
├── .env                        # Local environment secrets (Git-ignored)
├── .env.example                # Safe environment configuration template
├── .gitignore                  # Strict security & cache ignore rules
├── requirements.txt            # Python dependencies
├── config.py                   # Central configuration & runtime constants
├── main.py                     # Entry point & application lifecycle manager
├── mcp_servers.json            # Official MCP server configurations
├── PROJECT_ARCHITECTURE.md     # In-depth architectural blueprint
├── CHANGELOG.md                # Release version history
├── README.md                   # Portfolio showcase & documentation
│
├── core/                       # Core system logic
│   ├── event_bus.py            # Thread-safe PySide6 signal bus
│   ├── brain.py                # Gemini cognitive processor & fallback chain
│   ├── tools.py                # Native macOS tools (Vision, Mouse, Keyboard)
│   ├── task_manager.py         # Stealth task registry & on-demand reveal
│   ├── raw_archive.py          # 365-day monthly partitioned JSONL raw storage
│   └── mcp_manager.py          # MCP client & persistent schema disk cache
│
├── integrations/               # External developer integrations
│   └── antigravity_bridge.py   # Silent file-based task bridge + Watchdog
│
├── voice/                      # Voice I/O pipeline
│   ├── listener.py             # Dual-engine STT, 3 listening modes, silence cutoff
│   └── speaker.py              # Bilingual dual-tone Edge-TTS + macOS afplay
│
├── ui/                         # PySide6 desktop interface
│   ├── dynamic_island.py       # Floating macOS pill status indicator
│   ├── overlay_chat.py         # Spotlight/Raycast style chat HUD
│   └── tray.py                 # Menu bar status icon & mode switcher
│
└── memory/                     # Local data storage (Git-ignored)
    └── .gitkeep                # Repository directory anchor
```

---

## 🛠️ Prerequisites & macOS Permissions

To enable seamless low-level system interaction on macOS:

1. **Accessibility (`AXIsProcessTrustedWithOptions`)**:
   - Required for Quartz System EventTap (`Cmd+Shift+J`, `Alt+Space`) and synthetic mouse/keyboard automation.
   - Go to: **System Settings > Privacy & Security > Accessibility**
   - Enable: **Terminal / iTerm / IDE / Python**
2. **Microphone**:
   - Required for `voice/listener.py`.
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
git clone <your-repo-url>
cd "Javis Project"

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

# Voice Listening Mode: hybrid, push_to_talk, or hi_jarvis
VOICE_LISTEN_MODE=hybrid
```

### 3. Launch Jarvis
```bash
python3 main.py
```

---

## ⌨️ Control & Shortcuts

| Action | Shortcut / Trigger | Description |
| :--- | :--- | :--- |
| **Toggle Chat HUD** | `Alt + Space` | Show/hide Spotlight-style overlay chat window |
| **Toggle Voice Mic** | `Cmd + Shift + J` | Press to record (Tink), press again to send (Pop) |
| **Wake Word Trigger** | *"Hi Jarvis"* | Wake up assistant via speech in `hybrid` or `hi_jarvis` mode |
| **Silence Cutoff** | *3.5s pause* | Automatically dispatches voice query after speaking ends |
| **Switch Voice Mode** | Status Bar Menu | Change between `Hybrid`, `Push-to-Talk`, and `Hi Jarvis` |
| **Inspect Work** | *"เปิดดูผลงานล่าสุด"* | Reveals completed background files/URLs on screen |

---

## 📋 Technology Stack

- **Core Runtime:** Python 3.11+, PySide6 (Qt for Python 6.6+)
- **Large Language Models:** Google GenAI SDK (`gemini-3.5-flash-lite`, `gemini-3.6-flash`, `gemini-3.8-flash`)
- **Speech-to-Text:** Groq Cloud API (`whisper-large-v3-turbo`), Faster-Whisper (CTranslate2, int8)
- **Speech Synthesis:** Microsoft Edge-TTS (`th-TH-NiwatNeural`, `en-GB-RyanNeural`), macOS `/usr/bin/afplay`
- **Protocols & Standards:** Model Context Protocol (MCP) Stdio Client
- **macOS Low-Level APIs:** Quartz Event Tap (`CGEventTapCreate`), ApplicationServices Accessibility, `screencapture`, `pbcopy`/`pbpaste`
- **GUI Automation:** PyAutoGUI, Pillow (PIL), NumPy, SoundDevice

---

## 📄 License

This project is open-sourced under the [MIT License](LICENSE).
