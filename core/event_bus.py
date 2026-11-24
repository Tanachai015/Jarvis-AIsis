"""
Central Event Bus for Jarvis Desktop Assistant.
Uses PySide6 QObject and Signals for thread-safe cross-component communication.
"""

from PySide6.QtCore import QObject, Signal


class EventBus(QObject):
    """
    Central event bus providing signals to orchestrate UI, Voice, Brain,
    and background integrations across different threads.
    """

    # Fired when system state changes ('idle', 'listening', 'thinking', 'running_tool', 'speaking')
    state_changed = Signal(str)

    # Fired when a user message is received (from voice STT or overlay chat)
    user_message_received = Signal(str)

    # Fired when assistant generates a full response for UI display (Overlay Chat)
    assistant_reply_ready = Signal(str)

    # Fired when assistant prepares a short spoken summary for voice synthesis (Edge-TTS)
    assistant_speak_ready = Signal(str)

    # Fired when a background task or tool produces logs / outputs: (title, details)
    task_log_updated = Signal(str, str)

    # Fired when raw process data or tool payloads are generated for the Process & Raw viewer: (title, raw_content)
    raw_data_received = Signal(str, str)

    # Fired to toggle the Overlay Chat window
    toggle_overlay_signal = Signal()

    # Fired to toggle Voice Recording (1-Tap Toggle: Cmd+Shift+J)
    toggle_voice_record_signal = Signal()

    # Fired to immediately cancel ongoing Voice Recording without sending (Esc)
    cancel_voice_record_signal = Signal()

    # Fired to explicitly show or hide the Overlay Chat window
    show_overlay_signal = Signal()
    hide_overlay_signal = Signal()

    # Fired when high-impact tool requires owner approval: dict with tool_name, tool_args, description
    approval_requested = Signal(dict)

    # Fired when owner approves or rejects pending tool execution: bool (True=Approve, False=Reject)
    approval_resolved = Signal(bool)

    # Fired when Voice Mode / Wake Trigger is toggled at runtime ('wake_on', 'wake_off', 'push_to_talk')
    voice_mode_changed = Signal(str)

    # Fired when todo list is updated (added, removed, completed)
    todo_updated = Signal()

    # Fired when a live todo alert triggers: alert_message (str)
    todo_alert_triggered = Signal(str)

    # Fired when AI brain requests ambiguity confirmation: (raw_stt, inferred_intent, question_text)
    confirmation_requested = Signal(str, str, str)


# Singleton instance shared across the entire application
event_bus = EventBus()
