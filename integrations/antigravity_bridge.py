"""
Antigravity Bridge Integration for Jarvis Desktop Assistant.
Optimized for macOS using native pbcopy and osascript (AppleScript),
with Watchdog file monitoring to track completion results.
"""

import sys
import time
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import config
from core.event_bus import event_bus
from core.task_manager import task_manager


def set_clipboard_text(text: str) -> bool:
    """Copies text to macOS clipboard using pbcopy, with fallback to pyperclip."""
    if sys.platform == "darwin":
        try:
            proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, close_fds=True)
            proc.communicate(input=text.encode("utf-8"))
            return proc.returncode == 0
        except Exception as e:
            print(f"[Bridge] pbcopy error: {e}")

    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception as e:
        print(f"[Bridge] Fallback clipboard error: {e}")
        return False


def focus_antigravity_window(app_title: str = config.ANTIGRAVITY_WINDOW_TITLE) -> bool:
    """
    Activates and focuses the Antigravity window using AppleScript on macOS.
    """
    if sys.platform != "darwin":
        print(f"[Bridge] Non-macOS platform ({sys.platform}) - Skipping AppleScript focus.")
        return True

    # Try activating the application directly or finding its process/window
    applescript = f'''
    try
        tell application "{app_title}" to activate
        return "true"
    on error
        tell application "System Events"
            set matched to (every process whose name contains "{app_title}")
            if (count of matched) > 0 then
                set frontmost of (item 1 of matched) to true
                return "true"
            end if
            repeat with p in (every process whose background only is false)
                try
                    repeat with w in (windows of p)
                        if name of w contains "{app_title}" then
                            set frontmost of p to true
                            return "true"
                        end if
                    end repeat
                end try
            end repeat
        end tell
        return "false"
    end try
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True,
            timeout=5
        )
        return "true" in result.stdout.lower()
    except Exception as e:
        print(f"[Bridge] Error focusing Antigravity via osascript: {e}")
        return False


def send_chat_shortcut_and_paste() -> bool:
    """
    Sends Cmd+L to open agent chat, Cmd+V to paste prompt, and Enter to submit
    using native macOS AppleScript.
    """
    if sys.platform != "darwin":
        # Fallback for other platforms using pyautogui
        try:
            import pyautogui
            pyautogui.hotkey("ctrl", "l")
            time.sleep(0.3)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.2)
            pyautogui.press("enter")
            return True
        except Exception as e:
            print(f"[Bridge] Cross-platform pyautogui error: {e}")
            return False

    applescript = '''
    tell application "System Events"
        delay 0.3
        keystroke "l" using {command down}
        delay 0.4
        keystroke "v" using {command down}
        delay 0.3
        key code 36 -- Return key
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception as e:
        print(f"[Bridge] Error sending keystrokes via osascript: {e}")
        return False


class ResultFileHandler(FileSystemEventHandler):
    """
    Watchdog event handler for monitoring changes to the Antigravity result file.
    """

    def __init__(self, target_filename: str, on_updated: Callable[[str], None]):
        super().__init__()
        self.target_filename = target_filename
        self.on_updated = on_updated
        self._last_processed_time = 0.0
        self._last_content_hash = None

    def on_modified(self, event):
        if event.is_directory:
            return
        if Path(event.src_path).name == self.target_filename:
            self._handle_file_change(event.src_path)

    def on_created(self, event):
        if event.is_directory:
            return
        if Path(event.src_path).name == self.target_filename:
            self._handle_file_change(event.src_path)

    def _handle_file_change(self, file_path: str):
        # Debounce rapid filesystem events within 1.5 seconds
        now = time.time()
        if now - self._last_processed_time < 1.5:
            return

        try:
            path = Path(file_path)
            if not path.exists():
                return
            content = path.read_text(encoding="utf-8").strip()
            if not content:
                return

            content_hash = hash(content)
            if content_hash == self._last_content_hash:
                return

            self._last_processed_time = now
            self._last_content_hash = content_hash
            self.on_updated(content)
        except Exception as e:
            print(f"[Bridge] Error reading updated result file: {e}")


