# Jarvis Desktop Assistant 🚀

ผู้ช่วยอัจฉริยะบนเดสก์ท็อป (macOS / Desktop) ที่ออกแบบสถาปัตยกรรมแบบแยกโมดูลชัดเจน (Decoupled Architecture) สื่อสารข้ามเธรดด้วย **PySide6 Signals / Event Bus**, ขับเคลื่อนด้วยสมองหลัก **Gemini API (`google-genai` SDK)**, มีหน้าต่าง **Dynamic Island** แจ้งเตือนสถานะแบบลอยตัว, หน้าต่าง **Overlay Chat** สไตล์ Spotlight/Raycast, สังเคราะห์เสียงพูดธรรมชาติด้วย **Edge-TTS**, และมีระบบ **Antigravity Bridge** เพื่อส่งต่องานโค้ดหรือการวิเคราะห์เข้าสู่ Antigravity IDE Agent อัตโนมัติ

---

## 📂 โครงสร้างโปรเจกต์ (Project Directory Structure)

```text
jarvis-desktop/
├── .env                        # ไฟล์เก็บค่า Config และ GEMINI_API_KEY ส่วนตัว
├── .env.example                # เทมเพลตตัวแปรสภาพแวดล้อม
├── requirements.txt            # รายการ Dependencies ทั้งหมด
├── config.py                   # ค่าคงที่หลักของระบบ (โมเดล, คีย์ลัด, เสียง, พาธไฟล์)
├── main.py                     # Entry point เริ่มต้น QApplication, UI, Brain และ Voice
│
├── core/
│   ├── __init__.py
│   ├── event_bus.py            # ตัวกลางสื่อสารข้าม Thread (PySide6 Signals)
│   ├── brain.py                # สมองหลักเชื่อมต่อ Gemini API + Function Calling Loop
│   └── tools.py                # ฟังก์ชันเครื่องมือที่ Gemini เรียกใช้ (Tools)
│
├── integrations/
│   ├── __init__.py
│   └── antigravity_bridge.py   # เชื่อมต่อ Antigravity ด้วย AppleScript, pbcopy และ Watchdog
│
├── voice/
│   ├── __init__.py
│   ├── listener.py             # Worker Thread บันทึกเสียงและแปลงเป็นข้อความ (Faster-Whisper)
│   └── speaker.py              # Worker Thread สังเคราะห์เสียงพูดธรรมชาติ (Edge-TTS + afplay/pygame)
│
└── ui/
    ├── __init__.py
    ├── tray.py                 # System Tray / Menu Bar Icon และ Context Menu
    ├── dynamic_island.py       # หน้าต่างแคปซูลโปร่งแสงลอยบนหน้าจอ (Always-on-top)
    └── overlay_chat.py         # หน้าต่าง Overlay Chat สไตล์ Spotlight / Raycast
```

---

## 🛠️ ความต้องการของระบบและการเปิดสิทธิ์บน macOS (Permissions)

เนื่องจากระบบทำงานบน **macOS** และมีการดึงหน้าต่างแอปพลิเคชัน, ส่งคีย์ลัดด้วย AppleScript (`osascript`), ดักจับคีย์ลัดระดับ System Event Tap ด้วย macOS Quartz (`CGEventTapCreate`), และรับเสียงจากไมโครโฟนแบบ Persistent Mic Session กรุณาตั้งค่าสิทธิ์ใน macOS ดังนี้:

### 1. สิทธิ์ Accessibility (การควบคุมและการจำลองการกดแป้นพิมพ์)
จำเป็นสำหรับการใช้คีย์ลัด **`Alt+Space`** (Option+Space) และคำสั่งจำลองการกดคีย์ `Cmd+L`, `Cmd+V`, `Enter` ส่งให้ Antigravity:
1. เปิด **System Settings** (การตั้งค่าระบบ)
2. ไปที่ **Privacy & Security** (ความเป็นส่วนตัวและความปลอดภัย) ➔ **Accessibility** (การช่วยการเข้าถึง)
3. กดปุ่ม `+` หรือเปิดสวิตช์อนุญาตให้กับ:
   - **Terminal** หรือ **iTerm** หรือ **Visual Studio Code / Antigravity** (ขึ้นอยู่กับโปรแกรมที่คุณใช้รันคำสั่ง `python main.py`)
   - **Python** (หากมีปรากฏในรายการ)

