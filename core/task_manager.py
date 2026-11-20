"""
Task Manager module for Jarvis Desktop Assistant.
Records background task executions, affected files, and completion statuses to memory/background_tasks.json.
Provides on-demand revealing of completed work (e.g. opening files in default editor or Finder,
opening URLs or activating apps) ONLY when explicitly requested by the user.
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from core.event_bus import event_bus

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEMORY_DIR = PROJECT_ROOT / "memory"
TASKS_FILE = MEMORY_DIR / "background_tasks.json"


class TaskManager:
    """
    Manages background task registry and on-demand artifact revealing.
    """

    def __init__(self, file_path: Optional[Path] = None):
        self.file_path = file_path or TASKS_FILE
        self._ensure_storage()

    def _ensure_storage(self):
        """Ensures the storage file exists with valid JSON array."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            try:
                with open(self.file_path, "w", encoding="utf-8") as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"[TaskManager] Error initializing {self.file_path}: {e}")

    def _load_tasks(self) -> List[Dict[str, Any]]:
        """Loads task history from JSON file."""
        if not self.file_path.exists():
            return []
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[TaskManager] Error loading tasks: {e}")
            return []

    def _save_tasks(self, tasks: List[Dict[str, Any]]):
        """Saves task list to JSON file."""
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[TaskManager] Error saving tasks: {e}")

    def record_task(
        self,
        title: str,
        summary: str,
        files_affected: Optional[List[str]] = None,
        app_or_url: Optional[str] = None,
        details: str = "",
        command_or_prompt: str = "",
        status: str = "completed"
    ) -> Dict[str, Any]:
        """
        Records a completed or running background task.
        Returns the created task dictionary.
        """
        tasks = self._load_tasks()
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(tasks)+1}"

        # Clean file paths to string
        clean_files = []
        if files_affected:
            for f in files_affected:
                if f and isinstance(f, (str, Path)):
                    clean_files.append(str(f))

        entry = {
            "task_id": task_id,
            "title": title.strip(),
            "command_or_prompt": command_or_prompt.strip(),
            "summary": summary.strip(),
            "files_affected": clean_files,
            "app_or_url": (app_or_url or "").strip(),
            "status": status,
            "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "revealed": False,
            "details": details.strip()
        }

        tasks.append(entry)
        # Keep recent 50 tasks
        if len(tasks) > 50:
            tasks = tasks[-50:]

        self._save_tasks(tasks)
        print(f"[TaskManager] 📝 Recorded background task '{title}' ({task_id})")
        event_bus.task_log_updated.emit("Task Manager", f"บันทึกผลงานเบื้องหลัง: {title} ({task_id})")
        return entry

    def get_latest_task(self, only_unrevealed: bool = False) -> Optional[Dict[str, Any]]:
        """Returns the most recent task, optionally filtering for unrevealed ones."""
        tasks = self._load_tasks()
        if not tasks:
            return None
        if only_unrevealed:
            for t in reversed(tasks):
                if not t.get("revealed", False):
                    return t
        return tasks[-1]

    def find_task(self, task_ref: str) -> Optional[Dict[str, Any]]:
        """
        Finds a task by ID, keyword, or filename.
        Defaults to latest task if reference is 'latest', 'ล่าสุด', or empty.
        """
        tasks = self._load_tasks()
        if not tasks:
            return None

        clean_ref = (task_ref or "").strip().lower()
        if clean_ref in ("latest", "last", "ล่าสุด", ""):
            return tasks[-1]

        # By exact task_id
        for t in reversed(tasks):
            if t.get("task_id", "").lower() == clean_ref:
                return t

        # By keyword in title, summary, or affected files
        for t in reversed(tasks):
            if clean_ref in t.get("title", "").lower() or clean_ref in t.get("summary", "").lower():
                return t
            for f in t.get("files_affected", []):
                if clean_ref in Path(f).name.lower():
                    return t

        return tasks[-1]

    def reveal_task(self, task_ref: str = "latest") -> str:
        """
        Reveals/opens artifacts associated with a background task:
        - Opens files in default application (or reveals in Finder)
        - Opens URL in default browser or activates application window
        - Marks task as revealed (revealed = True)
        """
        tasks = self._load_tasks()
        if not tasks:
            return "ยังไม่มีประวัติงานเบื้องหลังในระบบครับบอส"

        target_task = self.find_task(task_ref)
        if not target_task:
            return f"ไม่พบข้อมูลงานที่อ้างอิง '{task_ref}' ครับบอส"

        opened_items = []
        failed_items = []
        files = target_task.get("files_affected", [])
        app_or_url = target_task.get("app_or_url", "")

        # 1. Open affected files if any exist
        if files:
            for file_path_str in files:
                expanded = os.path.expanduser(file_path_str)
                p = Path(expanded)
                if not p.is_absolute():
                    p = PROJECT_ROOT / p

                if not p.exists():
                    failed_items.append(f"{p.name} (ไม่พบไฟล์ที่ {p})")
                    continue

                try:
                    if sys.platform == "darwin":
                        res = subprocess.run(["open", str(p)], capture_output=True, text=True, timeout=5)
                        if res.returncode == 0:
                            opened_items.append(p.name)
                        else:
                            failed_items.append(f"{p.name} (เกิดข้อผิดพลาด: {res.stderr.strip()})")
                    else:
                        os.system(f"start {p}")
                        opened_items.append(p.name)
                except Exception as e:
                    failed_items.append(f"{p.name} ({str(e)})")

        # 2. Open App or URL if specified
        if app_or_url:
            if app_or_url.startswith("http://") or app_or_url.startswith("https://"):
                try:
                    res = subprocess.run(["open", app_or_url], capture_output=True, text=True, timeout=5)
                    if res.returncode == 0:
                        opened_items.append(f"URL ({app_or_url})")
                    else:
                        failed_items.append(f"URL ({res.stderr.strip()})")
                except Exception as e:
                    failed_items.append(f"URL ({str(e)})")
            elif app_or_url.lower() in ("antigravity", "antigravity ide"):
                # Activate Antigravity IDE window
                try:
                    from integrations.antigravity_bridge import focus_antigravity_window
                    if focus_antigravity_window():
                        opened_items.append("หน้าต่าง Antigravity IDE")
                    else:
                        failed_items.append("ไม่พบหน้าต่าง Antigravity IDE บน macOS")
                except Exception as e:
                    failed_items.append(f"หน้าต่าง Antigravity ({str(e)})")
            else:
                try:
                    res = subprocess.run(["open", "-a", app_or_url], capture_output=True, text=True, timeout=5)
                    if res.returncode == 0:
                        opened_items.append(f"แอป {app_or_url}")
                    else:
                        failed_items.append(f"แอป {app_or_url} ({res.stderr.strip()})")
                except Exception as e:
                    failed_items.append(f"แอป {app_or_url} ({str(e)})")

        # Mark as revealed only if at least one item was opened or there were no files
        if opened_items or (not files and not app_or_url):
            target_id = target_task.get("task_id")
            for t in tasks:
                if t.get("task_id") == target_id:
                    t["revealed"] = True
                    break
            self._save_tasks(tasks)

        title = target_task.get("title", "งานเบื้องหลัง")
        summary = target_task.get("summary", "")

        msg_parts = []
        if opened_items:
            msg_parts.append(f"เปิดผลลัพธ์ของ '{title}' ({', '.join(opened_items)}) ขึ้นมาบนหน้าจอเรียบร้อยแล้วครับบอส\nสรุปงาน: {summary}")
        if failed_items:
            msg_parts.append(f"รายการที่ไม่สามารถเปิดได้: {', '.join(failed_items)}")
        if not opened_items and not failed_items:
            msg_parts.append(f"รายละเอียดผลงาน '{title}':\n{summary}\n(หมายเหตุ: งานนี้ไม่มีไฟล์หรือหน้าต่างแอปพลิเคชันที่ต้องเปิดครับ)")

        res_msg = "\n".join(msg_parts)
        event_bus.task_log_updated.emit("Task Revealed", res_msg)
        return res_msg

        event_bus.task_log_updated.emit("Task Revealed", res_msg)
        return res_msg


# Singleton instance
task_manager = TaskManager()
