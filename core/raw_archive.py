"""
Long-term Raw Data Archive module for Jarvis Desktop Assistant.
Stores rich raw data, tool outputs, and historical execution records into
monthly partitioned JSON Lines files: memory/raw_archive/YYYY-MM.jsonl.
Preserves records long-term (365+ days) without bloating the active chat history.
"""

import os
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = PROJECT_ROOT / "memory" / "raw_archive"


class RawArchive:
    """
    Manages long-term structured raw data archives partitioned by month.
    """

    def __init__(self, archive_dir: Optional[Path] = None):
        self.archive_dir = archive_dir or ARCHIVE_DIR
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def _get_month_file(self, dt: Optional[datetime] = None) -> Path:
        """Returns the file path for the given date's monthly archive (YYYY-MM.jsonl)."""
        dt = dt or datetime.now()
        filename = f"{dt.strftime('%Y-%m')}.jsonl"
        return self.archive_dir / filename

    def archive_record(
        self,
        task_title: str,
        summary: str,
        raw_output: str,
        related_paths: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Appends a new structured record to the current month's archive file.
        """
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        record_id = f"raw_{now.strftime('%Y%m%d_%H%M%S')}_{int(time.time() * 1000) % 1000}"

        clean_paths = []
        if related_paths:
            for p in related_paths:
                if p:
                    clean_paths.append(str(p))

        clean_keywords = []
        if keywords:
            clean_keywords = [k.strip().lower() for k in keywords if k and k.strip()]

        # Auto-extract keywords from title if not provided (enhanced with Thai tokenization)
        if not clean_keywords:
            try:
                from core.thai_nlp import tokenize_for_search
                clean_keywords = tokenize_for_search(task_title)[:8]
            except Exception:
                words = [w for w in task_title.replace(":", " ").replace("/", " ").split() if len(w) > 2]
                clean_keywords = list(dict.fromkeys(words))[:8]

        record = {
            "id": record_id,
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "task_title": task_title.strip(),
            "keywords": clean_keywords,
            "summary": summary.strip(),
            "related_paths": clean_paths,
            "raw_output": raw_output.strip()
        }

        target_file = self._get_month_file(now)
        try:
            with open(target_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(f"[RawArchive] 📦 Archived record '{task_title}' to {target_file.name}")
        except Exception as e:
            print(f"[RawArchive] Error saving archive record: {e}")

        return record

    def search_archive(self, query: str, days_back: int = 365, limit: int = 6) -> List[Dict[str, Any]]:
        """
        Searches records from the past `days_back` days matching the query.
        Matches against task_title, summary, keywords, and related_paths.
        """
        if not self.archive_dir.exists():
            return []

        clean_query = query.strip().lower()
        query_terms = [t for t in clean_query.split() if t]

        # Expand query terms with Thai segmentation if available
        try:
            from core.thai_nlp import tokenize_for_search
            thai_tokens = tokenize_for_search(clean_query)
            query_terms = list(dict.fromkeys(query_terms + thai_tokens))
        except Exception:
            pass

        if not query_terms:
            return []

        cutoff_date = datetime.now() - timedelta(days=max(1, days_back))
        results: List[Dict[str, Any]] = []

        # Find all .jsonl files in reverse chronological order
        jsonl_files = sorted(self.archive_dir.glob("*.jsonl"), reverse=True)

        for file_path in jsonl_files:
            # Check file year-month prefix
            file_name = file_path.stem  # e.g. "2026-11"
            try:
                file_dt = datetime.strptime(file_name, "%Y-%m")
                # If file's month is older than cutoff's month, we can stop
                if file_dt.year < cutoff_date.year or (file_dt.year == cutoff_date.year and file_dt.month < cutoff_date.month):
                    break
            except Exception:
                pass

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                for line in reversed(lines):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        rec_ts_str = record.get("timestamp", "")
                        try:
                            rec_dt = datetime.strptime(rec_ts_str, "%Y-%m-%d %H:%M:%S")
                            if rec_dt < cutoff_date:
                                continue
                        except Exception:
                            pass

                        # Search matching
                        text_to_search = (
                            record.get("task_title", "") + " " +
                            record.get("summary", "") + " " +
                            " ".join(record.get("keywords", [])) + " " +
                            " ".join(record.get("related_paths", []))
                        ).lower()

                        if any(term in text_to_search for term in query_terms):
                            results.append(record)
                            if len(results) >= limit:
                                return results
                    except Exception:
                        continue

            except Exception as e:
                print(f"[RawArchive] Note reading {file_path.name}: {e}")

        return results

    def get_recent_records(self, limit: int = 25) -> List[Dict[str, Any]]:
        """Returns the most recent raw records across archive files."""
        if not self.archive_dir.exists():
            return []

        results: List[Dict[str, Any]] = []
        jsonl_files = sorted(self.archive_dir.glob("*.jsonl"), reverse=True)

        for file_path in jsonl_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                for line in reversed(lines):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        results.append(json.loads(line))
                        if len(results) >= limit:
                            return results
                    except Exception:
                        pass
            except Exception:
                pass

        return results


# Singleton instance
raw_archive = RawArchive()
