"""
Main entry point for Jarvis Desktop Assistant.
Orchestrates EventBus, Google GenAI Brain, UI (Tray, Dynamic Island, Overlay Chat),
Voice (Speaker, Listener), and Global Hotkey on macOS / Desktop.
"""

import sys
import signal
import threading
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

import config
from core.event_bus import event_bus
from core.brain import JarvisBrain
from core.tools import set_bridge_instance
from core.mcp_manager import mcp_manager
from integrations.antigravity_bridge import AntigravityBridge
from ui.dynamic_island import DynamicIsland
from ui.overlay_chat import OverlayChat
from ui.tray import JarvisTrayIcon
from voice.speaker import JarvisSpeaker
from voice.listener import JarvisListener


import time
import subprocess

_last_overlay_time = 0.0
_last_voice_time = 0.0


def trigger_toggle_overlay():
    """Debounced trigger for Overlay Chat."""
    global _last_overlay_time
    now = time.time()
    if now - _last_overlay_time < 0.35:
        return
    _last_overlay_time = now
    event_bus.toggle_overlay_signal.emit()


def trigger_toggle_voice():
    """Debounced trigger for 1-Tap Voice Recording Toggle (Cmd+Shift+J)."""
    global _last_voice_time
    now = time.time()
    if now - _last_voice_time < 0.35:
        return
    _last_voice_time = now
    event_bus.toggle_voice_record_signal.emit()


def check_accessibility_permission() -> bool:
    """
    Checks macOS Accessibility permission using AXIsProcessTrustedWithOptions.
    If untrusted, prompts user and opens System Settings automatically.
    """
    if sys.platform != "darwin":
        return True
    try:
        from ApplicationServices import AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt
        is_trusted = AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})
        if not is_trusted:
            print("[Permissions] ⚠️ Accessibility permission not granted. Prompting user...")
            event_bus.task_log_updated.emit(
                "Accessibility Permission Required",
                "กรุณาเปิดสิทธิ์ Accessibility สำหรับ Terminal / Python ใน System Settings > Privacy & Security > Accessibility เพื่อใช้งานคีย์ลัดระดับ System Event Tap"
            )
            subprocess.Popen(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"])
        else:
            print("[Permissions] ✅ macOS Accessibility permission verified.")
        return bool(is_trusted)
    except Exception as e:
        print(f"[Permissions] Accessibility check note: {e}")
        return False


def start_global_hotkey_listener():
    """
    Sets up system-level global hotkey listener.
    On macOS: uses Quartz CGEventTapCreate in a dedicated background thread.
    Intercepts Cmd+Shift+J (and Alt+Space) from ANY active window/application.
    Returns None in the callback to swallow the event so active apps do not react.
    """
    if sys.platform == "darwin":
        try:
            import Quartz

            tap_ref = [None]

            def quartz_event_callback(proxy, event_type, event, refcon):
                try:
                    # Automatically re-enable tap if disabled by system timeout
                    if event_type in (Quartz.kCGEventTapDisabledByTimeout, Quartz.kCGEventTapDisabledByUserInput):
                        if tap_ref[0]:
                            Quartz.CGEventTapEnable(tap_ref[0], True)
                        return event

                    if event_type == Quartz.kCGEventKeyDown:
                        keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
                        flags = Quartz.CGEventGetFlags(event)

                        is_cmd = bool(flags & Quartz.kCGEventFlagMaskCommand)
                        is_shift = bool(flags & Quartz.kCGEventFlagMaskShift)
                        is_alt = bool(flags & Quartz.kCGEventFlagMaskAlternate)

                        # Cmd + Shift + J (Keycode 38 is 'J' on macOS)
                        if is_cmd and is_shift and keycode == 38:
                            trigger_toggle_voice()
                            return None  # Swallow event to protect active applications

                        # Alt + Space (Keycode 49 is Spacebar on macOS)
                        if is_alt and keycode == 49:
                            trigger_toggle_overlay()
                            return None  # Swallow event
                except Exception as ex:
                    print(f"[Hotkey Quartz] Event callback error: {ex}")

                return event

            def _quartz_thread_worker():
                mask = Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)
                tap = Quartz.CGEventTapCreate(
                    Quartz.kCGSessionEventTap,
                    Quartz.kCGHeadInsertEventTap,
                    Quartz.kCGEventTapOptionDefault,
                    mask,
                    quartz_event_callback,
                    None
                )

                if not tap:
                    print("[Hotkey] ⚠️ Quartz CGEventTapCreate failed. Falling back to Cocoa NSEvent.")
                    _setup_cocoa_fallback()
                    return

                tap_ref[0] = tap
                run_loop_source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
                current_loop = Quartz.CFRunLoopGetCurrent()
                Quartz.CFRunLoopAddSource(current_loop, run_loop_source, Quartz.kCFRunLoopCommonModes)
                Quartz.CGEventTapEnable(tap, True)
                print("[Hotkey] ✅ Quartz System EventTap active: Cmd+Shift+J (Voice Toggle) | Alt+Space (Chat)")
                Quartz.CFRunLoopRun()

            def _setup_cocoa_fallback():
                try:
                    from AppKit import (
                        NSEvent,
                        NSKeyDownMask,
                        NSEventModifierFlagOption,
                        NSEventModifierFlagCommand,
                        NSEventModifierFlagShift,
                    )

                    def mac_key_handler(event):
                        try:
                            flags = event.modifierFlags()
                            code = event.keyCode()
                            is_alt_space = bool(flags & NSEventModifierFlagOption) and code == 49
                            is_cmd_shift_j = (
                                bool(flags & NSEventModifierFlagCommand)
                                and bool(flags & NSEventModifierFlagShift)
                                and code == 38
                            )
                            if is_alt_space:
                                trigger_toggle_overlay()
                            elif is_cmd_shift_j:
                                trigger_toggle_voice()
                        except Exception as ex:
                            print(f"[Hotkey Cocoa] Error: {ex}")

                    NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(NSKeyDownMask, mac_key_handler)
                    print("[Hotkey] Cocoa fallback monitor registered.")
                except Exception as ex:
                    print(f"[Hotkey] Cocoa monitor note: {ex}")

            tap_thread = threading.Thread(target=_quartz_thread_worker, daemon=True)
            tap_thread.start()
            return tap_thread

        except Exception as e:
            print(f"[Hotkey] Note initializing Quartz EventTap: {e}")
            return None

    # Cross-platform fallback for Windows/Linux only
    def _run_pynput_listener():
        try:
            from pynput import keyboard

            hotkeys_map = {
                "<alt>+<space>": trigger_toggle_overlay,
                config.VOICE_TOGGLE_HOTKEY: trigger_toggle_voice,
            }
            hotkeys = keyboard.GlobalHotKeys(hotkeys_map)
            with hotkeys:
                print(f"[Hotkey] pynput GlobalHotKeys active in background: {config.VOICE_TOGGLE_HOTKEY}")
                hotkeys.join()
        except Exception as e:
            print(f"[Hotkey] Note: pynput background listener info: {e}")

    hotkey_thread = threading.Thread(target=_run_pynput_listener, daemon=True)
    hotkey_thread.start()
    return hotkey_thread


