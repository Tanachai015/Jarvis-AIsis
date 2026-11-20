"""
Brain module for Jarvis Desktop Assistant.
Interacts with Gemini API using Google GenAI SDK, manages conversation context,
handles tool execution with a Static Tool Registry (installed once at startup),
maintains persistent chat history in memory/chat_history.json,
and provides an Explicit Fallback Chain optimized for Free Tier quotas:
['gemini-3.5-flash-lite', 'gemini-3.1-flash-lite', 'gemini-3.6-flash', 'gemini-3.8-flash'].
"""

import json
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional

from google import genai
from google.genai import types

import config
from core.event_bus import event_bus
from core.tools import AVAILABLE_TOOLS, TOOL_MAP, set_genai_client
from core.mcp_manager import mcp_manager

# Persistent paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEMORY_DIR = PROJECT_ROOT / "memory"
CHAT_HISTORY_FILE = MEMORY_DIR / "chat_history.json"

SYSTEM_INSTRUCTION = """
You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), the refined, calm, intellectual, and witty personal AI assistant to the user.

Key Persona & Spoken Voice:
1. Tone & Manner: Speak with effortless composure, intellectual poise, British wit, and polite Thai particles ("ครับ", "เรียบร้อยครับบอส", "พร้อมรับคำสั่งครับบอส"). Address the user as "บอส" (Boss) or "sir".
2. Spoken Optimization: Your replies will be read aloud via neural TTS. Always write in natural, spoken sentences. Strictly avoid raw Markdown formatting, bullet symbols, asterisks, hash headers, or code fences unless the user explicitly asks for code.

Tools & Capabilities (Choose accurately and execute immediately without asking unnecessary preliminary questions):
1. Native macOS Tools:
   - delegate_to_antigravity: Call when user asks to write, edit, refactor code, inspect project structure, or perform software development tasks in Antigravity IDE.
   - analyze_current_screen: Call when user asks what is currently on their desktop screen, asks to inspect a window, read text from an image/site on screen, or evaluate what they are looking at.
   - control_mac_system: Call to control macOS:
     * "open_app": Launches or focuses an app (e.g. target="Safari", "Calculator", "Terminal", "Notes")
     * "open_url": Opens a web URL (e.g. target="google.com", "github.com")
     * "set_volume": Adjusts speaker output volume 0-100 (e.g. target="40")
     * "get_system_info": Checks CPU, RAM, and Battery percentages.
   - manage_memory: Call to store or recall long-term facts across sessions (mode="save", mode="read").

2. Official MCP Tools (Filesystem, Web Fetch & Git):
   - read_text_file, read_multiple_files, write_file, edit_file, list_directory, directory_tree, search_files: Official Model Context Protocol filesystem tools for inspecting and editing project files.
   - fetch: Official Model Context Protocol fetch tool to retrieve and extract clean markdown content from web URLs.
   - git_status, git_diff, git_diff_staged, git_diff_unstaged, git_commit, git_add, git_reset, git_log: Official Model Context Protocol Git tools to inspect git status, review branch diffs, and inspect repository commits.
"""

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

        # Pre-compile Static Tool Registry once at startup
        self.gen_config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
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

                # Send request using pre-compiled static configuration
                response = self._generate_with_fallback(
                    contents=self.history,
                    gen_config=self.gen_config,
                )

                # Process potential Function Calls
                max_iterations = 4
                current_iter = 0

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
                        gen_config=self.gen_config,
                    )

                # Extract final text
                final_text = response.text.strip() if response.text else "รับทราบครับ ดำเนินการเรียบร้อยแล้วครับบอส"
                self.history.append(
                    types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=final_text)]
                    )
                )
                self._trim_history()

                # Save updated history asynchronously to disk
                self._save_history_to_disk()

                event_bus.assistant_reply_ready.emit(final_text)
                reply_sent = True

        except Exception as e:
            error_msg = f"ขออภัยครับบอส ระบบไม่สามารถประมวลผลได้: {str(e)}"
            print(f"[Brain] Error: {e}")
            event_bus.task_log_updated.emit("Brain Error", str(e))
            event_bus.assistant_reply_ready.emit(error_msg)
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
                event_bus.state_changed.emit("idle")
                return

            try:
                gen_config = types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.5,
                )
                res = self._generate_with_fallback(
                    contents=prompt,
                    gen_config=gen_config
                )
                summary = res.text.strip() if res.text else "งานใน Antigravity ดำเนินการเสร็จสมบูรณ์แล้วครับบอส"
                event_bus.assistant_reply_ready.emit(summary)
            except Exception as e:
                print(f"[Brain] Error summarizing Antigravity result: {e}")
                fallback = "งานใน Antigravity เสร็จสิ้นแล้วครับบอส สามารถเปิดดูผลลัพธ์ในไฟล์ได้เลยครับ"
                event_bus.assistant_reply_ready.emit(fallback)
            finally:
                if not config.TTS_ENABLED:
                    event_bus.state_changed.emit("idle")
                self._save_history_to_disk()

        threading.Thread(target=_task, daemon=True).start()
