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
