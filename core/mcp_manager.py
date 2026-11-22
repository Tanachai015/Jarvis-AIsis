"""
MCP Manager module for Jarvis Desktop Assistant.
Manages long-lived persistent connections to official Model Context Protocol (MCP) servers.
Features Persistent Schema Disk Caching (memory/mcp_tools_cache.json):
- Loads tools instantly from disk cache (0.001s) on boot.
- Auto-invalidates and refreshes only when mcp_servers.json is modified (hash change) or cache is deleted.
- Background worker maintains stdio subprocesses for actual tool execution.
"""

import os
import sys
import json
import time
import shutil
import hashlib
import keyword
import asyncio
import threading
from pathlib import Path
from contextlib import AsyncExitStack
from typing import List, Dict, Any, Optional, Tuple, Callable

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import ClientSession

from core.event_bus import event_bus

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "mcp_servers.json"
MEMORY_DIR = PROJECT_ROOT / "memory"
CACHE_FILE = MEMORY_DIR / "mcp_tools_cache.json"


class MCPManager:
    """
    Singleton manager connecting to Official MCP Servers configured in mcp_servers.json.
    Operates an internal asyncio runner thread to maintain live stdio sessions throughout the app lifecycle,
    and caches tool schemas to disk for instantaneous application startup.
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or CONFIG_FILE
        self.loop = asyncio.new_event_loop()
        self.worker_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.ready_event = threading.Event()
        self.stop_event: Optional[asyncio.Event] = None

        # Maps tool_name -> (server_name, ClientSession, ToolDefinition)
        self.tool_registry: Dict[str, Tuple[str, ClientSession, Any]] = {}
        # Dynamic Python callable functions for GenAI
        self.callable_tools: List[Callable] = []
        self.callable_map: Dict[str, Callable] = {}
        self._cached_loaded = False

    def _compute_config_hash(self) -> str:
        """Computes SHA256 hash of mcp_servers.json to detect updates or changes."""
        if not self.config_path.exists():
            return ""
        try:
            content = self.config_path.read_bytes()
            return hashlib.sha256(content).hexdigest()
        except Exception:
            return ""

    def _load_cache(self) -> bool:
        """
        Loads pre-compiled tool schemas from disk cache if valid and up-to-date.
        Returns True if cache was loaded successfully.
        """
        if not CACHE_FILE.exists():
            return False

        current_hash = self._compute_config_hash()
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            cached_hash = data.get("config_hash", "")
            # If config file was modified, invalidate and refresh
            if cached_hash != current_hash:
                print("[MCP Cache] 🔄 mcp_servers.json was modified. Refreshing tools cache...")
                return False

            tools_meta = data.get("tools", [])
            if not tools_meta:
                return False

            self.callable_tools.clear()
            self.callable_map.clear()

            for item in tools_meta:
                t_name = item["name"]
                t_desc = item.get("description", "")
                t_props = item.get("properties", [])

                wrapper_func = self._create_mcp_callable(
                    tool_name=t_name,
                    description=t_desc,
                    properties=t_props
                )
                self.callable_tools.append(wrapper_func)
                self.callable_map[t_name] = wrapper_func

            self._cached_loaded = True
            print(f"[MCP Cache] ⚡ Loaded {len(self.callable_tools)} tools instantly from disk cache ({CACHE_FILE.name})")
            return True

        except Exception as e:
            print(f"[MCP Cache] Note loading cache: {e}")
            return False

    def _save_cache(self, tools_meta: List[Dict[str, Any]]):
        """Saves discovered tool definitions and config hash to disk cache."""
        try:
            MEMORY_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "config_hash": self._compute_config_hash(),
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "tools": tools_meta
            }
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[MCP Cache] 💾 Cached {len(tools_meta)} tool definitions to {CACHE_FILE.name}")
        except Exception as e:
            print(f"[MCP Cache] Error saving cache: {e}")

    def _run_loop(self):
        """Runs background asyncio loop."""
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._runner())

    def _create_mcp_callable(self, tool_name: str, description: str, properties: List[str]) -> Callable:
        """
        Creates a dynamically compiled Python callable wrapper for an MCP tool.
        This allows Google GenAI SDK to discover parameters and execute the function seamlessly.
        """
        clean_props = [p for p in properties if p.isidentifier() and not keyword.iskeyword(p)]
        params_str = ", ".join([f"{p}: str = ''" for p in clean_props]) if clean_props else "**kwargs"

        if clean_props:
            args_str = ", ".join([f"{p!r}: {p}" for p in clean_props])
            body = f"args = {{{args_str}}}"
        else:
            body = "args = kwargs"

        clean_doc = (description or f"MCP tool {tool_name}").replace('"""', "'''")

        code = f'''
def {tool_name}({params_str}) -> str:
    """{clean_doc}"""
    {body}
    return manager.call_tool({tool_name!r}, args)
'''
        scope: Dict[str, Any] = {"manager": self}
        exec(code, scope)
        return scope[tool_name]

    async def _runner(self):
        """Persistent runner maintaining stdio client sessions inside a single task group."""
        self.stop_event = asyncio.Event()

        if not self.config_path.exists():
            print(f"[MCP] Config file not found at {self.config_path}")
            self.ready_event.set()
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            servers_config = config_data.get("mcpServers", {})
        except Exception as e:
            print(f"[MCP] Error reading {self.config_path}: {e}")
            self.ready_event.set()
            return

        tools_metadata_to_cache: List[Dict[str, Any]] = []
        needs_cache_save = not self._cached_loaded

        try:
            async with AsyncExitStack() as stack:
                for server_name, srv in servers_config.items():
                    cmd = srv.get("command", "")
                    args = srv.get("args", [])
                    env = srv.get("env", None)

                    # Resolve command path (e.g. npx, python3)
                    if cmd in ("python", "python3"):
                        cmd_resolved = sys.executable
                    else:
                        cmd_resolved = shutil.which(cmd) or cmd

                    print(f"[MCP] Connecting to official MCP server '{server_name}' ({cmd_resolved})...")
                    try:
                        server_params = StdioServerParameters(
                            command=cmd_resolved,
                            args=args,
                            env=env
                        )
                        read_stream, write_stream = await stack.enter_async_context(
                            stdio_client(server_params)
                        )
                        session = await stack.enter_async_context(
                            ClientSession(read_stream, write_stream)
                        )
                        await session.initialize()

                        tools_response = await session.list_tools()
                        count = len(tools_response.tools)
                        print(f"[MCP] ✅ '{server_name}' connected: {count} tools registered.")

                        for t in tools_response.tools:
                            self.tool_registry[t.name] = (server_name, session, t)

                            raw_schema = getattr(t, "input_schema", getattr(t, "inputSchema", {}))
                            props = list(raw_schema.get("properties", {}).keys()) if isinstance(raw_schema, dict) else []

                            tools_metadata_to_cache.append({
                                "server": server_name,
                                "name": t.name,
                                "description": t.description or f"MCP tool {t.name}",
                                "properties": props
                            })

                            # Only compile callables if not already loaded from cache
                            if not self._cached_loaded:
                                wrapper_func = self._create_mcp_callable(
                                    tool_name=t.name,
                                    description=t.description or f"Official MCP tool {t.name} from {server_name}",
                                    properties=props
                                )
                                self.callable_tools.append(wrapper_func)
                                self.callable_map[t.name] = wrapper_func

                        event_bus.task_log_updated.emit(
                            "MCP Server",
                            f"เชื่อมต่อเซิร์ฟเวอร์ '{server_name}' สำเร็จ ({count} เครื่องมือ)"
                        )

                    except Exception as srv_err:
                        err_msg = f"ไม่สามารถเชื่อมต่อ MCP server '{server_name}': {srv_err}"
                        print(f"[MCP] ⚠️ {err_msg}")
                        event_bus.task_log_updated.emit("MCP Error", err_msg)

                # Save new cache if this was the first run or after update
                if needs_cache_save and tools_metadata_to_cache:
                    self._save_cache(tools_metadata_to_cache)

                self.ready_event.set()

                # Keep connection open until stop_event is triggered
                await self.stop_event.wait()
                print("[MCP] Shutting down MCP sessions gracefully...")

        except Exception as ex:
            print(f"[MCP] Runner error: {ex}")
            self.ready_event.set()

    def start(self, timeout: float = 15.0):
        """
        Starts MCP manager.
        If valid disk cache exists, loads tool schemas instantly (0.001s) so the app boots without waiting!
        Background connections start concurrently.
        """
        cache_loaded = self._load_cache()
        if cache_loaded:
            # Tool definitions are instantly ready for Gemini!
            self.ready_event.set()

        if not self.worker_thread.is_alive():
            self.worker_thread.start()

        # If cache wasn't available, wait for initial discovery to finish
        if not cache_loaded:
            self.ready_event.wait(timeout=timeout)

    def get_callable_tools(self) -> List[Callable]:
        """Returns list of dynamic Python callable wrappers for all MCP tools."""
        return self.callable_tools

    def has_tool(self, tool_name: str) -> bool:
        """Checks if a tool name belongs to one of the connected MCP servers."""
        return tool_name in self.tool_registry or tool_name in self.callable_map

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Executes an MCP tool call thread-safely against the corresponding active session.
        """
        if tool_name not in self.tool_registry:
            # Wait briefly if session is still connecting in background
            wait_count = 0
            while tool_name not in self.tool_registry and wait_count < 10:
                time.sleep(0.3)
                wait_count += 1
            if tool_name not in self.tool_registry:
                return f"Error: Tool '{tool_name}' not ready or server not reachable."

        server_name, session, tool_def = self.tool_registry[tool_name]

        # Extract required properties from tool schema if present
        required_fields = set()
        if tool_def is not None:
            if isinstance(tool_def, dict):
                raw_schema = tool_def.get("input_schema") or tool_def.get("inputSchema") or {}
            else:
                raw_schema = getattr(tool_def, "input_schema", getattr(tool_def, "inputSchema", {}))
            if isinstance(raw_schema, dict):
                required_fields = set(raw_schema.get("required", []))

        # Filter out empty arguments ("" or None) unless they are required by schema
        cleaned_arguments = {}
        for k, v in arguments.items():
            if (v is None or v == "") and k not in required_fields:
                continue
            cleaned_arguments[k] = v
        arguments = cleaned_arguments

        # Smart defaults for MCP tools (e.g. Git tools require repo_path)
        if server_name == "git" and ("repo_path" not in arguments or not arguments.get("repo_path")):
            arguments["repo_path"] = str(PROJECT_ROOT)

        print(f"[MCP] Dispatching '{tool_name}' to {server_name} with args: {arguments}")
        event_bus.task_log_updated.emit(f"MCP Action ({server_name})", f"{tool_name}({arguments})")

        try:
            future = asyncio.run_coroutine_threadsafe(
                session.call_tool(tool_name, arguments),
                self.loop
            )
            result = future.result(timeout=60.0)

            # Extract text content from CallToolResult
            text_outputs = []
            if hasattr(result, "content") and result.content:
                for block in result.content:
                    if hasattr(block, "text") and block.text:
                        text_outputs.append(block.text)
                    elif hasattr(block, "data"):
                        text_outputs.append(str(block.data))
                    else:
                        text_outputs.append(str(block))

            if text_outputs:
                joined = "\n".join(text_outputs)
                return joined
            return f"Tool '{tool_name}' executed successfully with no output."

        except Exception as e:
            err_msg = f"Error executing MCP tool '{tool_name}': {str(e)}"
            print(f"[MCP] ⚠️ {err_msg}")
            event_bus.task_log_updated.emit("MCP Tool Error", err_msg)
            return err_msg

    def close(self):
        """Closes all MCP client sessions cleanly."""
        if self.stop_event and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.stop_event.set)
            self.worker_thread.join(timeout=3.0)
            print("[MCP] All sessions closed.")


# Singleton instance
mcp_manager = MCPManager()
