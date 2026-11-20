# เอกสารโครงสร้างสถาปัตยกรรมระบบ J.A.R.V.I.S. Desktop Assistant 🚀
*(J.A.R.V.I.S. Architecture & Technical Reference Manual)*

เอกสารฉบับนี้สรุปภาพรวม สถาปัตยกรรม โครงสร้างไฟล์ ลำดับการทำงานของข้อมูล (Data Flow) และรายละเอียดเชิงลึกของทุกโมดูลในระบบ **Jarvis Desktop Assistant** ซึ่งพัฒนาขึ้นเพื่อทำงานบน **macOS (Apple Silicon & Intel)** โดยเฉพาะ

---

## 📑 สารบัญ
1. [ภาพรวมของระบบ (System Overview)](#1-ภาพรวมของระบบ-system-overview)
2. [แผนผังโครงสร้างไฟล์ทั้งหมด (Full Directory Tree)](#2-แผนผังโครงสร้างไฟล์ทั้งหมด-full-directory-tree)
3. [รายละเอียดเชิงลึกของแต่ละโมดูล (Module Deep Dive)](#3-รายละเอียดเชิงลึกของแต่ละโมดูล-module-deep-dive)
   - [3.1 Entry Point & Lifecycle (`main.py`)](#31-entry-point--lifecycle-mainpy)
   - [3.2 การกำหนดค่าระบบ (`config.py`, `.env`)](#32-การกำหนดค่าระบบ-configpy-env)
   - [3.3 ตัวกลางสื่อสารข้ามเธรด (`core/event_bus.py`)](#33-ตัวกลางสื่อสารข้ามเธรด-coreevent_buspy)
   - [3.4 สมองหลักและการประมวลผล AI (`core/brain.py`)](#34-สมองหลักและการประมวลผล-ai-corebrainpy)
   - [3.5 เครื่องมือระบบ macOS พื้นฐาน (`core/tools.py`)](#35-เครื่องมือระบบ-macos-พื้นฐาน-coretoolspy)
   - [3.6 ระบบจัดการ MCP มาตรฐานสากล (`core/mcp_manager.py`)](#36-ระบบจัดการ-mcp-มาตรฐานสากล-coremcp_managerpy)
   - [3.7 ระบบเชื่อมต่อ Antigravity IDE (`integrations/antigravity_bridge.py`)](#37-ระบบเชื่อมต่อ-antigravity-ide-integrationsantigravity_bridgepy)
   - [3.8 ระบบรับเสียงพูดอัจฉริยะ (`voice/listener.py`)](#38-ระบบรับเสียงพูดอัจฉริยะ-voicelistenerpy)
   - [3.9 ระบบสังเคราะห์เสียงพูด 2 ภาษา (`voice/speaker.py`)](#39-ระบบสังเคราะห์เสียงพูด-2-ภาษา-voicespeakerpy)
   - [3.10 ส่วนติดต่อผู้ใช้ (`ui/`)](#310-ส่วนติดต่อผู้ใช้-ui)
   - [3.11 หน่วยความจำถาวร (`memory/`)](#311-หน่วยความจำถาวร-memory)
4. [แผนภาพลำดับการไหลของข้อมูล (System Data Flow)](#4-แผนภาพลำดับการไหลของข้อมูล-system-data-flow)
5. [ตารางคีย์ลัดและสิทธิ์ของระบบ macOS (Keybindings & Permissions)](#5-ตารางคีย์ลัดและสิทธิ์ของระบบ-macos-keybindings--permissions)

---

## 1. ภาพรวมของระบบ (System Overview)

Jarvis Desktop Assistant ได้รับการออกแบบภายใต้สถาปัตยกรรม **Decoupled Event-Driven Architecture** โดยใช้ **PySide6 (Qt for Python)** เป็นแกนกลางในการจัดการ User Interface และ Event Loop มีจุดเด่นสำคัญดังนี้:

- **AI Engine:** ขับเคลื่อนด้วย **Google GenAI SDK (`google-genai`)** ใช้โมเดลหลัก `gemini-3.5-flash-lite` (ความเร็วตอบสนอง ~1.2 วินาที พร้อมโควต้า Free Tier 500 RPD / 15 RPM) เสริมด้วย **Explicit Fallback Chain** สลับโมเดลสำรองอัตโนมัติหากติด 429/503/504
- **Hybrid Tool Architecture:** ผสมผสานระหว่าง **Native macOS Tools** (ควบคุมระบบ Mac, ดูหน้าจอด้วย Vision, ส่งงาน Antigravity, จดจำข้อมูล) และ **Official Model Context Protocol (MCP) Servers** (Filesystem, Web Fetch และ Git มาตรฐานสากล) รวม 35 เครื่องมือ พร้อมใช้งานทันทีโดยไม่ต้องโหลดใหม่ในแต่ละรอบสนทนา
- **Instant Boot Caching:** มีระบบ **Schema Disk Cache** โหลดสเปกเครื่องมือทั้ง 17+ ตัวในเวลาเพียง **0.0017 วินาที** พร้อมระบบตรวจจับการอัปเดตอัตโนมัติด้วย SHA-256
- **System-level Global Interception:** ใช้ **Quartz `CGEventTapCreate`** ดักจับคีย์ลัดระดับลึกจากทุกหน้าต่างและดูดกลืนคีย์ (Event Swallowing) ไม่ให้ไปรบกวนแอปอื่น
- **Persistent Mic Session:** สแตนด์บายไมโครโฟนตลอดเวลา ใช้ **CPU 0% ในขณะ Idle** ไม่หน่วงตอนเริ่มอัด และสิทธิ์ไมค์ไม่หลุด

---

## 2. แผนผังโครงสร้างไฟล์ทั้งหมด (Full Directory Tree)

```text
/Volumes/WorkDrive/Javis Project/
├── .env                                # ไฟล์ตั้งค่าส่วนตัว (API Keys, โมเดล, เสียง, คีย์ลัด)
├── .env.example                        # เทมเพลตตัวอย่างค่าคอนฟิกสำหรับแจกจ่าย
├── requirements.txt                    # รายการไลบรารี Dependencies ทั้งหมดของ Python
├── mcp_servers.json                    # คอนฟิกการรัน Official MCP Servers (filesystem, fetch, git)
├── config.py                           # ตัวแปรคงที่ระดับ Global และการโหลด Environment
├── main.py                             # Entry Point หลัก: Cocoa Loop, Quartz Tap, Lifecycle
├── README.md                           # เอกสารแนะนำการติดตั้งและคู่มือผู้ใช้งาน
├── PROJECT_ARCHITECTURE.md             # [ไฟล์นี้] สรุปสถาปัตยกรรมโครงสร้างโปรเจกต์โดยละเอียด
├── Project Directory Structure.txt     # ผังโครงสร้างแบบย่อ
│
├── core/                               # แกนกลางระบบ (Logic, Brain, Tools, MCP, Signals)
│   ├── __init__.py
│   ├── event_bus.py                    # ตัวกลางส่งสัญญาณ PySide6 Signals (Thread-safe)
│   ├── brain.py                        # สมอง AI: Fallback Chain, Persistent History, GenAI Client
│   ├── tools.py                        # Native macOS Tools (Screen Vision, Antigravity, System Control)
│   └── mcp_manager.py                  # ตัวจัดการ Official MCP Servers และ Schema Disk Cache
│
├── integrations/                       # การเชื่อมต่อภายนอก
│   ├── __init__.py
│   └── antigravity_bridge.py           # ตัวเชื่อม Antigravity IDE (AppleScript + Watchdog Observer)
│
├── voice/                              # ระบบเสียงพูดและการได้ยิน
│   ├── __init__.py
│   ├── listener.py                     # 1-Tap Toggle Voice, Persistent Mic, Faster-Whisper STT
│   └── speaker.py                      # สังเคราะห์เสียงพูด Dual-Tone J.A.R.V.I.S. (Edge-TTS + afplay)
│
├── ui/                                 # ส่วนติดต่อผู้ใช้ (PySide6 Graphical Interface)
│   ├── __init__.py
│   ├── dynamic_island.py               # หน้าต่างแคปซูลลอยตัวด้านบนหน้าจอ (สถานะระบบ)
│   ├── overlay_chat.py                 # หน้าต่าง Overlay Chat สไตล์ Spotlight/Raycast
│   └── tray.py                         # ไอคอนบน Menu Bar (macOS Status Item) พร้อมเมนู
│
└── memory/                             # โฟลเดอร์เก็บข้อมูลถาวรข้ามเซสชัน
    ├── chat_history.json               # ประวัติการสนทนา 10 รอบล่าสุด (Persistent Context)
    ├── jarvis_memory.json              # ความจำระยะยาวของผู้ใช้ (Persistent Facts)
    └── mcp_tools_cache.json            # แคชสเปกเครื่องมือ MCP ถาวร (Instant Boot 0.001s)
```

---

## 3. รายละเอียดเชิงลึกของแต่ละโมดูล (Module Deep Dive)

### 3.1 Entry Point & Lifecycle (`main.py`)
ทำหน้าที่เป็นศูนย์รวมการบูตโปรแกรมและจัดการวงจรชีวิต (Lifecycle):
1. **Accessibility Verification:** ตรวจสอบสิทธิ์การควบคุมระบบผ่าน `AXIsProcessTrustedWithOptions` หากยังไม่ได้รับสิทธิ์จะเด้งหน้า System Settings ให้อัตโนมัติ
2. **MCP Boot:** สั่งให้ `mcp_manager.start()` ทำงานเพื่ออ่านแคชและเชื่อมต่อ Stdio Subprocess
3. **Component Initialization:** สร้างอ็อบเจกต์ `JarvisBrain`, `AntigravityBridge`, `JarvisSpeaker`, `JarvisListener`, `DynamicIsland`, `OverlayChat`, และ `JarvisTrayIcon`
4. **Quartz System EventTap:** เริ่มต้นเธรดดักจับคีย์ลัดระดับระบบ (`CGEventTapCreate`) สำหรับปุ่ม **`Cmd + Shift + J`** และ **`Alt + Space`**
5. **Graceful Teardown:** เมื่อปิดแอปพลิเคชัน จะสั่งปิดเธรดเสียง, สตรีมไมโครโฟน, ตัวเฝ้าไฟล์ และปิด MCP Sessions ทั้งหมดอย่างสะอาด

### 3.2 การกำหนดค่าระบบ (`config.py`, `.env`)
ทำหน้าที่รวมศูนย์การอ่านค่า Environment Variables:
- `GEMINI_MODEL`: ตั้งค่าเริ่มต้นเป็น `gemini-3.5-flash-lite`
- `VOICE_TOGGLE_HOTKEY`: ปุ่มลัดบันทึกเสียง `<cmd>+<shift>+j`
- `VOICE_RECORD_TIMEOUT`: ระยะเวลาปิดรับฟังเสียงอัตโนมัติ (จำกัดช่วง 10–25 วินาที, ค่าเริ่มต้น 15s)
- `VOICE_COOLDOWN_SECONDS`: ระยะเวลาคูลดาวน์ป้องกันการกดเบิ้ล (ค่าเริ่มต้น 1.5s)
- `TTS_VOICE_TH` / `TTS_VOICE_EN`: โทนเสียง J.A.R.V.I.S. ภาษาไทย (`th-TH-NiwatNeural`, -14Hz, +14%, +40%) และอังกฤษ (`en-GB-RyanNeural`, -8Hz, +8%, +40%)

### 3.3 ตัวกลางสื่อสารข้ามเธรด (`core/event_bus.py`)
เป็น Singleton Class สืบทอดจาก `PySide6.QtCore.QObject` ช่วยให้การส่งข้อมูลระหว่าง Background Threads (Voice STT, AI Inference, File Watcher) เข้าสู่ Main UI Loop เป็นไปอย่างปลอดภัย (Thread-Safe):
- `state_changed(str)`: แจ้งเปลี่ยนสถานะ (`idle`, `listening`, `thinking`, `running_tool`, `speaking`)
- `user_message_received(str)`: ส่งข้อความที่ได้จากเสียงพูดหรือช่องแชทเข้าสู่สมอง AI
- `assistant_reply_ready(str)`: ส่งคำตอบสุดท้ายของ Jarvis ไปยังโมดูลเสียงพูดและหน้าต่างแชท
- `task_log_updated(str, str)`: ส่งบันทึกการทำงานของ Tool หรือข้อผิดพลาดไปแสดงผล
- `toggle_overlay_signal()`, `toggle_voice_record_signal()`: สัญญาณสลับหน้าต่างและสลับไมค์

### 3.4 สมองหลักและการประมวลผล AI (`core/brain.py`)
- **Static Tool Registry:** รวมฟังก์ชัน Native Tools และ Dynamic MCP Tools เข้าด้วยกันใน `GenerateContentConfig` เพียงครั้งเดียวตอนเริ่มต้นโปรแกรม ไม่มีการโหลดหรือสร้าง Schema ซ้ำ
- **Explicit Fallback Chain:** ลำดับโมเดลสำรองแบบกำหนดชัดเจน:
  `["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.6-flash", "gemini-3.8-flash"]`
  รองรับการสลับโมเดลอัตโนมัติเมื่อพบ Error 429 (Quota), 503 (Overloaded), 504 (Timeout), หรือ 404
- **ThinkingConfig Handling:** ตั้งค่า `thinking_budget=0` เฉพาะโมเดลที่รองรับ (ยกเว้นตระกูล Lite เพื่อป้องกันข้อผิดพลาด 400)
- **Persistent Chat History:** โหลดประวัติ 10 รอบล่าสุดจาก `memory/chat_history.json` ตอนเปิดโปรแกรม และบันทึกประวัติแบบ Asynchronous หลังจบแต่ละรอบ

### 3.5 เครื่องมือระบบ macOS พื้นฐาน (`core/tools.py`)
ประกอบด้วย 4 เครื่องมือหลักที่เขียนด้วย Native Python และคำสั่งของ macOS:
1. `delegate_to_antigravity(task_prompt)`: ส่งคำสั่งเขียนโค้ดเข้า Antigravity IDE ผ่าน AppleScript
2. `analyze_current_screen(question)`: ถ่ายภาพหน้าจอด้วย `screencapture -x /tmp/jarvis_screen.jpg` ส่งให้ Gemini Vision วิเคราะห์ และลบไฟล์ทิ้งทันที
3. `control_mac_system(action, target)`: ควบคุมระบบ macOS (`open_app`, `open_url`, `set_volume`, `get_system_info`)
4. `manage_memory(mode, content)`: บันทึกและดึงข้อมูลความจำระยะยาวใน `memory/jarvis_memory.json`

### 3.6 ระบบจัดการ MCP มาตรฐานสากล (`core/mcp_manager.py`)
- **Official Servers:** รันและสื่อสารผ่าน Stdio Client กับ:
  - `@modelcontextprotocol/server-filesystem`: จัดการไฟล์ อ่าน เขียน ลิสต์ และค้นหาไฟล์ในโปรเจกต์ (16 เครื่องมือ)
  - `mcp-server-fetch`: ดึงข้อมูลจาก URL และแปลงเป็น Markdown (1 เครื่องมือ)
  - `mcp-server-git`: ตรวจสอบสถานะโค้ด (`git_status`), ประวัติ Commit (`git_log`), ดู Diff ทั้ง staged/unstaged (`git_diff`), สลับ Branch (`git_checkout`), สร้าง Commit และตรวจตรา Git Repository (14 เครื่องมือ)
  - **สรุปเครื่องมือในระบบ:** MCP Tools รวม 31 เครื่องมือ + Native macOS Tools 4 เครื่องมือ = รวมทั้งสิ้น **35 เครื่องมือ**
- **Persistent Schema Disk Cache:** บันทึกโครงสร้างเครื่องมือไว้ใน `memory/mcp_tools_cache.json` ทำให้เปิดโปรแกรมครั้งถัดไปได้ในเวลาเพียง **0.005 วินาที** โดยไม่ต้องรอ Subprocess เริ่มทำงาน
- **SHA-256 Invalidation:** ตรวจสอบความถูกต้องของคอนฟิก หากไฟล์ `mcp_servers.json` มีการแก้ไข ระบบจะอัปเดตแคชใหม่ให้อัตโนมัติ

### 3.7 ระบบเชื่อมต่อ Antigravity IDE (`integrations/antigravity_bridge.py`)
- ใช้ **AppleScript (`osascript`)** และ **`pbcopy`** ในการสลับโฟกัสไปยังหน้าต่าง Antigravity IDE และส่งคีย์ลัด `Cmd + L` (เปิดแชท) ➔ `Cmd + V` (วาง Prompt) ➔ `Enter` (ส่งคำสั่ง)
- ใช้ **`watchdog.observers.Observer`** เฝ้าดูการสร้างไฟล์ `.jarvis_result.md` เมื่อ Agent ทำงานเสร็จ จะส่งเนื้อหากลับมาให้ Jarvis สรุปผลด้วยเสียงทันที

### 3.8 ระบบรับเสียงพูดอัจฉริยะ (`voice/listener.py`)
- **1-Tap Toggle Mode:** กด `Cmd + Shift + J` ครั้งแรกเพื่อเริ่มอัด (เล่นเสียง *Tink*) และกดอีกครั้งเพื่อส่ง (เล่นเสียง *Pop*)
- **Persistent Mic Session:** เปิดสตรีม `sounddevice.InputStream` ค้างไว้ตลอดเวลา โดยในขณะไม่ได้อัดเสียงฟังก์ชัน Callback จะคืนค่าทันที ทำให้ใช้ **CPU 0%** และลดอาการหน่วงตอนเริ่มอัดเสียง
- **Auto-close Timeout & Cooldown:** หากพูดไม่หยุด ระบบจะตัดส่งคำสั่งให้อัตโนมัติเมื่อครบ 15 วินาที (ปรับได้ 10–25s) พร้อม Micro-Debounce (0.6s) และ Post-Session Cooldown (1.5s) ป้องกันการกดทับซ้ำ
- **Faster-Whisper:** โหลดโมเดลขนาด `small` บน CPU (`compute_type="int8"`) ทำงานใน Background Worker ถอดความได้รวดเร็วและแม่นยำ

### 3.9 ระบบสังเคราะห์เสียงพูด 2 ภาษา (`voice/speaker.py`)
- ตรวจจับภาษาอัตโนมัติจากชุดตัวอักษรไทย (Unicode Range `\u0E00-\u0E7F`)
- สลับโทนเสียงระหว่างภาษาไทย (`th-TH-NiwatNeural`) และภาษาอังกฤษ (`en-GB-RyanNeural`) โดยอัตโนมัติ
- ล้างสัญลักษณ์ Markdown (ดอกจัน, สัญลักษณ์หัวข้อ, Code fences) ออกจากข้อความก่อนพูด
- ส่งเสียงผ่านเครื่องเล่นระบบของ macOS (`/usr/bin/afplay`) โดยตรงเพื่อความเสถียรและเสียงคมชัดสูงสุด

### 3.10 ส่วนติดต่อผู้ใช้ (`ui/`)
- **Dynamic Island (`ui/dynamic_island.py`):** แคปซูลโปร่งแสงลอยอยู่กึ่งกลางด้านบนของหน้าจอ (Always-on-top, กว้าง 300px) แสดงสถานะและจุดสีแอนิเมชันตามสถานะปัจจุบัน และซ่อนตัวอัตโนมัติเมื่อเข้าสู่สถานะ `Idle`
- **Overlay Chat (`ui/overlay_chat.py`):** หน้าต่างลอยสไตล์ Spotlight / Raycast สำหรับพิมพ์ข้อความ ดูประวัติการแชท และตรวจสอบ System / Tool Logs
- **System Tray (`ui/tray.py`):** ไอคอนวงแหวนสีฟ้าบน macOS Menu Bar พร้อม Context Menu สำหรับเปิดแชท, เปิดไมค์, ล้างประวัติ หรือออกจากโปรแกรม

### 3.11 หน่วยความจำถาวร (`memory/`)
- `memory/chat_history.json`: บันทึกประวัติการสนทนา 10 เทิร์นล่าสุด ทำให้เปิดโปรแกรมใหม่แล้วคุยต่อได้ทันที
- `memory/jarvis_memory.json`: บันทึกข้อมูลสำคัญที่ผู้ใช้สั่งให้จำ (เช่น ความชอบ, ข้อมูลส่วนตัว)
- `memory/mcp_tools_cache.json`: แคชโครงสร้างเครื่องมือ MCP ทั้งหมด เพื่อการบูตเครื่องใน 0.001 วินาที

---

## 4. แผนภาพลำดับการไหลของข้อมูล (System Data Flow)

```
[ผู้ใช้กด Cmd+Shift+J]
         │
         ▼
[Quartz CGEventTapCreate (System-level)] ──> [ดูดกลืนคีย์ (Swallow Event)]
         │
         ▼ (emit toggle_voice_record_signal)
[JarvisListener (voice/listener.py)]
         │
         ├──> ครั้งที่ 1: เล่นเสียง Tink.aiff ➔ เปลี่ยนสถานะ "Listening..." ➔ เริ่มเก็บเฟรมเสียงลง Buffer
         │
         └──> ครั้งที่ 2 (หรือครบ 15s): เล่นเสียง Pop.aiff ➔ เปลี่ยนสถานะ "Thinking..."
                     │
                     ▼
             [Faster-Whisper (STT)]
                     │
                     ▼ (emit user_message_received)
             [JarvisBrain (core/brain.py)]
                     │
                     ├──> ส่งประวัติและข้อความเข้า Gemini API (Explicit Fallback Chain)
                     │
                     ├──> Gemini ร้องขอ Function Call (Tools / MCP)
                     │         │
                     │         ├── [Native Tools (core/tools.py)]
                     │         │     • analyze_current_screen (screencapture + Vision)
                     │         │     • control_mac_system (open_app, volume, sysinfo)
                     │         │     • delegate_to_antigravity (AppleScript + Watchdog)
                     │         │     • manage_memory (jarvis_memory.json)
                     │         │
                     │         └── [Official MCP Tools (core/mcp_manager.py)]
                     │               • @modelcontextprotocol/server-filesystem (read, write, list)
                     │               • mcp-server-fetch (web fetcher)
                     │
                     └──> ส่งผลลัพธ์ Tool กลับสู่ Gemini จนได้คำตอบสรุปสุดท้าย
                               │
                               ├──> บันทึกประวัติลง memory/chat_history.json (Background)
                               │
                               ▼ (emit assistant_reply_ready)
                     [JarvisSpeaker (voice/speaker.py)]
                               │
                               ├──> ตรวจภาษา (TH/EN) ➔ ล้าง Markdown ดิบ
                               ├──> สังเคราะห์เสียงด้วย Edge-TTS (Dual Tone)
                               └──> ขับเสียงผ่าน macOS /usr/bin/afplay
                               │
                               ▼ (จบการทำงาน)
                     [Dynamic Island แสดงสถานะ Idle ➔ ซ่อนตัวอัตโนมัติ]
```

---

## 5. ตารางคีย์ลัดและสิทธิ์ของระบบ macOS (Keybindings & Permissions)

### ⌨️ ตารางคีย์ลัดหลัก (Global Shortcuts)
| ปุ่มลัด | หน้าที่การทำงาน | การตอบสนองของระบบ |
|---|---|---|
| **`Cmd + Shift + J`** | สลับเปิด/ปิดการฟังเสียง (1-Tap Toggle Voice) | ได้ยินเสียง *Tink* เมื่อเริ่มฟัง และ *Pop* เมื่อส่งคำสั่ง |
| **`Alt + Space`** *(Option+Space)* | เปิด/ปิดหน้าต่าง Overlay Chat | แสดงหรือซ่อนหน้าต่างแชทสไตล์ Spotlight |
| **`Escape`** *(Esc)* | ซ่อนหน้าต่าง Overlay Chat | ยุบหน้าต่างแชทลงเมื่อเปิดอยู่ |

### 🔒 สิทธิ์ระบบปฏิบัติการที่จำเป็น (macOS Permissions)
1. **Accessibility (การช่วยการเข้าถึง):**  
   - จำเป็นสำหรับ **Quartz Event Tap** เพื่อดักจับคีย์ลัดจากทุกแอป และการส่งคีย์ด้วย AppleScript ไปยัง Antigravity  
   - ตั้งค่าที่: `System Settings ➔ Privacy & Security ➔ Accessibility` (อนุญาต Terminal / Python)
2. **Microphone (ไมโครโฟน):**  
   - จำเป็นสำหรับโมดูล **`voice/listener.py`** ในการรับเสียงคำสั่งของผู้ใช้  
   - ตั้งค่าที่: `System Settings ➔ Privacy & Security ➔ Microphone` (อนุญาต Terminal / Python)
3. **Screen Recording (การบันทึกหน้าจอ):**  
   - จำเป็นสำหรับเครื่องมือ Native **`analyze_current_screen`** (`core/tools.py`) ที่เรียกใช้คำสั่งระบบ `screencapture -x` เพื่อจับภาพหน้าจอเดสก์ท็อปส่งให้ Gemini Vision ทำการวิเคราะห์ภาพหน้าต่างหรือข้อความบนจอ  
   - ตั้งค่าที่: `System Settings ➔ Privacy & Security ➔ Screen Recording` (อนุญาต Terminal / Python)
