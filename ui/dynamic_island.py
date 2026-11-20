"""
Dynamic Island UI for Jarvis Desktop Assistant.
Floating translucent capsule window at top of screen displaying real-time system state.
"""

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush
from PySide6.QtWidgets import QWidget, QApplication

import config
from core.event_bus import event_bus


class DynamicIsland(QWidget):
    """
    Sleek, always-on-top capsule widget inspired by Apple's Dynamic Island.
    Automatically displays current state and retracts when idle.
    """

    STATE_CONFIG = {
        "idle": {
            "label": "Jarvis Ready",
            "color": QColor(100, 116, 139),  # Slate
            "dot": QColor(148, 163, 184),
        },
        "listening": {
            "label": f"Listening... ({config.VOICE_RECORD_TIMEOUT}s auto-send)",
            "color": QColor(14, 165, 233),   # Cyan
            "dot": QColor(56, 189, 248),
        },
        "thinking": {
            "label": "Thinking...",
            "color": QColor(168, 85, 247),   # Purple
            "dot": QColor(192, 132, 252),
        },
        "running_tool": {
            "label": "Running Tool...",
            "color": QColor(245, 158, 11),   # Amber
            "dot": QColor(251, 191, 36),
        },
        "speaking": {
            "label": "Speaking...",
            "color": QColor(16, 185, 129),   # Emerald
            "dot": QColor(52, 211, 153),
        },
    }

    def __init__(self, parent=None):
        super().__init__(parent)

        # macOS and X11 window flags for overlay pill
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self.current_state = "idle"
        self._is_visible = False

        # Timer to auto-hide when returning to idle
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._auto_hide)

        # Dimensions
        self.capsule_width = 300
        self.capsule_height = 38
        self.resize(self.capsule_width + 20, self.capsule_height + 20)

        self._position_on_screen()

        # Connect to event bus
        event_bus.state_changed.connect(self.on_state_changed)

    def _position_on_screen(self):
        """Positions the capsule centered horizontally at the top of the main screen."""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.geometry()
            x = screen_geo.x() + (screen_geo.width() - self.width()) // 2
            y = screen_geo.y() + 16  # 16px below menu bar
            self.move(x, y)

    def on_state_changed(self, new_state: str):
        """Slot for state_changed signal."""
        clean_state = new_state.lower().strip()
        self.current_state = clean_state

        if clean_state == "idle":
            # Auto hide after 2.5 seconds of inactivity
            self.hide_timer.start(2500)
            self.update()
        else:
            self.hide_timer.stop()
            self._position_on_screen()
            self.show()
            self.raise_()
            self._is_visible = True
            self.update()

    def _auto_hide(self):
        if self.current_state == "idle":
            self.hide()
            self._is_visible = False

    def paintEvent(self, event):
        """Custom paint for modern frosted glass capsule."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        config_data = self.STATE_CONFIG.get(self.current_state, self.STATE_CONFIG["idle"])
        state_label = config_data["label"]
        dot_color = config_data["dot"]

        # Capsule bounding box
        rect = QRectF(10, 10, self.capsule_width, self.capsule_height)
        corner_radius = self.capsule_height / 2.0

        # Background (Deep Charcoal translucent)
        bg_color = QColor(18, 18, 22, 230)
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(QColor(255, 255, 255, 30), 1.2))
        painter.drawRoundedRect(rect, corner_radius, corner_radius)

        # Glowing status dot
        dot_radius = 5.0
        dot_x = rect.x() + 18
        dot_y = rect.y() + rect.height() / 2.0

        painter.setBrush(QBrush(dot_color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(dot_x - dot_radius, dot_y - dot_radius, dot_radius * 2, dot_radius * 2))

        # Text label
        painter.setPen(QPen(QColor(240, 240, 245), 1))
        font = self.font()
        font.setPointSize(11)
        font.setWeight(QFont.Medium)
        font.setStyleHint(QFont.SansSerif)
        painter.setFont(font)

        text_rect = QRectF(dot_x + 12, rect.y(), rect.width() - (dot_x + 20), rect.height())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, state_label)
