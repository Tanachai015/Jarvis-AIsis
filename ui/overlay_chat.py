"""
Overlay Chat UI for Jarvis Desktop Assistant.
Spotlight / Raycast style floating window for typing commands and viewing agent logs.
"""

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QTextBrowser,
    QScrollArea,
    QLabel,
    QFrame,
    QApplication,
    QPushButton,
    QSplitter
)

from core.event_bus import event_bus


class OverlayChat(QWidget):
    """
    Spotlight/Raycast inspired overlay window.
    Activated with Alt+Space or system tray, closed with Esc.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.setFixedSize(700, 520)
        self._init_ui()
        self._position_on_screen()
        self._setup_shortcuts()
        self._connect_signals()

    def _init_ui(self):
        # Outer layout with margin for drop shadow effect
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 12, 12, 12)

        # Main container frame
        self.container = QFrame(self)
        self.container.setObjectName("MainContainer")
        self.container.setStyleSheet("""
            QFrame#MainContainer {
                background-color: rgba(26, 26, 32, 0.95);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 16px;
            }
        """)

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(18, 16, 18, 16)
        container_layout.setSpacing(12)

        # Header bar with Title and Status
        header_layout = QHBoxLayout()
        header_title = QLabel("JARVIS DESKTOP", self.container)
        header_title.setStyleSheet("""
            font-size: 11px;
            font-weight: 700;
            color: #94A3B8;
            letter-spacing: 1.5px;
        """)
        header_layout.addWidget(header_title)

        header_layout.addStretch()

        esc_hint = QLabel("Press ESC to hide", self.container)
        esc_hint.setStyleSheet("font-size: 11px; color: #64748B;")
        header_layout.addWidget(esc_hint)
        container_layout.addLayout(header_layout)

        # Input box (Prompt)
        self.input_field = QLineEdit(self.container)
        self.input_field.setPlaceholderText("Ask Jarvis anything or command Antigravity... (Enter to send)")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: rgba(38, 38, 48, 0.9);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 12px 14px;
                font-size: 14px;
                color: #FFFFFF;
                selection-background-color: #3B82F6;
            }
            QLineEdit:focus {
                border: 1.5px solid #3B82F6;
                background-color: rgba(45, 45, 58, 0.95);
            }
        """)
        self.input_field.returnPressed.connect(self._on_send_message)
        container_layout.addWidget(self.input_field)

        # Splitter between Chat History and Task Logs
        splitter = QSplitter(Qt.Vertical, self.container)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: rgba(255, 255, 255, 0.08);
                height: 1px;
                margin: 4px 0px;
            }
        """)

        # Chat History Browser
        self.chat_display = QTextBrowser(splitter)
        self.chat_display.setOpenExternalLinks(True)
        self.chat_display.setStyleSheet("""
            QTextBrowser {
                background-color: transparent;
                border: none;
                color: #E2E8F0;
                font-size: 13px;
                line-height: 1.6;
            }
        """)
        splitter.addWidget(self.chat_display)

        # Task & Bridge Log Box
        self.log_container = QFrame(splitter)
        log_layout = QVBoxLayout(self.log_container)
        log_layout.setContentsMargins(0, 6, 0, 0)
        log_layout.setSpacing(4)

        log_label = QLabel("TASK & BRIDGE LOGS", self.log_container)
        log_label.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748B; letter-spacing: 1px;")
        log_layout.addWidget(log_label)

        self.log_display = QTextBrowser(self.log_container)
        self.log_display.setStyleSheet("""
            QTextBrowser {
                background-color: rgba(18, 18, 22, 0.6);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 8px;
                color: #A1A1AA;
                font-family: Menlo, Monaco, 'Courier New', monospace;
                font-size: 11px;
                padding: 6px;
            }
        """)
        self.log_display.setFixedHeight(95)
        log_layout.addWidget(self.log_display)
        splitter.addWidget(self.log_container)

        # Allocate 70% space to chat and 30% to logs
        splitter.setSizes([260, 110])
        container_layout.addWidget(splitter)

        outer_layout.addWidget(self.container)

    def _position_on_screen(self):
        """Positions overlay at the top-center of the primary monitor."""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.geometry()
            x = screen_geo.x() + (screen_geo.width() - self.width()) // 2
            y = screen_geo.y() + int(screen_geo.height() * 0.16)
            self.move(x, y)

    def _setup_shortcuts(self):
        """Sets up key shortcuts like Escape to close."""
        esc_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        esc_shortcut.activated.connect(self.hide_overlay)

    def _connect_signals(self):
        """Connects signals from event bus."""
        event_bus.toggle_overlay_signal.connect(self.toggle_visibility)
        event_bus.show_overlay_signal.connect(self.show_overlay)
        event_bus.hide_overlay_signal.connect(self.hide_overlay)

        event_bus.user_message_received.connect(self.on_user_message)
        event_bus.assistant_reply_ready.connect(self.on_assistant_reply)
        event_bus.task_log_updated.connect(self.on_task_log)

    def toggle_visibility(self):
        """Toggles overlay visibility."""
        if self.isVisible():
            self.hide_overlay()
        else:
            self.show_overlay()

    def show_overlay(self):
        """Shows overlay and focuses input box."""
        self._position_on_screen()
        self.show()
        self.raise_()
        self.activateWindow()
        self.input_field.setFocus()
        self.input_field.selectAll()

    def hide_overlay(self):
        """Hides overlay."""
        self.hide()

    def _on_send_message(self):
        """Triggered when Enter is pressed in input field."""
        text = self.input_field.text().strip()
        if not text:
            return

        self.input_field.clear()
        # Emit user message so brain and UI can process
        event_bus.user_message_received.emit(text)

    def on_user_message(self, message: str):
        """Appends user chat bubble."""
        html = f"""
        <div style="margin: 8px 0; text-align: right;">
            <div style="display: inline-block; background-color: #2563EB; color: #FFFFFF;
                        padding: 8px 14px; border-radius: 12px; font-size: 13px; max-width: 80%;
                        text-align: left; line-height: 1.4;">
                {self._escape_html(message)}
            </div>
        </div>
        """
        self.chat_display.append(html)
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())

    def on_assistant_reply(self, message: str):
        """Appends assistant chat bubble."""
        html = f"""
        <div style="margin: 8px 0; text-align: left;">
            <div style="display: inline-block; background-color: rgba(45, 45, 55, 0.95);
                        border: 1px solid rgba(255, 255, 255, 0.08); color: #F1F5F9;
                        padding: 8px 14px; border-radius: 12px; font-size: 13px; max-width: 85%;
                        line-height: 1.5;">
                <b style="color: #60A5FA;">Jarvis:</b><br>{self._escape_html(message)}
            </div>
        </div>
        """
        self.chat_display.append(html)
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())

    def on_task_log(self, title: str, details: str):
        """Appends to task log drawer."""
        log_entry = f"[{title}] {details}"
        self.log_display.append(self._escape_html(log_entry))
        self.log_display.verticalScrollBar().setValue(self.log_display.verticalScrollBar().maximum())

    @staticmethod
    def _escape_html(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )
