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
   - [3.6 ระบบบันทึกผลงานเบื้องหลังและ On-Demand Reveal (`core/task_manager.py`)](#36-ระบบบันทึกผลงานเบื้องหลังและ-on-demand-reveal-coretask_managerpy)
   - [3.7 คลังจัดเก็บข้อมูลดิบระยะยาว 365+ วัน (`core/raw_archive.py`)](#37-คลังจัดเก็บข้อมูลดิบระยะยาว-365-วัน-coreraw_archivepy)
   - [3.8 ระบบจัดการ MCP มาตรฐานสากล (`core/mcp_manager.py`)](#38-ระบบจัดการ-mcp-มาตรฐานสากล-coremcp_managerpy)
   - [3.9 ระบบเชื่อมต่อ Antigravity IDE (`integrations/antigravity_bridge.py`)](#39-ระบบเชื่อมต่อ-antigravity-ide-integrationsantigravity_bridgepy)
   - [3.10 ระบบรับเสียงพูดอัจฉริยะ (`voice/listener.py`)](#310-ระบบรับเสียงพูดอัจฉริยะ-voicelistenerpy)
   - [3.11 ระบบสังเคราะห์เสียงพูด 2 ภาษา (`voice/speaker.py`)](#311-ระบบสังเคราะห์เสียงพูด-2-ภาษา-voicespeakerpy)
   - [3.12 ส่วนติดต่อผู้ใช้แบบแยกแท็บสนทนาและข้อมูลดิบ (`ui/`)](#312-ส่วนติดต่อผู้ใช้แบบแยกแท็บสนทนาและข้อมูลดิบ-ui)
   - [3.13 หน่วยความจำถาวร (`memory/`)](#313-หน่วยความจำถาวร-memory)
4. [แผนภาพลำดับการไหลของข้อมูล (System Data Flow)](#4-แผนภาพลำดับการไหลของข้อมูล-system-data-flow)
5. [ตารางคีย์ลัดและสิทธิ์ของระบบ macOS (Keybindings & Permissions)](#5-ตารางคีย์ลัดและสิทธิ์ของระบบ-macos-keybindings--permissions)

---

## 1. ภาพรวมของระบบ (System Overview)

Jarvis Desktop Assistant ได้รับการออกแบบภายใต้สถาปัตยกรรม **Decoupled Event-Driven Architecture** โดยใช้ **PySide6 (Qt for Python)** เป็นแกนกลางในการจัดการ User Interface และ Event Loop มีจุดเด่นสำคัญดังนี้:

- **AI Engine:** ขับเคลื่อนด้วย **Google GenAI SDK (`google-genai`)** ใช้โมเดลหลัก `gemini-3.5-flash-lite` (ความเร็วตอบสนอง ~1.2 วินาที พร้อมโควต้า Free Tier 500 RPD / 15 RPM) เสริมด้วย **Explicit Fallback Chain** สลับโมเดลสำรองอัตโนมัติหากติด 429/503/504
- **Hybrid Tool Architecture:** ผสมผสานระหว่าง **Native macOS Tools** (ควบคุมระบบ Mac, ดูหน้าจอด้วย Vision, ส่งงาน Antigravity, จดจำข้อมูล, เปิดดูผลงาน On-Demand, ค้นประวัติ Raw Data 365 วัน) และ **Official Model Context Protocol (MCP) Servers** (Filesystem, Web Fetch และ Git มาตรฐานสากล) รวม **37 เครื่องมือ** พร้อมใช้งานทันทีโดยไม่ต้องโหลดใหม่ในแต่ละรอบสนทนา
- **Stealth Background Execution & On-Demand Reveal:** ทำงานเบื้องหลัง 100% ไม่แย่งโฟกัสหน้าจอ ไม่เปิดแอปหรือไฟล์ขึ้นมาเองโดยพลการ บันทึกประวัติผลงานใน `task_manager` และเปิดดูเมื่อสั่งเท่านั้น
- **Dual-Tab UI (Conversation vs. Process & Raw Data):** แยกหน้าต่างแชทสะอาดตาออกจากข้อมูลดิบ (Logs / JSON / Listicles) ป้องกันข้อมูลดิบถมทับบทสนทนา
- **Long-term Raw Archive (365+ วัน):** แยกประวัติข้อมูลดิบรายเดือน (`memory/raw_archive/YYYY-MM.jsonl`) เก็บย้อนหลังได้ทั้งปีโดยไม่เปลืองโทเคน และค้นหาคืนได้ผ่านเครื่องมือ `search_raw_history`
- **Clarification & Stateful Continuity:** คิดทบทวนและถามกลับสั้นๆ 1 ประโยคเมื่อคำสั่งกำกวม พร้อมจำลำดับตัวเลือก [1], [2], [3] เพื่อเลือกต่อในเทิร์นถัดไปได้อย่างแม่นยำ
- **Instant Boot Caching:** มีระบบ **Schema Disk Cache** โหลดสเปกเครื่องมือทั้ง 17+ ตัวในเวลาเพียง **0.005 วินาที** พร้อมระบบตรวจจับการอัปเดตอัตโนมัติด้วย SHA-256
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
│   ├── tools.py                        # Native macOS Tools (Vision, Antigravity, System Control, Memory, Reveal, Raw Search)
│   ├── task_manager.py                 # ตัวจัดการบันทึกผลงานเบื้องหลังและ On-Demand Reveal (Stealth Mode)
│   ├── raw_archive.py                  # คลังจัดเก็บและค้นหา Raw Data ระยะยาว 365 วัน แยกรายเดือน (YYYY-MM.jsonl)
│   └── mcp_manager.py                  # ตัวจัดการ Official MCP Servers และ Schema Disk Cache
│
├── integrations/                       # การเชื่อมต่อภายนอก
│   ├── __init__.py
│   └── antigravity_bridge.py           # ตัวเชื่อม Antigravity IDE (Background Task File + Watchdog)
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
    ├── background_tasks.json           # ประวัติและผลลัพธ์ของงานเบื้องหลัง (On-Demand Reveal)
    ├── mcp_tools_cache.json            # แคชสเปกเครื่องมือ MCP ถาวร (Instant Boot 0.005s)
    └── raw_archive/                    # คลังเก็บ Raw Data ระยะยาว 365+ วัน แยกไฟล์รายเดือน (YYYY-MM.jsonl)
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
- `VOICE_LISTEN_MODE`: โหมดรับฟังเสียงเริ่มต้น ค่าเริ่มต้น `"hybrid"` (รองรับ `"push_to_talk"`, `"hi_jarvis"`, `"hybrid"`)
- `WAKE_WORDS`: คำปลุกระบบ (เช่น `"hi jarvis, jarvis, จาร์วิส, จาวิส, ไฮ จาร์วิส"` รองรับการตัดวรรค/อักขระพิเศษเพื่อเทียบคำอย่างแม่นยำ)
- `STT_MODE`: โหมดถอดเสียงพูดเป็นข้อความ ค่าเริ่มต้น `"groq"` (เร็วพิเศษผ่าน Cloud) หรือ `"local"` (ออฟไลน์บนเครื่อง)
- `GROQ_API_KEY`: API Key สำหรับบริการ Groq Cloud Speech-to-Text
- `GROQ_WHISPER_MODEL`: โมเดล Whisper บน Groq Cloud (ค่าเริ่มต้น `whisper-large-v3-turbo`)
- `WHISPER_MODEL`: ขนาดหรือชื่อโมเดล Faster-Whisper ในเครื่อง (ค่าเริ่มต้น `small` สำหรับสำรองยามออฟไลน์ ไม่กิน RAM)
- `WHISPER_INITIAL_PROMPT`: ข้อความชี้นำบริบทเริ่มต้นของ Whisper ป้องกันการถอดเสียงเพี้ยนสำหรับคำทับศัพท์, ชื่อเพลง, และชื่อแอปยอดนิยม
- `VOICE_RECORD_TIMEOUT`: ระยะเวลารอรับฟังเสียงสูงสุดกรณีไม่พบเสียงพูด (จำกัดช่วง 10–25 วินาที, ค่าเริ่มต้น 15s)
- `VOICE_POST_SPEECH_SILENCE`: ระยะเวลาตรวจจับความเงียบหลังผู้ใช้พูดจบเพื่อตัดส่งคำสั่งอัตโนมัติ (จำกัดช่วง 3.0–5.0 วินาที, ค่าเริ่มต้น 3.5s)
- `VOICE_ENERGY_THRESHOLD`: ระดับพลังงานเสียง (RMS) สำหรับตัดสินว่ามีเสียงพูด (ค่าเริ่มต้น 0.015)
- `VOICE_COOLDOWN_SECONDS`: ระยะเวลาคูลดาวน์ป้องกันการกดเบิ้ล (ค่าเริ่มต้น 1.5s)
- `TTS_VOICE_TH` / `TTS_VOICE_EN`: โทนเสียง J.A.R.V.I.S. ภาษาไทย (`th-TH-NiwatNeural`, -14Hz, +6%, +40%) และอังกฤษ (`en-GB-RyanNeural`, -8Hz, +8%, +40%)

### 3.3 ตัวกลางสื่อสารข้ามเธรด (`core/event_bus.py`)
เป็น Singleton Class สืบทอดจาก `PySide6.QtCore.QObject` ช่วยให้การส่งข้อมูลระหว่าง Background Threads (Voice STT, AI Inference, File Watcher) เข้าสู่ Main UI Loop เป็นไปอย่างปลอดภัย (Thread-Safe):
- `state_changed(str)`: แจ้งเปลี่ยนสถานะ (`idle`, `listening`, `thinking`, `running_tool`, `speaking`)
- `user_message_received(str)`: ส่งข้อความที่ได้จากเสียงพูดหรือช่องแชทเข้าสู่สมอง AI
- `assistant_reply_ready(str)`: ส่งข้อความคำตอบฉบับเต็ม (พร้อมโค้ดและ Markdown) ไปแสดงผลในหน้าต่างแชท `OverlayChat`
- `assistant_speak_ready(str)`: ส่งข้อความสรุปภาษาพูดสั้นๆ (ตัดโค้ดและสัญลักษณ์ Markdown) ไปยัง `JarvisSpeaker` เพื่ออ่านออกเสียง
- `task_log_updated(str, str)`: ส่งบันทึกการทำงานของ Tool หรือข้อผิดพลาดไปแสดงผล
- `toggle_overlay_signal()`, `toggle_voice_record_signal()`: สัญญาณสลับหน้าต่างและสลับไมค์
- `voice_mode_changed(str)`: สัญญาณเปลี่ยนโหมดรับฟังเสียงแบบเรียลไทม์ (`push_to_talk`, `hi_jarvis`, `hybrid`) จากเมนูบาร์

### 3.4 สมองหลักและการประมวลผล AI (`core/brain.py`)
- **Static Tool Registry:** รวมฟังก์ชัน Native Tools (9 เครื่องมือ) และ Dynamic MCP Tools (31 เครื่องมือ) เข้าด้วยกันใน `GenerateContentConfig` เพียงครั้งเดียวตอนเริ่มต้นโปรแกรม รวมทั้งหมด **40 เครื่องมือ** ไม่มีการโหลดหรือสร้าง Schema ซ้ำ
- **Dual-Output Protocol (`[SPEAK]` Tags):** ปรับแต่งคำสั่งระบบ (System Instruction) ให้โมเดลสร้างผลลัพธ์ 2 รูปแบบในรอบเดียว: ข้อความฉบับเต็มพร้อมโค้ดสำหรับแสดงผลบนจอ และข้อความสรุปฉบับเต็มในแท็ก `[SPEAK]...[/SPEAK]` สำหรับส่งให้อ่านออกเสียงอย่างลื่นหู ต่อเนื่องทุกประโยคและทุกย่อหน้าโดยไม่ตัดจบกลางคัน
- **macOS GUI Automation Policy:** ให้สิทธิ์และคำสั่งเด็ดขาดแก่ Jarvis ในการมองเห็นหน้าจอ คลิกเมาส์ และพิมพ์ข้อความลงในแอปใดก็ได้บน macOS ผ่าน `click_on_screen`, `type_text_on_screen`, และ `click_and_type` โดยไม่ปฏิเสธคำสั่งผู้ใช้
- **Phonetic Mistranscription & Ambiguous Speech Guard:** กฎดักจับคำพูดที่ถอดเสียงเพี้ยน หากได้ยินคำภาษาไทยหรือคำแปลกๆ ที่มีเค้าโครงของชื่อเพลง/ศิลปิน/แอปภาษาอังกฤษ (เช่น "เลิก 3,000" แทนที่จะเป็น "Love 3000") ระบบจะหยุดเรียก Tool ค้นหาหรือเปิดเว็บทันที แล้วถามยืนยันด้วยความสุภาพรอบเดียวก่อนดำเนินการ
- **Explicit Fallback Chain & Transient Error Retries:** ลำดับโมเดลสำรองแบบกำหนดชัดเจน:
  `["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.6-flash", "gemini-3.8-flash"]`
  - **Automatic Transient Retries:** เมื่อพบปัญหาชั่วคราวจากเซิร์ฟเวอร์ เช่น `500 INTERNAL`, `503 UNAVAILABLE`, หรือ `504 DEADLINE_EXCEEDED` ระบบจะลองซ้ำอัตโนมัติ (Retry with Backoff 2–3 รอบ) พร้อมแจ้งเตือนผ่าน UI (`event_bus.task_log_updated`) ให้ผู้ใช้ทราบแบบเรียลไทม์ก่อนตัดใจสลับโมเดล
  - **Auto-Switching:** สลับโมเดลสำรองถัดไปทันทีเมื่อพบ Error 429 (Quota), 503 (Overloaded หลังลองซ้ำครบ), หรือ 404 โดยบันทึกโมเดลที่ทำงานได้จริงไว้ใช้อย่างต่อเนื่อง
- **ThinkingConfig Handling:** ตั้งค่า `thinking_budget=0` เฉพาะโมเดลที่รองรับ (ยกเว้นตระกูล Lite เพื่อป้องกันข้อผิดพลาด 400)
- **Persistent Chat History:** โหลดประวัติ 10 รอบล่าสุดจาก `memory/chat_history.json` ตอนเปิดโปรแกรม และบันทึกประวัติแบบ Asynchronous หลังจบแต่ละรอบ

### 3.5 เครื่องมือระบบ macOS พื้นฐาน (`core/tools.py`)
ประกอบด้วย 9 เครื่องมือหลักที่เขียนด้วย Native Python และคำสั่งของ macOS:
1. `delegate_to_antigravity(task_prompt)`: ส่งงานเขียนโค้ดไปยัง Antigravity IDE ในเบื้องหลังผ่านไฟล์ `.jarvis_task.md` โดยไม่แย่งโฟกัสหน้าจอ
2. `analyze_current_screen(question)`: ถ่ายภาพหน้าจอด้วย `screencapture -x /tmp/jarvis_screen.jpg` ส่งให้ Gemini Vision วิเคราะห์ และลบไฟล์ทิ้งทันที
3. `control_mac_system(action, target, app)`: ควบคุมระบบ macOS (`open_path`, `open_app`, `open_url` ระบุเบราว์เซอร์, `set_volume`, `get_system_info`)
4. `manage_memory(mode, content)`: บันทึกและดึงข้อมูลความจำระยะยาวใน `memory/jarvis_memory.json`
5. `reveal_task_result(task_ref)`: เปิดไฟล์/หน้าต่างแอป/ผลลัพธ์ของงานเบื้องหลังขึ้นมาบนหน้าจอเฉพาะเมื่อผู้ใช้สั่งเปิดดู (On-Demand Reveal)
6. `search_raw_history(query, days_back)`: ค้นหาประวัติข้อมูลดิบย้อนหลัง 365 วันจากคลัง `memory/raw_archive/`
7. `click_on_screen(target_description, double_click)`: แคปหน้าจอ ส่งให้ Gemini Vision ค้นหาพิกัดกึ่งกลาง (โดยเฉพาะภาพปกวิดีโอ/Thumbnail หรือลิงก์หลัก) คำนวณ Scale Factor รองรับ Retina Display 100% พร้อมแก้ปัญหา Inactive Window ด้วยการคลิก Activate โฟกัสหน้าต่างก่อน 1 ครั้ง (หน่วง 0.15s) แล้วส่งคลิก Action ซ้ำเพื่อให้เปิดเล่นวิดีโอหรือเปิดลิงก์ทันที
8. `type_text_on_screen(text, press_enter)`: พิมพ์ข้อความลงในช่องที่โฟกัสอยู่ รองรับภาษาไทยและอังกฤษสมบูรณ์แบบผ่าน Clipboard Injection (`pbcopy` + `Cmd+V`) พร้อมคืนค่าคลิปบอร์ดเดิม
9. `click_and_type(target_description, text, press_enter)`: ควบคุมแบบรวบขั้นตอนเดียว: หาเป้าหมาย ➔ คลิกโฟกัสและ Activate ➔ พิมพ์ข้อความทันที

### 3.6 ระบบบันทึกผลงานเบื้องหลังและ On-Demand Reveal (`core/task_manager.py`)
- **Stealth Task Registry:** ทุกงานที่รันในเบื้องหลัง (การเขียนไฟล์, การแก้โค้ด, การส่งงาน Antigravity) จะถูกบันทึกประวัติลง `memory/background_tasks.json` อย่างเงียบกริบ
- **ข้อมูลที่บันทึก:** `task_id`, `title`, `command_or_prompt`, `summary`, `files_affected` (รายชื่อไฟล์ที่สร้างหรือแก้ไข), `app_or_url`, `status`, `completed_at`, และสถานะ `revealed`
- **On-Demand Reveal:** เมื่อผู้ใช้สั่งให้เปิดดูงาน (เช่น "เปิดดูไฟล์ที่แก้", "เปิดผลลัพธ์ล่าสุด") ตัวจัดการจะสั่งเปิดไฟล์ด้วย `open` บน macOS หรือเปิดเบราว์เซอร์/หน้าต่างแอปที่เกี่ยวข้อง และปรับสถานะ `revealed = True` ทันที โดยระหว่างที่งานยังรันหรือเพิ่งเสร็จจะไม่มีการเด้งหน้าต่างขึ้นมาขัดจังหวะผู้ใช้เด็ดขาด

### 3.7 ระบบจัดการ MCP มาตรฐานสากล (`core/mcp_manager.py`)
- **Official Servers:** รันและสื่อสารผ่าน Stdio Client กับ:
  - `@modelcontextprotocol/server-filesystem`: จัดการไฟล์ อ่าน เขียน ลิสต์ และค้นหาไฟล์ในโปรเจกต์ (16 เครื่องมือ)
  - `mcp-server-fetch`: ดึงข้อมูลจาก URL และแปลงเป็น Markdown (1 เครื่องมือ)
  - `mcp-server-git`: ตรวจสอบสถานะโค้ด (`git_status`), ประวัติ Commit (`git_log`), ดู Diff ทั้ง staged/unstaged (`git_diff`), สลับ Branch (`git_checkout`), สร้าง Commit และตรวจตรา Git Repository (14 เครื่องมือ)
  - **สรุปเครื่องมือในระบบ:** MCP Tools รวม 31 เครื่องมือ + Native macOS Tools 9 เครื่องมือ = รวมทั้งสิ้น **40 เครื่องมือ**
- **Persistent Schema Disk Cache:** บันทึกโครงสร้างเครื่องมือไว้ใน `memory/mcp_tools_cache.json` ทำให้เปิดโปรแกรมครั้งถัดไปได้ในเวลาเพียง **0.005 วินาที** โดยไม่ต้องรอ Subprocess เริ่มทำงาน
- **SHA-256 Invalidation:** ตรวจสอบความถูกต้องของคอนฟิก หากไฟล์ `mcp_servers.json` มีการแก้ไข ระบบจะอัปเดตแคชใหม่ให้อัตโนมัติ

### 3.8 ระบบเชื่อมต่อ Antigravity IDE (`integrations/antigravity_bridge.py`)
- **Stealth Background Execution (100% เบื้องหลัง):** เปลี่ยนจากการสั่งสลับหน้าต่างและส่งคีย์ลัด มาเป็นการเขียนไฟล์คำสั่ง `.jarvis_task.md` ลงในพื้นที่โปรเจกต์โดยตรง ทำให้ผู้ใช้สามารถพิมพ์งานหรือใช้งานแอปอื่นบนหน้าจอต่อไปได้โดยไม่ถูกแย่งโฟกัส
- **Result Watching:** ใช้ **`watchdog.observers.Observer`** เฝ้าดูการสร้างไฟล์ `.jarvis_result.md` เมื่อ Agent ทำงานเสร็จ จะส่งเนื้อหากลับมาให้ Jarvis สรุปผลด้วยเสียงทันที และบันทึกเข้า `task_manager` เพื่อรอให้ผู้ใช้สั่งเปิดดูเมื่อพร้อม

### 3.9 ระบบรับเสียงพูดอัจฉริยะ (`voice/listener.py`)
- **3 Listening Modes & RAM Management (กติกาการถือครองและคืน RAM ตามโหมด):**
  1. `push_to_talk`: สั่งงานเฉพาะเมื่อกดคีย์ลัด `Cmd + Shift + J` เท่านั้น ไม่มีการดักฟังคำปลุกเบื้องหลัง โมเดล Local Faster-Whisper จะถูกปลดออกจาก RAM ทันที (`_unload_whisper_model` + `gc.collect()`) เพื่อคืนทรัพยากรหน่วยความจำ 100% ให้ระบบ
  2. `hi_jarvis`: ดักจับคำปลุกเบื้องหลังแบบ Silent Background Listening โดยบังคับใช้ **Local `Faster-Whisper` (`small`, beam_size=1)** ตรวจสอบคำปลุกใน `WAKE_WORDS` เท่านั้น (ห้ามเรียกใช้ Groq Cloud STT ในขั้นตอนนี้เพื่อป้องกันโควต้าหมด) โดยโมเดลจะถูกโหลดค้างไว้ใน RAM อย่างต่อเนื่องเพื่อความรวดเร็วในการตรวจจับ
  3. `hybrid` (ค่าเริ่มต้น): รองรับทั้งกดคีย์ลัด `Cmd + Shift + J` และตรวจจับคำปลุกเบื้องหลังด้วย Local Faster-Whisper โดยโมเดลจะถูกโหลดค้างไว้ใน RAM เช่นเดียวกัน
  - **Zero Reload Overhead:** เมื่อผู้ใช้สลับโหมดไปมาระหว่าง `hi_jarvis` กับ `hybrid` ระบบจะใช้โมเดลเดิมที่ค้างอยู่ใน RAM ต่อทันที ไม่มีการ Unload แล้วโหลดใหม่ซ้ำ
  - **Graceful RAM Cleanup:** เมื่อสลับกลับเป็น `push_to_talk` หรือเมื่อปิดแอปพลิเคชัน (`stop()` / Graceful Teardown ใน `main.py`) ระบบจะสั่งปลดโมเดลและเรียก `gc.collect()` คืน RAM ทันที
- **Non-Blocking Wake Ack & Round-2 Continuous Operation:**
  - เมื่อตรวจพบ Wake Word (`hi jarvis`, `jarvis`, `จาร์วิส`, `จาวิส`, `ไฮ จาร์วิส`) ในโหมด `hi_jarvis` หรือ `hybrid` ระบบจะสั่งเล่นเสียงตอบรับ (`/tmp/jarvis_wake_ack.mp3` หรือ `Tink.aiff`) แยก Subprocess (`/usr/bin/afplay`) แบบ Non-Blocking โดยไม่บล็อกลูปการอัดเสียง
  - ปลดล็อกสถานะการพูด (`is_speaking = False`) ทันที เพื่อป้องกันไม่ให้ไมโครโฟนถูกปิดเสียง (Mute) ทำให้การสั่งการในรอบที่ 2 (Round 2) หรือคำสั่งถัดไปรับเสียงและถอดความได้อย่างราบรื่นต่อเนื่อง 100%
  - รีเซ็ตตัวแปรสถานะและค้างหลงเหลือ (`is_recording`, `is_speaking`, `is_processing`) อย่างสมบูรณ์ทั้งใน `_start_recording` และ `set_listen_mode` เพื่อป้องกันปัญหา Deadlock
- **1D Float32 Audio Representation Guard:**
  - บังคับแปลงสัญญาณเสียงทั้งหมดให้อยู่ในรูปแบบ 1D Float32 (`np.asarray(..., dtype=np.float32).reshape(-1)`) ตลอด Pipeline ทั้งใน `_audio_callback`, `_transcribe_and_dispatch`, `_audio_to_wav_bytes`, และ `_check_wake_snippet`
  - ป้องกันข้อผิดพลาด Array Dimension Mismatch (1D vs 2D) ระหว่าง `sounddevice`, `numpy`, และ `Groq Cloud STT` อย่างเบ็ดเสร็จ
- **1-Tap Toggle Mode:** กด `Cmd + Shift + J` ครั้งแรกเพื่อเริ่มอัด (เล่นเสียง *Tink*) และกดอีกครั้งเพื่อส่ง (เล่นเสียง *Pop*)
- **Persistent Mic Session:** เปิดสตรีม `sounddevice.InputStream` ค้างไว้ตลอดเวลา โดยในขณะไม่ได้อัดเสียงฟังก์ชัน Callback จะคืนค่าทันที ทำให้ใช้ **CPU 0%** และลดอาการหน่วงตอนเริ่มอัดเสียง
- **2-Stage Smart Cutoff (Silence Detection):**
  - **กรณีที่ 1 (ยังไม่พบเสียงพูด):** รอคอยคำสั่งจนครบเวลาสูงสุด `VOICE_RECORD_TIMEOUT` (15 วินาที)
  - **กรณีที่ 2 (เริ่มพูดแล้ว):** ตรวจจับพลังงานเสียงพูด (RMS >= 0.015) เมื่อผู้ใช้พูดจบและเงียบต่อเนื่องครบ `VOICE_POST_SPEECH_SILENCE` (3.5 วินาที) ระบบจะตัดจบและส่งไปประมวลผลทันทีโดยไม่ต้องรอจนครบ 15s พร้อม Post-Session Cooldown (1.5s) ป้องกันการกดทับซ้ำ
- **Groq Cloud STT (Default Primary สำหรับคำสั่ง):**
  - เมื่อตรวจพบคำปลุกหรือกดสั่งงาน และบันทึกคำสั่งเสร็จสิ้น จะส่งเสียงคำสั่งไปยัง Groq Audio API (`whisper-large-v3-turbo`) เป็นหลัก เพื่อความเร็วและแม่นยำระดับ 0.2 - 0.4s
  - หาก Groq ล่มหรือออฟไลน์ จึงจะสลับมาใช้ Local Faster-Whisper สำรองอัตโนมัติ
  - เมื่อ `STT_MODE="groq"` และมี `GROQ_API_KEY` ระบบจะไม่โหลด Local Whisper ขึ้น RAM ตอนบูตเครื่อง (Lazy Loading) โดยพิมพ์ Log: `[Listener] STT Mode: groq (whisper-large-v3-turbo)`
  - เมื่อผู้ใช้พูดจบ ระบบจะแปลงเสียงเป็น WAV ในหน่วยความจำ (`io.BytesIO`) แล้วส่งไปยัง Groq Audio API (`whisper-large-v3-turbo`) พร้อม `WHISPER_INITIAL_PROMPT`
  - ประมวลผลเสร็จในเวลาเพียง **0.2 - 0.4 วินาที** โดยใช้ CPU และ RAM เครื่อง 0%
- **Automatic Local Fallback (Faster-Whisper):**
  - หากไม่มีอินเทอร์เน็ต, ไม่ได้ใส่ `GROQ_API_KEY`, หรือ Groq API ส่งกลับ Error ระบบจะแสดง Log: `[Listener] ⚠️ Fallback to Local Faster-Whisper...` แล้วโหลดและถอดความด้วย Local `Faster-Whisper` (`small`) อัตโนมัติทันที
  - ใช้ `beam_size=5`, `vad_filter=True` พร้อม `vad_parameters={"speech_pad_ms": 400}` ป้องกันคำหัวท้ายตกหล่น

### 3.10 ระบบสังเคราะห์เสียงพูด 2 ภาษา (`voice/speaker.py`)
- ตรวจจับภาษาอัตโนมัติจากชุดตัวอักษรไทย (Unicode Range `\u0E00-\u0E7F`)
- สลับโทนเสียงระหว่างภาษาไทย (`th-TH-NiwatNeural`, Rate `+6%`, Pitch `-14Hz`, Volume `+40%` สุขุม นุ่มนวล) และภาษาอังกฤษ (`en-GB-RyanNeural`, Rate `+8%`, Pitch `-8Hz`) โดยอัตโนมัติ
- **Continuous Multi-Line Speech:** ปรับระบบแยกข้อความพูดให้ดึงข้อความสนทนาครบถ้วนทุกประโยคและทุกย่อหน้าต่อเนื่องกัน ไม่ตัดจบแค่ประโยคแรกหรือย่อหน้าเดียว
- **Pacing & Clean Speech:** ตัดคำและเว้นจังหวะวรรคตอนภาษาไทย/อังกฤษอย่างเป็นธรรมชาติ (แยกตัวอักษรไทยและอังกฤษ/ตัวเลขด้วยวรรคเพื่อให้ออกเสียงชัดเจน ไม่กลืนคำ) กรองสัญลักษณ์ดิบ, Emoji, Markdown และแท็ก `[SPEAK]` ออกทั้งหมด
- ขับเสียงผ่านเครื่องเล่นระบบของ macOS (`/usr/bin/afplay`) โดยตรงเพื่อความเสถียรและเสียงคมชัดสูงสุด

### 3.11 ส่วนติดต่อผู้ใช้ (`ui/`)
- **Dynamic Island (`ui/dynamic_island.py`):** แคปซูลโปร่งแสงลอยอยู่กึ่งกลางด้านบนของหน้าจอ (Always-on-top, กว้าง 300px) แสดงสถานะและจุดสีแอนิเมชันตามสถานะปัจจุบัน และซ่อนตัวอัตโนมัติเมื่อเข้าสู่สถานะ `Idle`
- **Overlay Chat (`ui/overlay_chat.py`):** หน้าต่างลอยสไตล์ Spotlight / Raycast สำหรับพิมพ์ข้อความ ดูประวัติการแชท และตรวจสอบ System / Tool Logs
- **System Tray (`ui/tray.py`):** ไอคอนวงแหวนสีฟ้าบน macOS Menu Bar พร้อม Context Menu สำหรับเปิดแชท, เปิดไมค์, เมนูย่อย `🎙️ Voice Listen Mode` สำหรับสลับโหมดรับเสียง (`Hybrid`, `Push-to-Talk`, `Wake Word Only`) แบบเรียลไทม์โดยไม่ต้องรีสตาร์ท, ล้างประวัติ หรือออกจากโปรแกรม

### 3.12 หน่วยความจำถาวร (`memory/`)
- `memory/chat_history.json`: บันทึกประวัติการสนทนา 10 เทิร์นล่าสุด ทำให้เปิดโปรแกรมใหม่แล้วคุยต่อได้ทันที
- `memory/jarvis_memory.json`: บันทึกข้อมูลสำคัญที่ผู้ใช้สั่งให้จำ (เช่น ความชอบ, ข้อมูลส่วนตัว)
- `memory/background_tasks.json`: บันทึกประวัติและรายการไฟล์ผลลัพธ์ของงานเบื้องหลัง สำหรับการเปิดดูแบบ On-Demand
- `memory/mcp_tools_cache.json`: แคชโครงสร้างเครื่องมือ MCP ทั้งหมด เพื่อการบูตเครื่องใน 0.005 วินาที

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
             [Speech-to-Text Pipeline (voice/listener.py)]
                     │
                     ├──> Primary: Groq Cloud STT (whisper-large-v3-turbo) ──> ~0.2s, CPU 0%
                     │         │
                     │         └──> (Fallback เมื่อออฟไลน์ / ไร้ Key / ขัดข้อง)
                     │                   │
                     └──> Fallback: Local Faster-Whisper (small, int8, beam_size=5, speech_pad_ms=400)
                               │
                               ▼ (emit user_message_received)
             [JarvisBrain (core/brain.py)]
                     │
                     ├──> ส่งประวัติและข้อความเข้า Gemini API (Explicit Fallback Chain)
                     │
                     ├──> Gemini ร้องขอ Function Call (Tools / MCP)
                     │         │
                     │         ├── [Native Tools (core/tools.py)]
                     │         │     • click_on_screen / type_text_on_screen / click_and_type (GUI Automation)
                     │         │     • delegate_to_antigravity (.jarvis_task.md + Watchdog)
                     │         │     • reveal_task_result (On-Demand Reveal งานเบื้องหลัง)
                     │         │     • search_raw_history (ค้นหาประวัติ Raw Archive 365 วัน)
                     │         │     • analyze_current_screen (screencapture + Vision)
                     │         │     • control_mac_system (open_path, browser url, volume, sysinfo)
                     │         │     • manage_memory (jarvis_memory.json)
                     │         │
                     │         └── [Official MCP Tools (core/mcp_manager.py)]
                     │               • @modelcontextprotocol/server-filesystem (read, write, list)
                     │               • mcp-server-fetch (web fetcher)
                     │               • mcp-server-git (status, diff, log)
                     │
                     ├──> [Raw Data Pipeline]
                     │         ├──> (emit raw_data_received) ──> [OverlayChat ⚡ Process & Raw Tab]
                     │         └──> บันทึกลงคลังรายเดือน ───> [memory/raw_archive/YYYY-MM.jsonl] (365+ วัน)
                     │
                     └──> ส่งผลลัพธ์ Tool กลับสู่ Gemini จนได้คำตอบสรุปสุดท้าย
                               │
                               ├──> บันทึกประวัติ 10 รอบลง memory/chat_history.json (Active History)
                               ├──> บันทึกผลงานลง memory/background_tasks.json (Stealth Mode)
                               │
                               ├──> [Dual-Output Separator (core/brain.py)]
                               │         │
                               │         ├──> (emit assistant_reply_ready)
                               │         │         ▼
                               │         │   [OverlayChat 💬 Conversation Tab]
                               │         │   (แสดงผลสรุปสะอาดตา + ตัวเลือก [1], [2], [3] สำหรับเลือกต่อ)
                               │         │
                               │         └──> (emit assistant_speak_ready)
                               │                   ▼
                               │             [JarvisSpeaker (voice/speaker.py)]
                               │             (รับข้อความสรุปกระชับ 1-2 ประโยคจาก [SPEAK])
                               │                   │
                               │                   ├──> ตรวจภาษา (TH/EN) ➔ ล้างสัญลักษณ์ & ปรับจังหวะวรรคตอน
                               │                   ├──> สังเคราะห์เสียงด้วย Edge-TTS (Rate +6%)
                               │                   └──> ขับเสียงผ่าน macOS /usr/bin/afplay
                               │
                               ▼ (จบการทำงานในเบื้องหลัง - ไม่เปิดหน้าต่างเอง)
                     [Dynamic Island แสดงสถานะ Idle ➔ ซ่อนตัวอัตโนมัติ]
                               │
                               │ (เมื่อผู้ใช้สั่ง: "เปิดดูผลงานล่าสุด" / "ขอดูผลหน่อย")
                               ▼
                     [reveal_task_result("latest")] ➔ สั่งเปิดไฟล์หรือโฟกัสหน้าต่างเฉพาะเมื่อสั่งเท่านั้น!
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
