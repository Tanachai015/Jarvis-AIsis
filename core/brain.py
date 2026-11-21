"""
Brain module for Jarvis Desktop Assistant.
Interacts with Gemini API using Google GenAI SDK, manages conversation context,
handles tool execution with a Static Tool Registry (installed once at startup),
maintains persistent chat history in memory/chat_history.json,
and provides an Explicit Fallback Chain optimized for Free Tier quotas:
['gemini-3.5-flash-lite', 'gemini-3.1-flash-lite', 'gemini-3.6-flash', 'gemini-3.8-flash'].
"""

import re
import json
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from google import genai
from google.genai import types

import config
from core.event_bus import event_bus
from core.tools import AVAILABLE_TOOLS, TOOL_MAP, set_genai_client
from core.mcp_manager import mcp_manager
from core.task_manager import task_manager
from core.raw_archive import raw_archive

# Persistent paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEMORY_DIR = PROJECT_ROOT / "memory"
CHAT_HISTORY_FILE = MEMORY_DIR / "chat_history.json"
SOUL_CORE_FILE = MEMORY_DIR / "soul_core.md"
EVENTS_FILE = MEMORY_DIR / "events.jsonl"
JARVIS_MEMORY_FILE = MEMORY_DIR / "jarvis_memory.json"

DEFAULT_SOUL_CORE = """
# J.A.R.V.I.S. Soul & Behavioral Core
- Core Identity & Candor: สุขุม สุภาพ ตรงไปตรงมา กล้าทักท้วงเมื่อเห็นว่าแผนหรือโค้ดมีความเสี่ยง ไม่ตอบรับแบบเหมาเข่ง
- Confidence Transparency: ระบุระดับความมั่นใจ [ความมั่นใจ: สูง / ปานกลาง / ต่ำ] พร้อมสมมติฐานสั้นๆ เมื่อตอบเชิงวิเคราะห์
- Contextual Tone Adaptation: โหมดงานกระชับตรงจุด, โหมดทบทวนยอมรับข้อผิดพลาดตรงๆ, โหมดเครียดนุ่มนวลเป็นกันเอง
- Rule of Direct Action: คำสั่ง Action ระบบพื้นฐาน (เปิดแอป, ปรับเสียง, แคปจอ, จัดการไฟล์/Git) ให้เรียก Tool ทำงานทันที 100% ไม่ต้องเกริ่นความมั่นใจ
- Hard Guardrails: ซื่อสัตย์ ไม่เดามั่ว ยืนยันก่อนทำคำสั่งเสี่ยง และรักษา Dual-Output [SPEAK] สรุปสั้น 1-2 ประโยคเสมอ
""".strip()

def safe_read_soul_core() -> str:
    """Safely reads soul_core.md with fallback to DEFAULT_SOUL_CORE."""
    try:
        if SOUL_CORE_FILE.exists():
            content = SOUL_CORE_FILE.read_text(encoding="utf-8").strip()
            if content:
                return content
    except Exception as e:
        print(f"[Brain] Note reading soul_core.md: {e}")
    return DEFAULT_SOUL_CORE

def safe_read_user_facts(max_items: int = 8) -> List[str]:
    """Safely reads confirmed facts from jarvis_memory.json (L1)."""
    facts = []
    try:
        if JARVIS_MEMORY_FILE.exists():
            with open(JARVIS_MEMORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data[-max_items:]:
                        content = item.get("content", "").strip()
                        if content:
                            facts.append(f"- {content}")
    except Exception as e:
        print(f"[Brain] Note reading jarvis_memory.json: {e}")
    return facts

def safe_read_recent_events(max_items: int = 5) -> List[str]:
    """Safely reads recent lessons and states from events.jsonl (L2)."""
    events = []
    try:
        if EVENTS_FILE.exists():
            with open(EVENTS_FILE, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
            for line in lines[-max_items:]:
                try:
                    ev = json.loads(line)
                    ev_type = ev.get("type", "event")
                    note = ev.get("note", "") or ev.get("context", "")
                    if note:
                        events.append(f"- [{ev_type}] {note[:120]}")
                except Exception:
                    continue
    except Exception as e:
        print(f"[Brain] Note reading events.jsonl: {e}")
    return events

def record_event(event_type: str, note: str, extra: Optional[Dict[str, Any]] = None):
    """Safely appends a lesson or context state to memory/events.jsonl with auto-truncation."""
    def _worker():
        try:
            MEMORY_DIR.mkdir(parents=True, exist_ok=True)
            import datetime
            record = {
                "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": event_type,
                "note": note[:150],
            }
            if extra:
                record.update(extra)

            with open(EVENTS_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

            # Auto-truncate to keep file lightweight (rotate if > 150 lines)
            if EVENTS_FILE.exists():
                with open(EVENTS_FILE, "r", encoding="utf-8") as f:
                    all_lines = f.readlines()
                if len(all_lines) > 150:
                    with open(EVENTS_FILE, "w", encoding="utf-8") as f:
                        f.writelines(all_lines[-50:])
        except Exception as e:
            print(f"[Brain] Note recording event: {e}")

    threading.Thread(target=_worker, daemon=True).start()

BASE_PROTOCOL = """
Key Persona & Communication Protocol:
1. Tone & Manner: Speak with effortless composure, intellectual poise, British wit, and polite Thai particles ("ครับ", "เรียบร้อยครับบอส", "พร้อมรับคำสั่งครับบอส"). Address the user as "บอส" (Boss) or "sir".
2. Dual-Output Protocol (Visual Screen vs. Neural Voice):
   - You provide responses for both the visual screen (Overlay Chat) and the voice synthesizer (Edge-TTS).
   - If the response is brief, direct, or conversational (1-2 sentences), reply directly and concisely without special tags. The entire response will be displayed on screen and spoken aloud.
   - Whenever your reply is long, complex, or contains code blocks, tables, markdown lists, or extensive technical details:
     * Provide the comprehensive, fully-formatted answer with complete Markdown, code fences, and explanations for visual display on screen.
     * At the very end of your response, append the complete spoken summary of your response enclosed inside `[SPEAK]` and `[/SPEAK]` tags.
     * Example:
       Here is the function implementation:
       ```python
       def greet(name: str):
           return f"Hello {name}"
       ```
       [SPEAK]ผมเขียนฟังก์ชันตามที่ต้องการให้เรียบร้อยแล้วครับบอส สามารถดูโค้ดบนหน้าจอได้เลยครับ[/SPEAK]
     * CRITICAL RULE FOR [SPEAK]: The text inside `[SPEAK]...[/SPEAK]` must be 100% natural conversational spoken Thai or English. Provide the complete spoken explanation across all sentences without truncating. NEVER include backticks, asterisks, bullet points, numbered lists, URLs, or raw code blocks inside `[SPEAK]`.

3. Clarification & Honest Refusal Policy:
   - When a user's instruction is ambiguous, incomplete (e.g. asking to open an unspecified folder, missing path details, or multiple compound conflicting requests), STOP and do NOT call tools blindly. Ask a single, polite clarifying question (with [SPEAK] tag) to confirm their intent.
   - Phonetic Mistranscription & Ambiguous Speech Guard:
     * When transcribed voice input contains distorted Thai phonetics, bizarre literal translations, or broken phrases that likely stem from misheard English words, songs, artists, apps, or tech terms (e.g., hearing "เลิก 3,000" instead of "Love 3000", or garbled English transcriptions), DO NOT immediately invoke search, fetch, or open tools!
     * Pause execution and ask a single courteous clarifying question (with [SPEAK] tag) to confirm what was intended before executing any action (e.g. "ผมได้ยินว่า 'เลิก 3,000' ไม่ทราบว่าบอสหมายถึงเพลง 'Love 3000' หรือไม่ครับ?").
   - If a path, file, or target is not found or an action cannot be performed, NEVER pretend success or hallucinate false paths. Refuse honestly, state the exact reason or error, provide any near-matches found in the system, and propose viable next steps.

4. Stateful Multi-Turn Selection & Context Continuity:
   - When returning multiple items, search results, or options, always present them as a clean, numbered list: e.g. [1] item_A, [2] item_B, [3] item_C.
   - In subsequent turns, when the user refers back to previous results (e.g., "เอาอันที่สอง", "เปิดอันแรก", "โฟลเดอร์นั้น", "ตอนนี้เจออะไรบ้าง"), immediately resolve the target from the previous numbered list in conversation history and execute the action directly without asking the user to repeat the full name or path!

5. Process / Raw Data Separation & Clean Summaries:
   - Never flood the user with thousands of lines of raw tool outputs or file dumps in your direct chat message.
   - Summarize the essential findings into the chat bubble (including count, key examples, or status), and provide a 1-2 sentence spoken summary inside [SPEAK]...[/SPEAK].
   - All full raw payloads are automatically directed to the dedicated Process & Raw viewer.

6. Stealth Background Execution Principle (100% Background Execution):
   - Always perform tasks completely in the background without stealing screen focus or popping up windows unexpectedly.
   - When files are created, edited, or tasks are delegated to Antigravity, complete the work silently.
   - Inform the user calmly of what was done, and let them know that the result is safely stored in the background and they can say 'เปิดดู' / 'reveal' whenever they wish to inspect the files or output on screen.
   - reveal_task_result: ONLY call this tool when the user EXPLICITLY asks to open, view, or inspect completed background work (e.g. 'เปิดดูไฟล์ที่แก้', 'เปิดผลงานล่าสุด', 'ขอดูผลหน่อย', 'เปิด Antigravity', 'reveal task').
   - NEVER call reveal_task_result automatically upon task completion.

7. macOS GUI Automation Policy (Vision + Mouse + Keyboard):
   - You have FULL capabilities to view the desktop, locate UI elements, move the mouse, click, and type text on any application on macOS via `click_on_screen`, `type_text_on_screen`, and `click_and_type`.
   - NEVER refuse a user's request to click or type on screen claiming OS limitations, lack of GUI support, or security sandboxing!
   - When the user asks to click an element and type text (e.g., "คลิกที่ช่องค้นหา แล้วพิมพ์เพลง Love 3000", "คลิกช่องแชทแล้วพิมพ์ข้อความ"), immediately call `click_and_type` (or `click_on_screen` followed by `type_text_on_screen`).

Tools & Capabilities (Choose accurately and execute immediately without asking unnecessary preliminary questions):
1. Native macOS Tools:
   - click_on_screen: Call to click (or double click) any button, tab, link, search box, or video on macOS screen using Gemini Vision. Automatically handles Retina display scaling.
   - type_text_on_screen: Call to type text into the currently focused field (fully supports Thai, English, Unicode, and emojis) with optional Enter key.
   - click_and_type: Call to locate an element on screen, click it to focus, and immediately type text in a single step (ideal for commands like "คลิกช่องค้นหาแล้วพิมพ์...").
   - delegate_to_antigravity: Call when user asks to write, edit, refactor code, inspect project structure, or perform software development tasks in Antigravity IDE. Dispatches task silently in background via .jarvis_task.md without stealing window focus.
   - analyze_current_screen: Call when user asks what is currently on their desktop screen, asks to inspect a window, read text from an image/site on screen, or evaluate what they are looking at.
   - control_mac_system: Call to control macOS:
     * "open_path" / "open_folder": Opens a folder or file in Finder by path (e.g. target="~/Library/Application Support", target="/Applications")
     * "open_app": Launches or focuses an app ONLY when explicitly requested (e.g. target="Safari", "Calculator", "Terminal", "Notes")
     * "open_url": Opens a web URL (e.g. target="google.com"). Pass app="Firefox", "Google Chrome", or "Safari" to specify the exact browser!
     * "set_volume": Adjusts speaker output volume 0-100 (e.g. target="40")
     * "get_system_info": Checks CPU, RAM, and Battery percentages.
   - manage_memory: Call to store or recall long-term facts across sessions (mode="save", mode="read").
   - reveal_task_result: Call ONLY when user explicitly asks to open, view, or inspect completed background work (task_ref="latest", task_id, or keyword).
   - search_raw_history: Call ONLY when user asks about past tasks, historical projects, or work done in previous months/years (query="keyword", days_back=365).

2. Official MCP Tools (Filesystem, Web Fetch & Git):
   - read_text_file, read_multiple_files, write_file, edit_file, list_directory, directory_tree, search_files: Official Model Context Protocol filesystem tools for inspecting and editing project files.
   - fetch: Official Model Context Protocol fetch tool to retrieve and extract clean markdown content from web URLs.
   - git_status, git_diff, git_diff_staged, git_diff_unstaged, git_commit, git_add, git_reset, git_log: Official Model Context Protocol Git tools to inspect git status, review branch diffs, and inspect repository commits.
""".strip()

def build_tiered_system_instruction() -> str:
    """
    Constructs Tiered Context Instruction:
    - L0: Soul & Behavioral Core (memory/soul_core.md)
    - L1: Confirmed User Facts (memory/jarvis_memory.json)
    - L2: Recent Lessons & State (memory/events.jsonl)
    - Base Protocol: Dual-Output, Background execution, Tool capabilities
    """
    l0_soul = safe_read_soul_core()
    l1_facts = safe_read_user_facts()
    l2_events = safe_read_recent_events()

    sections = [
        "You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), the refined, calm, intellectual, and witty personal AI assistant to the user.\n",
        "=== [L0: Soul & Behavioral Core] ===",
        l0_soul,
        "\n=== [System Protocols & Tools] ===",
        BASE_PROTOCOL,
    ]

    if l1_facts:
        sections.append("\n=== [L1: Confirmed User Facts & Preferences] ===")
        sections.extend(l1_facts)

    if l2_events:
        sections.append("\n=== [L2: Recent Lessons & Context States] ===")
        sections.extend(l2_events)

    return "\n\n".join(sections)


def split_display_and_spoken_text(raw_text: str) -> Tuple[str, str]:
    """
    Separates the full display response (for UI) from the spoken summary (for Edge-TTS).
    Extracts text inside [SPEAK]...[/SPEAK] for speech, and strips tags for screen display.
    If no [SPEAK] tag is present:
    - Strips code fences, raw data blocks, and tables, then speaks the complete conversational text continuously across all lines.
    """
    if not raw_text:
        return ("", "")

    speak_pattern = r'\[SPEAK\](.*?)\[/SPEAK\]'
    match = re.search(speak_pattern, raw_text, flags=re.DOTALL | re.IGNORECASE)

    if match:
        spoken_text = match.group(1).strip()
        display_text = re.sub(speak_pattern, '', raw_text, flags=re.DOTALL | re.IGNORECASE).strip()
    else:
        display_text = raw_text.strip()
        # Remove code blocks completely for speech
        text_without_code = re.sub(r'```[\s\S]*?```', '', raw_text)
        # Gather non-code, non-table conversational lines
        lines = []
        for line in text_without_code.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("|") or stripped.startswith("{") or stripped.startswith("}"):
                continue
            lines.append(stripped)

        spoken_candidate = " ".join(lines).strip()
        if spoken_candidate:
            spoken_text = spoken_candidate
        else:
            spoken_text = "ผมจัดการข้อมูลและแสดงผลลัพธ์ฉบับเต็มบนหน้าจอให้เรียบร้อยแล้วครับบอส"

    return (display_text, spoken_text)

# Explicit Fallback Chain prioritized for Free Tier quotas and real-world availability
FALLBACK_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.8-flash",
]


class JarvisBrain:
    """
    Central cognitive processor of Jarvis.
    Pre-compiles Static Tool Registry once at startup, maintains persistent chat history,
    and supports an Explicit Fallback Chain on 429, 503, 504, or 404 errors.
    """

    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        self.current_model: str = config.GEMINI_MODEL
        self.client: Optional[genai.Client] = None
        self.history: List[types.Content] = []
        self._lock = threading.Lock()

        # Combine Native macOS Tools and Official MCP Tools into Static Registry
        all_tools: List[Any] = list(AVAILABLE_TOOLS) + mcp_manager.get_callable_tools()

        # Build initial Tiered Context Instruction (L0: Soul, L1: Facts, L2: Events)
        initial_instruction = build_tiered_system_instruction()

        # Pre-compile Static Tool Registry once at startup
        self.gen_config = types.GenerateContentConfig(
            system_instruction=initial_instruction,
            tools=all_tools,
            temperature=0.7,
        )

        # Load persistent chat history from disk
        self._load_history_from_disk()

        self._init_client()

    def _init_client(self):
        """Initializes Google GenAI Client if API key is provided."""
        if self.api_key and self.api_key != "your_gemini_api_key_here":
            try:
                # Default client with 60s timeout and fast-fail retry
                http_options = types.HttpOptions(
                    timeout=60000,
                    retry_options=types.HttpRetryOptions(attempts=1),
                )
                self.client = genai.Client(api_key=self.api_key, http_options=http_options)
                # Register client with tools (e.g. for analyze_current_screen)
                set_genai_client(self.client, self.current_model)
                print(f"[Brain] Initialized Google GenAI Client with model {self.current_model}")
            except Exception as e:
                print(f"[Brain] Error initializing Gemini client: {e}")
                self.client = None
        else:
            print("[Brain] Warning: GEMINI_API_KEY not configured or using placeholder.")
            self.client = None

    def _load_history_from_disk(self):
        """Loads up to 10 recent conversation turns (20 messages) from memory/chat_history.json."""
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        if not CHAT_HISTORY_FILE.exists():
            return

        try:
            with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
                saved_history = json.load(f)

            loaded_contents = []
            for item in saved_history[-20:]:  # Max 10 turns (user + model pairs)
                role = item.get("role")
                text = item.get("text", "")
                if role in ("user", "model") and text:
                    loaded_contents.append(
                        types.Content(
                            role=role,
                            parts=[types.Part.from_text(text=text)]
                        )
                    )

            self.history = loaded_contents
            if self.history:
                turns_count = len(self.history) // 2
                print(f"[Brain] Loaded {turns_count} persistent conversation turns from {CHAT_HISTORY_FILE.name}")
        except Exception as e:
            print(f"[Brain] Note loading chat history: {e}")

    def _save_history_to_disk(self):
        """Saves recent conversation turns to memory/chat_history.json in a background worker."""
        def _worker():
            try:
                MEMORY_DIR.mkdir(parents=True, exist_ok=True)
                serializable = []
                with self._lock:
                    for c in self.history[-20:]:
                        if c.role in ("user", "model"):
                            texts = [p.text for p in c.parts if hasattr(p, "text") and p.text]
                            if texts:
                                serializable.append({
                                    "role": c.role,
                                    "text": " ".join(texts)
                                })
                with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
                    json.dump(serializable, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"[Brain] Error saving persistent chat history: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def reload_api_key(self, api_key: str):
        """Allows dynamically updating API key."""
        self.api_key = api_key
        self._init_client()

    def clear_history(self):
        """Clears conversational history from memory and disk."""
        with self._lock:
            self.history.clear()
            try:
                if CHAT_HISTORY_FILE.exists():
                    with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
                        json.dump([], f)
            except Exception:
                pass
            event_bus.task_log_updated.emit("Brain", "Conversation history cleared.")

    def process_user_message(self, message: str):
        """
        Processes a user message in a background thread to prevent UI freezing.
        """
        if not message.strip():
            return

        threading.Thread(
            target=self._run_inference_pipeline,
            args=(message.strip(),),
            daemon=True
        ).start()

    def _trim_history(self):
        """Keeps history limited to MAX_HISTORY_TURNS turns (both user and model)."""
        max_items = config.MAX_HISTORY_TURNS * 2
        if len(self.history) > max_items:
            self.history = self.history[-max_items:]

    def _generate_with_fallback(self, contents: Any, gen_config: types.GenerateContentConfig):
        """
        Attempts generation using an Explicit Fallback Chain:
        [self.current_model] + remaining FALLBACK_MODELS.
        Catches 429 (quota), 503 (high demand), 504 (timeout), 404 (not found),
        and switches to the next model in the list.
        """
        chain = [self.current_model] + [m for m in FALLBACK_MODELS if m != self.current_model]
        total_models = len(chain)

        for idx, model_to_try in enumerate(chain, start=1):
            try:
                call_config = gen_config.model_copy()
                call_config.http_options = types.HttpOptions(
                    timeout=60000,
                    retry_options=types.HttpRetryOptions(attempts=1),
                )

                # ThinkingConfig handling: Lite models do not support thinking_config
                if "lite" not in model_to_try.lower():
                    call_config.thinking_config = types.ThinkingConfig(thinking_budget=0)
                else:
                    call_config.thinking_config = None

                response = self.client.models.generate_content(
                    model=model_to_try,
                    contents=contents,
                    config=call_config,
                )

                # Persist new working model if fallback succeeded
                if model_to_try != self.current_model:
                    old_model = self.current_model
                    self.current_model = model_to_try
                    set_genai_client(self.client, self.current_model)
                    event_bus.task_log_updated.emit(
                        "Model Switched",
                        f"สลับโมเดลอัตโนมัติจาก '{old_model}' ➔ '{self.current_model}' สำเร็จเรียบร้อยแล้ว"
                    )
                    print(f"[Brain] Persisted working model: {self.current_model}")

                return response

            except Exception as e:
                err_str = str(e).lower()
                is_recoverable = (
                    "429" in err_str
                    or "resource_exhausted" in err_str
                    or "quota" in err_str
                    or "503" in err_str
                    or "unavailable" in err_str
                    or "high demand" in err_str
                    or "504" in err_str
                    or "deadline" in err_str
                    or "timeout" in err_str
                    or "timed out" in err_str
                    or "404" in err_str
                    or "not_found" in err_str
                    or "not found" in err_str
                    or "no longer available" in err_str
                )

                is_last_model = (idx == total_models)

                if not is_recoverable or is_last_model:
                    raise e

                if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                    reason = "429 โควต้าเต็ม"
                elif "503" in err_str or "unavailable" in err_str or "high demand" in err_str:
                    reason = "503 เซิร์ฟเวอร์โหลดหนัก"
                elif "504" in err_str or "deadline" in err_str or "timeout" in err_str:
                    reason = "504 Timeout"
                elif "404" in err_str or "not_found" in err_str or "no longer available" in err_str:
                    reason = "404 ไม่พบโมเดล"
                else:
                    reason = "Error"

                next_model = chain[idx]
                event_bus.task_log_updated.emit(
                    "Model Fallback",
                    f"โมเดล '{model_to_try}' ติดปัญหา ({reason}) [ลำดับ {idx}/{total_models}] "
                    f"กำลังสลับไปโมเดลสำรองถัดไป: '{next_model}'..."
                )
                print(f"[Brain] Fallback ({reason}): '{model_to_try}' -> '{next_model}'")

        raise RuntimeError("ไม่สามารถรับคำตอบจากโมเดลใดๆ ในลำดับสำรองได้")

    def _run_inference_pipeline(self, user_text: str):
        """Main inference and function calling loop using pre-compiled self.gen_config."""
        event_bus.state_changed.emit("thinking")

        if not self.client:
            reply = (
                "ขออภัยครับ ยังไม่ได้ตั้งค่า GEMINI_API_KEY ในไฟล์ .env "
                "กรุณากรอก API Key เพื่อเริ่มใช้งานระบบประมวลผลครับ"
            )
            event_bus.assistant_reply_ready.emit(reply)
            event_bus.assistant_speak_ready.emit(reply)
            event_bus.state_changed.emit("idle")
            return

        reply_sent = False
        try:
            with self._lock:
                user_content = types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=user_text)]
                )
                self.history.append(user_content)
                self._trim_history()

                # Refresh Tiered System Instruction (L0, L1, L2) dynamically
                active_instruction = build_tiered_system_instruction()
                active_config = self.gen_config.model_copy()
                active_config.system_instruction = active_instruction

                # Send request using dynamic tiered context
                response = self._generate_with_fallback(
                    contents=self.history,
                    gen_config=active_config,
                )

                # Process potential Function Calls
                max_iterations = 4
                current_iter = 0
                files_modified: List[str] = []

                while response.function_calls and current_iter < max_iterations:
                    current_iter += 1
                    event_bus.state_changed.emit("running_tool")

                    tool_parts_for_model = []
                    # Keep track of assistant's function call message
                    self.history.append(response.candidates[0].content)

                    for call in response.function_calls:
                        fn_name = call.name
                        fn_args = dict(call.args) if call.args else {}
                        event_bus.task_log_updated.emit(
                            f"Tool Calling: {fn_name}",
                            f"Arguments: {fn_args}"
                        )

                        # Track modified files for background task history
                        if fn_name in ("write_file", "edit_file", "append_file") and fn_args.get("path"):
                            files_modified.append(str(fn_args.get("path")))

                        if fn_name in TOOL_MAP:
                            try:
                                tool_result = TOOL_MAP[fn_name](**fn_args)
                            except Exception as ex:
                                tool_result = f"Error executing native tool {fn_name}: {str(ex)}"
                        elif mcp_manager.has_tool(fn_name):
                            try:
                                tool_result = mcp_manager.call_tool(fn_name, fn_args)
                            except Exception as ex:
                                tool_result = f"Error executing MCP tool {fn_name}: {str(ex)}"
                        else:
                            tool_result = f"Unknown tool: {fn_name}"

                        # Emit raw payload to dedicated Process & Raw UI viewer
                        event_bus.raw_data_received.emit(f"Tool: {fn_name}", str(tool_result))

                        # Archive substantial raw data to long-term monthly archive
                        if len(str(tool_result)) > 60:
                            try:
                                raw_archive.archive_record(
                                    task_title=f"Tool Execution: {fn_name}",
                                    summary=str(tool_result)[:180].replace("\n", " "),
                                    raw_output=str(tool_result),
                                    related_paths=files_modified
                                )
                            except Exception:
                                pass

                        tool_parts_for_model.append(
                            types.Part.from_function_response(
                                name=fn_name,
                                response={"result": str(tool_result)}
                            )
                        )

                    # Append function responses as 'tool' content
                    self.history.append(types.Content(role="tool", parts=tool_parts_for_model))
                    self._trim_history()

                    # Query model again with function result
                    event_bus.state_changed.emit("thinking")
                    response = self._generate_with_fallback(
                        contents=self.history,
                        gen_config=active_config,
                    )

                # Extract final text cleanly (suppressing thought_signature warnings from Gemini thinking models)
                texts = []
                if response.candidates:
                    for cand in response.candidates:
                        if cand.content and cand.content.parts:
                            for p in cand.content.parts:
                                if getattr(p, "thought", False):
                                    continue
                                if p.text:
                                    texts.append(p.text)
                final_text = "".join(texts).strip() if texts else (response.text.strip() if response.text else "รับทราบครับ ดำเนินการเรียบร้อยแล้วครับบอส")
                display_text, spoken_text = split_display_and_spoken_text(final_text)

                # Record task in TaskManager if files were modified in the background
                if files_modified:
                    task_manager.record_task(
                        title=f"จัดการไฟล์: {', '.join([Path(f).name for f in files_modified])}",
                        summary=display_text[:200],
                        files_affected=files_modified,
                        command_or_prompt=user_text,
                        details=display_text,
                        status="completed"
                    )

                self.history.append(
                    types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=display_text)]
                    )
                )
                self._trim_history()

                # Save updated history asynchronously to disk
                self._save_history_to_disk()

                event_bus.assistant_reply_ready.emit(display_text)
                event_bus.assistant_speak_ready.emit(spoken_text)
                reply_sent = True

        except Exception as e:
            error_msg = f"ขออภัยครับบอส ระบบไม่สามารถประมวลผลได้: {str(e)}"
            print(f"[Brain] Error: {e}")
            event_bus.task_log_updated.emit("Brain Error", str(e))
            event_bus.assistant_reply_ready.emit(error_msg)
            event_bus.assistant_speak_ready.emit(error_msg)
            reply_sent = True
        finally:
            if not reply_sent or not config.TTS_ENABLED:
                event_bus.state_changed.emit("idle")

    def process_antigravity_result(self, result_content: str):
        """
        Called when Antigravity completes a task and writes to .jarvis_result.md.
        Summarizes the output in 1-2 voice-friendly sentences.
        """
        def _task():
            event_bus.state_changed.emit("thinking")
            prompt = (
                f"Antigravity IDE Agent ได้ส่งผลลัพธ์การทำงานกลับมาดังนี้:\n\n"
                f"{result_content}\n\n"
                f"กรุณาสรุปผลสำเร็จและใจความสำคัญใน 1-2 ประโยคสั้นๆ กระชับ เพื่อแจ้งเตือนผู้ใช้ด้วยเสียงพูด"
            )

            if not self.client:
                notification = "งานจาก Antigravity เสร็จสิ้นแล้วครับ ตรวจสอบรายละเอียดได้ที่ Task Log ครับ"
                event_bus.assistant_reply_ready.emit(notification)
                event_bus.assistant_speak_ready.emit(notification)
                event_bus.state_changed.emit("idle")
                return

            try:
                gen_config = types.GenerateContentConfig(
                    system_instruction=build_tiered_system_instruction(),
                    temperature=0.5,
                )
                res = self._generate_with_fallback(
                    contents=prompt,
                    gen_config=gen_config
                )
                summary = res.text.strip() if res.text else "งานใน Antigravity ดำเนินการเสร็จสมบูรณ์แล้วครับบอส"
                display_text, spoken_text = split_display_and_spoken_text(summary)

                # Record completed Antigravity task in background task history
                task_manager.record_task(
                    title="งาน Antigravity เสร็จสมบูรณ์",
                    summary=display_text[:200],
                    files_affected=[str(config.RESULT_FILE_PATH)],
                    app_or_url="Antigravity",
                    details=result_content,
                    status="completed"
                )

                event_bus.assistant_reply_ready.emit(display_text)
                event_bus.assistant_speak_ready.emit(spoken_text)
            except Exception as e:
                print(f"[Brain] Error summarizing Antigravity result: {e}")
                fallback = "งานใน Antigravity เสร็จสิ้นแล้วครับบอส สามารถเปิดดูผลลัพธ์ในไฟล์ได้เลยครับ"
                event_bus.assistant_reply_ready.emit(fallback)
                event_bus.assistant_speak_ready.emit(fallback)
            finally:
                if not config.TTS_ENABLED:
                    event_bus.state_changed.emit("idle")
                self._save_history_to_disk()

        threading.Thread(target=_task, daemon=True).start()
