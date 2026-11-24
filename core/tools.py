"""
Static Tool Registry for Jarvis Desktop Assistant.
Pre-registers all standard native tools once at startup for fast execution and minimal token overhead:
1. delegate_to_antigravity: Hands off coding/refactoring tasks to Antigravity IDE Agent via .jarvis_task.md in background.
2. analyze_current_screen: Captures desktop via screencapture and analyzes with Gemini Vision.
3. control_mac_system: Controls macOS apps, URLs, audio volume, and inspects system resources.
4. manage_memory: Stores and retrieves persistent long-term memories across sessions.
5. reveal_task_result: Opens files, apps, or displays results of background tasks on-demand when requested by the user.
"""

import os
import re
import sys
import json
import time
import threading
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

from google.genai import types

import config
from core.event_bus import event_bus

# Persistent paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEMORY_DIR = PROJECT_ROOT / "memory"
JARVIS_MEMORY_FILE = MEMORY_DIR / "jarvis_memory.json"
TODO_ITEMS_FILE = MEMORY_DIR / "todo_items.json"

# Global references set once at initialization
_antigravity_bridge = None
_genai_client = None
_current_model = config.GEMINI_MODEL


def set_bridge_instance(bridge):
    """Sets the active AntigravityBridge instance."""
    global _antigravity_bridge
    _antigravity_bridge = bridge


def set_genai_client(client, model_name: Optional[str] = None):
    """Sets the active Google GenAI Client and active model for vision analysis."""
    global _genai_client, _current_model
    _genai_client = client
    if model_name:
        _current_model = model_name


# ============================================================================
# 1. delegate_to_antigravity
# ============================================================================
def delegate_to_antigravity(task_prompt: str) -> str:
    """
    Delegates complex coding, file editing, refactoring, or repo analysis to the Antigravity IDE Agent.
    Use this whenever the user requests writing code, modifying files, or performing workspace tasks.
    IMPORTANT: Invoke this tool ONLY ONCE per user request. Do NOT invoke repeatedly to check status.
    The task runs silently in the background and will notify the user automatically upon completion.

    Args:
        task_prompt: Clear, detailed description of the task for Antigravity to perform.
    """
    global _antigravity_bridge
    if _antigravity_bridge is None:
        from integrations.antigravity_bridge import AntigravityBridge
        _antigravity_bridge = AntigravityBridge()

    return _antigravity_bridge.delegate_task(task_prompt)


# ============================================================================
# 2. analyze_current_screen
# ============================================================================
def analyze_current_screen(question: str) -> str:
    """
    Captures the current macOS desktop screen and analyzes what is visible using Gemini Vision.
    Use this when the user asks what is on the screen, asks to look at a window, image, or website.

    Args:
        question: Specific question or instruction about what to analyze on the screen.
    """
    temp_screen_path = "/tmp/jarvis_screen.jpg"
    event_bus.task_log_updated.emit("Vision Tool", f"กำลังบันทึกภาพหน้าจอเพื่อวิเคราะห์: '{question}'")

    try:
        # Hide overlay temporarily to capture clean background if needed
        event_bus.hide_overlay_signal.emit()
        time.sleep(0.2)

        # macOS native screencapture (-x = silent, no shutter sound)
        capture_cmd = ["screencapture", "-x", temp_screen_path]
        subprocess.run(capture_cmd, check=True, timeout=5)

        if not os.path.exists(temp_screen_path):
            return "ไม่สามารถจับภาพหน้าจอได้ครับบอส"

        with open(temp_screen_path, "rb") as f:
            image_bytes = f.read()

        # Clean up screenshot file immediately
        try:
            os.remove(temp_screen_path)
        except Exception:
            pass

        if not _genai_client:
            return "จับภาพหน้าจอสำเร็จ แต่ยังไม่ได้เชื่อมต่อ Gemini Client ครับบอส"

        # Analyze using current model or fallback model
        prompt = (
            f"คำถาม/คำสั่งของผู้ใช้: {question}\n"
            "กรุณาวิเคราะห์ภาพหน้าจอนี้อย่างละเอียดและตอบคำถามอย่างกระชับ สุภาพ ในฐานะ J.A.R.V.I.S. "
            "เขียนประโยคให้เหมาะกับเสียงพูด ไม่ต้องใส่สัญลักษณ์ Markdown ดิบ"
        )

        response = _genai_client.models.generate_content(
            model=_current_model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                prompt
            ]
        )

        analysis = response.text or "วิเคราะห์ภาพหน้าจอเสร็จสิ้นครับบอส"
        event_bus.task_log_updated.emit("Vision Tool", "วิเคราะห์ภาพหน้าจอสำเร็จเรียบร้อยแล้ว")
        return analysis

    except Exception as e:
        err_msg = f"เกิดข้อผิดพลาดในการวิเคราะห์ภาพหน้าจอ: {str(e)}"
        event_bus.task_log_updated.emit("Vision Error", err_msg)
        return err_msg


# ============================================================================
# 3. control_mac_system
# ============================================================================
def control_mac_system(action: str, target: str = "", app: str = "") -> str:
    """
    Controls macOS system settings, applications, URLs, folders/paths, or inspects machine hardware status.
    Guarantees strict return-code verification with NO false success reporting.

    Args:
        action: System operation to perform:
                - "open_app": Launches or focuses an application (e.g. target="Safari", target="Terminal")
                - "open_url": Opens a web URL (e.g. target="google.com"). Pass app="Firefox" or app="Google Chrome" to specify browser!
                - "open_path" or "open_folder": Opens a folder or file in macOS Finder (e.g. target="~/Library/Application Support")
                - "set_volume": Sets speaker output volume 0-100 (e.g. target="50")
                - "get_system_info": Checks current CPU, RAM, and Battery percentage.
        target: Parameter for the action (app name, URL, folder/file path, or volume number).
        app: Optional specific application or browser to launch the target with (e.g. "Firefox", "Google Chrome", "Safari").
    """
    clean_action = action.lower().strip()
    clean_target = target.strip()
    clean_app = app.strip()

    try:
        # 1. Open Folder / File Path
        if clean_action in ("open_path", "open_folder") or (
            clean_action == "open_app" and (clean_target.startswith("~") or clean_target.startswith("/") or "/" in clean_target)
        ):
            if not clean_target:
                return "กรุณาระบุพาธโฟลเดอร์หรือไฟล์ที่ต้องการเปิดครับบอส"

            expanded_path = os.path.expanduser(clean_target)
            if not os.path.exists(expanded_path):
                err = f"เกิดข้อผิดพลาด: ไม่พบโฟลเดอร์หรือไฟล์ตามพาธ '{clean_target}' (ตรวจสอบที่: {expanded_path}) ครับบอส"
                event_bus.task_log_updated.emit("System Error", err)
                return err

            if os.path.isdir(expanded_path):
                # Open directory in Finder
                res = subprocess.run(["open", "-a", "Finder", expanded_path], capture_output=True, text=True, timeout=5)
            else:
                # Open file with specific app or default handler
                cmd = ["open", "-a", clean_app, expanded_path] if clean_app else ["open", expanded_path]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

            if res.returncode == 0:
                msg = f"เปิด '{expanded_path}' บนหน้าจอให้เรียบร้อยแล้วครับบอส"
                event_bus.task_log_updated.emit("System Control", msg)
                return msg
            else:
                err = f"ไม่สามารถเปิด '{expanded_path}' ได้: {res.stderr.strip() or 'คำสั่งระบบไม่สำเร็จ'}"
                event_bus.task_log_updated.emit("System Error", err)
                return err

        # 2. Open Application
        elif clean_action == "open_app":
            if not clean_target:
                return "กรุณาระบุชื่อแอปพลิเคชันที่ต้องการเปิดครับบอส"

            target_app = clean_target
            try:
                from core.thai_nlp import resolve_macos_app_name
                resolved = resolve_macos_app_name(clean_target)
                if resolved:
                    print(f"[Tools] 🎯 Resolved app name: '{clean_target}' -> '{resolved}'")
                    target_app = resolved
            except Exception:
                pass

            res = subprocess.run(["open", "-a", target_app], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                msg = f"เปิดแอปพลิเคชัน '{target_app}' เรียบร้อยแล้วครับบอส"
                event_bus.task_log_updated.emit("System Control", msg)
                return msg
            else:
                err = f"ไม่สามารถเปิดแอป '{clean_target}' ได้: {res.stderr.strip() or 'ไม่พบแอปนี้บน macOS'}"
                event_bus.task_log_updated.emit("System Error", err)
                return err

        # 3. Open URL (Supports specific browser via app parameter)
        elif clean_action == "open_url":
            if not clean_target:
                return "กรุณาระบุ URL ที่ต้องการเปิดครับบอส"
            url = clean_target if clean_target.startswith(("http://", "https://")) else f"https://{clean_target}"

            if clean_app:
                target_browser = clean_app
                try:
                    from core.thai_nlp import resolve_macos_app_name
                    resolved = resolve_macos_app_name(clean_app)
                    if resolved:
                        print(f"[Tools] 🎯 Resolved browser name: '{clean_app}' -> '{resolved}'")
                        target_browser = resolved
                except Exception:
                    pass

                res = subprocess.run(["open", "-a", target_browser, url], capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    msg = f"เปิดเว็บไซต์ {url} ด้วยเบราว์เซอร์ '{target_browser}' เรียบร้อยแล้วครับบอส"
                    event_bus.task_log_updated.emit("System Control", msg)
                    return msg
                else:
                    err = f"ไม่สามารถเปิดเว็บด้วยเบราว์เซอร์ '{clean_app}' ได้: {res.stderr.strip() or 'ไม่พบเบราว์เซอร์ที่ระบุ'}"
                    event_bus.task_log_updated.emit("System Error", err)
                    return err
            else:
                res = subprocess.run(["open", url], capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    msg = f"เปิดลิงก์ {url} ในเบราว์เซอร์เริ่มต้นเรียบร้อยแล้วครับบอส"
                    event_bus.task_log_updated.emit("System Control", msg)
                    return msg
                else:
                    err = f"ไม่สามารถเปิด URL ได้: {res.stderr.strip()}"
                    event_bus.task_log_updated.emit("System Error", err)
                    return err

        # 4. Set Volume (0 - 100)
        elif clean_action == "set_volume":
            try:
                vol_int = int(''.join(c for c in clean_target if c.isdigit()))
                vol = max(0, min(100, vol_int))
            except Exception:
                vol = 50
            cmd = ["osascript", "-e", f"set volume output volume {vol}"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                msg = f"ปรับระดับเสียงเป็น {vol}% เรียบร้อยแล้วครับบอส"
                event_bus.task_log_updated.emit("System Control", msg)
                return msg
            else:
                return f"เกิดข้อผิดพลาดในการปรับระดับเสียง: {res.stderr.strip()}"

        # 5. Get System Info (CPU, RAM, Battery)
        elif clean_action == "get_system_info":
            info_parts = []
            try:
                import psutil
                cpu = psutil.cpu_percent(interval=0.1)
                ram = psutil.virtual_memory().percent
                info_parts.append(f"CPU: {cpu}%")
                info_parts.append(f"RAM: {ram}%")
                batt = psutil.sensors_battery()
                if batt:
                    plug_str = "กำลังชาร์จ" if batt.power_plugged else "ใช้พลังงานจากแบตเตอรี่"
                    info_parts.append(f"แบตเตอรี่: {batt.percent}% ({plug_str})")
            except Exception:
                try:
                    batt_out = subprocess.check_output(["pmset", "-g", "batt"], text=True)
                    info_parts.append(batt_out.strip().split("\n")[0])
                except Exception:
                    pass

            result_str = "สถานะระบบ macOS ปัจจุบัน: " + ", ".join(info_parts)
            event_bus.task_log_updated.emit("System Info", result_str)
            return result_str

        else:
            return f"ไม่รู้จักคำสั่ง action '{action}' สำหรับ control_mac_system ครับ"

    except Exception as e:
        err_msg = f"เกิดข้อผิดพลาดในการควบคุมระบบ ({action}): {str(e)}"
        event_bus.task_log_updated.emit("System Error", err_msg)
        return err_msg


# ============================================================================
# 4. manage_memory
# ============================================================================
def manage_memory(mode: str, content: str = "") -> str:
    """
    Stores and retrieves persistent long-term memories across Jarvis sessions in memory/jarvis_memory.json.

    Args:
        mode: Memory operation:
              - "save": Stores important information, user preferences, or notes into long-term memory.
              - "read": Retrieves all stored long-term memories.
        content: The text content or fact to remember when mode is "save".
    """
    clean_mode = mode.lower().strip()
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    try:
        memories: List[Dict[str, Any]] = []
        if JARVIS_MEMORY_FILE.exists():
            try:
                with open(JARVIS_MEMORY_FILE, "r", encoding="utf-8") as f:
                    memories = json.load(f)
            except Exception:
                memories = []

        # 1. Save Memory
        if clean_mode == "save":
            if not content.strip():
                return "กรุณาระบุข้อความที่ต้องการบันทึกความจำครับบอส"
            entry = {
                "id": len(memories) + 1,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "content": content.strip()
            }
            memories.append(entry)
            with open(JARVIS_MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(memories, f, ensure_ascii=False, indent=2)

            msg = f"บันทึกข้อมูลลงความจำระยะยาวเรียบร้อยแล้วครับบอส: '{content.strip()}'"
            event_bus.task_log_updated.emit("Memory Tool", msg)
            return msg

        # 2. Read Memories
        elif clean_mode == "read":
            if not memories:
                return "ยังไม่มีข้อมูลที่บันทึกไว้ในความจำระยะยาวครับบอส"

            formatted = []
            for item in memories[-20:]:  # Return up to 20 recent facts
                formatted.append(f"[{item.get('timestamp', '')}] {item.get('content', '')}")

            summary = f"ข้อมูลความจำระยะยาวของ Jarvis ({len(memories)} รายการ):\n" + "\n".join(formatted)
            event_bus.task_log_updated.emit("Memory Tool", f"ดึงข้อมูลความจำ {len(memories)} รายการสำเร็จ")
            return summary

        else:
            return f"ไม่รู้จักโหมด '{mode}' สำหรับ manage_memory ครับ"

    except Exception as e:
        err_msg = f"เกิดข้อผิดพลาดในการจัดการความจำ: {str(e)}"
        event_bus.task_log_updated.emit("Memory Error", err_msg)
        return err_msg


# ============================================================================
# 5. reveal_task_result
# ============================================================================
def reveal_task_result(task_ref: str = "latest") -> str:
    """
    Reveals and opens the output, files, app window, or results of a completed background task on screen.
    CRITICAL: ONLY invoke this tool when the user EXPLICITLY asks to open, view, inspect, or reveal completed work
    (e.g., 'เปิดดูไฟล์ที่แก้หน่อย', 'เปิดผลงานล่าสุด', 'ขอดูผลหน่อย', 'เปิด Antigravity', 'reveal task').
    NEVER call this tool automatically right after a task is finished in the background.

    Args:
        task_ref: Reference to the task ('latest', task_id, or keyword matching task title/file). Defaults to 'latest'.
    """
    from core.task_manager import task_manager
    event_bus.task_log_updated.emit("Reveal Tool", f"กำลังเปิดดูผลงานที่อ้างอิง: '{task_ref}'")
    return task_manager.reveal_task(task_ref)


# ============================================================================
# 6. search_raw_history
# ============================================================================
def search_raw_history(query: str, days_back: int = 365) -> str:
    """
    Searches long-term historical raw archives across months/years for past tasks,
    modified files, previous code outputs, or historical execution records.
    CRITICAL: Use this tool ONLY when the user asks about past tasks, previous project work,
    or historical records (e.g., 'งานเก่าที่เราเคยทำเมื่อเดือนก่อน', 'ประวัติไฟล์ที่เคยแก้').

    Args:
        query: Keywords or search query to look for in past archives.
        days_back: How many days back to search across monthly archives (default 365).
    """
    from core.raw_archive import raw_archive
    event_bus.task_log_updated.emit("Raw Archive", f"กำลังค้นหาประวัติย้อนหลัง: '{query}' ({days_back} วัน)")

    records = raw_archive.search_archive(query=query, days_back=days_back, limit=5)
    if not records:
        return f"ไม่พบประวัติข้อมูลดิบหรือผลงานเก่าที่ตรงกับคำค้นหา '{query}' ในรอบ {days_back} วันที่ผ่านมาครับบอส"

    # Emit raw payload to Process & Raw viewer
    event_bus.raw_data_received.emit(
        f"Raw History: '{query}'",
        json.dumps(records, ensure_ascii=False, indent=2)
    )

    # Format structured numbered list for model context
    formatted_items = []
    for idx, rec in enumerate(records, start=1):
        ts = rec.get("timestamp", "")
        title = rec.get("task_title", "")
        summary = rec.get("summary", "")
        paths = rec.get("related_paths", [])
        paths_str = f" | พาธไฟล์: {', '.join(paths)}" if paths else ""
        formatted_items.append(f"[{idx}] {ts} - {title}: {summary}{paths_str}")

    return f"พบประวัติผลงานเก่าที่ตรงกับ '{query}' ({len(records)} รายการ):\n" + "\n".join(formatted_items)


# ============================================================================
# 7. click_on_screen
# ============================================================================
def click_on_screen(target_description: str, double_click: bool = False) -> str:
    """
    Captures the current macOS screen, uses Gemini Vision to identify the target element,
    and moves the mouse to click (or double-click) directly on it.
    Accurately calculates Retina display scaling factors for 100% precise click coordinates.

    Args:
        target_description: Visual description of the element to click (e.g. 'ปุ่มเล่นวิดีโอ', 'ช่องค้นหา', 'แท็บแรก', 'ปุ่มขยาย').
        double_click: Whether to perform a double click instead of a single click (default False).
    """
    global _genai_client, _current_model
    if not _genai_client:
        return "ยังไม่ได้เชื่อมต่อ Gemini Client ครับบอส"

    temp_screen_path = "/tmp/jarvis_click_screen.png"
    action_type = "ดับเบิลคลิก" if double_click else "คลิก"
    event_bus.task_log_updated.emit("Mouse Tool", f"กำลังจับภาพหน้าจอเพื่อค้นหาและ{action_type}: '{target_description}'")

    try:
        import pyautogui
        from PIL import Image

        # 1. Temporarily hide overlay chat for an unobstructed view
        event_bus.hide_overlay_signal.emit()
        time.sleep(0.2)

        # 2. Native macOS screencapture (-x = silent)
        subprocess.run(["screencapture", "-x", temp_screen_path], check=True, timeout=5)
        if not os.path.exists(temp_screen_path):
            return "ไม่สามารถบันทึกภาพหน้าจอได้ครับบอส"

        # 3. Compute screen dimensions & Retina scaling factors
        screen_w, screen_h = pyautogui.size()
        with Image.open(temp_screen_path) as img:
            img_w, img_h = img.size

        scale_x = img_w / screen_w
        scale_y = img_h / screen_h

        with open(temp_screen_path, "rb") as f:
            image_bytes = f.read()

        try:
            os.remove(temp_screen_path)
        except Exception:
            pass

        # 4. Prompt Gemini Vision for exact pixel coordinates
        prompt = (
            f"You are an expert macOS GUI automation agent.\n"
            f"Identify the exact clickable center coordinate of the element described as: \"{target_description}\".\n"
            f"CRITICAL TARGETING RULES:\n"
            f"1. If the user asks to click a video, song, link, or article (e.g. 'วิดีโอแรก', 'เพลงแรก', 'YouTube video', 'คลิปแรกใน Firefox'):\n"
            f"   - Target the exact center of the video thumbnail (ภาพปกวิดีโอ) or the primary title/headline link that directly triggers playback or opens the item.\n"
            f"   - Avoid unclickable blank spaces, small metadata badges, or duration timestamps.\n"
            f"2. For buttons, tabs, or input boxes, target the geometric center of the clickable bounding box.\n"
            f"The image resolution is {img_w} pixels wide by {img_h} pixels high.\n"
            f"Output ONLY a valid JSON object in this exact format:\n"
            f"{{\n"
            f"  \"found\": true,\n"
            f"  \"x\": <pixel_x_number>,\n"
            f"  \"y\": <pixel_y_number>,\n"
            f"  \"description\": \"<brief element description>\"\n"
            f"}}\n"
            f"If the element is not found on screen, output:\n"
            f"{{\n"
            f"  \"found\": false,\n"
            f"  \"reason\": \"<explanation why not found>\"\n"
            f"}}\n"
            f"DO NOT include markdown fences or any explanation outside the JSON."
        )

        response = _genai_client.models.generate_content(
            model=_current_model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                prompt
            ]
        )

        raw_resp = response.text or ""
        clean_json = re.sub(r'```(?:json)?', '', raw_resp).strip('` \n')

        try:
            data = json.loads(clean_json)
        except Exception:
            json_match = re.search(r'\{.*\}', raw_resp, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
            else:
                return f"ไม่สามารถประมวลผลพิกัดจากภาพหน้าจอได้ครับ: {raw_resp[:120]}"

        if not data.get("found"):
            reason = data.get("reason", "ไม่พบองค์ประกอบดังกล่าวบนหน้าจอ")
            event_bus.task_log_updated.emit("Mouse Tool", f"ไม่พบเป้าหมาย: {reason}")
            return f"ไม่พบเป้าหมาย '{target_description}' บนหน้าจอครับ: {reason}"

        pixel_x = float(data["x"])
        pixel_y = float(data["y"])

        # 5. Convert physical image pixels to logical screen points
        click_x = int(pixel_x / scale_x)
        click_y = int(pixel_y / scale_y)

        # Clamp within screen bounds
        click_x = max(0, min(screen_w - 1, click_x))
        click_y = max(0, min(screen_h - 1, click_y))

        # 6. Execute mouse click with Inactive Window Focus handling
        # On macOS, clicking an inactive window (e.g. background Firefox/Safari/Chrome) only activates the window on the first click.
        # We perform an initial focus/activation click, wait 0.15s for the window to gain focus, then perform the actual click.
        pyautogui.moveTo(click_x, click_y, duration=0.2)
        
        # Initial focus click to bring inactive window forward
        pyautogui.click(click_x, click_y)
        time.sleep(0.15)

        # Action click on the now-active window
        if double_click:
            pyautogui.doubleClick(click_x, click_y)
        else:
            pyautogui.click(click_x, click_y)

        detected_desc = data.get("description", target_description)
        res_msg = f"{action_type}ที่ '{detected_desc}' (พิกัด {click_x}, {click_y}) เรียบร้อยแล้วครับบอส"
        event_bus.task_log_updated.emit("Mouse Tool", res_msg)
        return res_msg

    except Exception as e:
        err = f"เกิดข้อผิดพลาดในการคลิกบนหน้าจอ: {e}"
        event_bus.task_log_updated.emit("Mouse Error", err)
        return err


# ============================================================================
# 8. type_text_on_screen
# ============================================================================
def type_text_on_screen(text: str, press_enter: bool = False) -> str:
    """
    Types text into the currently focused window, text box, or application on macOS.
    Supports both Thai and English characters fully via the macOS clipboard mechanism.

    Args:
        text: Text string to type into the focused element.
        press_enter: Whether to press Enter/Return after typing (default False).
    """
    if not text:
        return "ไม่มีข้อความสำหรับพิมพ์ครับบอส"

    event_bus.task_log_updated.emit("Keyboard Tool", f"กำลังพิมพ์ข้อความ: '{text[:60]}...'")

    try:
        import pyautogui

        # 1. Backup previous clipboard content
        orig_clip = b""
        try:
            orig_clip = subprocess.run(["pbpaste"], capture_output=True, timeout=2).stdout
        except Exception:
            pass

        # 2. Copy target text to clipboard
        p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
        p.communicate(text.encode("utf-8"))

        # 3. Paste reliably with Cmd+V (handles Thai, Unicode, emojis, special characters)
        time.sleep(0.1)
        pyautogui.hotkey("command", "v")
        time.sleep(0.15)

        # 4. Optional Enter key
        if press_enter:
            pyautogui.press("enter")
            time.sleep(0.1)

        # 5. Restore previous clipboard content asynchronously
        def _restore():
            time.sleep(0.5)
            try:
                rp = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
                rp.communicate(orig_clip)
            except Exception:
                pass

        threading.Thread(target=_restore, daemon=True).start()

        enter_msg = " และกด Enter" if press_enter else ""
        res_msg = f"พิมพ์ข้อความ '{text}'{enter_msg} ลงในช่องที่เลือกเรียบร้อยแล้วครับบอส"
        event_bus.task_log_updated.emit("Keyboard Tool", res_msg)
        return res_msg

    except Exception as e:
        err = f"เกิดข้อผิดพลาดในการพิมพ์ข้อความ: {e}"
        event_bus.task_log_updated.emit("Keyboard Error", err)
        return err


# ============================================================================
# 9. click_and_type
# ============================================================================
def click_and_type(target_description: str, text: str, press_enter: bool = False) -> str:
    """
    Single-step GUI automation: Locates target element on screen via Gemini Vision,
    clicks it to focus, and immediately types the specified text (supporting Thai and English).
    Ideal for commands like 'คลิกที่ช่องค้นหาแล้วพิมพ์ Love 3000' or 'คลิกช่องแชทแล้วพิมพ์สวัสดี'.

    Args:
        target_description: Visual description of the target field to click (e.g. 'ช่องแชท', 'search bar').
        text: The text to type into the field once clicked.
        press_enter: Whether to press Enter after typing (default False).
    """
    click_res = click_on_screen(target_description=target_description, double_click=False)
    if "ไม่พบเป้าหมาย" in click_res or "เกิดข้อผิดพลาด" in click_res:
        return f"ไม่สามารถพิมพ์ได้เนื่องจาก: {click_res}"

    time.sleep(0.35)  # Allow focus to settle
    type_res = type_text_on_screen(text=text, press_enter=press_enter)
    return f"คลิกที่ '{target_description}' สำเร็จ และ{type_res}"


# ============================================================================
# 10. manage_todo
# ============================================================================
def manage_todo(action: str, text: Optional[str] = None, item_id: Optional[int] = None) -> str:
    """
    Manages persistent user todo items and reminders in memory/todo_items.json.
    Supported actions: 'add', 'list', 'complete', 'remove'.

    Args:
        action: The operation to perform ('add', 'list', 'complete', 'remove').
        text: The todo description text (required for 'add').
        item_id: The integer ID of the todo item (required for 'complete' or 'remove').
    """
    def _load_todos() -> List[Dict[str, Any]]:
        if not TODO_ITEMS_FILE.exists():
            return []
        try:
            with open(TODO_ITEMS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_todos(items: List[Dict[str, Any]]):
        TODO_ITEMS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TODO_ITEMS_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

    clean_action = (action or "").strip().lower()
    todos = _load_todos()

    if clean_action == "add":
        if not text or not text.strip():
            return "ข้อผิดพลาด: กรุณาระบุข้อความสิ่งที่ต้องการให้จำในพารามิเตอร์ text"
        new_item = {
            "id": int(time.time() * 1000),
            "text": text.strip(),
            "done": False,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        todos.insert(0, new_item)
        _save_todos(todos)
        event_bus.todo_updated.emit()
        msg = f"บันทึกสิ่งที่ต้องทำ: '{text.strip()}' เรียบร้อยแล้วครับบอส"
        event_bus.task_log_updated.emit("Todo Tool", msg)
        return msg

    elif clean_action == "list":
        if not todos:
            return "ขณะนี้ไม่มีรายการ Todo ค้างอยู่ครับบอส"
        lines = ["📌 รายการ Live Todo ทั้งหมด:"]
        for t in todos:
            status = "✓ [เสร็จแล้ว]" if t.get("done") else "○ [ค้างอยู่]"
            lines.append(f"- ID {t.get('id')}: {status} {t.get('text')}")
        return "\n".join(lines)

    elif clean_action in ("complete", "uncomplete", "toggle"):
        if item_id is None:
            # If item_id not provided, match by text substring if text provided
            matched = False
            if text:
                for t in todos:
                    if text.strip().lower() in t.get("text", "").lower():
                        if clean_action == "complete" and t.get("done"):
                            continue
                        if clean_action == "uncomplete" and not t.get("done"):
                            continue
                        t["done"] = (not t.get("done")) if clean_action == "toggle" else (clean_action == "complete")
                        matched = True
                        item_id = t.get("id")
                        break
            if not matched:
                return "ข้อผิดพลาด: กรุณาระบุ item_id ของงานที่ต้องการอัปเดต"
        else:
            found = False
            for t in todos:
                if t.get("id") == item_id:
                    t["done"] = (not t.get("done")) if clean_action == "toggle" else (clean_action == "complete")
                    found = True
                    break
            if not found:
                return f"ไม่พบรายการ Todo ที่มี ID {item_id}"

        _save_todos(todos)
        event_bus.todo_updated.emit()
        is_now_done = next((bool(x.get("done")) for x in todos if x.get("id") == item_id), True)
        msg = f"ติ๊กทำรายการ ID {item_id} {'เสร็จเรียบร้อย' if is_now_done else 'กลับมาเป็นค้างอยู่'} แล้วครับบอส"
        event_bus.task_log_updated.emit("Todo Tool", msg)
        return msg

    elif clean_action == "remove":
        if item_id is None:
            if text:
                initial_len = len(todos)
                todos = [t for t in todos if text.strip().lower() not in t.get("text", "").lower()]
                if len(todos) < initial_len:
                    _save_todos(todos)
                    event_bus.todo_updated.emit()
                    return f"ลบรายการที่ตรงกับ '{text}' เรียบร้อยแล้วครับบอส"
            return "ข้อผิดพลาด: กรุณาระบุ item_id ของงานที่ต้องการลบ"

        initial_len = len(todos)
        todos = [t for t in todos if t.get("id") != item_id]
        if len(todos) == initial_len:
            return f"ไม่พบรายการ Todo ที่มี ID {item_id}"

        _save_todos(todos)
        event_bus.todo_updated.emit()
        msg = f"ลบรายการ Todo ID {item_id} เรียบร้อยแล้วครับบอส"
        event_bus.task_log_updated.emit("Todo Tool", msg)
        return msg

    return f"ไม่รู้จักคำสั่ง '{action}' ใน manage_todo (รองรับเฉพาะ: add, list, complete, remove)"


# ============================================================================
# 11. ask_clarification
# ============================================================================
def ask_clarification(raw_stt: str, inferred_intent: str, question_text: str) -> str:
    """
    Deterministic Ambiguity Confirmation Tool:
    Invoked when user speech is garbled, noisy, or ambiguous.
    Records pending confirmation in workflow state and displays interactive confirmation card on HUD.
    Never recites the distorted words aloud.

    Args:
        raw_stt: The raw distorted phonetic transcript captured by STT.
        inferred_intent: The best logical intent inferred by the AI brain.
        question_text: The polite clarifying question proposing the inferred action to the user.
    """
    try:
        from core.brain import set_pending_confirmation
        set_pending_confirmation(raw_stt=raw_stt, inferred_intent=inferred_intent)
    except Exception as e:
        print(f"[Tools] Note setting pending confirmation: {e}")

    event_bus.confirmation_requested.emit(raw_stt, inferred_intent, question_text)
    event_bus.task_log_updated.emit("Ambiguity Confirmation", f"ถามยืนยัน: '{question_text}'")
    return f"ระบบแสดงการ์ดยืนยันคำสั่ง: '{inferred_intent}' บนหน้าจอ พร้อมถามบอสว่า: '{question_text}'"


# ============================================================================
# Static Registry of Native macOS Tools
# ============================================================================
AVAILABLE_TOOLS = [
    delegate_to_antigravity,
    analyze_current_screen,
    control_mac_system,
    manage_memory,
    reveal_task_result,
    search_raw_history,
    click_on_screen,
    type_text_on_screen,
    click_and_type,
    manage_todo,
    ask_clarification,
]

# Quick dispatch lookup map for native tools
TOOL_MAP = {func.__name__: func for func in AVAILABLE_TOOLS}
