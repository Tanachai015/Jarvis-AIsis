"""
Thai NLP Utilities module for Jarvis Desktop Assistant.

Provides lightweight, lazy-loaded Thai text processing:
1. prepare_thai_tts_text: Normalizes numbers, currencies (Baht), and natural clause pacing for Edge-TTS.
2. tokenize_for_search: Segments continuous Thai text into keywords for raw archive indexing and search.

All PyThaiNLP dependencies are 100% lazy-loaded to ensure sub-millisecond program boot time.
"""

import re
from typing import List, Optional


def prepare_thai_tts_text(text: str) -> str:
    """
    Normalizes Thai text for natural Edge-TTS speech synthesis:
    - Converts currency (e.g., 1,500 บาท -> หนึ่งพันห้าร้อยบาทถ้วน)
    - Converts standalone integers into Thai words (e.g., ในปี 2026 -> ในปี สองพันยี่สิบหก)
    - Protects technical tokens (ports, IPs, model names, versions, error codes)
    - Inserts subtle breathing pauses before major conjunctions (และ, หรือ, แต่, ดังนั้น)
    """
    if not text:
        return ""

    try:
        from pythainlp.util import num_to_thaiword, bahttext
    except ImportError:
        # Graceful fallback if pythainlp is not installed
        return text

    processed = text

    # 1. Convert Thai Baht Currency: e.g. 1,500 บาท -> หนึ่งพันห้าร้อยบาทถ้วน
    def _replace_baht(m):
        raw_num = m.group(1).replace(",", "")
        try:
            val = float(raw_num) if "." in raw_num else int(raw_num)
            return bahttext(val)
        except Exception:
            return m.group(0)

    processed = re.sub(
        r"(\b\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:บาท|THB)",
        _replace_baht,
        processed,
        flags=re.IGNORECASE
    )

    # 2. Protect technical strings from being converted to words
    protected: List[str] = []

    def _stash(m):
        protected.append(m.group(0))
        return f"__PROT_{len(protected) - 1}__"

    # IPs: 127.0.0.1, 192.168.1.1
    processed = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", _stash, processed)
    # Versions: v1.5.0, 1.5.0, v2
    processed = re.sub(r"\bv?\d+\.\d+(?:\.\d+)*\b", _stash, processed)
    # Ports and clock times: :8080, 07:15
    processed = re.sub(r":\d+", _stash, processed)
    # HTTP and error codes: HTTP 404, Error 500, port 8080, status 200
    processed = re.sub(
        r"\b(?:HTTP|Error|code|status|port|localhost)\s*[:=]?\s*\d+\b",
        _stash,
        processed,
        flags=re.IGNORECASE
    )
    # Frequencies and units attached to numbers: 16000Hz, 16kHz, 1080p, 4K, 60fps, M1, MP3, WAV
    processed = re.sub(r"\b\d+[a-zA-Z]+[a-zA-Z0-9]*\b", _stash, processed)
    processed = re.sub(r"\b[a-zA-Z]+\d+[a-zA-Z0-9]*\b", _stash, processed)

    # 3. Convert standalone integers into Thai words (e.g. 2026 -> สองพันยี่สิบหก, 5 รายการ -> ห้า รายการ)
    def _replace_standalone_num(m):
        raw_num = m.group(1).replace(",", "")
        try:
            val = int(raw_num)
            return f" {num_to_thaiword(val)} "
        except Exception:
            return m.group(0)

    processed = re.sub(
        r"(?<![a-zA-Z0-9_\.\:\-\/])(\d{1,3}(?:,\d{3})+|\d+)(?![a-zA-Z0-9_\.\:\-\/])",
        _replace_standalone_num,
        processed
    )

    # 4. Restore protected technical tokens
    for i, p in enumerate(protected):
        processed = processed.replace(f"__PROT_{i}__", p)

    # 5. Natural pacing: insert subtle breathing spaces before major conjunctions
    processed = re.sub(
        r"(?<=[\u0E00-\u0E7F])(และ|หรือ|แต่|ดังนั้น|เพราะว่า)(?=[\u0E00-\u0E7F])",
        r" \1 ",
        processed
    )

    # Normalize excessive spaces
    processed = re.sub(r"\s+", " ", processed).strip()
    return processed


def tokenize_for_search(text: str) -> List[str]:
    """
    Tokenizes continuous Thai and mixed text into meaningful keyword tokens for searching.
    Uses newmm engine with whitespace suppression and duplicate removal.
    """
    if not text:
        return []

    clean_text = text.strip().lower()
    try:
        from pythainlp.tokenize import word_tokenize
        tokens = word_tokenize(clean_text, engine="newmm", keep_whitespace=False)
        cleaned = [
            t.strip() for t in tokens
            if len(t.strip()) > 1 and not re.match(r"^[^\w\s]+$", t)
        ]
        return list(dict.fromkeys(cleaned))
    except Exception:
        # Fallback to simple whitespace splitting
        return [w for w in clean_text.split() if len(w) > 1]


def fuzzy_match_phrase(text: str, candidates: List[str], threshold: float = 80.0) -> Optional[str]:
    """
    Fuzzy matches text against a list of candidates using RapidFuzz.
    Returns the best matching candidate if similarity score >= threshold, else None.
    """
    if not text or not candidates:
        return None

    clean_text = text.strip()
    try:
        from rapidfuzz import process, fuzz
        res = process.extractOne(clean_text, candidates, scorer=fuzz.WRatio)
        if res and res[1] >= threshold:
            return res[0]
    except Exception:
        # Fallback to simple substring
        for c in candidates:
            if c.lower() in clean_text.lower():
                return c
    return None