### 2. สิทธิ์ Microphone (ไมโครโฟน)
จำเป็นสำหรับโมดูล `voice/listener.py` เมื่อเปิดใช้งาน `VOICE_INPUT_ENABLED=true`:
1. ไปที่ **Privacy & Security** ➔ **Microphone** (ไมโครโฟน)
2. ตรวจสอบว่าแอปพลิเคชัน Terminal / IDE ของคุณได้รับอนุญาตให้เข้าถึงไมโครโฟนแล้ว

> 💡 **หมายเหตุ**: หากยังไม่ได้เปิดสิทธิ์ไมโครโฟนหรือยังไม่ได้เชื่อมต่อไมค์ ระบบจะทำงานใน **Text-first Mode** ผ่าน Overlay Chat (`Alt+Space`) ได้อย่างราบรื่น 100% โดยไม่ทำให้แอปเกิดข้อผิดพลาด

---

## ⚙️ การติดตั้งและตั้งค่า (Installation & Setup)

### 1. ติดตั้ง Dependencies
```bash
pip install -r requirements.txt
```

### 2. ตั้งค่าไฟล์สภาพแวดล้อม (`.env`)
คัดลอกไฟล์เทมเพลตและระบุ `GEMINI_API_KEY` ของคุณ:
```bash
cp .env.example .env
```
เปิดไฟล์ `.env` แล้วแก้ไข:
```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
THINKING_LEVEL=low
HOTKEY=alt+space

# Voice Settings (J.A.R.V.I.S. Tone for edge-tts)
TTS_ENABLED=true
TTS_VOICE_TH=th-TH-NiwatNeural
TTS_PITCH_TH=-14Hz
TTS_RATE_TH=+14%
TTS_VOLUME_TH=+40%
TTS_VOICE_EN=en-GB-RyanNeural
TTS_PITCH_EN=-8Hz
TTS_RATE_EN=+8%
TTS_VOLUME_EN=+40%

# Voice Listener Settings (Faster-Whisper 1-Tap Toggle)
VOICE_INPUT_ENABLED=true
VOICE_TOGGLE_HOTKEY=<cmd>+<shift>+j
WHISPER_MODEL_SIZE=small
WAKE_WORDS=jarvis,จาร์วิส,จาวิส
```

---

## 🚀 การเปิดใช้งาน (Running Jarvis)

รันคำสั่งจากโฟลเดอร์โปรเจกต์:
```bash
python3 main.py
```

เมื่อโปรแกรมเริ่มทำงาน:
1. จะมีไอคอนวงแหวนสีฟ้าปรากฏบน **Menu Bar (System Tray)** ด้านขวาบนของ macOS
2. หน้าต่าง **Dynamic Island** แคปซูลจะแสดงสถานะด้านบนของหน้าจอ
3. **การสั่งงานผ่านแชท:** กดคีย์ลัด **`Alt+Space`** (หรือ Option+Space) เพื่อเปิด-ปิดหน้าต่าง **Overlay Chat**
4. **การสั่งงานด้วยเสียง (1-Tap Toggle + Auto Cooldown):** กดคีย์ลัด **`Cmd + Shift + J`** จากทุกหน้าจอ:
   - **กดครั้งที่ 1 (เริ่มบันทึก):** ได้ยินเสียง *Tink*, Dynamic Island แสดง `Listening... (15s auto-send)` และเริ่มบันทึกเสียง
   - **กดครั้งที่ 2 (หยุดและส่งคำสั่ง):** ได้ยินเสียง *Pop*, Dynamic Island แสดง `Thinking...` และส่งคำสั่งให้ถอดความทันที (หากพูดต่อเนื่องครบ 10 - 25 วินาที เช่น 15 วินาที ระบบจะตัดส่งให้อัตโนมัติ พร้อมระบบ Cooldown ป้องกันการกดทับซ้ำ)

---

## 💡 ตัวอย่างคำสั่งที่สามารถทดสอบได้ทันที (Native macOS + Official MCP)

