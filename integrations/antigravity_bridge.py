"""
Antigravity Bridge Integration for Jarvis Desktop Assistant.
100% Silent Background File-Bridge with Atomic File Write & Deduplication Guard.
Monitors .jarvis_result.md using Watchdog for asynchronous completion.
"""

import os
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
    Operates 100% silently in background without stealing screen focus.
    Includes Deduplication Guard to prevent rapid duplicate task triggers.
    """

    def __init__(self, on_result_callback: Optional[Callable[[str], None]] = None):
        self.on_result_callback = on_result_callback
        self.observer: Optional[Observer] = None
        self._watch_thread = None
        self._last_task_prompt: str = ""
        self._last_task_timestamp: float = 0.0
        self._task_lock = threading.Lock()
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
        Uses Atomic File Write and Deduplication Guard.
        """
        clean_prompt = task_prompt.strip()
        if not clean_prompt:
            return "ไม่พบคำสั่งงานสำหรับ Antigravity"

        now = time.time()
        with self._task_lock:
            # Deduplication Guard: Check if duplicate task within 60s or pending
            is_pending = config.TASK_FILE_PATH.exists() and not config.RESULT_FILE_PATH.exists()
            if self._last_task_prompt and (now - self._last_task_timestamp < 60.0 or is_pending):
                is_similar = False
                if clean_prompt.lower() == self._last_task_prompt.lower():
                    is_similar = True
                else:
                    try:
                        from rapidfuzz import fuzz
                        ratio = fuzz.WRatio(clean_prompt.lower(), self._last_task_prompt.lower())
                        if ratio >= 80.0:
                            is_similar = True
                    except Exception:
                        if clean_prompt[:40].lower() == self._last_task_prompt[:40].lower():
                            is_similar = True

                if is_similar:
                    dup_msg = "งานนี้ถูกส่งไปยัง Antigravity เรียบร้อยแล้วและกำลังดำเนินการอยู่เบื้องหลัง กรุณารอผลลัพธ์สักครู่ (ไม่ต้องส่งคำสั่งซ้ำ)"
                    print(f"[Bridge] 🛡️ Duplicate task blocked by Deduplication Guard: \"{clean_prompt[:40]}...\"")
                    event_bus.task_log_updated.emit("Bridge Deduplication", dup_msg)
                    return dup_msg

            self._last_task_prompt = clean_prompt
            self._last_task_timestamp = now

        event_bus.task_log_updated.emit(
            "Delegating to Antigravity (Stealth Background)",
            f"Task: {clean_prompt}\nTarget File: {config.TASK_FILE_PATH}"
        )

        # Clear previous result file to avoid stale triggers
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
            f"{clean_prompt}\n\n"
            f"---\n"
            f"### คำแนะนำสำหรับ Antigravity Agent:\n"
            f"1. ดำเนินการตามคำสั่งข้างต้นใน Workspace ให้เสร็จสมบูรณ์\n"
            f"2. เมื่อดำเนินการเสร็จสิ้น ให้เขียนสรุปผลลัพธ์และความคืบหน้าลงในไฟล์ `{config.RESULT_FILE_NAME}` โดยตรง เพื่อให้ Jarvis รับทราบผลลัพธ์\n"
        )

        # Atomic File Write (.tmp + os.replace)
        tmp_task_file = config.TASK_FILE_PATH.with_suffix(".tmp")
        try:
            tmp_task_file.write_text(task_markdown, encoding="utf-8")
            os.replace(tmp_task_file, config.TASK_FILE_PATH)
        except Exception as e:
            if tmp_task_file.exists():
                try:
                    tmp_task_file.unlink()
                except Exception:
                    pass
            err = f"ไม่สามารถเขียนไฟล์งาน {config.TASK_FILE_NAME} ได้: {str(e)}"
            event_bus.task_log_updated.emit("Bridge Error", err)
            return err

        # Record in TaskManager as running background task
        task_manager.record_task(
            title=f"งาน Antigravity: {clean_prompt[:35]}...",
            summary=f"ส่งคำสั่งให้ Antigravity ผ่าน {config.TASK_FILE_NAME} กำลังรอผลลัพธ์ในเบื้องหลัง",
            files_affected=[str(config.TASK_FILE_PATH), str(config.RESULT_FILE_PATH)],
            app_or_url="Antigravity",
            command_or_prompt=clean_prompt,
            status="running"
        )

        msg = (
            f"ส่งต่องานไปยัง Antigravity ในเบื้องหลังผ่านไฟล์ {config.TASK_FILE_NAME} เรียบร้อยแล้วครับ "
            f"โดยไม่รบกวนหน้าจอของบอส ระบบกำลังเฝ้ารอผลลัพธ์ที่ {config.RESULT_FILE_NAME} ครับ"
        )
        event_bus.task_log_updated.emit("Task Dispatched", msg)
        return msg