_INSTALLED_APPS_CACHE: Optional[List[str]] = None

COMMON_APP_ALIASES = {
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "vscode": "Visual Studio Code",
    "vs code": "Visual Studio Code",
    "code": "Visual Studio Code",
    "firefox": "Firefox",
    "safari": "Safari",
    "terminal": "Terminal",
    "finder": "Finder",
    "spotify": "Spotify",
    "line": "LINE",
    "telegram": "Telegram",
    "discord": "Discord",
    "antigravity": "Antigravity IDE",
    "iterm": "iTerm",
    "iterm2": "iTerm",
    "sublime": "Sublime Text",
    "calc": "Calculator",
    "calculator": "Calculator",
    "notes": "Notes",
    "settings": "System Settings",
    "system preferences": "System Settings",
    "mail": "Mail",
    "calendar": "Calendar",
    "music": "Music",
    "photos": "Photos",
}


def get_installed_macos_apps() -> List[str]:
    """
    Scans macOS standard application directories and caches the list of installed application names.
    Lazy-scanned only once per session.
    """
    global _INSTALLED_APPS_CACHE
    if _INSTALLED_APPS_CACHE is not None:
        return _INSTALLED_APPS_CACHE

    from pathlib import Path
    app_dirs = [
        Path("/Applications"),
        Path("/System/Applications"),
        Path("/System/Applications/Utilities"),
        Path.home() / "Applications"
    ]
    apps = set()
    for d in app_dirs:
        if d.exists():
            for item in d.glob("*.app"):
                apps.add(item.stem)

    _INSTALLED_APPS_CACHE = sorted(list(apps))
    return _INSTALLED_APPS_CACHE


def match_macos_app_name(query_name: str, installed_apps: List[str], threshold: float = 72.0) -> Optional[str]:
    """
    Matches a user or AI-provided application name against the list of installed macOS apps.
    Uses alias dictionary, Thai Soundex mapping, and RapidFuzz WRatio.
    """
    clean_query = query_name.strip()
    if not clean_query:
        return None

    # Strip .app suffix if present
    if clean_query.lower().endswith(".app"):
        clean_query = clean_query[:-4].strip()

    # 1. Exact match (case-insensitive)
    for app in installed_apps:
        if app.lower() == clean_query.lower():
            return app

    # 2. Known common aliases dictionary
    alias = COMMON_APP_ALIASES.get(clean_query.lower())
    if alias and alias in installed_apps:
        return alias

    # 3. Thai Phonetic / Soundex mapping
    if any("\u0E00" <= c <= "\u0E7F" for c in clean_query):
        try:
            from pythainlp.soundex import soundex
            sx = soundex(clean_query, engine="lk82")
            thai_phonetic_map = {
                soundex("โครม", engine="lk82"): "Google Chrome",
                soundex("กูเกิลโครม", engine="lk82"): "Google Chrome",
                soundex("ไฟร์ฟอกซ์", engine="lk82"): "Firefox",
                soundex("ไฟฟอก", engine="lk82"): "Firefox",
                soundex("ไฟ๊ฟ๊กอ", engine="lk82"): "Firefox",
                soundex("ซาฟารี", engine="lk82"): "Safari",
                soundex("ไลน์", engine="lk82"): "LINE",
                soundex("สปอติฟาย", engine="lk82"): "Spotify",
                soundex("ดิสคอร์ด", engine="lk82"): "Discord",
                soundex("เทอร์มินอล", engine="lk82"): "Terminal",
            }
            if sx in thai_phonetic_map:
                target_app = thai_phonetic_map[sx]
                if target_app in installed_apps:
                    return target_app
        except Exception:
            pass

    # 4. RapidFuzz fuzzy matching
    try:
        from rapidfuzz import process, fuzz
        res = process.extractOne(clean_query, installed_apps, scorer=fuzz.WRatio)
        if res and res[1] >= threshold:
            return res[0]
    except Exception:
        pass

    return None


def resolve_macos_app_name(query_name: str, threshold: float = 72.0) -> Optional[str]:
    """Convenience helper to resolve query_name against all installed apps on macOS."""
    apps = get_installed_macos_apps()
    return match_macos_app_name(query_name, apps, threshold=threshold)


def match_search_terms(query_terms: List[str], text: str, threshold: float = 80.0) -> bool:
    """
    Checks if any query term matches the target text either via exact substring,
    Thai phonetic Soundex, or RapidFuzz token similarity.
    """
    if not query_terms or not text:
        return False

    text_lower = text.lower()

    # 1. Fast direct substring check
    if any(t in text_lower for t in query_terms):
        return True

    # 2. Phonetic Soundex and RapidFuzz check for Thai tokens
    try:
        from pythainlp.soundex import soundex
        from rapidfuzz import fuzz

        # Extract words from text (both whitespace and punctuation split)
        words = [w for w in re.split(r"[\s,;:\.!?\-_/\\\[\]\(\)\{\}\"']+", text_lower) if len(w) >= 2]

        for term in query_terms:
            if len(term) < 2:
                continue
            is_thai = any("\u0E00" <= c <= "\u0E7F" for c in term)
            term_sx = soundex(term, engine="lk82") if is_thai else None

            for word in words:
                if is_thai and term_sx and any("\u0E00" <= c <= "\u0E7F" for c in word):
                    if soundex(word, engine="lk82") == term_sx:
                        return True
                if fuzz.partial_ratio(term, word) >= threshold:
                    return True
    except Exception:
        pass

    return False

