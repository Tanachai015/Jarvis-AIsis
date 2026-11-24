# เอกสารโครงสร้างสถาปัตยกรรมระบบ J.A.R.V.I.S. Desktop Assistant (Jarvis-AIsis) 🚀
*(J.A.R.V.I.S. Architecture & Technical Reference Manual — Release v1.9.3)*

เอกสารฉบับนี้สรุปภาพรวม สถาปัตยกรรม โครงสร้างไฟล์ ลำดับการทำงานของข้อมูล (Data Flow) และรายละเอียดเชิงลึกของทุกโมดูลในระบบ **Jarvis Desktop Assistant (`Jarvis-AIsis`)** ซึ่งพัฒนาขึ้นเพื่อทำงานบน **macOS (Apple Silicon & Intel)** โดยเฉพาะ ภายใต้ขุมพลัง **Google GenAI SDK (Gemini)**, **Official Model Context Protocol (MCP)**, **Vision GUI Automation**, **Single-Pipeline Unified Microphone**, และ **Context-Aware Interrupt Architecture**

---

## 📑 สารบัญ
1. [ภาพรวมของระบบ (System Overview)](#1-ภาพรวมของระบบ-system-overview)
2. [แผนผังโครงสร้างไฟล์ทั้งหมด (Full Directory Tree)](#2-แผนผังโครงสร้างไฟล์ทั้งหมด-full-directory-tree)
3. [รายละเอียดเชิงลึกของแต่ละโมดูล (Module Deep Dive)](#3-รายละเอียดเชิงลึกของแต่ละโมดูล-module-deep-dive)
   - [3.1 Entry Point & Lifecycle (`main.py`)](#31-entry-point--lifecycle-mainpy)
   - [3.2 การกำหนดค่าระบบ (`config.py`, `.env`, `voice_settings.json`)](#32-การกำหนดค่าระบบ-configpy-env-voice_settingsjson)
   - [3.3 ตัวกลางสื่อสารข้ามเธรด (`core/event_bus.py`)](#33-ตัวกลางสื่อสารข้ามเธรด-coreevent_buspy)
   - [3.4 สมองหลักและการประมวลผล AI (`core/brain.py`)](#34-สมองหลักและการประมวลผล-ai-corebrainpy)
   - [3.5 เครื่องมือระบบ macOS พื้นฐาน (`core/tools.py`)](#35-เครื่องมือระบบ-macos-พื้นฐาน-coretoolspy)
   - [3.6 ระบบบันทึกผลงานเบื้องหลังและ On-Demand Reveal (`core/task_manager.py`)](#36-ระบบบันทึกผลงานเบื้องหลังและ-on-demand-reveal-coretask_managerpy)
   - [3.7 คลังจัดเก็บข้อมูลดิบระยะยาว 365+ วัน (`core/raw_archive.py`)](#37-คลังจัดเก็บข้อมูลดิบระยะยาว-365-วัน-coreraw_archivepy)
   - [3.8 ระบบจัดการ MCP และ Tool Filtering (`core/mcp_manager.py`)](#38-ระบบจัดการ-mcp-และ-tool-filtering-coremcp_managerpy)
   - [3.9 ระบบเชื่อมต่อ Antigravity IDE (`integrations/antigravity_bridge.py`)](#39-ระบบเชื่อมต่อ-antigravity-ide-integrationsantigravity_bridgepy)
   - [3.10 ระบบรับเสียงพูดและ Context-Aware Interrupt (`voice/listener.py`)](#310-ระบบรับเสียงพูดและ-context-aware-interrupt-voicelistenerpy)
   - [3.11 ระบบสังเคราะห์เสียงพูดและ Pre-Cached Acks (`voice/speaker.py`)](#311-ระบบสังเคราะห์เสียงพูดและ-pre-cached-acks-voicespeakerpy)
   - [3.12 การประมวลผลภาษาไทยและ Phonetic Matching (`core/thai_nlp.py`)](#312-การประมวลผลภาษาไทยและ-phonetic-matching-corethai_nlppy)
   - [3.13 ส่วนติดต่อผู้ใช้ (`ui/`)](#313-ส่วนติดต่อผู้ใช้-ui)
   - [3.14 หน่วยความจำถาวรและแก่นความคิด (`memory/`)](#314-หน่วยความจำถาวรและแก่นความคิด-memory)
4. [แผนภาพลำดับการไหลของข้อมูล (System Data Flow)](#4-แผนภาพลำดับการไหลของข้อมูล-system-data-flow)
5. [ตารางคีย์ลัดและสิทธิ์ของระบบ macOS (Keybindings & Permissions)](#5-ตารางคีย์ลัดและสิทธิ์ของระบบ-macos-keybindings--permissions)
6. [ระบบทดสอบอัตโนมัติ (Automated Backtest Suite 24/24 PASS)](#6-ระบบทดสอบอัตโนมัติ-automated-backtest-suite-2424-pass)

---

## 1. ภาพรวมของระบบ (System Overview)

Jarvis Desktop Assistant ได้รับการออกแบบภายใต้สถาปัตยกรรม **Decoupled Event-Driven Architecture** โดยใช้ **PySide6 (Qt for Python)** เป็นแกนกลางในการจัดการ User Interface และ Event Loop มีจุดเด่นสำคัญดังนี้:

- **AI Engine:** ขับเคลื่อนด้วย **Google GenAI SDK (`google-genai`)** ใช้โมเดลหลัก `gemini-3.5-flash-lite` (ความเร็วตอบสนอง ~1.2 วินาที พร้อมโควต้า Free Tier 500 RPD / 15 RPM) เสริมด้วย **Explicit Fallback Chain** สลับโมเดลสำรองอัตโนมัติหากติด 429/503/504
- **Hybrid Tool Architecture:** ผสมผสานระหว่าง **Native macOS Tools** (ควบคุมระบบ Mac, ดูหน้าจอด้วย Vision, ส่งงาน Antigravity, จดจำข้อมูล, เปิดดูผลงาน On-Demand, ค้นประวัติ Raw Data 365 วัน) และ **Official Model Context Protocol (MCP) Servers** (Filesystem, Web Fetch และ Git มาตรฐานสากล) รวม **37 เครื่องมือ** พร้อมระบบกรอง Empty Arguments ป้องกัน Server Rejection
- **Single-Pipeline Unified Microphone:** สตรีมไมโครโฟนเส้นเดียว `16kHz mono float32` ให้บริการทั้ง Push-to-Talk, Standby Wake Word, และ Speaking Monitor พร้อมตัวขยายสัญญาณซอฟต์แวร์ **`wake_mic_gain: 2.5x`** ทำให้เรียกคำปลุกได้ง่ายจากระยะนั่งปกติ (50–70 ซม.)
- **Context-Aware Interrupt Engine (v1.8.3):** ยกเลิกการตัดเสียงด้วยเกณฑ์ความดังดิบ (ซึ่งเสี่ยงต่อ Acoustic Feedback Loop จากลำโพงเครื่อง) แล้วแทนที่ด้วย 3 ช่องทางขัดจังหวะที่แม่นยำ:
  1. ปุ่ม **`Esc` (Emergency Stop):** ตัดเสียงทันที ตอบรับ "Ok ครับ" และเปิดไมค์รับคำสั่งใหม่ 0ms
  2. คำปลุก **`"Hey Jarvis"`:** ทางด่วนตัดเสียงพูดของ Jarvis ทันทีด้วย `OpenWakeWord`
  3. คำสั่งเบรก 2 พยางค์ (**`interrupt_stop_phrases`**) พร้อมระบบ **Whole-Chunk Self-Echo Filter** (`fuzz.partial_ratio >= 60%`) ตัดเสียงสะท้อนตัวเองทิ้งเด็ดขาด ไม่ส่งเข้าสมอง
- **Clean Dialogue Loop:** มีแฟล็ก `suppress_next_followup` ระงับการเปิดไมค์หลังผู้ใช้บอกลา ทำให้คำตอบรับสุดท้ายไม่ไปกระตุ้น Followup Loop 60 วินาทีขึ้นมาซ้ำ
- **Stealth Background Execution & On-Demand Reveal:** ทำงานเบื้องหลัง 100% ไม่แย่งโฟกัสหน้าจอ ไม่เปิดแอปหรือไฟล์ขึ้นมาเองโดยพลการ บันทึกประวัติผลงานใน `task_manager` และเปิดดูเมื่อสั่งเท่านั้น
- **Dual-Tab UI (Conversation vs. Process & Raw Data):** แยกหน้าต่างแชทสะอาดตาออกจากข้อมูลดิบ (Logs / JSON / Listicles) ป้องกันข้อมูลดิบถมทับบทสนทนา
- **Long-term Raw Archive (365+ วัน):** แยกประวัติข้อมูลดิบรายเดือน (`memory/raw_archive/YYYY-MM.jsonl`) เก็บย้อนหลังได้ทั้งปีโดยไม่เปลืองโทเคน และค้นหาคืนได้ผ่านเครื่องมือ `search_raw_history`
- **Instant Boot Caching:** มีระบบ **Schema Disk Cache** โหลดสเปกเครื่องมือทั้ง 17+ ตัวในเวลาเพียง **0.005 วินาที** พร้อมระบบตรวจจับการอัปเดตอัตโนมัติด้วย SHA-256
- **System-level Global Interception:** ใช้ **Quartz `CGEventTapCreate`** ดักจับคีย์ลัดระดับลึกจากทุกหน้าต่างและดูดกลืนคีย์ (Event Swallowing) ไม่ให้ไปรบกวนแอปอื่น
- **Pre-Cached Instant Audio:** แคชไฟล์เสียงตอบรับคำปลุกและเสียงยืนยัน `"Ok ครับ"` (`memory/cached_ok_krub.mp3`) ล่วงหน้า เล่นผ่าน `/usr/bin/afplay` ด้วย Latency 0ms

---

## 2. แผนผังโครงสร้างไฟล์ทั้งหมด (Full Directory Tree)

```text
/Volumes/WorkDrive/Javis Project/
├── .env                                # ไฟล์ตั้งค่าส่วนตัว (API Keys, โมเดล, เสียง, คีย์ลัด)
├── .env.example                        # เทมเพลตตัวอย่างค่าคอนฟิกสำหรับแจกจ่าย
├── requirements.txt                    # รายการไลบรารี Dependencies ทั้งหมดของ Python
├── mcp_servers.json                    # คอนฟิกการรัน Official MCP Servers (filesystem, fetch, git)
├── voice_settings.json                 # การกำหนดค่าเสียง, เกณฑ์คำปลุก, คำสั่งเบรก, และระยะเวลา
├── config.py                           # ตัวแปรคงที่ระดับ Global และการโหลด Environment
├── main.py                             # Entry Point หลัก: Cocoa Loop, Quartz Tap, Lifecycle
├── README.md                           # เอกสารแนะนำการติดตั้งและคู่มือผู้ใช้งาน (v1.8.3)
├── PROJECT_ARCHITECTURE.md             # [ไฟล์นี้] สรุปสถาปัตยกรรมโครงสร้างโปรเจกต์โดยละเอียด
├── automated_backtest_full_report.md   # รายงานผลการทดสอบระบบอัตโนมัติฉบับเต็ม
├── Project Directory Structure.txt     # ผังโครงสร้างแบบย่อ
│
├── core/                               # แกนกลางระบบ (Logic, Brain, Tools, MCP, Signals)
│   ├── __init__.py
│   ├── event_bus.py                    # ตัวกลางส่งสัญญาณ PySide6 Signals (Thread-safe)
│   ├── brain.py                        # สมอง AI: Tiered Context (L0-L3), Explicit Fallback Chain
│   ├── tools.py                        # Native macOS Tools (Vision, Antigravity, System, Memory, Reveal)
│   ├── task_manager.py                 # ตัวจัดการบันทึกผลงานเบื้องหลังและ On-Demand Reveal
│   ├── raw_archive.py                  # คลังจัดเก็บและค้นหา Raw Data ระยะยาว 365 วัน แยกรายเดือน
│   ├── mcp_manager.py                  # ตัวจัดการ Official MCP Servers พร้อมตัวกรอง Empty Arguments
│   └── thai_nlp.py                     # ระบบประมวลผลภาษาไทย, Soundex (lk82), RapidFuzz WRatio
│
├── integrations/                       # การเชื่อมต่อภายนอก
│   ├── __init__.py
│   └── antigravity_bridge.py           # ตัวเชื่อม Antigravity IDE (.jarvis_task.md + Watchdog)
│
├── voice/                              # ระบบเสียงพูดและการได้ยิน
│   ├── __init__.py
│   ├── listener.py                     # Single-Pipeline Mic, OpenWakeWord (2.5x gain), Silero VAD, Context Interrupt
│   └── speaker.py                      # สังเคราะห์เสียง Dual-Tone (Edge-TTS) + Pre-Cached "Ok ครับ" + afplay
│
├── ui/                                 # ส่วนติดต่อผู้ใช้ (PySide6 Graphical Interface)
│   ├── __init__.py
│   ├── dynamic_island.py               # หน้าต่างแคปซูลลอยตัวด้านบนหน้าจอ (สถานะระบบ)
│   ├── overlay_chat.py                 # หน้าต่าง Overlay Chat สไตล์ Spotlight/Raycast
│   └── tray.py                         # ไอคอนบน Menu Bar (macOS Status Item) พร้อมสวิตช์เปิด/ปิด Wake Trigger
│
├── tests/                              # ชุดทดสอบความสมบูรณ์ของระบบ
│   └── run_backtest.py                 # Automated Backtest Runner (4 Suites, 24/24 PASS)
│
└── memory/                             # โฟลเดอร์เก็บข้อมูลถาวรข้ามเซสชัน
    ├── soul_core.md                    # แก่นแท้บุคลิกภาพและความคิด (L0 Context)
    ├── chat_history.json               # ประวัติการสนทนา 10 รอบล่าสุด (L3 Active Context)
    ├── jarvis_memory.json              # ความจำระยะยาวของผู้ใช้ (L1 User Facts)
    ├── events.jsonl                    # บันทึกบทเรียนและสถานะบริบทสำคัญ (L2 Lessons Context)
    ├── background_tasks.json           # ประวัติและผลลัพธ์ของงานเบื้องหลัง (On-Demand Reveal)
    ├── mcp_tools_cache.json            # แคชสเปกเครื่องมือ MCP ถาวร (Instant Boot 0.005s)
    ├── cached_ok_krub.mp3              # ไฟล์เสียงแคช "Ok ครับ" สำหรับการตอบรับ Interrupt ทันที
    └── raw_archive/                    # คลังเก็บ Raw Data ระยะยาว 365+ วัน แยกไฟล์รายเดือน (YYYY-MM.jsonl)
```

---

## 3. รายละเอียดเชิงลึกของแต่ละโมดูล (Module Deep Dive)

### 3.1 Entry Point & Lifecycle (`main.py`)
ทำหน้าที่เป็นศูนย์รวมการบูตโปรแกรมและจัดการวงจรชีวิต (Lifecycle):
1. **Accessibility Verification:** ตรวจสอบสิทธิ์การควบคุมระบบผ่าน `AXIsProcessTrustedWithOptions` หากยังไม่ได้รับสิทธิ์จะเด้งหน้า System Settings ให้อัตโนมัติ
2. **MCP Boot:** สั่งให้ `mcp_manager.start()` ทำงานเพื่ออ่านแคชและเชื่อมต่อ Stdio Subprocess
3. **Component Initialization:** สร้างอ็อบเจกต์ `JarvisBrain`, `AntigravityBridge`, `JarvisSpeaker`, `JarvisListener`, `DynamicIsland`, `OverlayChat`, และ `JarvisTrayIcon`
4. **Quartz System EventTap (`CGEventTapCreate`):** เริ่มต้นเธรดดักจับคีย์ลัดระดับระบบ พร้อมส่งผ่านการอ้างอิง `speaker`, `listener`, และ `overlay_chat`:
   - **`Escape` (Keycode 53):**
     - หาก `speaker.is_speaking == True`: สั่งตัดเสียงทันที (`speaker.stop_speaking()`), เล่นเสียงแคช `"Ok ครับ"` (`speaker.play_cached_ack()`), เปิดโหมดรับคำสั่งใหม่ (`listener.trigger_barge_in_direct()`) และดูดกลืนคีย์
     - หาก `overlay_chat.isVisible() == True`: สั่งซ่อนหน้าต่างแชทและดูดกลืนคีย์
     - หากไม่ได้พูดและไม่ได้เปิดแชท: ปล่อยคีย์ทะลุผ่านให้ macOS ใช้งานตามปกติ
   - **`Cmd + Shift + J` (Keycode 38):** 1-Tap Toggle Voice
   - **`Alt + Space` (Keycode 49):** Toggle Overlay Chat
5. **Graceful Teardown:** เมื่อปิดแอปพลิเคชัน จะสั่งปิดเธรดเสียง, สตรีมไมโครโฟน, ตัวเฝ้าไฟล์ และปิด MCP Sessions ทั้งหมดอย่างสะอาด

### 3.2 การกำหนดค่าระบบ (`config.py`, `.env`, `voice_settings.json`)
- **`config.py` & `.env`:** รวมศูนย์ค่า API Keys, โมเดล Gemini (`gemini-3.5-flash-lite`), STT Provider (`groq`), Hotkeys, และการเชื่อมโยงไดเรกทอรีโปรเจกต์
- **`voice_settings.json`:** คอนฟิกการทำงานของระบบเสียงระดับสูง:
  - `"wake_mic_gain": 2.5`: ตัวคูณขยายสัญญาณไมค์ 2.5 เท่าสำหรับป้อนเข้า `OpenWakeWord`
  - `"wake_score_threshold": 0.36`: เกณฑ์คะแนนการปลุกด้วยคำว่า `"hey_jarvis"`
  - `"interrupt_stop_phrases"`: รายการคำสั่งเบรก 2 พยางค์ขึ้นไป เช่น `["หยุดก่อน", "โอเคหยุด", "พอก่อนจาร์วิส", "ok stop", "stop please"]`
  - `"post_speech_silence_sec": 3.0`: ตรวจจับความเงียบหลังพูดเพื่อตัดส่งอัตโนมัติ
  - `"followup_timeout_sec": 60.0`: หน้าต่างรอฟังต่อเนื่องหลัง Jarvis พูดจบ

### 3.3 ตัวกลางสื่อสารข้ามเธรด (`core/event_bus.py`)
เป็น Singleton Class สืบทอดจาก `PySide6.QtCore.QObject` ช่วยให้การส่งข้อมูลระหว่าง Background Threads เข้าสู่ Main UI Loop เป็นไปอย่างปลอดภัย (Thread-Safe):
- `state_changed(str)`: แจ้งเปลี่ยนสถานะ (`idle`, `listening`, `thinking`, `running_tool`, `speaking`)
- `user_message_received(str)`: ส่งข้อความที่ได้จากเสียงพูดหรือช่องแชทเข้าสู่สมอง AI
- `assistant_reply_ready(str)`: ส่งข้อความคำตอบฉบับเต็มไปแสดงผลในหน้าต่างแชท `OverlayChat`
- `assistant_speak_ready(str)`: ส่งข้อความสรุปภาษาพูดสั้นๆ จากแท็ก `[SPEAK]` ไปยัง `JarvisSpeaker`
- `task_log_updated(str, str)`: ส่งบันทึกการทำงานของ Tool หรือข้อผิดพลาดไปแสดงผล

### 3.4 สมองหลักและการประมวลผล AI (`core/brain.py`)
- **4-Tier Cognitive Context Engine:**
  - **L0 (Soul Core):** แก่นแท้ ปรัชญา และจริยธรรม (`memory/soul_core.md`)
  - **L1 (User Facts):** ข้อมูลความจำถาวรของผู้ใช้ (`memory/jarvis_memory.json`)
  - **L2 (Lessons Context):** บันทึกบทเรียนและสถานะบริบทสำคัญ (`memory/events.jsonl`)
  - **L3 (Active Conversation):** ประวัติสนทนา 10 เทิร์นล่าสุด (`memory/chat_history.json`)
- **Dual-Output Protocol (`[SPEAK]` Tags):** สั่งโมเดลแยกผลลัพธ์ 2 ชุด: หน้าจอฉบับเต็ม และเสียงพูดสรุปกระชับใน `[SPEAK]...[/SPEAK]`
- **Explicit Fallback Chain:** ลำดับโมเดลสำรอง:
  `["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.6-flash", "gemini-3.8-flash"]`
- **macOS GUI Automation Policy:** ให้สิทธิ์เต็มที่ในการมองเห็นและควบคุมหน้าจอผ่าน `click_on_screen`, `type_text_on_screen`, และ `click_and_type`

### 3.5 เครื่องมือระบบ macOS พื้นฐาน (`core/tools.py`)
ประกอบด้วย 9 เครื่องมือหลักที่เขียนด้วย Native Python และคำสั่งของ macOS:
1. `delegate_to_antigravity(task_prompt)`: ส่งงานเขียนโค้ดไปยัง Antigravity IDE ในเบื้องหลังผ่านไฟล์ `.jarvis_task.md`
2. `analyze_current_screen(question)`: ถ่ายภาพหน้าจอด้วย `screencapture -x` ส่งให้ Gemini Vision วิเคราะห์
3. `control_mac_system(action, target, app)`: ควบคุมระบบ macOS (`open_path`, `open_app`, `open_url`, `set_volume`, `get_system_info`)
4. `manage_memory(mode, content)`: บันทึกและดึงข้อมูลความจำระยะยาวใน `memory/jarvis_memory.json`
5. `reveal_task_result(task_ref)`: เปิดไฟล์/หน้าต่างแอปของงานเบื้องหลังขึ้นมาบนหน้าจอเฉพาะเมื่อผู้ใช้สั่งเปิดดู (On-Demand Reveal)
6. `search_raw_history(query, days_back)`: ค้นหาประวัติข้อมูลดิบย้อนหลัง 365 วันจากคลัง `memory/raw_archive/`
7. `click_on_screen(target_description, double_click)`: แคปหน้าจอ ค้นหาพิกัดกึ่งกลางด้วย Vision คำนวณ Retina Scale Factor และคลิกแม่นยำ
8. `type_text_on_screen(text, press_enter)`: พิมพ์ข้อความภาษาไทย/อังกฤษผ่าน Clipboard Injection (`pbcopy` + `Cmd+V`)
9. `click_and_type(target_description, text, press_enter)`: ควบคุมแบบรวบขั้นตอนเดียว: หาพิกัด ➔ คลิกโฟกัส ➔ พิมพ์ข้อความทันที

### 3.6 ระบบบันทึกผลงานเบื้องหลังและ On-Demand Reveal (`core/task_manager.py`)
- บันทึกประวัติงานเบื้องหลังลง `memory/background_tasks.json` อย่างเงียบกริบ (Stealth Mode)
- แสดงผลเมื่อผู้ใช้สั่งเปิดดูผลงาน (`reveal_task_result`) เท่านั้น ไม่มีการเปิดแอปหรือไฟล์ขึ้นมาขัดจังหวะเอง

### 3.7 คลังจัดเก็บข้อมูลดิบระยะยาว 365+ วัน (`core/raw_archive.py`)
- แยกเก็บข้อมูลดิบรายเดือนลงไฟล์ `memory/raw_archive/YYYY-MM.jsonl`
- รองรับการค้นหาย้อนหลังด้วยคำตัดคำภาษาไทย (`newmm`) และ Thai Soundex (`lk82`)

### 3.8 ระบบจัดการ MCP และ Tool Filtering (`core/mcp_manager.py`)
- เชื่อมต่อ Official MCP Servers (Filesystem, Web Fetch, Git) รวม 31 เครื่องมือ
- **Empty Arguments Sanitization (v1.8.2):** กรองค่า `None` และสตริงว่าง `""` ออกจากพารามิเตอร์ที่เป็น Option ก่อนส่งเข้า MCP Server ป้องกันปัญหา Server Rejection
- **Persistent Schema Cache:** โหลดสเปกเครื่องมือจาก `memory/mcp_tools_cache.json` ในเวลาเพียง 0.005 วินาที พร้อมตรวจสอบ SHA-256

### 3.9 ระบบเชื่อมต่อ Antigravity IDE (v1.8.5 — 100% Silent File-Bridge)
- **Zero osascript Focus:** ตัดคำสั่ง AppleScript ที่พยายามแย่งโฟกัสหน้าจอออก 100% ป้องกันปัญหาค้าง Timeout 5 วินาที และรักษาปรัชญา Stealth Mode สมบูรณ์แบบ
- **Atomic File Write:** เขียนไฟล์ผ่าน `.jarvis_task.md.tmp` แล้วใช้ `os.replace` สลับไฟล์ ป้องกัน Race Condition และความเสียหายของไฟล์
- **Deduplication Guard:** ป้องกันโมเดล LLM เรียก `delegate_to_antigravity` ซ้ำซ้อน ด้วย RapidFuzz WRatio $\ge 80\%$ ภายใน Cooldown 60 วินาที หรือขณะที่งานเดิมยังค้างทำอยู่
- **Watchdog Result Monitoring:** เฝ้าดูผลลัพธ์ผ่าน `.jarvis_result.md` ด้วย `watchdog.observers.Observer` และแจ้งเตือนด้วยเสียงเมื่อเสร็จสิ้น

### 3.10 ระบบรับเสียงพูดและ Context-Aware Interrupt (`voice/listener.py`)
ยึดท่อส่งเสียง **Single-Pipeline Microphone Architecture** แบ่งเป็น 3 สถานะ:
1. **`STANDBY_WAKE` (โหมดรอคำปลุก):**
   - รันโมเดล `OpenWakeWord` (`hey_jarvis` ONNX) บน CPU ต่ำกว่า 1% โดยไม่โหลด Whisper เข้า RAM
   - ขยายสัญญาณไมค์ **`wake_mic_gain: 2.5x`** ก่อนป้อนเข้าโมเดล ทำให้ระยะนั่งปกติ (50–70 ซม.) ปลุกติดง่ายที่เกณฑ์คะแนน `0.36`
   - เมื่อตรวจพบคำปลุก: สุ่มเล่นเสียงตอบรับสั้นๆ (`wake_ack_phrases`), เคลียร์ Buffer ไมค์, และเข้าสู่ `ACTIVE_PTT`
2. **`ACTIVE_PTT` (โหมดบันทึกเสียงคำสั่ง):**
   - ใช้ **Silero VAD** (512 samples / 32ms float32) วิเคราะห์เสียงมนุษย์จริง ป้องกันเสียงเคาะแป้นพิมพ์และเสียงแอร์ 100%
   - ตัดส่งคำสั่งอัตโนมัติเมื่อหยุดพูดครบ 3.0 วินาที (`post_speech_silence_sec`)
   - ถอดความด้วย Groq Cloud STT (`whisper-large-v3-turbo`, ~0.2s) สำรองด้วย Local Faster-Whisper
   - **Exit Phrase Detection:** หากพบคำปิดบทสนทนา (เช่น *"พักก่อน"*, *"ขอบคุณครับ"*) จะตั้งค่า `suppress_next_followup = True`, ตอบรับสั้นๆ และกลับสู่ `STANDBY_WAKE` โดยไม่เปิดลูปต่อ
3. **`SPEAKING_MONITOR` (โหมดควบคุมขณะ Jarvis กำลังพูด — v1.8.4 Zero-Overhead):**
   - **ปุ่ม Esc (Direct Instant Barge-in — Keycode 53):** ใช้ปุ่ม `Esc` ผ่าน Quartz System EventTap เป็นกลไกตัดเสียงพูดทันที (Latency 0ms) เมื่อกดปุ่ม ระบบจะ:
     1. สั่ง `speaker.stop_speaking()` หยุดเสียงพูดทันที
     2. เรียก `speaker.play_cached_ack()` เล่นเสียง "Ok ครับ" สั้นๆ ยืนยัน
     3. เรียก `listener.trigger_barge_in_direct()` เปลี่ยนสถานะเป็น `ACTIVE_PTT` พร้อมรับคำสั่งใหม่ทันที
   - **Zero API / CPU Overhead:** ขณะที่ Jarvis กำลังอ่านข้อความ ไมโครโฟนจะปิดการส่งข้อมูลเข้าคิว (Drain Audio Queue) ไม่มีการส่งเสียงขึ้น Groq Whisper และไม่รันโมเดลคำปลุกซ้อน เพื่อป้องกันปัญหาเสียงลำโพงรบกวนไมค์ (Acoustic Feedback Loop) และประหยัดโควต้า API 100%
   - **Future Roadmap (v1.9.0+):** การพูดแทรกด้วยเสียง (Full-Duplex Voice Barge-in) ถูกกำหนดแผนงานพัฒนาโดยใช้ **macOS Native Audio Unit (`AUVoiceProcessingIO`)** ซึ่งมีระบบ Acoustic Echo Cancellation (AEC) ระดับ Hardware/CoreAudio เพื่อหักลบสัญญาณเสียงลำโพงออกจากไมโครโฟนโดยตรง

### 3.11 ระบบสังเคราะห์เสียงพูดและ Pre-Cached Acks (`voice/speaker.py`)
- สลับโทนเสียงภาษาไทย (`th-TH-NiwatNeural`) และอังกฤษ (`en-GB-RyanNeural`) อัตโนมัติ
- ปรับแต่งคำอ่านภาษาไทยด้วย `core/thai_nlp.py` (แปลงเงินบาท, คงรหัสพอร์ต/IP, จัดวรรคตอนหายใจ)
- บันทึกข้อความที่กำลังอ่านลงใน `self.current_spoken_text` แบบเรียลไทม์เพื่อใช้เป็นฐานข้อมูลตัดเสียงสะท้อน
- มีระบบพรีโหลดและแคชไฟล์เสียงยืนยัน `"Ok ครับ"` (`memory/cached_ok_krub.mp3`) ตั้งแต่ตอนบูตโปรแกรม
- เมธอด `play_cached_ack()` เล่นเสียงตอบรับผ่าน `/usr/bin/afplay` แบบ Blocking เพื่อให้ผู้ใช้ได้รับสัญญาณยืนยันทันที

### 3.12 การประมวลผลภาษาไทยและ Phonetic Matching (`core/thai_nlp.py`)
- **100% Lazy Loading:** โหลด `PyThaiNLP` และ `RapidFuzz` เฉพาะเมื่อเรียกใช้ รักษาความเร็วบูตใน 0.005 วินาที
- `prepare_thai_tts_text()`: ทำความสะอาดข้อความก่อนส่งเข้า Edge-TTS
- `resolve_macos_app_name()`: จับคู่ชื่อเล่น/ชื่อเรียกแอปภาษาไทย-อังกฤษ (`Chrome` ➔ `Google Chrome`)
- `fuzzy_match_phrase()`: จับคู่คำสแลงเพี้ยนด้วย RapidFuzz WRatio สำหรับคำบอกลาและคำสั่งเบรก

### 3.13 ส่วนติดต่อผู้ใช้ (`ui/`)
- **Dynamic Island (`ui/dynamic_island.py` — v1.9.2 True Native NSStatusItem & Always-On-Top Expanded Island):**
  - **Coordinated Dual-Layer Architecture:**
    1. **True Native macOS `NSStatusItem` (Menu Bar Embedding):** ใช้ `AppKit.NSStatusBar.systemStatusBar().statusItemWithLength_(88.0)` ฝังตัวในฐานะพลเมืองชั้นหนึ่งของ Menu Bar บนทุกหน้าจอและทุก Space ขยับหลบไอคอนไมโครโฟนสีส้มและไอคอนระบบอัตโนมัติ 100% ไม่มีวันซ้อนทับกัน แสดงผล **Chill Pixel Life** (14x16 พิกเซลอวตาร 7 สี พร้อม 13 กิจกรรม เช่น เดิน, วิ่งสปีด, แอบส่อง, กิน, นอนหลับ, ทำงานพิมพ์คีย์บอร์ด, ค้นคว้าข้อมูล, อ่านหนังสือ) พร้อมพื้นหลังสีเข้มทึบสไตล์ Cyber Glass (`QColor(10, 16, 29, 238)`) และกราฟคลื่นเสียง **4-Bar Pill Waveform** + จุดไฟสถานะไมค์กระพริบ
    2. **Always-On-Top Expanded Pop-out Window (`360x70` px):** เมื่อมีสถานะตอบโต้ (`speaking`, `listening`, `thinking`, `running_tool`, `wake_ack`, `confused`) หรือเมื่อคลิกเมาส์ซ้ายที่ `NSStatusItem` หน้าต่างจะเด้งสปริง Pop-out (OutBack 320ms) ออกมาใต้ตัว `NSStatusItem` พอดี โดยตั้งค่า `NSPopUpMenuWindowLevel`, `setHidesOnDeactivate_(False)`, และ `BypassWindowManagerHint` ทำให้ไม่หายเมื่อสลับแอป พับจอ หรือเปิดโหมด Capture ภาพ (`Cmd+Shift+4`/`5`) แสดงหุ่นยนต์เวกเตอร์ **Cyber Mini-Robot Avatar (60 FPS)** เต็มตัว พร้อมข้อความสถานะ และ 4 ปุ่มสั่งงานด่วน: `🎙️ Voice` (Cmd+Shift+J), `💬 Chat` (Alt+Space), `⚡ Wake: ON/OFF`, และ `⚙️ More`
    3. **Idle Hidden Window:** เมื่ออยู่ในโหมด Standby/Idle หน้าต่างลอยจะถูกสั่ง `self.hide()` 100% เพื่อประหยัดทรัพยากรการวาด โดยเหลือเฉพาะ Native `NSStatusItem` บนแถบ Menu Bar
  - **Multi-Screen Synchronization (`DynamicIslandManager`):** รองรับการแสดงผล Dynamic Island บนทุกหน้าจอที่เชื่อมต่อ (เช่น จอ Built-in ของ MacBook ร่วมกับจอแยก External HDMI/USB-C) สตรีมสถานะและแอนิเมชันพร้อมเพรียงกัน และรองรับ Hotplug หน้าจออัตโนมัติ (`screenAdded` / `screenRemoved`)
  - **Unified Single Interface (Zero Redundant Tray):** ยุบรวมไอคอน System Tray แบบเดิมเข้ามาไว้ภายใน `NSStatusItem` 100% พร้อมคลิกขวาเปิด Cyber Context Menu ใต้ตัว Status Item (สลับเปิดแชท, เปิด/ปิดไมค์, สลับคำปลุก Wake Word, ยุบ/ขยายเกาะ, ล้างประวัติ, ออกจากโปรแกรม)
  - **Pure Vector & Pixel Art Graphics (`QPainter` 100%):** วาดโครงสร้างเวกเตอร์และสไปรต์พิกเซลทั้งหมดด้วยโค้ด Python/QPainter ปราศจากไฟล์รูปภาพภายนอก รองรับจอภาพ Retina Display คมชัด 100%
  - **Autonomous Quirks & Chill Pacing:** ระบบสุ่มท่าทางและกิจกรรมว่างของหุ่นยนต์ (เดินไป-มาด้วยความเร็วชิลล์ 5.5 px/s ความถี่ 3.5 Hz แอบส่องขอบเส้นแบ่ง ยืนบิดขี้เกียจ งีบหลับ) พร้อมระบบพับเก็บอัตโนมัติ (Auto-fold) หลังไม่มีการใช้งาน 12 วินาที
- **Overlay Chat (`ui/overlay_chat.py`):** หน้าต่างลอยสไตล์ Spotlight แยกแท็บสนทนาและข้อมูลดิบ

### 3.14 หน่วยความจำถาวรและแก่นความคิด (`memory/`)
- `soul_core.md`: แก่นแท้บุคลิกภาพและความคิด (L0 Context)
- `jarvis_memory.json`: ข้อมูลความจำระยะยาวของผู้ใช้ (L1 User Facts)
- `events.jsonl`: บันทึกบทเรียนและบริบทสำคัญ (L2 Lessons Context)
- `chat_history.json`: ประวัติการสนทนา 10 รอบล่าสุด (L3 Active Context)
- `cached_ok_krub.mp3`: แคชไฟล์เสียงตอบรับ "Ok ครับ" ความเร็วสูง

---

## 4. แผนภาพลำดับการไหลของข้อมูล (System Data Flow)

```text
[ผู้ใช้เรียกใช้งานผ่าน 3 ช่องทาง]
  ├── ช่องทาง 1: กดปุ่มลัด Cmd+Shift+J (Quartz Event Tap ดูดกลืนคีย์)
  ├── ช่องทาง 2: พูดคำปลุก "Hey Jarvis" (OpenWakeWord + wake_mic_gain 2.5x)
  └── ช่องทาง 3: กดปุ่ม Esc (Direct Barge-in) เพื่อตัดเสียงพูดและสั่งงานใหม่ทันที
         │
         ▼
 [JarvisListener Single-Pipeline (voice/listener.py)]
         │
         ├── [สถานะ STANDBY_WAKE]:
         │      • ขยายสัญญาณเสียงไมค์ 2.5x (wake_mic_gain) ป้อนเข้า OpenWakeWord
         │      • เมื่อคะแนน 'hey_jarvis' >= 0.36 ➔ เล่นเสียง Ack ➔ เข้าสู่ ACTIVE_PTT
         │
         ├── [สถานะ SPEAKING_MONITOR (ขณะ Jarvis กำลังพูด)]:
         │      • Drain Audio Queue ไม่ส่งเสียงขึ้น Groq STT และไม่รันโมเดลปลุก (Zero Overhead)
         │      • กดปุ่ม Esc (Keycode 53) ➔ stop_speaking() ➔ play_cached_ack() ➔ ACTIVE_PTT ทันที
         │
         └── [สถานะ ACTIVE_PTT]:
                • Silero VAD ตรวจจับเสียงมนุษย์แท้จริง ตัดส่งเมื่อหยุดพูดครบ 3.0s
                • เล่นเสียง Pop.aiff ➔ เปลี่ยนสถานะเป็น "Thinking..."
                      │
                      ▼
              [Speech-to-Text Pipeline (voice/listener.py)]
                      │
                      ├──> Primary: Groq Cloud STT (whisper-large-v3-turbo) ──> ~0.2s, CPU 0%
                      └──> Fallback: Local Faster-Whisper (small, int8)
                                │
                                ▼
              [Pre-Brain Fast Noise Filter & Exit Guard]
                      │
                      ├──> ผู้ใช้บอกลา/ปิดไมค์ ("ขอบคุณครับ", "พอแค่นี้", "พักก่อน")
                      │         │
                      │         ▼
                      │    [ตั้งค่า suppress_next_followup = True ➔ ตอบรับสั้นๆ ➔ กลับสู่ Standby]
                      │
                      └──> ข้อความคำสั่งปกติ ──> (emit user_message_received)
                                │
                                ▼
              [JarvisBrain (core/brain.py)]
                      │
                      ├──> ประกอบบริบท 4 ระดับ (L0: Soul Core, L1: Facts, L2: Events, L3: History)
                      ├──> ส่งคำสั่งเข้า Gemini API (Explicit Fallback Chain)
                      │
                      ├──> Gemini ร้องขอ Function Call (Tools / MCP)
                      │         │
                      │         ├── [Native Tools (core/tools.py)]
                      │         │     • click_on_screen / type_text_on_screen / click_and_type (GUI)
                      │         │     • delegate_to_antigravity (.jarvis_task.md + Watchdog)
                      │         │     • reveal_task_result / search_raw_history / analyze_current_screen
                      │         │
                      │         └── [Official MCP Tools (core/mcp_manager.py)]
                      │               • กรองอาร์กิวเมนต์ว่าง ("" / None) ก่อนส่งเข้า Server
                      │               • Filesystem (16 tools), Fetch (1 tool), Git (14 tools)
                      │
                      └──> ผลิตผลลัพธ์คำตอบสุดท้าย
                                │
                                ├──> (emit assistant_reply_ready) ──> [OverlayChat 💬 Conversation Tab]
                                └──> (emit assistant_speak_ready) ──> [JarvisSpeaker (voice/speaker.py)]
                                          │
                                          ├──> เก็บข้อความลง self.current_spoken_text
                                          ├──> ปรับจังหวะคำอ่านด้วย core/thai_nlp.py
                                          ├──> สังเคราะห์เสียงผ่าน Edge-TTS และเล่นผ่าน /usr/bin/afplay
                                          │
                                          └──> [เมื่อพูดจบสนิท (และไม่โดนระงับ)]:
                                                 เปิด Continuous Follow-up Loop ต่อเนื่อง 60s
```

---

## 5. ตารางคีย์ลัดและสิทธิ์ของระบบ macOS (Keybindings & Permissions)

### ⌨️ ตารางคีย์ลัดหลัก (Global Shortcuts)
| ปุ่มลัด | เงื่อนไข / สถานะ | การตอบสนองของระบบ |
|---|---|---|
| **`Cmd + Shift + J`** | ทุกสถานะ | สลับเปิด/ปิดการบันทึกเสียง (1-Tap Toggle Voice) |
| **`Alt + Space`** | ทุกสถานะ | แสดงหรือซ่อนหน้าต่างแชทสไตล์ Spotlight (Overlay Chat) |
| **`Escape`** *(Esc)* | **ขณะ Jarvis กำลังพูด** | ตัดเสียงทันที (Barge-in Stop) $\rightarrow$ เล่นเสียง "Ok ครับ" $\rightarrow$ เปิดไมค์ฟังคำสั่งใหม่ |
| **`Escape`** *(Esc)* | ขณะหน้าต่าง Overlay Chat เปิดอยู่ | ปิดซ่อนหน้าต่างแชทลง |
| **`Escape`** *(Esc)* | นอกเหนือจากเงื่อนไขข้างต้น | ปล่อยผ่านไปให้ระบบปฏิบัติการ macOS ใช้งานตามปกติ |

### 🔒 สิทธิ์ระบบปฏิบัติการที่จำเป็น (macOS Permissions)
1. **Accessibility (การช่วยการเข้าถึง):** จำเป็นสำหรับ Quartz Event Tap ในการดักจับคีย์ลัดระดับระบบ
2. **Microphone (ไมโครโฟน):** จำเป็นสำหรับ Single-Pipeline InputStream ในการรับเสียงพูด
3. **Screen Recording (การบันทึกหน้าจอ):** จำเป็นสำหรับคำสั่ง `screencapture -x` เพื่อวิเคราะห์ภาพหน้าจอด้วย Vision

---

## 6. ระบบทดสอบอัตโนมัติ (Automated Backtest Suite 31/31 PASS)

ระบบมีชุดทดสอบอัตโนมัติแบบ **Offline-first, Zero-Hardware & Zero-Side-Effect** ครอบคลุม **31 เคสทดสอบ** ใน 4 หมวดหมู่หลักในไฟล์ `tests/run_backtest.py`:

```bash
# รันการทดสอบครบทุกโมดูล
python3 tests/run_backtest.py
```

### รายละเอียด 4 ชุดทดสอบ (Test Suites):
1. **Suite 1: Thai NLP & Matching Engine (`core/thai_nlp.py`) — 5/5 PASS:**
   - ตรวจสอบ `prepare_thai_tts_text` แปลงเงินบาทเป็นคำอ่าน แต่คงรหัสเวอร์ชัน, หมายเลขพอร์ต, และ IP Address
   - ตรวจสอบ `fuzzy_match_phrase` สำหรับการดักคำปิดสนทนา (สแลงเพี้ยน vs ประโยคทั่วไป)
   - ตรวจสอบ `resolve_macos_app_name` แมตช์ชื่อแอปผ่าน Aliases, Thai Soundex (`lk82`), และ RapidFuzz
   - ตรวจสอบ `tokenize_for_search` และ `match_search_terms`
2. **Suite 2: Voice Engine & State Transitions (`voice/listener.py` & `voice/speaker.py`) — 12/12 PASS:**
   - ตรวจสอบ Standby Silence และ OpenWakeWord int16 PCM 1280-sample Accumulation
   - ตรวจสอบตัวขยายสัญญาณไมค์ **`wake_mic_gain: 2.5x`** ก่อนป้อนเข้าโมเดล
   - ตรวจสอบการตัดจบลูปด้วยคำปิดสนทนา พร้อมตั้งแฟล็ก `suppress_next_followup` ระงับการเด้ง Followup ซ้ำ
   - ตรวจสอบ **Zero-Overhead Speaking Monitor:** เมื่อผู้ช่วยกำลังพูด จะไม่มีการส่งเสียงเข้า STT หรือรันโมเดลปลุกซ้อน (Zero API & CPU overhead)
   - ตรวจสอบการทำงานของปุ่ม **`Esc` (Direct Barge-in)**: ตัดเสียงพูดทันที (`stop_speaking`), เล่นเสียงยืนยัน `"Ok ครับ"` (`play_cached_ack`), และเข้าสู่ `ACTIVE_PTT`
   - ตรวจสอบการบล็อก Followup Loop เมื่อผู้ช่วยถูกสั่งเบรกด้วย Barge-in
3. **Suite 3: Brain Tiered Context & OS Subprocess Sandbox (`core/brain.py` & `core/tools.py`) — 6/6 PASS:**
   - ตรวจสอบการแยกแท็ก `[SPEAK]` และ Fallback กรองโค้ดบล็อก
   - ตรวจสอบการประกอบ Tiered Context (`L0`, `L1`, `L2`) บนโฟลเดอร์จำลองโดยไม่แตะต้องไฟล์หน่วยความจำจริง
   - ตรวจสอบการเรียกคำสั่งระบบ (`open -a`, `osascript`, `screencapture`) ผ่าน Mock 100% ไม่เปิดหน้าต่างหรือแคปหน้าจอจริง
   - ตรวจสอบ `AntigravityBridge` ปราศจากคำสั่ง `osascript` 100% และเขียนไฟล์แบบ Atomic Write
   - ตรวจสอบ `Deduplication Guard` บล็อกคำสั่งงานซ้ำซ้อนภายใน Cooldown 60 วินาที
4. **Suite 4: System Integrity, GUI & Config Validation — 11/11 PASS:**
   - ทดสอบความเร็ว Cold Import ไม่บล็อกการบูตโปรแกรม ($< 0.3$s)
   - ตรวจสอบตัวกรอง Empty Arguments (`""` / `None`) ใน `MCPManager.call_tool`
   - ตรวจสอบความถูกต้องของสกีมา `voice_settings.json` และ `mcp_servers.json`
   - ตรวจสอบ **Dynamic Island Adaptive Edge Detection:** ตรวจจับแถบ Menu Bar ด้านบน และคำนวณตำแหน่งจอดเกาะ Dock บนหน้าจออย่างถูกต้อง
   - ตรวจสอบ **Dynamic Island State Geometry Transitions:** ตรวจสอบการสลับขนาด Folded ($68 \times 24$ px) ในโหมด `idle` และ Expanded ($360 \times 70$ px) ในสถานะทำงาน รวมถึงการคลิกเปิด/พับแบบแมนนวล
   - ตรวจสอบ **Dynamic Island Multi-Screen & Mode Selection:** ตรวจสอบ `DynamicIslandManager` สร้างอ็อบเจกต์สำหรับทุกหน้าจอ พร้อมปุ่มเลือกโหมด 4 ปุ่ม (`Voice`, `Chat`, `Wake`, `Menu`) และการตรวจจับตำแหน่งคลิกแม่นยำ
   - ตรวจสอบ **Dynamic Island Pure Vector Paint Zero-Crash:** ทดสอบการเรนเดอร์หุ่นยนต์อวตารเวกเตอร์ `QPainter` ครบทั้ง 7 สถานะ และ 5 ท่าทางพิเศษ (Quirks) โดยไม่มี Exception และปลอดการกระตุกจาก Font Aliases
   - ตรวจสอบ **Chill Pixel Life Engine & Standby Render:** ตรวจสอบการจำลองชีวิตพิกเซล 13 กิจกรรม และการเรนเดอร์เฟรมสแตนบาย Retina $88 \times 22$ pt ($176 \times 44$ px)
   - ตรวจสอบ **v1.9.2 Native NSStatusItem & Always-On-Top:** ตรวจสอบการฝัง `NSStatusItem` เมนูบาร์ของแท้, พื้นหลังทึบคมชัด Cyber Glass ($\alpha \ge 235$), และการปิด `Qt.Tool` เพื่อไม่ให้หน้าต่างหายขณะแคปหน้าจอ
   - ตรวจสอบ **v1.9.3 Standard Mode, Speech Bubble & Single-Screen Pop-out:**
     - ตรวจสอบการบูตใน **Standard Mode (`WAKE_TRIGGER_ENABLED = False`)** พร้อมระบบ **On-Demand Microphone Stream Lifecycle** ปล่อยฮาร์ดแวร์ไมค์ 100% ในช่วงสแตนบาย ไม่มีไอคอนไมค์สีส้มของ macOS มารบกวนสายตา
     - ตรวจสอบกล่องคำพูดเวกเตอร์ **Robot Speech Bubble** (`_show_robot_bubble`) พร้อมหน่วงเวลา `_auto_fold_timer` อัตโนมัติ
     - ตรวจสอบ **Single-Screen Dynamic Island Pop-out** (`expand_active`) เด้งเปิดเฉพาะจอที่ Active ตามตำแหน่งเมาส์ จออื่นพับเรียบร้อย
     - ตรวจสอบ **Two-Factor Wake Gate:** กรองเสียงเคาะแป้นพิมพ์ด้วยเกณฑ์ 2 เฟรมต่อเนื่อง ($\ge 160$ms) ร่วมกับ Silero VAD ตรวจสอบเสียงมนุษย์ย้อนหลัง 0.8s (`wake_mic_gain: 1.6`, `wake_score_threshold: 0.48`)