def main():
    # Setup QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("Jarvis Desktop Assistant")
    app.setOrganizationName("Google DeepMind")

    # Important: Ensure app does not quit when windows are hidden
    app.setQuitOnLastWindowClosed(False)

    print("=" * 60)
    print("  JARVIS DESKTOP ASSISTANT - STARTING")
    print(f"  Model: {config.GEMINI_MODEL} | Hotkey: {config.HOTKEY}")
    print("=" * 60)

    # 0. Check macOS Permissions (Accessibility for Quartz EventTap)
    check_accessibility_permission()

    # 1. Initialize & Connect Official MCP Servers (Model Context Protocol)
    print("[Main] Booting Official MCP Servers from mcp_servers.json...")
    mcp_manager.start(timeout=15.0)

    # 2. Initialize Cognitive Brain (combines Native + MCP tools)
    brain = JarvisBrain()

    # 2. Initialize Antigravity Bridge & File Watcher
    bridge = AntigravityBridge(on_result_callback=brain.process_antigravity_result)
    set_bridge_instance(bridge)

    # 3. Initialize Voice Speaker & Listener
    speaker = JarvisSpeaker()
    speaker.start()

    listener = JarvisListener()
    listener.start_listening()

    # 4. Initialize UI Components
    dynamic_island = DynamicIsland()
    overlay_chat = OverlayChat()
    tray_icon = JarvisTrayIcon(on_clear_history=brain.clear_history)
    tray_icon.show()

    # 5. Connect Signal Pipelines
    event_bus.user_message_received.connect(brain.process_user_message)
    event_bus.assistant_reply_ready.connect(speaker.speak)

    # 6. Start Global Hotkey Listener
    _hotkey_monitor = start_global_hotkey_listener()

    # Allow Python to handle Ctrl+C in terminal
    signal.signal(signal.SIGINT, lambda *args: app.quit())
    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(500)

    # Show a brief ready state on Dynamic Island
    event_bus.state_changed.emit("idle")

    print("[Main] Jarvis is active in the menu bar/system tray.")
    print("[Main] Press Alt+Space (or click Tray Icon) to toggle Overlay Chat.")
    print("=" * 60)

    # Run Qt Event Loop
    exit_code = app.exec()

    # Cleanup upon exit
    bridge.stop_watching()
    speaker.stop()
    listener.stop()
    mcp_manager.close()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