class AntigravityBridge:
    """
    Coordinates delegation to Antigravity and watches for completion output.
    """

    def __init__(self, on_result_callback: Optional[Callable[[str], None]] = None):
        self.on_result_callback = on_result_callback
        self.observer: Optional[Observer] = None
        self._watch_thread = None
        self.start_watching()

    def start_watching(self):
        """Starts the watchdog observer to monitor .jarvis_result.md."""
        watch_dir = config.RESULT_FILE_PATH.parent
        watch_dir.mkdir(parents=True, exist_ok=True)

        handler = ResultFileHandler(
            target_filename=config.RESULT_FILE_NAME,
            on_updated=self._on_result_updated
        )

        try:
            self.observer = Observer()
            self.observer.schedule(handler, path=str(watch_dir), recursive=False)
            self.observer.daemon = True
            self.observer.start()
            print(f"[Bridge] Started watching for {config.RESULT_FILE_PATH}")
        except Exception as e:
            print(f"[Bridge] Failed to start watchdog observer: {e}")

    def stop_watching(self):
        """Stops the watchdog observer."""
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join(timeout=2)

    def _on_result_updated(self, content: str):
        """Called when .jarvis_result.md is updated."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_title = f"Antigravity Result ({timestamp})"
        event_bus.task_log_updated.emit(log_title, content)

        if self.on_result_callback:
            self.on_result_callback(content)

    def delegate_task(self, task_prompt: str) -> str:
        """
        Delegates the task to Antigravity 100% in the background without stealing screen focus.
        Writes the task instruction to .jarvis_task.md and waits for .jarvis_result.md via Watchdog.
        """
        event_bus.task_log_updated.emit(
            "Delegating to Antigravity (Stealth Background)",
            f"Task: {task_prompt}\nTarget File: {config.TASK_FILE_PATH}"
        )

        # Clear or prepare previous result file to avoid stale triggers
        try:
            if config.RESULT_FILE_PATH.exists():
                config.RESULT_FILE_PATH.unlink()
        except Exception as e:
            print(f"[Bridge] Warning clearing previous result file: {e}")

        # Construct markdown task file content
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        task_markdown = (
            f"# Jarvis Background Task\n\n"
            f"- **Dispatched At:** {now_str}\n"
            f"- **Target Result File:** `{config.RESULT_FILE_NAME}`\n"
            f"- **Stealth Execution:** ทำงานเบื้องหลัง 100% ไม่แย่งโฟกัสหน้าจอ\n\n"
            f"## คำสั่ง / Prompt:\n"
            f"{task_prompt.strip()}\n\n"
            f"---\n"
            f"### คำแนะนำสำหรับ Antigravity Agent:\n"
            f"1. ดำเนินการตามคำสั่งข้างต้นใน Workspace ให้เสร็จสมบูรณ์\n"
            f"2. เมื่อดำเนินการเสร็จสิ้น ให้เขียนสรุปผลลัพธ์และความคืบหน้าลงในไฟล์ `{config.RESULT_FILE_NAME}` โดยตรง เพื่อให้ Jarvis รับทราบผลลัพธ์\n"
        )

        try:
            config.TASK_FILE_PATH.write_text(task_markdown, encoding="utf-8")
        except Exception as e:
            err = f"ไม่สามารถเขียนไฟล์งาน {config.TASK_FILE_NAME} ได้: {str(e)}"
            event_bus.task_log_updated.emit("Bridge Error", err)
            return err

        # Record in TaskManager as running background task
        task_manager.record_task(
            title=f"งาน Antigravity: {task_prompt[:35]}...",
            summary=f"ส่งคำสั่งให้ Antigravity ผ่าน {config.TASK_FILE_NAME} กำลังรอผลลัพธ์ในเบื้องหลัง",
            files_affected=[str(config.TASK_FILE_PATH), str(config.RESULT_FILE_PATH)],
            app_or_url="Antigravity",
            command_or_prompt=task_prompt,
            status="running"
        )

        msg = (
            f"ส่งต่องานไปยัง Antigravity ในเบื้องหลังผ่านไฟล์ {config.TASK_FILE_NAME} เรียบร้อยแล้วครับ "
            f"โดยไม่รบกวนหน้าจอของบอส ระบบกำลังเฝ้ารอผลลัพธ์ที่ {config.RESULT_FILE_NAME} ครับ"
        )
        event_bus.task_log_updated.emit("Task Dispatched", msg)
        return msg
