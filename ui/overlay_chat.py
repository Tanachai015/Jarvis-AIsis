"""
Overlay Chat UI for Jarvis Desktop Assistant.
Spotlight / Raycast style floating window for typing commands and viewing agent logs.
"""

import time
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
    QSplitter,
    QTabWidget
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
        header_title = QLabel("J.A.R.V.I.S. JR. // K.A.R.I.S.", self.container)
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
        self.input_field.setPlaceholderText("Ask Karis anything or command Antigravity... (Enter to send)")
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

        # Tab Widget separating Clean Conversation from Process & Raw Data
        self.tab_widget = QTabWidget(self.container)
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid rgba(255, 255, 255, 0.08);
                background-color: transparent;
                border-radius: 8px;
            }
            QTabBar::tab {
                background-color: rgba(30, 30, 38, 0.85);
                color: #94A3B8;
                padding: 6px 14px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-size: 11px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background-color: #2563EB;
                color: #FFFFFF;
            }
            QTabBar::tab:hover:!selected {
                background-color: rgba(45, 45, 58, 0.9);
                color: #F1F5F9;
            }
        """)

        # -------------------------------------------------------------
        # Tab 1: Clean Conversation (Chat Display)
        # -------------------------------------------------------------
        chat_tab = QWidget()
        chat_tab_layout = QVBoxLayout(chat_tab)
        chat_tab_layout.setContentsMargins(4, 4, 4, 4)

        self.chat_display = QTextBrowser(chat_tab)
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
        chat_tab_layout.addWidget(self.chat_display)
        self.tab_widget.addTab(chat_tab, "💬 Conversation")

        # -------------------------------------------------------------
        # Tab 2: Process & Raw Data Viewer
        # -------------------------------------------------------------
        process_tab = QWidget()
        process_tab_layout = QVBoxLayout(process_tab)
        process_tab_layout.setContentsMargins(6, 6, 6, 6)
        process_tab_layout.setSpacing(6)

        # Process Toolbar
        process_toolbar = QHBoxLayout()
        process_title = QLabel("LIVE EXECUTION & RAW PAYLOADS", process_tab)
        process_title.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748B; letter-spacing: 1px;")
        process_toolbar.addWidget(process_title)
        process_toolbar.addStretch()

        load_archive_btn = QPushButton("📦 Load Archive", process_tab)
        load_archive_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(45, 45, 58, 0.8);
                color: #93C5FD;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2563EB;
                color: #FFFFFF;
            }
        """)
        load_archive_btn.clicked.connect(self._on_load_archive_clicked)
        process_toolbar.addWidget(load_archive_btn)

        clear_btn = QPushButton("Clear", process_tab)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(45, 45, 58, 0.8);
                color: #A1A1AA;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: rgba(65, 65, 80, 0.9);
                color: #FFFFFF;
            }
        """)
        clear_btn.clicked.connect(self._on_clear_process_clicked)
        process_toolbar.addWidget(clear_btn)

        process_tab_layout.addLayout(process_toolbar)

        # Process Splitter: Top is Task Logs, Bottom is Raw Payloads
        process_splitter = QSplitter(Qt.Vertical, process_tab)
        process_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: rgba(255, 255, 255, 0.08);
                height: 1px;
                margin: 2px 0px;
            }
        """)

        # Top: Live Task Logs
        log_box = QFrame(process_splitter)
        log_box_layout = QVBoxLayout(log_box)
        log_box_layout.setContentsMargins(0, 0, 0, 0)
        log_box_layout.setSpacing(2)
        log_box_title = QLabel("EXECUTION LOGS", log_box)
        log_box_title.setStyleSheet("font-size: 9px; font-weight: 600; color: #475569;")
        log_box_layout.addWidget(log_box_title)

        self.log_display = QTextBrowser(log_box)
        self.log_display.setStyleSheet("""
            QTextBrowser {
                background-color: rgba(18, 18, 22, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 6px;
                color: #A1A1AA;
                font-family: Menlo, Monaco, 'Courier New', monospace;
                font-size: 11px;
                padding: 6px;
            }
        """)
        log_box_layout.addWidget(self.log_display)
        process_splitter.addWidget(log_box)

        # Bottom: Raw Output & Archive Payloads
        raw_box = QFrame(process_splitter)
        raw_box_layout = QVBoxLayout(raw_box)
        raw_box_layout.setContentsMargins(0, 0, 0, 0)
        raw_box_layout.setSpacing(2)
        raw_box_title = QLabel("RAW DATA & TOOL PAYLOADS", raw_box)
        raw_box_title.setStyleSheet("font-size: 9px; font-weight: 600; color: #475569;")
        raw_box_layout.addWidget(raw_box_title)

        self.raw_display = QTextBrowser(raw_box)
        self.raw_display.setStyleSheet("""
            QTextBrowser {
                background-color: rgba(15, 15, 18, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 6px;
                color: #CBD5E1;
                font-family: Menlo, Monaco, 'Courier New', monospace;
                font-size: 11px;
                padding: 6px;
            }
        """)
        raw_box_layout.addWidget(self.raw_display)
        process_splitter.addWidget(raw_box)

        process_splitter.setSizes([140, 200])
        process_tab_layout.addWidget(process_splitter)

        self.tab_widget.addTab(process_tab, "⚡ Process & Raw")

        container_layout.addWidget(self.tab_widget)
        outer_layout.addWidget(self.container)

    def _get_active_screen(self):
        """Returns the screen containing the mouse cursor, falling back to primary screen."""
        from PySide6.QtGui import QCursor, QGuiApplication
        cursor_pos = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor_pos)
        if screen:
            return screen
        app = QApplication.instance()
        return app.primaryScreen() if app else None

    def _position_on_screen(self):
        """Positions overlay at the top-center of the currently active monitor."""
        screen = self._get_active_screen()
        if screen:
            screen_geo = screen.geometry()
            x = screen_geo.x() + (screen_geo.width() - self.width()) // 2
            y = screen_geo.y() + int(screen_geo.height() * 0.16)
            self.move(x, y)

    def _setup_shortcuts(self):
        """Sets up key shortcuts like Escape to close."""
        esc_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        esc_shortcut.activated.connect(self._on_escape_pressed)

    def _on_escape_pressed(self):
        """Handles Escape key when OverlayChat has focus: cancels active listening and hides overlay."""
        event_bus.cancel_voice_record_signal.emit()
        self.hide_overlay()

    def _connect_signals(self):
        """Connects signals from event bus."""
        event_bus.toggle_overlay_signal.connect(self.toggle_visibility)
        event_bus.show_overlay_signal.connect(self.show_overlay)
        event_bus.hide_overlay_signal.connect(self.hide_overlay)

        event_bus.user_message_received.connect(self.on_user_message)
        event_bus.assistant_reply_ready.connect(self.on_assistant_reply)
        event_bus.task_log_updated.connect(self.on_task_log)
        event_bus.raw_data_received.connect(self.on_raw_data)

    def toggle_visibility(self):
        """Toggles overlay visibility, moving to active screen if toggled from a different screen."""
        if self.isVisible():
            active_screen = self._get_active_screen()
            current_screen = self.screen()
            if active_screen and current_screen and active_screen != current_screen:
                # User pressed hotkey on another monitor: move to active monitor!
                self.show_overlay()
                return
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
                <b style="color: #00FFD1;">Karis:</b><br>{self._escape_html(message)}
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

    def on_raw_data(self, title: str, content: str):
        """Appends raw process data or payload to the Process & Raw tab."""
        timestamp = time.strftime("%H:%M:%S")
        html = (
            f"<div style='margin-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 8px;'>"
            f"<span style='color: #60A5FA; font-weight: bold;'>[{timestamp}] {self._escape_html(title)}</span><br>"
            f"<pre style='color: #CBD5E1; font-size: 11px; margin: 4px 0 0 0; white-space: pre-wrap; word-break: break-all;'>"
            f"{self._escape_html(content)}"
            f"</pre></div>"
        )
        self.raw_display.append(html)
        self.raw_display.verticalScrollBar().setValue(self.raw_display.verticalScrollBar().maximum())

    def _on_clear_process_clicked(self):
        """Clears both log and raw displays."""
        self.log_display.clear()
        self.raw_display.clear()

    def _on_load_archive_clicked(self):
        """Loads and displays recent historical records from raw archive."""
        import json
        from core.raw_archive import raw_archive
        records = raw_archive.get_recent_records(limit=15)
        if not records:
            self.on_raw_data("Archive Inspector", "ยังไม่มีประวัติในคลัง Raw Archive ครับ")
            return
        self.on_raw_data(f"Historical Archive ({len(records)} รายการล่าสุด)", json.dumps(records, ensure_ascii=False, indent=2))

    @staticmethod
    def _escape_html(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )
