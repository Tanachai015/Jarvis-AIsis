"""
Static Tool Registry for Jarvis Desktop Assistant.
Pre-registers all 5 standard tools once at startup for fast execution and minimal token overhead:
1. delegate_to_antigravity: Hands off coding/refactoring tasks to Antigravity IDE Agent.
2. analyze_current_screen: Captures desktop via screencapture and analyzes with Gemini Vision.
3. control_mac_system: Controls macOS apps, URLs, audio volume, and inspects system resources.
4. manage_project_files: Lists directory contents and safely reads project files (up to 15,000 chars).
5. manage_memory: Stores and retrieves persistent long-term memories across sessions.
"""

import os
import sys
import json
import time
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
def control_mac_system(action: str, target: str = "") -> str:
    """
    Controls macOS system settings, applications, URLs, or inspects machine hardware status.

    Args:
        action: System operation to perform:
                - "open_app": Launches or focuses an application (e.g. target="Safari", target="Terminal")
                - "open_url": Opens a web URL in the default browser (e.g. target="google.com")
                - "set_volume": Sets speaker output volume 0-100 (e.g. target="50")
                - "get_system_info": Checks current CPU, RAM, and Battery percentage.
        target: Parameter for the action (app name, URL, or volume number).
    """
    clean_action = action.lower().strip()
    clean_target = target.strip()

    try:
        # 1. Open Application
        if clean_action == "open_app":
            if not clean_target:
                return "กรุณาระบุชื่อแอปพลิเคชันที่ต้องการเปิดครับบอส"
            res = subprocess.run(["open", "-a", clean_target], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                msg = f"เปิดแอปพลิเคชัน '{clean_target}' เรียบร้อยแล้วครับบอส"
                event_bus.task_log_updated.emit("System Control", msg)
                return msg
            else:
                return f"ไม่สามารถเปิดแอป '{clean_target}' ได้: {res.stderr.strip()}"

        # 2. Open URL
        elif clean_action == "open_url":
            if not clean_target:
                return "กรุณาระบุ URL ที่ต้องการเปิดครับบอส"
            url = clean_target if clean_target.startswith(("http://", "https://")) else f"https://{clean_target}"
            subprocess.run(["open", url], check=True, timeout=5)
            msg = f"เปิดลิงก์ {url} ในเบราว์เซอร์เรียบร้อยแล้วครับบอส"
            event_bus.task_log_updated.emit("System Control", msg)
            return msg

        # 3. Set Volume (0 - 100)
        elif clean_action == "set_volume":
            try:
                # Extract digits
                vol_int = int(''.join(c for c in clean_target if c.isdigit()))
                vol = max(0, min(100, vol_int))
            except Exception:
                vol = 50
            cmd = ["osascript", "-e", f"set volume output volume {vol}"]
            subprocess.run(cmd, check=True, timeout=5)
            msg = f"ปรับระดับเสียงเป็น {vol}% เรียบร้อยแล้วครับบอส"
            event_bus.task_log_updated.emit("System Control", msg)
            return msg

        # 4. Get System Info (CPU, RAM, Battery)
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
                # Fallback to macOS pmset
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
# Static Registry of Native macOS Tools
# ============================================================================
AVAILABLE_TOOLS = [
    delegate_to_antigravity,
    analyze_current_screen,
    control_mac_system,
    manage_memory,
]

# Quick dispatch lookup map for native tools
TOOL_MAP = {func.__name__: func for func in AVAILABLE_TOOLS}
