"""
System Tray module for Jarvis Desktop Assistant.
Displays a menu bar icon on macOS / Windows with quick actions and status.
"""

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QActionGroup
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication

import config
from core.event_bus import event_bus


def create_tray_icon() -> QIcon:
    """Generates a crisp procedural icon for the tray/menu bar."""
    size = 48
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Draw outer ring
    pen = QPen(QColor(56, 189, 248), 4)  # Cyan
    painter.setPen(pen)
    painter.drawEllipse(QRectF(6, 6, size - 12, size - 12))

    # Draw inner dot
    painter.setBrush(QColor(59, 130, 246))  # Blue
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(QRectF(18, 18, size - 36, size - 36))

    painter.end()
    return QIcon(pixmap)


class JarvisTrayIcon(QSystemTrayIcon):
    """
    Manages the system tray / macOS status bar icon and contextual menu.
    """

    def __init__(self, parent=None, on_clear_history=None):
        super().__init__(parent)
        self.on_clear_history = on_clear_history

        self.setIcon(create_tray_icon())
        self.setToolTip("Jarvis Desktop Assistant")

        self._build_menu()
        self.activated.connect(self._on_tray_activated)

    def _build_menu(self):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #1E1E24;
                color: #F1F5F9;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 18px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #2563EB;
                color: #FFFFFF;
            }
        """)

        # Toggle Overlay
        toggle_action = menu.addAction("Toggle Overlay Chat (Alt+Space)")
        toggle_action.triggered.connect(lambda: event_bus.toggle_overlay_signal.emit())

        # Toggle Voice Recording
        toggle_voice_action = menu.addAction("Toggle Voice Input (Cmd+Shift+J)")
        toggle_voice_action.triggered.connect(lambda: event_bus.toggle_voice_record_signal.emit())

        # Voice Listen Mode Selection Submenu
        voice_mode_menu = menu.addMenu("🎙️ Voice Listen Mode")
        self.mode_group = QActionGroup(self)
        self.mode_group.setExclusive(True)

        mode_options = [
            ("hybrid", "Hybrid (Hotkey + Hi Jarvis)"),
            ("push_to_talk", "Push-to-Talk (Cmd+Shift+J)"),
            ("hi_jarvis", "Wake Word Only (Hi Jarvis)"),
        ]

        current_mode = config.VOICE_LISTEN_MODE
        for mode_key, mode_label in mode_options:
            action = voice_mode_menu.addAction(mode_label)
            action.setCheckable(True)
            if mode_key == current_mode:
                action.setChecked(True)
            action.triggered.connect(lambda checked=False, m=mode_key: event_bus.voice_mode_changed.emit(m))
            self.mode_group.addAction(action)

        menu.addSeparator()

        # Clear History
        if self.on_clear_history:
            clear_action = menu.addAction("Clear Conversation History")
            clear_action.triggered.connect(self.on_clear_history)

        menu.addSeparator()

        # Quit
        quit_action = menu.addAction("Quit Jarvis")
        quit_action.triggered.connect(QApplication.instance().quit)

        self.setContextMenu(menu)

    def _on_tray_activated(self, reason):
        # On single click or double click, toggle overlay
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            event_bus.toggle_overlay_signal.emit()
