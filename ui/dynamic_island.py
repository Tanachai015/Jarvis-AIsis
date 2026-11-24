"""
Dynamic Island UI for Jarvis Desktop Assistant.
Adaptive Edge-Aware Menu Bar Docked Dynamic Island (Folded ↔ Expanded)
with 60 FPS Pure Vector Cyber Mini-Robot Avatar (QPainter & Kinematics).
"""

import sys
import time
import math
import random
from typing import Optional, Dict, Any

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, QPoint, QPropertyAnimation, QEasingCurve, Property, QBuffer, QIODevice
from PySide6.QtGui import QPainter, QPainterPath, QColor, QFont, QPen, QBrush, QGuiApplication, QScreen, QCursor, QPolygonF
from PySide6.QtWidgets import QWidget, QApplication, QMenu

import config
from core.event_bus import event_bus
from ui.pixel_engine import ChillPixelLifeEngine, render_standby_frame

# Setup macOS PyObjC if available
_HAS_APPKIT = False
if sys.platform == "darwin":
    try:
        import AppKit
        import objc
        _HAS_APPKIT = True
    except Exception:
        _HAS_APPKIT = False


class DynamicIsland(QWidget):
    """
    Menu Bar Docked Dynamic Island with Cyber Mini-Robot Avatar.
    - Folded Mode (idle): Compact pill (68x24 px) embedded seamlessly in macOS Menu Bar.
    - Expanded Mode (active): 340x56 px 2-stage spring popup displaying the animated robot and status.
    - Pure QPainter vector graphics: Zero raster assets, 100% Retina crisp, 60 FPS / 30 FPS adaptive.
    """

    STATES = {
        "speaking": {
            "id": "speaking",
            "tag": "speaking",
            "status": "กำลังพูดตอบกลับ...",
            "subtext": "Jarvis Speaker กำลังอ่านข้อความสรุป",
            "color": QColor("#00E5FF"),       # Primary Neon Cyan
            "bg_tint": QColor("#05141F"),
            "visor_tint": QColor("#082030"),
        },
        "listening": {
            "id": "listening",
            "tag": "listening",
            "status": "กำลังฟังคำสั่ง...",
            "subtext": "Silero VAD เปิดรับเสียง • พูดคำสั่งได้เลยครับบอส",
            "color": QColor("#00FFD1"),       # Listening Mint
            "bg_tint": QColor("#041816"),
            "visor_tint": QColor("#072622"),
        },
        "thinking": {
            "id": "thinking",
            "tag": "thinking",
            "status": "กำลังวิเคราะห์คำสั่ง...",
            "subtext": "Gemini 3.5 Flash Lite กำลังประมวลผลบริบท",
            "color": QColor("#38BDF8"),       # Sky Glow
            "bg_tint": QColor("#061224"),
            "visor_tint": QColor("#0A1E3A"),
        },
        "running_tool": {
            "id": "running_tool",
            "tag": "running_tool",
            "status": "กำลังรันเครื่องมือ MCP...",
            "subtext": "Executing macOS Control / Filesystem / Web Fetch",
            "color": QColor("#60A5FA"),       # Tool Blue
            "bg_tint": QColor("#071126"),
            "visor_tint": QColor("#0C1C3D"),
        },
        "wake_ack": {
            "id": "wake_ack",
            "tag": "ready",
            "status": "พร้อมครับบอส!",
            "subtext": "ตรวจพบคำปลุก 'Hey Jarvis' พร้อมรับคำสั่ง",
            "color": QColor("#22D3EE"),       # Joy Cyan
            "bg_tint": QColor("#051822"),
            "visor_tint": QColor("#092838"),
        },
        "confused": {
            "id": "confused",
            "tag": "confused",
            "status": "ขออภัยครับ ฟังไม่ถนัด...",
            "subtext": "กรุณาพูดคำสั่งใหม่อีกครั้งครับบอส",
            "color": QColor("#FBBF24"),       # Warning Amber
            "bg_tint": QColor("#1A1305"),
            "visor_tint": QColor("#291E08"),
        },
        "idle": {
            "id": "idle",
            "tag": "standby",
            "status": "Standby Wake (รอคำปลุก)",
            "subtext": "พูด 'Hey Jarvis' หรือกด Cmd+Shift+J",
            "color": QColor("#0EA5E9"),       # Calm Sky
            "bg_tint": QColor("#06101D"),
            "visor_tint": QColor("#09182B"),
        },
    }

    QUIRK_NAMES = ["look_around", "double_blink", "hum_hop", "mini_yawn", "curious_nod"]

    def __init__(self, parent=None, screen: Optional[Any] = None, on_clear_history=None):
        super().__init__(parent)
        self.screen = screen
        if not self.screen:
            app = QGuiApplication.instance()
            self.screen = app.primaryScreen() if app else None
        self.on_clear_history = on_clear_history

        # macOS Frameless Always-On-Top Window Flags (v1.9.2: NO Qt.Tool, with BypassWindowManager)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
            | Qt.BypassWindowManagerHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)

        self.current_state = "idle"
        self._custom_subtext = ""
        self._manually_expanded = False
        self._hovered_btn: Optional[str] = None
        self._hovered_capsule: bool = False

        # Geometry & Dimension Settings
        self.edge = "top"
        self.bar_thickness = 24
        self.folded_w = 88
        self.folded_h = 22
        self.expanded_w = 360
        self.expanded_h = 70
        self.menubar_offset_x = 0

        # Robot Speech Bubble State (v1.9.3)
        self._bubble_title: Optional[str] = None
        self._bubble_subtext: Optional[str] = None
        self._bubble_expire_time: float = 0.0
        self._bubble_title_color: QColor = QColor("#00FFD1")

        # Chill Pixel Life Standby Engine
        self.pixel_engine = ChillPixelLifeEngine()

        # Auto-fold timer for manual expansion in idle state
        self._auto_fold_timer = QTimer(self)
        self._auto_fold_timer.setSingleShot(True)
        self._auto_fold_timer.timeout.connect(self._on_auto_fold_timeout)

        # Load menubar_offset_x from voice_settings.json if present
        self._load_settings()

        # Cache for system tray edge position
        self._cached_tray_min_x: Optional[float] = None
        self._last_tray_scan_time: float = 0.0

        # Kinematics & Animation State
        self.start_time = time.time()
        self.active_quirk: Optional[str] = None
        self.quirk_start_time: float = 0.0
        self.quirk_duration: float = 1.6
        self.next_auto_quirk_time: float = 3.0

        # Geometry Animation (Spring Pop-out)
        self.anim = QPropertyAnimation(self, b"geometry", self)
        self.anim.setDuration(320)
        self.anim.setEasingCurve(QEasingCurve.Type.OutBack)

        # 60 FPS / 30 FPS Adaptive Render Timer
        self.render_timer = QTimer(self)
        self.render_timer.timeout.connect(self._on_animation_tick)
        self.render_timer.start(33)  # Start at 30 FPS for idle

        # Setup macOS AppKit Window Level & Space behaviors
        self._setup_macos_window_level()

        # Calculate initial edge and position
        self._detect_system_edge_and_bar()
        self._apply_geometry_for_state(animated=False)

        # Connect screen geometry change events
        screen = self.screen or QGuiApplication.primaryScreen()
        if screen:
            screen.geometryChanged.connect(self._on_screen_geometry_changed)
            screen.availableGeometryChanged.connect(self._on_screen_geometry_changed)

        # Connect event bus signals
        event_bus.state_changed.connect(self.on_state_changed)
        event_bus.task_log_updated.connect(self._on_task_log_updated)
        self._pending_approval_active: bool = False
        self._pending_approval_info: Dict[str, Any] = {}
        event_bus.approval_requested.connect(self._on_approval_requested)
        event_bus.approval_resolved.connect(self._on_approval_resolved_slot)

        # In standby idle state, Expanded Island window starts hidden
        self.hide()

    @property
    def is_expanded(self) -> bool:
        """True if island is in expanded mode (either active AI state or manually expanded)."""
        return (self.current_state != "idle") or self._manually_expanded

    def _load_settings(self):
        """Loads optional menubar_offset_x from voice_settings.json."""
        try:
            import json
            settings_path = config.PROJECT_ROOT / "voice_settings.json"
            if settings_path.exists():
                with open(settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.menubar_offset_x = int(data.get("menubar_offset_x", 0))
        except Exception:
            self.menubar_offset_x = 0

    def _setup_macos_window_level(self):
        """Sets macOS Window level to NSPopUpMenuWindowLevel and enables multi-space & always-on-top persistence."""
        if sys.platform != "darwin" or not _HAS_APPKIT:
            return
        try:
            import AppKit
            import objc
            view_ptr = int(self.winId())
            nsview = objc.objc_object(c_void_p=view_ptr)
            nswindow = nsview.window()
            if nswindow:
                nswindow.setHidesOnDeactivate_(False)
                level = getattr(AppKit, "NSPopUpMenuWindowLevel", AppKit.NSMainMenuWindowLevel + 1)
                nswindow.setLevel_(level)
                fullscreen_aux = getattr(AppKit, "NSWindowCollectionBehaviorFullScreenAuxiliary", 256)
                nswindow.setCollectionBehavior_(
                    AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
                    | AppKit.NSWindowCollectionBehaviorStationary
                    | fullscreen_aux
                )
        except Exception:
            pass

    def _detect_system_edge_and_bar(self):
        """
        Detects macOS Menu Bar / System Taskbar edge ('top', 'bottom', 'left', 'right')
        and bar thickness by comparing full screen geometry with availableGeometry.
        Prioritizes 'top' for macOS Menu Bar.
        """
        screen = self.screen or QGuiApplication.primaryScreen()
        if not screen:
            self.edge = "top"
            self.bar_thickness = 24
            return

        full = screen.geometry()
        avail = screen.availableGeometry()

        # On macOS, Menu Bar is always at the top
        if avail.y() > full.y():
            self.edge = "top"
            self.bar_thickness = avail.y() - full.y()
        elif full.bottom() > avail.bottom():
            self.edge = "bottom"
            self.bar_thickness = full.bottom() - avail.bottom()
        elif avail.x() > full.x():
            self.edge = "left"
            self.bar_thickness = avail.x() - full.x()
        elif full.right() > avail.right():
            self.edge = "right"
            self.bar_thickness = full.right() - avail.right()
        else:
            # Auto-hide or full-screen fallback: check AppKit NSStatusBar thickness
            self.edge = "top"
            self.bar_thickness = 24
            if sys.platform == "darwin":
                try:
                    import AppKit
                    self.bar_thickness = int(AppKit.NSStatusBar.systemStatusBar().thickness())
                except Exception:
                    self.bar_thickness = 24

        # Enforce realistic menu bar height limits
        self.bar_thickness = max(22, min(40, self.bar_thickness))
        self.folded_h = 22
        self.folded_w = 88

    def _get_leftmost_tray_x(self) -> float:
        """
        Detects leftmost bounds of macOS Menu Bar Status/Tray items (Quartz Layer 25)
        for this specific screen. Caches result for 5 seconds to avoid CPU overhead.
        """
        now = time.time()
        if self._cached_tray_min_x is not None and (now - self._last_tray_scan_time < 5.0):
            return self._cached_tray_min_x

        screen = self.screen or QGuiApplication.primaryScreen()
        s_geo = screen.geometry() if screen else QRectF(0, 0, 1650, 1050)
        sx = float(s_geo.x())
        sy = float(s_geo.y())
        sw = float(s_geo.width())
        s_right = sx + sw

        # Safe default if Quartz is unavailable
        default_x = s_right - self.expanded_w - 100.0 - self.menubar_offset_x

        if sys.platform != "darwin":
            self._cached_tray_min_x = default_x
            self._last_tray_scan_time = now
            return default_x

        try:
            import Quartz
            opts = Quartz.kCGWindowListOptionOnScreenOnly
            wins = Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID)
            tray_xs = []
            for w in wins:
                if w.get('kCGWindowLayer', 0) == 25:
                    b = w.get('kCGWindowBounds', {})
                    bx = float(b.get('X', 0.0))
                    by = float(b.get('Y', 0.0))
                    # Only collect status items located on this screen's menu bar
                    if (sy <= by <= sy + 40.0) and (sx + sw * 0.35 <= bx < s_right):
                        tray_xs.append(bx)

            if tray_xs:
                min_x = min(tray_xs)
                min_safe_x = self._get_notch_min_safe_x()
                if min_safe_x > 0 and min_x < min_safe_x:
                    min_x = min_safe_x + 16.0
                self._cached_tray_min_x = min_x
                self._last_tray_scan_time = now
                return min_x
        except Exception:
            pass

        self._cached_tray_min_x = default_x
        self._last_tray_scan_time = now
        return default_x

    def _get_notch_min_safe_x(self) -> float:
        """Returns right edge of macOS camera notch via NSScreen.auxiliaryTopRightArea."""
        if sys.platform != "darwin":
            return 0.0
        screen = self.screen or QGuiApplication.primaryScreen()
        if screen and "built-in" not in screen.name().lower() and "internal" not in screen.name().lower():
            return 0.0
        try:
            import AppKit
            for ns in AppKit.NSScreen.screens():
                frame = ns.frame()
                if screen and int(frame.origin.x) == screen.geometry().x():
                    if hasattr(ns, "auxiliaryTopRightArea"):
                        area = ns.auxiliaryTopRightArea()
                        if area and area.size.width > 0:
                            return float(area.origin.x)
        except Exception:
            pass
        return 0.0

    def _calculate_target_geometry(self, is_expanded: bool) -> tuple:
        """Calculates (x, y, w, h) for Folded or Expanded pill avoiding Notch and Tray."""
        screen = self.screen or QGuiApplication.primaryScreen()
        screen_geo = screen.geometry() if screen else QRectF(0, 0, 1650, 1050)
        sx = screen_geo.x()
        sy = screen_geo.y()

        tray_min_x = self._get_leftmost_tray_x()
        min_safe_x = self._get_notch_min_safe_x()

        if is_expanded:
            w = self.expanded_w
            h = self.expanded_h

            # Anchor directly below NSStatusItem if available
            anchor_found = False
            if sys.platform == "darwin" and _HAS_APPKIT:
                try:
                    import AppKit
                    app_inst = QApplication.instance()
                    mgr = getattr(app_inst, "_dynamic_island_manager", None)
                    st_item = getattr(mgr, "status_item", None) if mgr else None
                    if st_item and hasattr(st_item, "button"):
                        btn = st_item.button()
                        if btn and btn.window():
                            wf = btn.window().frame()
                            main_h = AppKit.NSScreen.screens()[0].frame().size.height
                            item_x = int(round(wf.origin.x))
                            item_y = int(round(main_h - (wf.origin.y + wf.size.height)))
                            item_w = int(round(wf.size.width))
                            item_h = int(round(wf.size.height))

                            # Only anchor to status item if its position falls within this screen
                            s_right = sx + screen_geo.width()
                            if sx <= item_x < s_right:
                                x = int(item_x + (item_w / 2.0) - (w / 2.0))
                                y = int(item_y + item_h + 4)
                                # Clamp within screen bounds
                                if x < sx + 8:
                                    x = sx + 8
                                elif x + w > s_right - 8:
                                    x = s_right - w - 8
                                anchor_found = True
                except Exception:
                    anchor_found = False

            if not anchor_found:
                right_x = tray_min_x - 12.0 - self.menubar_offset_x
                x = right_x - w
                if min_safe_x > 0 and x < min_safe_x + 10:
                    x = min_safe_x + 10
                y = sy + 2
        else:
            w = self.folded_w
            h = self.folded_h
            right_x = tray_min_x - 12.0 - self.menubar_offset_x
            x = right_x - w
            if min_safe_x > 0 and x < min_safe_x + 10:
                x = min_safe_x + 10
            y = sy + 1

        return int(x), int(y), int(w), int(h)

    def compute_dock_geometry(self, is_expanded: bool) -> tuple:
        """Public method to compute dock geometry (x, y, w, h) for testing or layout queries."""
        return self._calculate_target_geometry(is_expanded)

    def trigger_quirk(self, quirk_name: str):
        """Manually triggers a specific autonomous quirk animation."""
        if quirk_name in self.QUIRK_NAMES:
            self.active_quirk = quirk_name
            self.quirk_start_time = time.time() - self.start_time
            self.quirk_duration = 1.9 if quirk_name == "mini_yawn" else 1.5

    def _apply_geometry_for_state(self, animated: bool = True):
        """Morphs geometry between Folded and Expanded pill using spring easing."""
        target_x, target_y, target_w, target_h = self._calculate_target_geometry(self.is_expanded)

        if animated:
            self.anim.stop()
            self.anim.setStartValue(self.geometry())
            self.anim.setEndValue(QRectF(target_x, target_y, target_w, target_h).toRect())
            self.anim.start()
        else:
            self.setGeometry(target_x, target_y, target_w, target_h)

    def _on_screen_geometry_changed(self):
        """Handles display resolution or dock location changes."""
        self._cached_tray_min_x = None
        self._detect_system_edge_and_bar()
        self._apply_geometry_for_state(animated=False)

    def _reset_auto_fold_timer(self):
        """Restarts or stops auto-fold timer."""
        if self._auto_fold_timer.isActive():
            self._auto_fold_timer.stop()
        if self.current_state == "idle":
            self._auto_fold_timer.start(12000)

    def _on_auto_fold_timeout(self):
        """Folds manually expanded island back to menu bar after inactivity."""
        if self.current_state == "idle" and self._manually_expanded:
            self.fold_manually()

    def expand_manually(self):
        """Manually pops out the island into expanded interactive mode."""
        self._manually_expanded = True
        self.show()
        self.raise_()
        self._apply_geometry_for_state(animated=True)
        self._reset_auto_fold_timer()
        self.update()

    def fold_manually(self):
        """Folds the island back into compact menu bar pill (hidden in idle)."""
        if self.current_state != "idle":
            return
        self._manually_expanded = False
        self._hovered_btn = None
        self.hide()
        self.update()

    def toggle_expanded_manually(self):
        """Toggles between folded and expanded modes."""
        if self.is_expanded:
            self.fold_manually()
        else:
            self.expand_manually()

    def _show_robot_bubble(self, title: str, subtext: str, duration: float = 3.0, title_color: Optional[QColor] = None):
        """Displays pure vector speech bubble pointing from robot's mouth with auto-fold delay."""
        self._bubble_title = title
        self._bubble_subtext = subtext
        self._bubble_expire_time = time.time() + duration
        self._bubble_title_color = title_color if title_color is not None else QColor("#00FFD1")
        # Delay auto-fold timer so speech bubble completes before window folds
        if self._auto_fold_timer.isActive():
            self._auto_fold_timer.stop()
        self._auto_fold_timer.start(int((duration + 3.5) * 1000))
        self.update()

    def _on_toggle_wake_word(self, checked: bool = None):
        """Toggles wake word detection and notifies event bus with speech bubble feedback."""
        if checked is None:
            config.WAKE_TRIGGER_ENABLED = not config.WAKE_TRIGGER_ENABLED
        else:
            config.WAKE_TRIGGER_ENABLED = checked
        status_text = "เปิดใช้งาน" if config.WAKE_TRIGGER_ENABLED else "ปิดชั่วคราว"
        print(f"[DynamicIsland] Wake word trigger changed to: {config.WAKE_TRIGGER_ENABLED}")
        event_bus.voice_mode_changed.emit("wake_on" if config.WAKE_TRIGGER_ENABLED else "wake_off")
        event_bus.task_log_updated.emit(
            "Wake Trigger Updated",
            f"การตรวจจับคำปลุก 'Hey Jarvis' ถูก{status_text}แล้ว"
        )
        if config.WAKE_TRIGGER_ENABLED:
            self.trigger_quirk("hum_hop")
            self._show_robot_bubble(
                title='Call me "Hey Jarvis" (aka Karis)',
                subtext="เปิดโหมด Wake Standby แล้วครับ พร้อมรับเสียงเรียก",
                duration=3.0,
                title_color=QColor("#00FFD1")
            )
        else:
            self.trigger_quirk("curious_nod")
            self._show_robot_bubble(
                title="กลับเข้าสู่โหมด Standard แล้วครับ",
                subtext="สามารถกด Cmd + Shift + J เรียก เปิด-ปิด ใช้งานสั่งการด้วยเสียงได้นะครับ",
                duration=3.8,
                title_color=QColor("#38BDF8")
            )
        self.update()

    def _on_approval_requested(self, payload: dict):
        """Displays approval prompt in Dynamic Island when a high-impact action is requested."""
        self._pending_approval_active = True
        self._pending_approval_info = payload or {}
        prompt_msg = payload.get("prompt") or f"ต้องการยืนยันรัน {payload.get('tool_name', 'คำสั่ง')} หรือไม่ครับ?"
        self.expand_manually()
        self._show_robot_bubble(
            title="Owner Approval Required",
            subtext=prompt_msg,
            duration=12.0,
            title_color=QColor("#FB7185")
        )
        self.update()

    def _on_approval_resolved_slot(self, approved: bool):
        """Resolves approval mode and restores normal buttons."""
        self._pending_approval_active = False
        self._pending_approval_info = {}
        self.update()
        if self.current_state == "idle":
            self.fold_manually()

    def _get_buttons_map(self) -> Dict[str, QRectF]:
        """Returns bounding rects for interactive buttons (standard mode or pending approval mode)."""
        if getattr(self, "_pending_approval_active", False):
            return {
                "approve": QRectF(62.0, 42.0, 138.0, 22.0),
                "reject": QRectF(206.0, 42.0, 138.0, 22.0),
            }
        return {
            "voice": QRectF(62.0, 42.0, 68.0, 22.0),
            "chat": QRectF(134.0, 42.0, 64.0, 22.0),
            "wake": QRectF(202.0, 42.0, 90.0, 22.0),
            "menu": QRectF(296.0, 42.0, 52.0, 22.0),
        }

    def _get_button_at_pos(self, pos: QPointF) -> Optional[str]:
        if not self.is_expanded:
            return None
        btns = self._get_buttons_map()
        for name, rect in btns.items():
            if rect.contains(pos):
                return name
        return None

    def _show_context_menu(self, global_pos: QPoint):
        """Displays dark-theme cyber context menu replacing standalone system tray."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0A101D;
                color: #F1F5F9;
                border: 1px solid rgba(0, 229, 255, 0.35);
                border-radius: 10px;
                padding: 6px;
                font-family: -apple-system;
                font-size: 11px;
            }
            QMenu::item {
                padding: 7px 22px;
                border-radius: 6px;
            }
            QMenu::item:selected {
                background-color: rgba(0, 229, 255, 0.22);
                color: #00E5FF;
            }
            QMenu::separator {
                height: 1px;
                background-color: rgba(255, 255, 255, 0.12);
                margin: 4px 8px;
            }
        """)

        # 1. Toggle Overlay Chat
        act_chat = menu.addAction("💬 Toggle Overlay Chat (Alt+Space)")
        act_chat.triggered.connect(lambda: event_bus.toggle_overlay_signal.emit())

        # 2. Toggle Voice Input
        act_voice = menu.addAction("🎙️ Toggle Voice Input (Cmd+Shift+J)")
        act_voice.triggered.connect(lambda: event_bus.toggle_voice_record_signal.emit())

        # 3. Toggle Wake Word Trigger
        wake_status = "Active" if config.WAKE_TRIGGER_ENABLED else "Disabled"
        act_wake = menu.addAction(f"⚡ Wake Word Trigger ({wake_status})")
        act_wake.setCheckable(True)
        act_wake.setChecked(config.WAKE_TRIGGER_ENABLED)
        act_wake.triggered.connect(self._on_toggle_wake_word)

        menu.addSeparator()

        # 4. Expand / Fold Island
        fold_text = "⬆️ Fold Dynamic Island" if self.is_expanded else "⬇️ Expand Dynamic Island"
        act_fold = menu.addAction(fold_text)
        act_fold.triggered.connect(self.toggle_expanded_manually)

        # 5. Clear Conversation History
        if self.on_clear_history:
            act_clear = menu.addAction("🗑️ Clear Conversation History")
            act_clear.triggered.connect(self.on_clear_history)

        menu.addSeparator()

        # 6. Quit Jarvis
        act_quit = menu.addAction("🚪 Quit Jarvis")
        act_quit.triggered.connect(QApplication.instance().quit)

        menu.exec(global_pos)

    def mouseMoveEvent(self, event):
        pos = event.position()
        if self.is_expanded:
            btn = self._get_button_at_pos(pos)
            if btn != self._hovered_btn:
                self._hovered_btn = btn
                self.setCursor(Qt.PointingHandCursor if btn else Qt.ArrowCursor)
                self.update()
        else:
            if not self._hovered_capsule:
                self._hovered_capsule = True
                self.setCursor(Qt.PointingHandCursor)
                self.update()

    def leaveEvent(self, event):
        if self._hovered_btn or self._hovered_capsule:
            self._hovered_btn = None
            self._hovered_capsule = False
            self.setCursor(Qt.ArrowCursor)
            self.update()

    def mousePressEvent(self, event):
        """Handles left-click mode selection/expansion and right-click menu."""
        if event.button() == Qt.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
            return

        if event.button() == Qt.LeftButton:
            pos = event.position()
            if not self.is_expanded:
                # User clicked on the folded pill -> Hit-test Robot, Chat, Voice, or Wake
                click_x = pos.x()
                if 38.0 <= click_x < 54.0:
                    event_bus.toggle_overlay_signal.emit()
                    return
                elif 54.0 <= click_x < 70.0:
                    event_bus.toggle_voice_record_signal.emit()
                    return
                elif click_x >= 70.0:
                    self._on_toggle_wake_word()
                    return
                else:
                    self.expand_manually()
                    return

            btn = self._get_button_at_pos(pos)
            if getattr(self, "_pending_approval_active", False):
                if btn == "approve":
                    event_bus.approval_resolved.emit(True)
                    return
                elif btn == "reject":
                    event_bus.approval_resolved.emit(False)
                    return

            if btn == "voice":
                event_bus.toggle_voice_record_signal.emit()
                self._reset_auto_fold_timer()
            elif btn == "chat":
                event_bus.toggle_overlay_signal.emit()
                self._reset_auto_fold_timer()
            elif btn == "wake":
                self._on_toggle_wake_word()
                self._reset_auto_fold_timer()
            elif btn == "menu":
                global_pos = self.mapToGlobal(QPoint(int(296), int(self.height() + 2)))
                self._show_context_menu(global_pos)
            else:
                # Clicked on robot or background: if idle, fold back
                if self.current_state == "idle":
                    self.fold_manually()

    def on_state_changed(self, new_state: str):
        """Slot for state_changed signal from event_bus."""
        clean_state = new_state.lower().strip()
        if clean_state not in self.STATES:
            if "listen" in clean_state:
                clean_state = "listening"
            elif "think" in clean_state:
                clean_state = "thinking"
            elif "speak" in clean_state:
                clean_state = "speaking"
            elif "tool" in clean_state:
                clean_state = "running_tool"
            else:
                clean_state = "idle"

        prev_state = self.current_state
        self.current_state = clean_state

        # Adaptive FPS: 60 FPS for active states, 30 FPS for folded idle
        if self.current_state == "idle":
            self.render_timer.setInterval(33)  # 30 FPS
            self._custom_subtext = ""
            if not self._manually_expanded:
                self.hide()
            else:
                self._reset_auto_fold_timer()
        else:
            self.render_timer.setInterval(16)  # 60 FPS
            # Single-Screen State Guard: only show island on the active cursor screen
            cursor_pos = QCursor.pos()
            active_scr = QGuiApplication.screenAt(cursor_pos) or (QApplication.instance().primaryScreen() if QApplication.instance() else None)
            my_scr = self.screen or (self.window().screen() if hasattr(self, 'window') else None)
            if active_scr and my_scr and (my_scr != active_scr):
                self.hide()
                return

            self.show()
            self.raise_()
            self._apply_geometry_for_state(animated=True)

        self.update()

    def _on_task_log_updated(self, title: str, content: str):
        """Displays user-friendly task updates in subtext if active."""
        if self.current_state != "idle" and content:
            clean = content.strip().split("\n")[0]
            if len(clean) > 55:
                clean = clean[:52] + "..."
            self._custom_subtext = clean
            self.update()

    def _on_animation_tick(self):
        """60 FPS / 30 FPS tick updating kinematics, quirks, and Chill Pixel Life standby."""
        now = time.time()
        t = now - self.start_time

        # Update Chill Pixel Life standby engine (30 FPS dt ~ 0.033)
        if hasattr(self, "pixel_engine"):
            dt = 0.016 if self.is_expanded else 0.033
            self.pixel_engine.update(dt)

        # Autonomous Quirks engine during idle or listening (expanded mode)
        if (self.current_state in ("idle", "listening")) and (self.active_quirk is None) and (t >= self.next_auto_quirk_time):
            self.active_quirk = random.choice(self.QUIRK_NAMES)
            self.quirk_start_time = t
            self.quirk_duration = 1.9 if self.active_quirk == "mini_yawn" else 1.5
            self.next_auto_quirk_time = t + random.uniform(3.0, 5.5)

        # Always-On-Top Guard: Ensure window stays visible if expanded mode is active
        if self.is_expanded and not self.isVisible():
            self.show()
            self.raise_()

        self.update()

    # =========================================================================
    # Pure Vector Graphics (QPainter Cyber Mini-Robot Avatar)
    # =========================================================================

    def paintEvent(self, event):
        """Renders 60 FPS cyber capsule and animated vector robot avatar."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        w = self.width()
        h = self.height()
        is_folded = (w < 120)

        cfg = self.STATES.get(self.current_state, self.STATES["idle"])
        neon_color = cfg["color"]

        t = time.time() - self.start_time

        # 2. Render Avatar / Standby Pill
        if is_folded:
            # Standby Mode in Menu Bar: Chill Pixel Life & Pill Waveform (88x22)
            if hasattr(self, "pixel_engine"):
                img = render_standby_frame(
                    self.pixel_engine,
                    scale=2.0,
                    is_wake_on=config.WAKE_TRIGGER_ENABLED,
                    is_light_bg=False
                )
                painter.drawImage(QRectF(0, 0, w, h), img)
            else:
                rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
                radius = h / 2.0
                bg_color = QColor(7, 11, 19, 240)
                border_alpha = 220 if self._hovered_capsule else 100
                border_pen = QPen(QColor(neon_color.red(), neon_color.green(), neon_color.blue(), border_alpha), 1.2)
                border_pen.setCosmetic(True)
                painter.setBrush(QBrush(bg_color))
                painter.setPen(border_pen)
                painter.drawRoundedRect(rect, radius, radius)
                painter.save()
                scale_s = (h - 4.0) / 48.0
                painter.translate(6.0, 2.0)
                painter.scale(scale_s, scale_s)
                self._draw_cyber_robot(painter, t, cfg, is_mini=True)
                painter.restore()
        else:
            # Expanded Mode: Capsule Background with Frosting & Cyber Border
            rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
            radius = 18.0
            bg_color = QColor(7, 11, 19, 240)
            border_pen = QPen(QColor(neon_color.red(), neon_color.green(), neon_color.blue(), 100), 1.2)
            border_pen.setCosmetic(True)
            painter.setBrush(QBrush(bg_color))
            painter.setPen(border_pen)
            painter.drawRoundedRect(rect, radius, radius)

            # Expanded Mode: Full 48x48 animated avatar on the left
            painter.save()
            painter.translate(8.0, 11.0)
            self._draw_cyber_robot(painter, t, cfg, is_mini=False)
            painter.restore()

            # Status Texts or Robot Speech Bubble (Top area)
            text_x = 62.0
            text_w = w - text_x - 30.0

            show_bubble = bool(self._bubble_title and time.time() < self._bubble_expire_time)
            if show_bubble:
                # Robot Speech Bubble (Pure Vector QPainterPath pointing to robot)
                rem = self._bubble_expire_time - time.time()
                bubble_alpha = min(1.0, rem / 0.35) if rem < 0.35 else 1.0

                bubble_rect = QRectF(text_x, 5.0, text_w, 33.0)
                beak = QPainterPath()
                beak.moveTo(text_x, 17.0)
                beak.lineTo(text_x - 7.0, 21.0)
                beak.lineTo(text_x, 25.0)
                beak.closeSubpath()

                bubble_path = QPainterPath()
                bubble_path.addRoundedRect(bubble_rect, 6.0, 6.0)
                bubble_path = bubble_path.united(beak)

                bubble_bg = QColor(10, 16, 29, int(240 * bubble_alpha))
                b_color = self._bubble_title_color
                bubble_border = QColor(b_color.red(), b_color.green(), b_color.blue(), int(210 * bubble_alpha))

                painter.save()
                painter.setBrush(QBrush(bubble_bg))
                b_pen = QPen(bubble_border, 1.2)
                b_pen.setCosmetic(True)
                painter.setPen(b_pen)
                painter.drawPath(bubble_path)

                # Bubble Title
                font_b_title = painter.font()
                font_b_title.setStyleHint(QFont.SansSerif)
                font_b_title.setFamily("-apple-system")
                font_b_title.setPointSize(8)
                font_b_title.setWeight(QFont.Bold)
                painter.setFont(font_b_title)
                t_col = QColor(b_color.red(), b_color.green(), b_color.blue(), int(255 * bubble_alpha))
                painter.setPen(QPen(t_col, 1))
                painter.drawText(QRectF(text_x + 6.0, 7.0, text_w - 12.0, 14.0), Qt.AlignLeft | Qt.AlignVCenter, self._bubble_title)

                # Bubble Subtext
                font_b_sub = painter.font()
                font_b_sub.setStyleHint(QFont.SansSerif)
                font_b_sub.setFamily("-apple-system")
                font_b_sub.setPointSize(7)
                font_b_sub.setWeight(QFont.Medium)
                painter.setFont(font_b_sub)
                s_col = QColor(226, 232, 240, int(230 * bubble_alpha))
                painter.setPen(QPen(s_col, 1))
                painter.drawText(QRectF(text_x + 6.0, 21.0, text_w - 12.0, 14.0), Qt.AlignLeft | Qt.AlignVCenter, self._bubble_subtext or "")
                painter.restore()
            else:
                # Title
                painter.setPen(QPen(neon_color, 1))
                font_title = painter.font()
                font_title.setStyleHint(QFont.Monospace)
                font_title.setFamily("Menlo")
                font_title.setPointSize(9)
                font_title.setWeight(QFont.Bold)
                painter.setFont(font_title)
                painter.drawText(QRectF(text_x, 8.0, 95.0, 16.0), Qt.AlignLeft | Qt.AlignVCenter, "K.A.R.I.S. // JR.")

                # Status Text
                painter.setPen(QPen(QColor("#F1F5F9"), 1))
                font_status = painter.font()
                font_status.setStyleHint(QFont.SansSerif)
                font_status.setFamily("-apple-system")
                font_status.setPointSize(9)
                font_status.setWeight(QFont.Medium)
                painter.setFont(font_status)
                painter.drawText(QRectF(text_x + 92.0, 8.0, text_w - 92.0, 16.0), Qt.AlignLeft | Qt.AlignVCenter, f"• {cfg['status']}")

                # Subtext
                subtext_str = self._custom_subtext if self._custom_subtext else cfg["subtext"]
                painter.setPen(QPen(QColor("#94A3B8"), 1))
                font_sub = painter.font()
                font_sub.setStyleHint(QFont.SansSerif)
                font_sub.setFamily("-apple-system")
                font_sub.setPointSize(8)
                font_sub.setWeight(QFont.Normal)
                painter.setFont(font_sub)
                painter.drawText(QRectF(text_x, 24.0, text_w, 14.0), Qt.AlignLeft | Qt.AlignVCenter, subtext_str)

            # Mini Live Wave Indicator (Top right edge)
            wave_x = w - 24.0
            wave_y = 15.0
            painter.setPen(Qt.NoPen)
            for i in range(3):
                bar_mult = 1.0 if self.current_state == "speaking" else (0.65 if self.current_state == "listening" else 0.25)
                bar_h = 3.0 + abs(math.sin(t * (8.0 + i * 2.5) + i)) * 10.0 * bar_mult
                bx = wave_x + i * 4.0
                by = wave_y - bar_h / 2.0
                painter.setBrush(QBrush(neon_color))
                painter.drawRoundedRect(QRectF(bx, by, 2.0, bar_h), 1.0, 1.0)

            # 3. Interactive Mode Selection Buttons (Bottom Row)
            btns = self._get_buttons_map()
            for name, b_rect in btns.items():
                is_hover = (self._hovered_btn == name)
                painter.save()

                if name == "approve":
                    label = "✓ Approve"
                    accent = QColor("#00FFD1")
                    bg_col = QColor(0, 255, 209, 65) if is_hover else QColor(10, 40, 35, 210)
                    bd_col = QColor(0, 255, 209, 240) if is_hover else QColor(0, 255, 209, 140)
                elif name == "reject":
                    label = "✕ Reject"
                    accent = QColor("#FB7185")
                    bg_col = QColor(251, 113, 133, 65) if is_hover else QColor(40, 15, 25, 210)
                    bd_col = QColor(251, 113, 133, 240) if is_hover else QColor(251, 113, 133, 140)
                elif name == "voice":
                    label = "🎙️ Voice"
                    accent = QColor("#00FFD1")
                    bg_col = QColor(0, 255, 209, 50) if is_hover else QColor(10, 28, 32, 190)
                    bd_col = QColor(0, 255, 209, 220) if is_hover else QColor(0, 255, 209, 80)
                elif name == "chat":
                    label = "💬 Chat"
                    accent = QColor("#38BDF8")
                    bg_col = QColor(56, 189, 248, 50) if is_hover else QColor(10, 24, 38, 190)
                    bd_col = QColor(56, 189, 248, 220) if is_hover else QColor(56, 189, 248, 80)
                elif name == "wake":
                    is_wake_on = config.WAKE_TRIGGER_ENABLED
                    label = "⚡ Wake: ON" if is_wake_on else "⚡ Wake: OFF"
                    accent = QColor("#00FFD1") if is_wake_on else QColor("#94A3B8")
                    if is_wake_on:
                        bg_col = QColor(0, 255, 209, 55) if is_hover else QColor(10, 32, 38, 210)
                        bd_col = QColor(0, 255, 209, 240) if is_hover else QColor(0, 255, 209, 140)
                        # Outer Glow for Active Wake Standby
                        glow_pen = QPen(QColor(0, 255, 209, 45), 2.2)
                        glow_pen.setCosmetic(True)
                        painter.setPen(glow_pen)
                        painter.setBrush(Qt.NoBrush)
                        painter.drawRoundedRect(b_rect.adjusted(-1.5, -1.5, 1.5, 1.5), 7.0, 7.0)
                    else:
                        bg_col = QColor(148, 163, 184, 40) if is_hover else QColor(20, 24, 30, 190)
                        bd_col = QColor(148, 163, 184, 180) if is_hover else QColor(100, 116, 139, 70)
                else:  # menu
                    label = "⚙️ More"
                    accent = QColor("#94A3B8")
                    bg_col = QColor(148, 163, 184, 50) if is_hover else QColor(15, 23, 42, 190)
                    bd_col = QColor(148, 163, 184, 220) if is_hover else QColor(100, 116, 139, 70)

                painter.setBrush(QBrush(bg_col))
                painter.setPen(QPen(bd_col, 1))
                painter.drawRoundedRect(b_rect, 6.0, 6.0)

                font_btn = painter.font()
                font_btn.setStyleHint(QFont.SansSerif)
                font_btn.setFamily("-apple-system")
                font_btn.setPointSize(8)
                font_btn.setWeight(QFont.Bold if is_hover else QFont.Medium)
                painter.setFont(font_btn)
                text_col = QColor("#FFFFFF") if is_hover else (accent if name == "wake" else QColor("#E2E8F0"))
                painter.setPen(QPen(text_col, 1))
                painter.drawText(b_rect, Qt.AlignCenter, label)

                if name == "wake" and is_wake_on:
                    # Draw mini mint status LED on top-right of wake button
                    dot_x = b_rect.right() - 8.0
                    dot_y = b_rect.top() + 6.0
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QBrush(QColor("#00FFD1")))
                    painter.drawEllipse(QPointF(dot_x, dot_y), 2.0, 2.0)

                painter.restore()

    def _draw_cyber_robot(self, painter: QPainter, t: float, cfg: Dict[str, Any], is_mini: bool = False):
        """
        Pure QPainter Vector Renderer of the Cyber Mini-Robot Avatar.
        Normalized to a 48x48 coordinate box matching the visual mockup.
        """
        neon = cfg["color"]
        bg_tint = cfg["bg_tint"]
        visor_tint = cfg["visor_tint"]

        # Evaluate Quirk Envelope (0 -> 1 -> 0 smooth bell curve)
        q_env = 0.0
        q_prog = 0.0
        if self.active_quirk:
            q_prog = (t - self.quirk_start_time) / self.quirk_duration
            if q_prog >= 1.0:
                self.active_quirk = None
            else:
                q_env = math.sin(q_prog * math.pi)

        # Kinematics Computation
        body_y = 0.0
        head_tilt = 0.0
        head_bob_y = 0.0
        look_x = 0.0
        look_y = 0.0
        antenna_angle = math.sin(t * 3.2) * 0.08
        left_paw_y = 0.0
        right_paw_y = 0.0
        left_paw_x = 0.0
        right_paw_x = 0.0

        st = self.current_state
        if st == "speaking":
            body_y = -abs(math.sin(t * 7.5)) * 1.6
            head_tilt = math.sin(t * 5.2) * 0.09
            head_bob_y = -abs(math.cos(t * 7.5)) * 0.7
            antenna_angle = math.sin(t * 11.0) * 0.22
            left_paw_y = -2.2 + math.sin(t * 8.0) * 1.8
            right_paw_y = -2.2 + math.sin(t * 8.0 + math.pi) * 1.8
        elif st == "listening":
            body_y = math.sin(t * 2.6) * 0.6
            head_tilt = -0.11 + math.sin(t * 2.0) * 0.03
            antenna_angle = math.sin(t * 9.0) * 0.25
            left_paw_y = math.sin(t * 2.6) * 0.7
            right_paw_y = math.cos(t * 2.6) * 0.7
        elif st == "thinking":
            body_y = math.sin(t * 2.2) * 0.9
            look_x = math.sin(t * 3.4) * 2.3
            look_y = -0.5
            right_paw_y = -5.5 + math.sin(t * 3.0) * 0.5
            right_paw_x = -2.5
            left_paw_y = math.sin(t * 2.2) * 0.6
        elif st == "running_tool":
            body_y = math.sin(t * 6.0) * 0.45
            look_x = math.sin(t * 9.5) * 2.6
            left_paw_y = -3.8 + math.sin(t * 22.0) * 1.6
            right_paw_y = -3.8 + math.sin(t * 22.0 + math.pi) * 1.6
            left_paw_x = 1.4
            right_paw_x = -1.4
        elif st == "wake_ack":
            body_y = -abs(math.sin(t * 6.8)) * 2.8
            head_tilt = math.sin(t * 6.8) * 0.11
            antenna_angle = math.sin(t * 14.0) * 0.3
            left_paw_y = -6.2 + math.sin(t * 10.0) * 1.2
            right_paw_y = -6.2 + math.cos(t * 10.0) * 1.2
        elif st == "confused":
            body_y = math.sin(t * 2.4) * 0.5
            head_tilt = 0.24 + math.sin(t * 3.5) * 0.04
            left_paw_y = -3.2
            right_paw_y = 0.4
        else:
            # idle gentle breathing
            body_y = math.sin(t * 2.1) * 0.85
            left_paw_y = math.sin(t * 2.1 + 0.5) * 0.9
            right_paw_y = math.sin(t * 2.1 + 0.5) * 0.9

        # Apply Autonomous Quirk Modifiers
        if self.active_quirk == "look_around":
            look_x += math.sin(q_prog * math.pi * 2.0) * 3.0
            head_tilt += math.sin(q_prog * math.pi * 2.0) * 0.12
        elif self.active_quirk == "double_blink":
            antenna_angle += math.sin(q_prog * math.pi * 6.0) * 0.35 * q_env
        elif self.active_quirk == "hum_hop":
            body_y -= abs(math.sin(q_prog * math.pi * 3.0)) * 2.2
            head_tilt += math.sin(q_prog * math.pi * 4.0) * 0.12
            left_paw_y -= q_env * 2.5
            right_paw_y -= q_env * 2.5
        elif self.active_quirk == "mini_yawn":
            head_tilt -= q_env * 0.14
            head_bob_y -= q_env * 0.9
            left_paw_y -= q_env * 5.2
            right_paw_y -= q_env * 5.2
            left_paw_x -= q_env * 1.2
            right_paw_x += q_env * 1.2
        elif self.active_quirk == "curious_nod":
            head_tilt += q_env * 0.18
            head_bob_y += abs(math.sin(q_prog * math.pi * 2.0)) * 1.4

        # Configure cosmetic pens for Retina crispness
        main_pen = QPen(neon, 1.6)
        main_pen.setCosmetic(True)
        thin_pen = QPen(neon, 1.1)
        thin_pen.setCosmetic(True)

        # Low-Poly Facet Shading based on head_tilt
        tilt_ratio = max(-1.0, min(1.0, head_tilt * 4.0))
        def _facet_color(delta: float) -> QColor:
            factor = max(0.0, min(1.0, 0.5 + delta * 0.5))
            r = int(5 + (14 - 5) * factor)
            g = int(22 + (58 - 22) * factor)
            b = int(36 + (93 - 36) * factor)
            return QColor(r, g, b)

        col_forehead = _facet_color(0.3)
        col_temple_l = _facet_color(-tilt_ratio * 0.6)
        col_temple_r = _facet_color(tilt_ratio * 0.6)
        col_cheek_l = _facet_color(-tilt_ratio * 0.9)
        col_cheek_r = _facet_color(tilt_ratio * 0.9)

        painter.translate(0.0, body_y + 1.2)

        # 1. Low-Poly Faceted Torso & Shoulders (Skip or simplify in mini mode)
        if not is_mini:
            torso_mesh_pen = QPen(QColor(0, 229, 255, 90), 1.0)
            torso_mesh_pen.setCosmetic(True)

            poly_chest_center = QPolygonF([
                QPointF(18.2, 29.2), QPointF(29.8, 29.2),
                QPointF(32.0, 42.5), QPointF(16.0, 42.5)
            ])
            poly_shoulder_l = QPolygonF([
                QPointF(12.5, 34.8), QPointF(18.2, 29.2),
                QPointF(16.0, 42.5), QPointF(12.5, 42.5)
            ])
            poly_shoulder_r = QPolygonF([
                QPointF(29.8, 29.2), QPointF(35.5, 34.8),
                QPointF(35.5, 42.5), QPointF(32.0, 42.5)
            ])

            painter.setPen(torso_mesh_pen)
            painter.setBrush(QBrush(QColor("#081D2E")))
            painter.drawPolygon(poly_chest_center)
            painter.setBrush(QBrush(QColor("#061624")))
            painter.drawPolygon(poly_shoulder_l)
            painter.setBrush(QBrush(QColor("#0A2438")))
            painter.drawPolygon(poly_shoulder_r)

            # Outer torso contour
            painter.setPen(main_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawLine(QPointF(12.5, 42.5), QPointF(12.5, 34.8))
            painter.drawLine(QPointF(12.5, 34.8), QPointF(18.2, 29.2))
            painter.drawLine(QPointF(18.2, 29.2), QPointF(29.8, 29.2))
            painter.drawLine(QPointF(29.8, 29.2), QPointF(35.5, 34.8))
            painter.drawLine(QPointF(35.5, 34.8), QPointF(35.5, 42.5))

            # Torso Vertex Nodes
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor("#00E5FF")))
            for vpt in [QPointF(12.5, 34.8), QPointF(18.2, 29.2), QPointF(29.8, 29.2), QPointF(35.5, 34.8), QPointF(16.0, 42.5), QPointF(32.0, 42.5)]:
                painter.drawEllipse(vpt, 1.0, 1.0)

            # Chest Core / Equalizer
            painter.setBrush(Qt.NoBrush)
            painter.setPen(thin_pen)
            painter.drawRoundedRect(QRectF(18.2, 32.5, 11.6, 7.6), 2.0, 2.0)

            if st == "speaking" or self.active_quirk == "hum_hop":
                b1 = 2.0 + abs(math.sin(t * 14.0)) * 3.4
                b2 = 2.2 + abs(math.sin(t * 11.0 + 1.2)) * 3.8
                b3 = 2.0 + abs(math.cos(t * 13.0)) * 3.4
                painter.setBrush(QBrush(neon))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(QRectF(20.0, 38.6 - b1, 1.6, b1), 0.7, 0.7)
                painter.drawRoundedRect(QRectF(23.2, 38.6 - b2, 1.6, b2), 0.7, 0.7)
                painter.drawRoundedRect(QRectF(26.4, 38.6 - b3, 1.6, b3), 0.7, 0.7)
            elif st in ("running_tool", "thinking"):
                active_dot = int(t * (10 if st == "running_tool" else 4)) % 3
                painter.setPen(Qt.NoPen)
                for idx, cx in enumerate([20.5, 24.0, 27.5]):
                    alpha = 255 if idx == active_dot else 70
                    painter.setBrush(QBrush(QColor(neon.red(), neon.green(), neon.blue(), alpha)))
                    painter.drawEllipse(QPointF(cx, 36.3), 1.25, 1.25)
            else:
                pulse_w = 5.0 + math.sin(t * 3.0) * 1.4
                painter.setBrush(QBrush(neon))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(QRectF(24.0 - pulse_w / 2.0, 35.5, pulse_w, 1.6), 0.8, 0.8)

            # Neck Connectors
            painter.setPen(main_pen)
            painter.drawLine(QPointF(21.0, 26.2), QPointF(21.0, 29.2))
            painter.drawLine(QPointF(27.0, 26.2), QPointF(27.0, 29.2))

        # 2. Faceted Poly-Head Group (Rotates around neck 24, 25)
        painter.save()
        painter.translate(24.0, 25.0 + head_bob_y)
        painter.rotate(math.degrees(head_tilt))
        painter.translate(-24.0, -25.0)

        # Antenna with Diamond Crystal Tip
        painter.save()
        painter.translate(24.0, 8.2)
        painter.rotate(math.degrees(antenna_angle))
        painter.setPen(main_pen)
        painter.drawLine(QPointF(0.0, 0.0), QPointF(0.0, -4.2))

        tip_scale = 1.25 if st == "listening" else 1.0
        poly_crystal_tip = QPolygonF([
            QPointF(0.0, -6.8 * tip_scale),
            QPointF(2.1 * tip_scale, -4.9 * tip_scale),
            QPointF(0.0, -3.0 * tip_scale),
            QPointF(-2.1 * tip_scale, -4.9 * tip_scale),
        ])
        painter.setBrush(QBrush(neon))
        painter.setPen(thin_pen)
        painter.drawPolygon(poly_crystal_tip)
        painter.restore()

        # Prism Ear Pods
        poly_ear_l = QPolygonF([
            QPointF(11.4, 14.0), QPointF(8.4, 15.5),
            QPointF(8.4, 20.0), QPointF(11.4, 21.5)
        ])
        poly_ear_r = QPolygonF([
            QPointF(36.6, 14.0), QPointF(39.6, 15.5),
            QPointF(39.6, 20.0), QPointF(36.6, 21.5)
        ])
        painter.setPen(thin_pen)
        painter.setBrush(QBrush(QColor("#071E2E")))
        painter.drawPolygon(poly_ear_l)
        painter.drawPolygon(poly_ear_r)

        # Faceted Poly-Head Shell (Forehead, Temples, Cheeks)
        poly_forehead = QPolygonF([
            QPointF(16.5, 8.2), QPointF(31.5, 8.2),
            QPointF(34.5, 11.2), QPointF(24.0, 11.8),
            QPointF(13.5, 11.2)
        ])
        poly_temple_l = QPolygonF([
            QPointF(13.5, 11.2), QPointF(24.0, 11.8),
            QPointF(24.0, 16.0), QPointF(11.4, 16.0),
            QPointF(11.4, 14.0)
        ])
        poly_temple_r = QPolygonF([
            QPointF(24.0, 11.8), QPointF(34.5, 11.2),
            QPointF(36.6, 14.0), QPointF(36.6, 16.0),
            QPointF(24.0, 16.0)
        ])
        poly_cheek_l = QPolygonF([
            QPointF(11.4, 16.0), QPointF(24.0, 16.0),
            QPointF(24.0, 26.2), QPointF(16.5, 26.2),
            QPointF(11.4, 22.0)
        ])
        poly_cheek_r = QPolygonF([
            QPointF(24.0, 16.0), QPointF(36.6, 16.0),
            QPointF(36.6, 22.0), QPointF(31.5, 26.2),
            QPointF(24.0, 26.2)
        ])

        mesh_head_pen = QPen(QColor(0, 229, 255, 95), 1.0)
        mesh_head_pen.setCosmetic(True)

        painter.setPen(mesh_head_pen)
        painter.setBrush(QBrush(col_forehead))
        painter.drawPolygon(poly_forehead)
        painter.setBrush(QBrush(col_temple_l))
        painter.drawPolygon(poly_temple_l)
        painter.setBrush(QBrush(col_temple_r))
        painter.drawPolygon(poly_temple_r)
        painter.setBrush(QBrush(col_cheek_l))
        painter.drawPolygon(poly_cheek_l)
        painter.setBrush(QBrush(col_cheek_r))
        painter.drawPolygon(poly_cheek_r)

        # Outer Head Contour
        painter.setPen(main_pen)
        painter.setBrush(Qt.NoBrush)
        head_outline = QPainterPath()
        head_outline.moveTo(16.5, 8.2)
        head_outline.lineTo(31.5, 8.2)
        head_outline.lineTo(36.6, 14.0)
        head_outline.lineTo(36.6, 22.0)
        head_outline.lineTo(31.5, 26.2)
        head_outline.lineTo(16.5, 26.2)
        head_outline.lineTo(11.4, 22.0)
        head_outline.lineTo(11.4, 14.0)
        head_outline.closeSubpath()
        painter.drawPath(head_outline)

        # Head Vertex Nodes
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor("#00E5FF")))
        for hpt in [QPointF(16.5, 8.2), QPointF(31.5, 8.2), QPointF(36.6, 14.0), QPointF(36.6, 22.0), QPointF(31.5, 26.2), QPointF(16.5, 26.2), QPointF(11.4, 22.0), QPointF(11.4, 14.0)]:
            painter.drawEllipse(hpt, 0.9, 0.9)

        # Hexagonal Dark Visor (QPolygonF)
        poly_visor = QPolygonF([
            QPointF(14.2, 17.0),
            QPointF(17.8, 11.2),
            QPointF(30.2, 11.2),
            QPointF(33.8, 17.0),
            QPointF(30.2, 22.8),
            QPointF(17.8, 22.8),
        ])
        painter.setBrush(QBrush(visor_tint))
        painter.setPen(thin_pen)
        painter.drawPolygon(poly_visor)

        # 3. Eyes & Mouth Inside Visor
        painter.save()
        painter.translate(look_x, look_y)

        # Blink calculation
        periodic_blink = (t % 3.6) > 3.46
        quirk_blink = (self.active_quirk == "double_blink") and (
            (0.15 < q_prog < 0.32) or (0.52 < q_prog < 0.70)
        )
        is_blinking = periodic_blink or quirk_blink or (self.active_quirk == "mini_yawn")

        # --- EYES ---
        eye_pen = QPen(neon, 1.65)
        eye_pen.setCosmetic(True)
        painter.setPen(eye_pen)

        if is_blinking:
            # Closed blink lines
            painter.drawLine(QPointF(16.6, 16.0), QPointF(20.6, 16.0))
            painter.drawLine(QPointF(27.4, 16.0), QPointF(31.4, 16.0))
        elif st in ("speaking", "wake_ack") or self.active_quirk == "hum_hop":
            # Happy Arched Eyes (^ ^)
            p1 = QPainterPath()
            p1.moveTo(16.6, 16.6)
            p1.quadTo(18.6, 13.6, 20.6, 16.6)
            p2 = QPainterPath()
            p2.moveTo(27.4, 16.6)
            p2.quadTo(29.4, 13.6, 31.4, 16.6)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(p1)
            painter.drawPath(p2)
        elif st in ("thinking", "running_tool"):
            # Visor Scanning Bars
            bar_w = 4.8 if st == "running_tool" else 5.4
            painter.setBrush(QBrush(neon))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(QRectF(16.4, 14.6, bar_w, 2.6), 1.2, 1.2)
            painter.drawRoundedRect(QRectF(26.8, 14.6, bar_w, 2.6), 1.2, 1.2)
        elif st == "confused":
            # Left eye circle O, right eye slit -
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(18.6, 15.6), 2.2, 2.2)
            painter.drawLine(QPointF(27.2, 16.0), QPointF(31.4, 15.4))
        elif st == "listening":
            # Sparkly attentive round eyes
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(18.6, 15.6), 2.25, 2.25)
            painter.drawEllipse(QPointF(29.4, 15.6), 2.25, 2.25)
            painter.setBrush(QBrush(QColor("#FFFFFF")))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(19.3, 14.9), 0.7, 0.7)
            painter.drawEllipse(QPointF(30.1, 14.9), 0.7, 0.7)
        else:
            # Soft friendly dots
            painter.setBrush(QBrush(neon))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(18.6, 15.8), 1.75, 1.75)
            painter.drawEllipse(QPointF(29.4, 15.8), 1.75, 1.75)

        # --- MOUTH ---
        mouth_pen = QPen(neon, 1.45)
        mouth_pen.setCosmetic(True)
        painter.setPen(mouth_pen)
        painter.setBrush(Qt.NoBrush)

        mouth_cx = 24.0
        mouth_cy = 20.4

        if self.active_quirk == "mini_yawn":
            yawn_r = 1.0 + q_env * 2.1
            painter.drawEllipse(QPointF(mouth_cx, mouth_cy - 0.2), yawn_r * 0.85, yawn_r)
        elif self.active_quirk == "hum_hop":
            hum_r = 1.1 + abs(math.sin(t * 14.0)) * 0.9
            painter.drawEllipse(QPointF(mouth_cx, mouth_cy), hum_r, hum_r)
        elif st == "speaking":
            syllable = abs(math.sin(t * 14.5) * math.cos(t * 6.2))
            mouth_w = 3.4 + math.sin(t * 10.0) * 1.4
            mouth_h = 0.8 + syllable * 3.1
            if syllable > 0.55:
                # Open D-Shape mouth
                d_path = QPainterPath()
                d_path.moveTo(mouth_cx - mouth_w / 2.0, mouth_cy - 0.7)
                d_path.lineTo(mouth_cx + mouth_w / 2.0, mouth_cy - 0.7)
                d_path.quadTo(mouth_cx, mouth_cy + mouth_h + 0.8, mouth_cx - mouth_w / 2.0, mouth_cy - 0.7)
                painter.setBrush(QBrush(QColor(neon.red(), neon.green(), neon.blue(), 90)))
                painter.drawPath(d_path)
            else:
                painter.drawRoundedRect(QRectF(mouth_cx - mouth_w / 2.0, mouth_cy - mouth_h / 2.0, mouth_w, max(1.2, mouth_h)), 1.4, 1.4)
        elif st == "listening":
            pulse_o = 1.35 + math.sin(t * 5.0) * 0.2
            painter.drawEllipse(QPointF(mouth_cx, mouth_cy), pulse_o, pulse_o)
        elif st == "thinking":
            # Wavy ponder ~
            shift = math.sin(t * 5.0) * 0.5
            w_path = QPainterPath()
            w_path.moveTo(21.2, mouth_cy + shift)
            w_path.quadTo(22.6, mouth_cy - 1.2 - shift, 24.0, mouth_cy)
            w_path.quadTo(25.4, mouth_cy + 1.2 + shift, 26.8, mouth_cy - shift)
            painter.drawPath(w_path)
        elif st == "running_tool":
            painter.drawLine(QPointF(21.4, mouth_cy), QPointF(26.6, mouth_cy - 0.3))
        elif st == "wake_ack":
            d_path = QPainterPath()
            d_path.moveTo(20.6, mouth_cy - 0.8)
            d_path.lineTo(27.4, mouth_cy - 0.8)
            d_path.quadTo(24.0, mouth_cy + 3.2, 20.6, mouth_cy - 0.8)
            painter.setBrush(QBrush(QColor(neon.red(), neon.green(), neon.blue(), 80)))
            painter.drawPath(d_path)
        elif st == "confused":
            c_path = QPainterPath()
            c_path.moveTo(21.4, mouth_cy + 0.6)
            c_path.quadTo(24.0, mouth_cy - 1.0, 26.6, mouth_cy + 0.5)
            painter.drawPath(c_path)
        else:
            # Idle gentle smile
            s_path = QPainterPath()
            s_path.moveTo(21.6, mouth_cy - 0.3)
            s_path.quadTo(24.0, mouth_cy + 1.3, 26.4, mouth_cy - 0.3)
            painter.drawPath(s_path)

        painter.restore()  # End gaze offset
        painter.restore()  # End head rotation

        # Confused floating '?' mark
        if st == "confused":
            q_float = math.sin(t * 4.5) * 1.2
            painter.setPen(QPen(neon, 1))
            font_confused = QFont("Menlo", 7, QFont.Bold)
            font_confused.setStyleHint(QFont.Monospace)
            painter.setFont(font_confused)
            painter.drawText(QPointF(39.0, 11.5 + q_float), "?")

        # 4. Floating Crystal Paws (Hands)
        if not is_mini:
            paw_pen = QPen(neon, 1.2)
            paw_pen.setCosmetic(True)
            painter.setPen(paw_pen)
            painter.setBrush(QBrush(QColor("#082033")))

            poly_paw_l = QPolygonF([
                QPointF(9.0 + left_paw_x, 34.0 + left_paw_y),
                QPointF(11.4 + left_paw_x, 37.0 + left_paw_y),
                QPointF(9.0 + left_paw_x, 40.0 + left_paw_y),
                QPointF(6.6 + left_paw_x, 37.0 + left_paw_y)
            ])
            poly_paw_r = QPolygonF([
                QPointF(39.0 + right_paw_x, 34.0 + right_paw_y),
                QPointF(41.4 + right_paw_x, 37.0 + right_paw_y),
                QPointF(39.0 + right_paw_x, 40.0 + right_paw_y),
                QPointF(36.6 + right_paw_x, 37.0 + right_paw_y)
            ])
            painter.drawPolygon(poly_paw_l)
            painter.drawPolygon(poly_paw_r)

            # Crystal paw core nodes
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor("#00E5FF")))
            painter.drawEllipse(QPointF(9.0 + left_paw_x, 37.0 + left_paw_y), 0.8, 0.8)
            painter.drawEllipse(QPointF(39.0 + right_paw_x, 37.0 + right_paw_y), 0.8, 0.8)


# =============================================================================
# Multi-Screen Dynamic Island Manager & Native NSStatusItem Integration
# =============================================================================
class DynamicIslandManager:
    """
    Manages DynamicIsland instances and True Native macOS NSStatusItem.
    - Embeds 88x22 iPhone-pill in macOS Menu Bar with Chill Pixel Life Standby.
    - Synchronizes Floating Expanded Island across displays with spring popout.
    """

    def __init__(self, on_clear_history=None):
        self.on_clear_history = on_clear_history
        self.islands: list[DynamicIsland] = []
        self.status_item = None
        self._status_click_handler = None
        self.status_engine = ChillPixelLifeEngine()

        # Register instance in QApplication for anchor lookups
        app = QApplication.instance()
        if app:
            app._dynamic_island_manager = self

        self._init_islands()
        self._init_native_status_item()

        # 30 FPS Render Timer for Native NSStatusItem
        self._status_timer = QTimer()
        self._status_timer.timeout.connect(self._on_status_tick)
        self._status_timer.start(33)

        if app:
            app.screenAdded.connect(self._on_screens_changed)
            app.screenRemoved.connect(self._on_screens_changed)

    def _init_native_status_item(self):
        """Creates True Native macOS NSStatusItem embedded in Menu Bar (88pt)."""
        if sys.platform != "darwin" or not _HAS_APPKIT:
            return
        try:
            import AppKit
            import objc

            # Define Objective-C click handler
            class StatusClickHandler(AppKit.NSObject):
                def initWithManager_(self, mgr):
                    self = objc.super(StatusClickHandler, self).init()
                    if self is None:
                        return None
                    self._mgr = mgr
                    return self

                def onClick_(self, sender):
                    event = AppKit.NSApp.currentEvent()
                    e_type = event.type() if event else None
                    # NSEventTypeRightMouseUp is 4, or Control+Click
                    is_right = (e_type == 4)
                    if event and (event.modifierFlags() & AppKit.NSEventModifierFlagControl):
                        is_right = True

                    if is_right:
                        self._mgr.show_status_context_menu()
                        return

                    # Calculate local click_x inside status item button
                    click_x = 20.0
                    if event and sender:
                        try:
                            loc = event.locationInWindow()
                            pt = sender.convertPoint_fromView_(loc, None)
                            click_x = float(pt.x)
                        except Exception:
                            pass
                    self._mgr.handle_status_click(click_x)

            statusBar = AppKit.NSStatusBar.systemStatusBar()
            self.status_item = statusBar.statusItemWithLength_(88.0)
            btn = self.status_item.button()
            if btn:
                btn.setToolTip_("Jarvis: [Robot] Expand Island | [Chat] Alt+Space | [Voice] Cmd+Shift+J | [Wake] Toggle")

            self._status_click_handler = StatusClickHandler.alloc().initWithManager_(self)
            btn.setTarget_(self._status_click_handler)
            btn.setAction_(objc.selector(self._status_click_handler.onClick_, signature=b"v@:@"))
            NSEventMaskLeftMouseUp = 1 << 2
            NSEventMaskRightMouseUp = 1 << 3
            btn.sendActionOn_(NSEventMaskLeftMouseUp | NSEventMaskRightMouseUp)

            # Initial render
            self._on_status_tick()
        except Exception as e:
            # Safe fallback for environments without Cocoa WindowServer
            self.status_item = None

    def _on_status_tick(self):
        """Updates Chill Pixel Life animation and pushes Retina NSImage to NSStatusItem."""
        if not self.status_item or sys.platform != "darwin" or not _HAS_APPKIT:
            return
        try:
            import AppKit

            # Update animation step (30 FPS dt ~ 0.033)
            self.status_engine.update(0.033)

            img = render_standby_frame(
                self.status_engine,
                scale=2.0,
                is_wake_on=config.WAKE_TRIGGER_ENABLED,
                is_light_bg=False
            )
            ba = QBuffer()
            ba.open(QIODevice.WriteOnly)
            img.save(ba, "PNG")
            png_bytes = ba.data().data()

            ns_data = AppKit.NSData.dataWithBytes_length_(png_bytes, len(png_bytes))
            ns_img = AppKit.NSImage.alloc().initWithData_(ns_data)
            ns_img.setSize_(AppKit.NSMakeSize(88.0, 22.0))
            ns_img.setTemplate_(False)

            btn = self.status_item.button()
            if btn:
                btn.setImage_(ns_img)
        except Exception:
            pass

    def show_status_context_menu(self):
        """Displays dark-theme cyber context menu under NSStatusItem on active display."""
        active = self._get_active_island() or self.primary_island
        if not active:
            return
        # Calculate menu position at status item bottom
        pos = active.mapToGlobal(QPoint(active.width() - 40, active.height()))
        if sys.platform == "darwin" and self.status_item:
            try:
                import AppKit
                btn = self.status_item.button()
                if btn and btn.window():
                    wf = btn.window().frame()
                    main_h = AppKit.NSScreen.screens()[0].frame().size.height
                    item_x = int(round(wf.origin.x))
                    item_y = int(round(main_h - (wf.origin.y + wf.size.height))) + int(round(wf.size.height))
                    pos = QPoint(item_x, item_y + 2)
            except Exception:
                pass
        active._show_context_menu(pos)

    @property
    def primary_island(self) -> Optional[DynamicIsland]:
        return self.islands[0] if self.islands else None

    def _get_active_island(self) -> Optional[DynamicIsland]:
        """Returns the DynamicIsland on the currently active display (where mouse cursor is located)."""
        if not self.islands:
            return None
        cursor_pos = QCursor.pos()
        active_screen = QGuiApplication.screenAt(cursor_pos)
        if active_screen:
            for island in self.islands:
                if island.screen == active_screen:
                    return island
        return self.primary_island

    def _init_islands(self):
        """Creates an independent DynamicIsland widget docked in the menu bar of each screen."""
        for island in self.islands:
            try:
                island.close()
                island.deleteLater()
            except Exception:
                pass
        self.islands.clear()

        screens = QGuiApplication.screens()
        if not screens:
            self.islands.append(DynamicIsland(screen=None, on_clear_history=self.on_clear_history))
        else:
            for s in screens:
                island = DynamicIsland(screen=s, on_clear_history=self.on_clear_history)
                self.islands.append(island)

    def _on_screens_changed(self, screen=None):
        screens_count = len(QGuiApplication.screens())
        print(f"[DynamicIslandManager] 🖥️ Screen setup changed ({screens_count} displays). Re-syncing Dynamic Islands...")
        self._init_islands()

    def toggle_all(self):
        """Toggles between folded (hidden) and expanded (spring popout) modes on active screen."""
        any_expanded = any(isl.is_expanded for isl in self.islands)
        if any_expanded:
            self.fold_all()
        else:
            self.expand_active()

    def expand_active(self):
        """Pops out ONLY the dynamic island on the active display; keeps other displays folded."""
        active = self._get_active_island()
        for island in self.islands:
            if island is active:
                island.expand_manually()
            else:
                island.fold_manually()

    def expand_all(self):
        """Pops out all dynamic islands into expanded mode."""
        for island in self.islands:
            island.expand_manually()

    def fold_all(self):
        """Folds all dynamic islands back into menu bar pills."""
        for island in self.islands:
            island.fold_manually()

    def set_action_all(self, action_name: str):
        """Sets pixel life action across all island instances (e.g. 'wake', 'walk')."""
        self.status_engine.set_action(action_name)
        for island in self.islands:
            if hasattr(island, "pixel_engine"):
                island.pixel_engine.set_action(action_name)

    def handle_status_click(self, click_x: float):
        """Dispatches click on native NSStatusItem to Robot, Chat, Voice, or Wake based on x-coordinate."""
        print(f"[DynamicIslandManager] 🖱️ Menu Bar Dynamic Island clicked at x={click_x:.1f} pt")
        if click_x < 38.0:
            # 1. Robot Zone -> Toggle Expanded Island Pop-out window
            self.toggle_all()
        elif 38.0 <= click_x < 54.0:
            # 2. Chat Zone (💬) -> Toggle Overlay Chat (Alt+Space)
            event_bus.toggle_overlay_signal.emit()
        elif 54.0 <= click_x < 70.0:
            # 3. Voice Zone (🎙️) -> Toggle Voice Recording (Cmd+Shift+J)
            event_bus.toggle_voice_record_signal.emit()
        else:
            # 4. Wake Zone (⚡ / Dot) -> Toggle Wake Word Detection
            self._toggle_wake_word_direct()

    def _toggle_wake_word_direct(self):
        """Toggles wake word trigger directly from menu bar dot with instant visual & audio feedback."""
        config.WAKE_TRIGGER_ENABLED = not config.WAKE_TRIGGER_ENABLED
        status_text = "เปิดใช้งาน" if config.WAKE_TRIGGER_ENABLED else "ปิดชั่วคราว"
        print(f"[DynamicIslandManager] ⚡ Wake trigger toggled from Menu Bar: {config.WAKE_TRIGGER_ENABLED}")

        event_bus.voice_mode_changed.emit("wake_on" if config.WAKE_TRIGGER_ENABLED else "wake_off")
        event_bus.task_log_updated.emit(
            "Wake Trigger Updated",
            f"การตรวจจับคำปลุก 'Hey Jarvis' ถูก{status_text}แล้ว (ผ่าน Menu Bar Island)"
        )

        # Animate pixel robot inside menu bar
        if config.WAKE_TRIGGER_ENABLED:
            self.status_engine.trigger_wake()
            if sys.platform == "darwin":
                try:
                    import subprocess
                    subprocess.Popen(["/usr/bin/afplay", "/System/Library/Sounds/Tink.aiff"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass
        else:
            self.status_engine.set_action('sleep')
            if sys.platform == "darwin":
                try:
                    import subprocess
                    subprocess.Popen(["/usr/bin/afplay", "/System/Library/Sounds/Pop.aiff"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass

        # Update active island if expanded
        active = self._get_active_island()
        if active:
            if config.WAKE_TRIGGER_ENABLED:
                active.trigger_quirk("hum_hop")
            else:
                active.trigger_quirk("curious_nod")
            active.update()

        # Immediate re-render of status item
        self._on_status_tick()