- **1. วิเคราะห์หน้าจอปัจจุบัน (Native macOS - `analyze_current_screen`):**
  - *"หน้าจอนี้เปิดอะไรอยู่บ้าง ช่วยสรุปเนื้อหาให้ฟังที"*
  - *"ดูโค้ดบนหน้าจอให้หน่อย มีตรงไหนเขียนผิดไหม"*
- **2. ควบคุมระบบ macOS (Native macOS - `control_mac_system`):**
  - *"เปิดแอป Safari ให้หน่อย"* (open_app)
  - *"เปิดเว็บ google.com ที"* (open_url)
  - *"ปรับระดับเสียงเป็น 50 เปอร์เซ็นต์"* (set_volume)
  - *"เช็กสถานะ CPU แรม และแบตเตอรี่เครื่อง Mac ตอนนี้หน่อย"* (get_system_info)
- **3. จัดการไฟล์โปรเจกต์ (Official MCP - `@modelcontextprotocol/server-filesystem`):**
  - *"ช่วยดูรายชื่อไฟล์ในโฟลเดอร์ core ให้หน่อย"* (list_directory)
  - *"อ่านโค้ดในไฟล์ config.py ให้ฟังที"* (read_text_file)
  - *"ค้นหาไฟล์ที่มีคำว่า listener ในชื่อหน่อย"* (search_files)
- **4. ดึงข้อมูลจากหน้าเว็บ (Official MCP - `mcp-server-fetch`):**
  - *"ช่วยดึงข้อมูลสรุปจากเว็บ https://example.com ให้หน่อย"* (fetch)
- **5. ความจำระยะยาวข้ามเซสชัน (Native - `manage_memory`):**
  - *"จดจำไว้ว่า บอสชอบดื่มกาแฟดำไม่ใส่น้ำตาล"* (save)
  - *"คุณจำอะไรเกี่ยวกับตัวผมได้บ้าง"* (read)
- **6. สั่งงาน Antigravity IDE (Native Bridge - `delegate_to_antigravity`):**
  - *"Jarvis ส่งงานนี้ให้ Antigravity: ช่วยสร้างฟังก์ชันคำนวณภาษีและเขียน unit test"*

---

## 🧩 รายละเอียดสถาปัตยกรรม (Architecture Highlights)

1. **Hybrid Tools: Native macOS + Official MCP Servers (`core/mcp_manager.py` & `core/tools.py`):**
   - เชื่อมต่อกับ Official MCP Servers (`filesystem`, `fetch`) ผ่าน stdio เพียงครั้งเดียวตอนเปิดแอป (`main.py`)
   - แปลงเครื่องมือ MCP ทั้ง 17 ตัวเป็น Dynamic Python Callables รวมกับ Native macOS Tools เข้าสู่ `GenerateContentConfig` ของ Gemini ล่วงหน้า ตอบสนองฉับไวและประหยัด Token สูงสุด
   - ปิดเซสชัน MCP Process อย่างสะอาดเมื่อปิดโปรแกรม
2. **Persistent Context & Memory (`memory/`):**
   - กักเก็บประวัติการสนทนาต่อเนื่องใน `memory/chat_history.json` (โหลดอัตโนมัติ 10 รอบล่าสุดตอนเปิดแอป และบันทึกแบบ Background)
   - จัดเก็บความจำระยะยาวใน `memory/jarvis_memory.json`
3. **Decoupled Event Bus (`core/event_bus.py`):**
   - ใช้งาน PySide6 `QObject` และ `Signal` ป้องกันปัญหา Race Conditions ระหว่าง Thread การประมวลผล AI / Voice กับ Main UI Loop
4. **Native macOS Bridge (`integrations/antigravity_bridge.py`):**
   - สลับหน้าต่างและส่งคีย์ลัดด้วย AppleScript (`osascript`) และคัดลอกด้วย `pbcopy` ซึ่งเข้ากันได้กับ macOS Tahoe / Sonoma / Sequoia โดยตรง
   - เฝ้าดูผลลัพธ์ผ่าน `watchdog.observers.Observer` แบบ Asynchronous
